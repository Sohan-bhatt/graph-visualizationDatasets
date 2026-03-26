import networkx as nx
import logging
from typing import Optional, Dict, Set, Tuple

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def get_node_metadata(graph: nx.DiGraph, node_id: str) -> Optional[dict]:
    if node_id not in graph:
        return None
    data = graph.nodes[node_id]
    return {
        "id": node_id,
        "type": data.get("type", "Unknown"),
        "label": data.get("label", node_id),
        "metadata": data.get("metadata", {}),
        "degree": data.get("degree", 0),
        "is_anomaly": data.get("is_anomaly", False),
    }


def get_neighbors_page(
    graph: nx.DiGraph,
    node_id: str,
    exclude_ids: Optional[Set[str]] = None,
    offset: int = 0,
    limit: int = PAGE_SIZE,
) -> Tuple[list, list, int, int]:
    """Get paginated 1-hop neighbors of a node.

    Returns:
        new_nodes: list of node dicts
        new_edges: list of edge dicts
        returned_count: how many neighbors returned this call
        total_neighbors: total number of neighbors available (for "Show More")
    """
    if node_id not in graph:
        return [], [], 0, 0

    exclude = exclude_ids or set()
    exclude.add(node_id)

    # Collect ALL neighbors (both directions), deduplicated
    all_neighbor_ids = []
    seen = set()

    for neighbor in graph.neighbors(node_id):
        if neighbor not in exclude and neighbor not in seen:
            all_neighbor_ids.append(neighbor)
            seen.add(neighbor)

    for predecessor in graph.predecessors(node_id):
        if predecessor not in exclude and predecessor not in seen:
            all_neighbor_ids.append(predecessor)
            seen.add(predecessor)

    total_neighbors = len(all_neighbor_ids)

    # Paginate
    page_ids = all_neighbor_ids[offset : offset + limit]

    new_nodes = []
    new_edges = []

    for nid in page_ids:
        new_nodes.append(get_node_metadata(graph, nid))
        # Edge from node_id → nid
        if graph.has_edge(node_id, nid):
            edge_data = graph.edges[node_id, nid]
            new_edges.append(
                {
                    "source": node_id,
                    "target": nid,
                    "relationship": edge_data.get("relationship", "RELATED"),
                    "properties": edge_data.get("properties", {}),
                }
            )
        # Edge from nid → node_id
        if graph.has_edge(nid, node_id):
            edge_data = graph.edges[nid, node_id]
            new_edges.append(
                {
                    "source": nid,
                    "target": node_id,
                    "relationship": edge_data.get("relationship", "RELATED"),
                    "properties": edge_data.get("properties", {}),
                }
            )

    returned = len(page_ids)
    return new_nodes, new_edges, returned, total_neighbors


def get_initial_subgraph(
    graph: nx.DiGraph, max_nodes: int = PAGE_SIZE
) -> Tuple[list, list, str, int]:
    """Get initial subgraph — top nodes by degree centrality, limited to PAGE_SIZE.

    Returns:
        nodes, edges, render_mode, total_remaining
    """
    if graph.number_of_nodes() == 0:
        return [], [], "pull", 0

    centrality = nx.degree_centrality(graph)
    sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)

    top_ids = {nid for nid, _ in sorted_nodes[:max_nodes]}

    nodes = [get_node_metadata(graph, nid) for nid in top_ids]

    edges = []
    for source, target, data in graph.edges(data=True):
        if source in top_ids and target in top_ids:
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": data.get("relationship", "RELATED"),
                    "properties": data.get("properties", {}),
                }
            )

    total_remaining = graph.number_of_nodes() - len(nodes)
    return nodes, edges, "pull", total_remaining


def search_nodes_with_neighbors(
    graph: nx.DiGraph, query: str, max_search_results: int = 20
) -> Tuple[list, dict]:
    """Search nodes by label/properties. Return matching node info.

    Returns:
        results: list of {id, type, label, degree, total_neighbors}
        best_match_subgraph: for the top match, return it + up to 50 neighbors
    """
    query_lower = query.lower()
    results = []

    for node_id, data in graph.nodes(data=True):
        label = data.get("label", "").lower()
        node_type = data.get("type", "").lower()
        metadata = data.get("metadata", {})
        props = metadata.get("properties", {})

        searchable = f"{label} {node_type} {node_id.lower()}"
        for v in props.values():
            if v is not None:
                searchable += f" {str(v).lower()}"

        if query_lower in searchable:
            total_neighbors = len(set(graph.neighbors(node_id)) | set(graph.predecessors(node_id)))
            results.append(
                {
                    "id": node_id,
                    "type": data.get("type", "Unknown"),
                    "label": data.get("label", node_id),
                    "degree": data.get("degree", 0),
                    "total_neighbors": total_neighbors,
                }
            )
            if len(results) >= max_search_results:
                break

    # Build subgraph for the best match (first result)
    best_subgraph = None
    if results:
        best_id = results[0]["id"]
        nodes, edges, returned, total = get_neighbors_page(
            graph, best_id, exclude_ids=None, offset=0, limit=PAGE_SIZE
        )
        # Include the focal node itself
        focal = get_node_metadata(graph, best_id)
        all_nodes = [focal] + nodes if focal else nodes

        best_subgraph = {
            "focal_node": best_id,
            "nodes": all_nodes,
            "edges": edges,
            "neighbors_shown": returned,
            "total_neighbors": total,
            "has_more": total > returned,
        }

    return results, best_subgraph


def get_focal_subgraph(
    graph: nx.DiGraph, node_id: str, limit: int = PAGE_SIZE
) -> Optional[dict]:
    """Get a focal node + up to `limit` of its neighbors as a subgraph."""
    if node_id not in graph:
        return None

    focal = get_node_metadata(graph, node_id)
    if not focal:
        return None

    nodes, edges, returned, total = get_neighbors_page(
        graph, node_id, exclude_ids=None, offset=0, limit=limit
    )

    all_nodes = [focal] + nodes

    # Also add edges between the visible neighbors
    visible_ids = {n["id"] for n in all_nodes}
    for src, tgt, data in graph.edges(data=True):
        if src in visible_ids and tgt in visible_ids and src != node_id and tgt != node_id:
            edges.append(
                {
                    "source": src,
                    "target": tgt,
                    "relationship": data.get("relationship", "RELATED"),
                    "properties": data.get("properties", {}),
                }
            )

    return {
        "focal_node": node_id,
        "nodes": all_nodes,
        "edges": edges,
        "neighbors_shown": returned,
        "total_neighbors": total,
        "has_more": total > returned,
    }


def get_node_stats(graph: nx.DiGraph) -> dict:
    type_counts = {}
    for _, data in graph.nodes(data=True):
        t = data.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    edge_type_counts = {}
    for _, _, data in graph.edges(data=True):
        r = data.get("relationship", "UNKNOWN")
        edge_type_counts[r] = edge_type_counts.get(r, 0) + 1

    return {
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "nodes_by_type": type_counts,
        "edges_by_type": edge_type_counts,
    }
