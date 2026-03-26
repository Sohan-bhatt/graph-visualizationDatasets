import logging
from fastapi import APIRouter, HTTPException, Query
from app.models.graph_models import (
    GraphResponse,
    ExpandNodeResponse,
    AnomalyResponse,
    AnomalyItem,
    StatsResponse,
    SearchResponse,
    SearchHit,
    FocalSubgraph,
)
from app.services.graph_service import (
    get_initial_subgraph,
    get_neighbors_page,
    get_node_metadata,
    search_nodes_with_neighbors,
    get_node_stats,
    get_focal_subgraph,
    PAGE_SIZE,
)
import aiosqlite

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/initial", response_model=GraphResponse)
async def get_initial_graph(limit: int = Query(default=PAGE_SIZE, ge=1, le=200)):
    from app.main import app

    graph = app.state.graph
    nodes, edges, render_mode, remaining = get_initial_subgraph(graph, max_nodes=limit)
    return GraphResponse(
        nodes=nodes,
        edges=edges,
        total_nodes=graph.number_of_nodes(),
        total_edges=graph.number_of_edges(),
        render_mode=render_mode,
        remaining=remaining,
    )


@router.get("/expand/{node_id:path}", response_model=ExpandNodeResponse)
async def expand_node(
    node_id: str,
    exclude: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=PAGE_SIZE, ge=1, le=200),
):
    from app.main import app

    graph = app.state.graph
    exclude_ids = set(exclude.split(",")) if exclude else set()
    new_nodes, new_edges, returned, total = get_neighbors_page(
        graph, node_id, exclude_ids, offset=offset, limit=limit
    )
    if not new_nodes and total == 0:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return ExpandNodeResponse(
        new_nodes=new_nodes,
        new_edges=new_edges,
        node_id=node_id,
        neighbors_returned=returned,
        total_neighbors=total,
        has_more=(offset + returned) < total,
        next_offset=offset + returned,
    )


@router.get("/focal/{node_id:path}")
async def get_focal(node_id: str, limit: int = Query(default=PAGE_SIZE, ge=1, le=200)):
    from app.main import app

    graph = app.state.graph
    subgraph = get_focal_subgraph(graph, node_id, limit=limit)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return subgraph


@router.get("/node/{node_id:path}")
async def get_node(node_id: str):
    from app.main import app

    graph = app.state.graph
    node = get_node_metadata(graph, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    # Add neighbor info
    neighbors = set(graph.neighbors(node_id)) | set(graph.predecessors(node_id))
    node["total_neighbors"] = len(neighbors)
    return node


@router.get("/search", response_model=SearchResponse)
async def search_graph(q: str = Query(..., min_length=1)):
    from app.main import app

    graph = app.state.graph
    results, focal_subgraph = search_nodes_with_neighbors(graph, q)
    focal = FocalSubgraph(**focal_subgraph) if focal_subgraph else None
    return SearchResponse(
        results=[SearchHit(**r) for r in results],
        count=len(results),
        focal_subgraph=focal,
    )


@router.get("/anomalies", response_model=AnomalyResponse)
async def get_anomalies():
    from app.main import app

    db_path = app.state.db_path
    anomalies = []

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT DISTINCT soh.salesOrder, soh.soldToParty, soh.creationDate,
                   odh.deliveryDocument, odh.overallGoodsMovementStatus
            FROM sales_order_headers soh
            JOIN outbound_delivery_items odi ON soh.salesOrder = odi.referenceSdDocument
            JOIN outbound_delivery_headers odh ON odi.deliveryDocument = odh.deliveryDocument
            LEFT JOIN billing_document_items bdi ON odh.deliveryDocument = bdi.referenceSdDocument
            WHERE bdi.billingDocument IS NULL
            """
        )
        rows = await cursor.fetchall()
        for row in rows:
            anomalies.append(
                AnomalyItem(
                    type="delivered_not_billed",
                    sales_order=row["salesOrder"],
                    delivery_document=row["deliveryDocument"],
                    description=f"SO {row['salesOrder']} delivered via {row['deliveryDocument']} but not billed",
                )
            )

        cursor = await db.execute(
            """
            SELECT bdh.billingDocument, bdh.accountingDocument, bdh.totalNetAmount
            FROM billing_document_headers bdh
            LEFT JOIN journal_entry_items je ON bdh.accountingDocument = je.accountingDocument
            WHERE je.accountingDocument IS NULL
            AND bdh.billingDocumentIsCancelled = 0
            """
        )
        rows = await cursor.fetchall()
        for row in rows:
            anomalies.append(
                AnomalyItem(
                    type="billed_not_posted",
                    billing_document=row["billingDocument"],
                    accounting_document=row["accountingDocument"],
                    description=f"Billing doc {row['billingDocument']} has no journal entry",
                )
            )

        cursor = await db.execute(
            """
            SELECT je.accountingDocument, je.amountInTransactionCurrency, je.postingDate
            FROM journal_entry_items je
            LEFT JOIN payments p ON je.clearingAccountingDocument = p.clearingAccountingDocument
            WHERE p.clearingAccountingDocument IS NULL
            AND je.clearingDate IS NULL
            AND je.amountInTransactionCurrency > 0
            """
        )
        rows = await cursor.fetchall()
        for row in rows:
            anomalies.append(
                AnomalyItem(
                    type="posted_not_paid",
                    accounting_document=row["accountingDocument"],
                    description=f"Journal entry {row['accountingDocument']} ({row['amountInTransactionCurrency']} INR) not paid",
                )
            )

        cursor = await db.execute(
            """
            SELECT billingDocument, cancelledBillingDocument, totalNetAmount
            FROM billing_document_headers
            WHERE billingDocumentIsCancelled = 1
            """
        )
        rows = await cursor.fetchall()
        for row in rows:
            anomalies.append(
                AnomalyItem(
                    type="billing_cancellation",
                    billing_document=row["billingDocument"],
                    description=f"Billing doc {row['billingDocument']} cancelled (originally {row['totalNetAmount']} INR)",
                )
            )

    return AnomalyResponse(
        incomplete_flows=anomalies,
        total_count=len(anomalies),
        description=f"Found {len(anomalies)} anomalies across the O2C flow",
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    from app.main import app

    graph = app.state.graph
    stats = get_node_stats(graph)
    return StatsResponse(
        total_nodes=stats["total_nodes"],
        total_edges=stats["total_edges"],
        nodes_by_type=stats["nodes_by_type"],
        edges_by_type=stats["edges_by_type"],
        anomaly_counts={},
        date_range={"start": "2025-03-31", "end": "2025-07-24"},
    )
