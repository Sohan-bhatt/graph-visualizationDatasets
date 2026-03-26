import json
import glob
import os
import logging
import aiosqlite
import networkx as nx
from typing import Any
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
DB_PATH = settings.database_path
DATA_DIR = settings.data_dir

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS sales_order_headers (
        salesOrder TEXT PRIMARY KEY,
        salesOrderType TEXT,
        salesOrganization TEXT,
        distributionChannel TEXT,
        organizationDivision TEXT,
        soldToParty TEXT,
        creationDate TEXT,
        createdByUser TEXT,
        lastChangeDateTime TEXT,
        totalNetAmount REAL,
        overallDeliveryStatus TEXT,
        overallOrdReltdBillgStatus TEXT,
        transactionCurrency TEXT,
        requestedDeliveryDate TEXT,
        headerBillingBlockReason TEXT,
        deliveryBlockReason TEXT,
        incotermsClassification TEXT,
        incotermsLocation1 TEXT,
        customerPaymentTerms TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sales_order_items (
        salesOrder TEXT,
        salesOrderItem TEXT,
        salesOrderItemCategory TEXT,
        material TEXT,
        requestedQuantity REAL,
        requestedQuantityUnit TEXT,
        netAmount REAL,
        materialGroup TEXT,
        productionPlant TEXT,
        storageLocation TEXT,
        salesDocumentRjcnReason TEXT,
        itemBillingBlockReason TEXT,
        PRIMARY KEY (salesOrder, salesOrderItem)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sales_order_schedule_lines (
        salesOrder TEXT,
        salesOrderItem TEXT,
        scheduleLine TEXT,
        confirmedDeliveryDate TEXT,
        orderQuantityUnit TEXT,
        confdOrderQtyByMatlAvailCheck REAL,
        PRIMARY KEY (salesOrder, salesOrderItem, scheduleLine)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outbound_delivery_headers (
        deliveryDocument TEXT PRIMARY KEY,
        shippingPoint TEXT,
        overallGoodsMovementStatus TEXT,
        overallPickingStatus TEXT,
        creationDate TEXT,
        actualGoodsMovementDate TEXT,
        headerBillingBlockReason TEXT,
        deliveryBlockReason TEXT,
        hdrGeneralIncompletionStatus TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outbound_delivery_items (
        deliveryDocument TEXT,
        deliveryDocumentItem TEXT,
        referenceSdDocument TEXT,
        referenceSdDocumentItem TEXT,
        plant TEXT,
        storageLocation TEXT,
        actualDeliveryQuantity REAL,
        deliveryQuantityUnit TEXT,
        batch TEXT,
        itemBillingBlockReason TEXT,
        PRIMARY KEY (deliveryDocument, deliveryDocumentItem)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS billing_document_headers (
        billingDocument TEXT PRIMARY KEY,
        billingDocumentType TEXT,
        creationDate TEXT,
        billingDocumentDate TEXT,
        billingDocumentIsCancelled INTEGER,
        cancelledBillingDocument TEXT,
        totalNetAmount REAL,
        transactionCurrency TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        accountingDocument TEXT,
        soldToParty TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS billing_document_items (
        billingDocument TEXT,
        billingDocumentItem TEXT,
        material TEXT,
        billingQuantity REAL,
        billingQuantityUnit TEXT,
        netAmount REAL,
        transactionCurrency TEXT,
        referenceSdDocument TEXT,
        referenceSdDocumentItem TEXT,
        PRIMARY KEY (billingDocument, billingDocumentItem)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS billing_document_cancellations (
        billingDocument TEXT PRIMARY KEY,
        billingDocumentType TEXT,
        creationDate TEXT,
        billingDocumentDate TEXT,
        billingDocumentIsCancelled INTEGER,
        cancelledBillingDocument TEXT,
        totalNetAmount REAL,
        transactionCurrency TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        accountingDocument TEXT,
        soldToParty TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS journal_entry_items (
        companyCode TEXT,
        fiscalYear TEXT,
        accountingDocument TEXT,
        accountingDocumentItem TEXT,
        referenceDocument TEXT,
        glAccount TEXT,
        profitCenter TEXT,
        amountInTransactionCurrency REAL,
        transactionCurrency TEXT,
        postingDate TEXT,
        customer TEXT,
        clearingDate TEXT,
        clearingAccountingDocument TEXT,
        accountingDocumentType TEXT,
        PRIMARY KEY (accountingDocument, accountingDocumentItem)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        companyCode TEXT,
        fiscalYear TEXT,
        accountingDocument TEXT,
        accountingDocumentItem TEXT,
        clearingDate TEXT,
        clearingAccountingDocument TEXT,
        amountInTransactionCurrency REAL,
        transactionCurrency TEXT,
        customer TEXT,
        invoiceReference TEXT,
        postingDate TEXT,
        glAccount TEXT,
        profitCenter TEXT,
        financialAccountType TEXT,
        PRIMARY KEY (accountingDocument, accountingDocumentItem)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS business_partners (
        businessPartner TEXT PRIMARY KEY,
        customer TEXT,
        businessPartnerFullName TEXT,
        businessPartnerCategory TEXT,
        businessPartnerGrouping TEXT,
        businessPartnerName TEXT,
        isMarkedForArchiving INTEGER,
        businessPartnerIsBlocked INTEGER,
        creationDate TEXT,
        createdByUser TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS business_partner_addresses (
        businessPartner TEXT,
        addressId TEXT,
        cityName TEXT,
        country TEXT,
        postalCode TEXT,
        region TEXT,
        streetName TEXT,
        PRIMARY KEY (businessPartner, addressId)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        product TEXT PRIMARY KEY,
        productType TEXT,
        productOldId TEXT,
        grossWeight REAL,
        weightUnit TEXT,
        productGroup TEXT,
        baseUnit TEXT,
        division TEXT,
        industrySector TEXT,
        isMarkedForDeletion INTEGER,
        creationDate TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS product_descriptions (
        product TEXT,
        language TEXT,
        productDescription TEXT,
        PRIMARY KEY (product, language)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plants (
        plant TEXT PRIMARY KEY,
        plantName TEXT,
        salesOrganization TEXT,
        distributionChannel TEXT,
        division TEXT,
        language TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS customer_sales_area_assignments (
        customer TEXT,
        salesOrganization TEXT,
        distributionChannel TEXT,
        division TEXT,
        billingIsBlockedForCustomer TEXT,
        completeDeliveryIsDefined INTEGER,
        creditControlArea TEXT,
        currency TEXT,
        customerPaymentTerms TEXT,
        deliveryPriority TEXT,
        incotermsClassification TEXT,
        incotermsLocation1 TEXT,
        salesGroup TEXT,
        salesOffice TEXT,
        shippingCondition TEXT,
        supplyingPlant TEXT,
        PRIMARY KEY (customer, salesOrganization, distributionChannel, division)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS customer_company_assignments (
        customer TEXT,
        companyCode TEXT,
        paymentTerms TEXT,
        reconciliationAccount TEXT,
        deletionIndicator INTEGER,
        customerAccountGroup TEXT,
        PRIMARY KEY (customer, companyCode)
    )
    """,
]


# Mapping from folder names to (table_name, column_mapping)
# column_mapping: JSON key → SQL column (only when different)
TABLE_MAPPINGS: dict[str, dict[str, Any]] = {
    "sales_order_headers": {
        "table": "sales_order_headers",
        "pk": ["salesOrder"],
        "float_cols": ["totalNetAmount"],
    },
    "sales_order_items": {
        "table": "sales_order_items",
        "pk": ["salesOrder", "salesOrderItem"],
        "float_cols": ["requestedQuantity", "netAmount"],
    },
    "sales_order_schedule_lines": {
        "table": "sales_order_schedule_lines",
        "pk": ["salesOrder", "salesOrderItem", "scheduleLine"],
        "float_cols": ["confdOrderQtyByMatlAvailCheck"],
    },
    "outbound_delivery_headers": {
        "table": "outbound_delivery_headers",
        "pk": ["deliveryDocument"],
    },
    "outbound_delivery_items": {
        "table": "outbound_delivery_items",
        "pk": ["deliveryDocument", "deliveryDocumentItem"],
        "float_cols": ["actualDeliveryQuantity"],
    },
    "billing_document_headers": {
        "table": "billing_document_headers",
        "pk": ["billingDocument"],
        "float_cols": ["totalNetAmount"],
        "bool_cols": ["billingDocumentIsCancelled"],
    },
    "billing_document_items": {
        "table": "billing_document_items",
        "pk": ["billingDocument", "billingDocumentItem"],
        "float_cols": ["billingQuantity", "netAmount"],
    },
    "billing_document_cancellations": {
        "table": "billing_document_cancellations",
        "pk": ["billingDocument"],
        "float_cols": ["totalNetAmount"],
        "bool_cols": ["billingDocumentIsCancelled"],
    },
    "journal_entry_items_accounts_receivable": {
        "table": "journal_entry_items",
        "pk": ["accountingDocument", "accountingDocumentItem"],
        "float_cols": ["amountInTransactionCurrency", "amountInCompanyCodeCurrency"],
    },
    "payments_accounts_receivable": {
        "table": "payments",
        "pk": ["accountingDocument", "accountingDocumentItem"],
        "float_cols": ["amountInTransactionCurrency", "amountInCompanyCodeCurrency"],
    },
    "business_partners": {
        "table": "business_partners",
        "pk": ["businessPartner"],
        "bool_cols": ["isMarkedForArchiving", "businessPartnerIsBlocked"],
    },
    "business_partner_addresses": {
        "table": "business_partner_addresses",
        "pk": ["businessPartner", "addressId"],
    },
    "products": {
        "table": "products",
        "pk": ["product"],
        "float_cols": ["grossWeight", "netWeight"],
        "bool_cols": ["isMarkedForDeletion"],
    },
    "product_descriptions": {
        "table": "product_descriptions",
        "pk": ["product", "language"],
    },
    "plants": {
        "table": "plants",
        "pk": ["plant"],
    },
    "customer_sales_area_assignments": {
        "table": "customer_sales_area_assignments",
        "pk": ["customer", "salesOrganization", "distributionChannel", "division"],
        "bool_cols": ["completeDeliveryIsDefined", "slsUnlmtdOvrdelivIsAllwd"],
    },
    "customer_company_assignments": {
        "table": "customer_company_assignments",
        "pk": ["customer", "companyCode"],
        "bool_cols": ["deletionIndicator"],
    },
}


def flatten_value(value: Any) -> Any:
    """Flatten nested objects like time objects to strings."""
    if value is None:
        return None
    if isinstance(value, dict):
        if "hours" in value and "minutes" in value:
            return f"{value['hours']:02d}:{value['minutes']:02d}:{value.get('seconds', 0):02d}"
        return json.dumps(value)
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def process_record(record: dict, mapping: dict) -> dict:
    """Process a JSONL record according to table mapping."""
    result = {}
    float_cols = mapping.get("float_cols", [])
    bool_cols = mapping.get("bool_cols", [])

    for key, value in record.items():
        if key in float_cols:
            try:
                result[key] = float(value) if value not in (None, "", "null") else None
            except (ValueError, TypeError):
                result[key] = None
        elif key in bool_cols:
            result[key] = 1 if value else 0
        else:
            result[key] = flatten_value(value)

    return result


async def create_tables(db: aiosqlite.Connection):
    """Create all SQLite tables."""
    for sql in CREATE_TABLES_SQL:
        await db.execute(sql)
    await db.commit()
    logger.info("All SQLite tables created")


async def ingest_folder(
    db: aiosqlite.Connection, folder_path: str, mapping: dict
) -> int:
    """Ingest all JSONL files from a folder into the mapped SQLite table."""
    table = mapping["table"]
    files = sorted(glob.glob(os.path.join(folder_path, "*.jsonl")))
    if not files:
        logger.warning(f"No JSONL files found in {folder_path}")
        return 0

    # Get valid column names from the table
    cursor = await db.execute(f"PRAGMA table_info({table})")
    table_info = await cursor.fetchall()
    valid_columns = {row[1] for row in table_info}

    total = 0
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in {filepath}:{line_no}")
                    continue

                processed = process_record(record, mapping)

                # Filter to only columns that exist in the table
                filtered = {k: v for k, v in processed.items() if k in valid_columns}

                if not filtered:
                    continue

                columns = ", ".join(filtered.keys())
                placeholders = ", ".join(["?"] * len(filtered))
                values = list(filtered.values())

                sql = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                try:
                    await db.execute(sql, values)
                    total += 1
                except Exception as e:
                    logger.warning(f"Failed to insert in {table} from {filepath}:{line_no}: {e}")

    await db.commit()
    logger.info(f"Ingested {total} records into {table}")
    return total


async def ingest_all(db_path: str = DB_PATH, data_dir: str = DATA_DIR):
    """Ingest all JSONL data into SQLite."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA foreign_keys=OFF")  # Faster ingestion

        await create_tables(db)

        total_records = 0
        for folder_name, mapping in TABLE_MAPPINGS.items():
            folder_path = os.path.join(data_dir, folder_name)
            if os.path.isdir(folder_path):
                count = await ingest_folder(db, folder_path, mapping)
                total_records += count
            else:
                logger.warning(f"Folder not found: {folder_path}")

        logger.info(f"Total records ingested: {total_records}")
        return total_records


def build_graph(db_path: str = DB_PATH) -> nx.DiGraph:
    """Build NetworkX directed graph from SQLite data."""
    import sqlite3

    G = nx.DiGraph()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- Add Customer nodes ---
    cursor.execute("SELECT * FROM business_partners")
    for row in cursor.fetchall():
        node_id = f"CUST_{row['businessPartner']}"
        G.add_node(
            node_id,
            type="Customer",
            label=row["businessPartnerFullName"] or row["businessPartner"],
            metadata={
                "type": "Customer",
                "label": row["businessPartnerFullName"] or row["businessPartner"],
                "properties": dict(row),
            },
        )

    # --- Add Product nodes ---
    cursor.execute(
        "SELECT p.*, pd.productDescription FROM products p "
        "LEFT JOIN product_descriptions pd ON p.product = pd.product AND pd.language = 'EN'"
    )
    for row in cursor.fetchall():
        node_id = f"PROD_{row['product']}"
        desc = row["productDescription"] or row["productOldId"] or row["product"]
        G.add_node(
            node_id,
            type="Product",
            label=desc,
            metadata={
                "type": "Product",
                "label": desc,
                "properties": dict(row),
            },
        )

    # --- Add Plant nodes ---
    cursor.execute("SELECT * FROM plants")
    for row in cursor.fetchall():
        node_id = f"PLANT_{row['plant']}"
        G.add_node(
            node_id,
            type="Plant",
            label=row["plantName"] or row["plant"],
            metadata={
                "type": "Plant",
                "label": row["plantName"] or row["plant"],
                "properties": dict(row),
            },
        )

    # --- Add SalesOrder nodes ---
    cursor.execute("SELECT * FROM sales_order_headers")
    for row in cursor.fetchall():
        node_id = f"SO_{row['salesOrder']}"
        amount = row['totalNetAmount'] if row['totalNetAmount'] else 0
        G.add_node(
            node_id,
            type="SalesOrder",
            label=f"SO {row['salesOrder']} ({amount} INR)",
            metadata={
                "type": "SalesOrder",
                "label": f"SO {row['salesOrder']}",
                "properties": dict(row),
            },
        )

    # --- Add Delivery nodes ---
    cursor.execute("SELECT * FROM outbound_delivery_headers")
    for row in cursor.fetchall():
        node_id = f"DEL_{row['deliveryDocument']}"
        G.add_node(
            node_id,
            type="DeliveryDoc",
            label=f"DEL {row['deliveryDocument']}",
            metadata={
                "type": "DeliveryDoc",
                "label": f"DEL {row['deliveryDocument']}",
                "properties": dict(row),
            },
        )

    # --- Add BillingDoc nodes ---
    cursor.execute("SELECT * FROM billing_document_headers")
    for row in cursor.fetchall():
        node_id = f"BILL_{row['billingDocument']}"
        typ = "F2 Invoice" if row["billingDocumentType"] == "F2" else "S1 Cancellation"
        is_cancelled = bool(row["billingDocumentIsCancelled"])
        G.add_node(
            node_id,
            type="BillingDoc",
            label=f"BILL {row['billingDocument']} ({typ})",
            metadata={
                "type": "BillingDoc",
                "label": f"BILL {row['billingDocument']} ({typ})",
                "properties": dict(row),
            },
        )

    # --- Add JournalEntry nodes ---
    cursor.execute(
        "SELECT DISTINCT accountingDocument, postingDate, amountInTransactionCurrency, "
        "customer, clearingDate, clearingAccountingDocument, accountingDocumentType "
        "FROM journal_entry_items"
    )
    for row in cursor.fetchall():
        node_id = f"JE_{row['accountingDocument']}"
        G.add_node(
            node_id,
            type="JournalEntry",
            label=f"JE {row['accountingDocument']}",
            metadata={
                "type": "JournalEntry",
                "label": f"JE {row['accountingDocument']}",
                "properties": dict(row),
            },
        )

    # --- Add Payment nodes ---
    cursor.execute(
        "SELECT DISTINCT clearingAccountingDocument, clearingDate, "
        "amountInTransactionCurrency, customer "
        "FROM payments WHERE clearingAccountingDocument IS NOT NULL AND clearingAccountingDocument != ''"
    )
    for row in cursor.fetchall():
        doc = row["clearingAccountingDocument"]
        node_id = f"PAY_{doc}"
        if node_id not in G:
            G.add_node(
                node_id,
                type="Payment",
                label=f"PAY {doc}",
                metadata={
                    "type": "Payment",
                    "label": f"PAY {doc}",
                    "properties": dict(row),
                },
            )

    # ===== EDGES =====

    # Customer --[PLACED]--> SalesOrder
    cursor.execute("SELECT salesOrder, soldToParty FROM sales_order_headers")
    for row in cursor.fetchall():
        cust_id = f"CUST_{row['soldToParty']}"
        so_id = f"SO_{row['salesOrder']}"
        if cust_id in G and so_id in G:
            G.add_edge(cust_id, so_id, relationship="PLACED", properties={})

    # SalesOrder --[HAS_ITEM]--> Product (via sales_order_items)
    cursor.execute("SELECT salesOrder, material, productionPlant FROM sales_order_items")
    for row in cursor.fetchall():
        so_id = f"SO_{row['salesOrder']}"
        prod_id = f"PROD_{row['material']}"
        plant_id = f"PLANT_{row['productionPlant']}"
        if so_id in G and prod_id in G:
            G.add_edge(so_id, prod_id, relationship="CONTAINS_ITEM", properties={"material": row["material"]})
        if so_id in G and plant_id in G:
            G.add_edge(so_id, plant_id, relationship="SHIPS_FROM", properties={})

    # SalesOrder --[FULFILLED_BY]--> Delivery (via outbound_delivery_items.referenceSdDocument)
    cursor.execute(
        "SELECT DISTINCT odi.referenceSdDocument, odi.deliveryDocument, odi.plant "
        "FROM outbound_delivery_items odi"
    )
    for row in cursor.fetchall():
        so_id = f"SO_{row['referenceSdDocument']}"
        del_id = f"DEL_{row['deliveryDocument']}"
        plant_id = f"PLANT_{row['plant']}"
        if so_id in G and del_id in G:
            G.add_edge(so_id, del_id, relationship="FULFILLED_BY", properties={})
        if del_id in G and plant_id in G:
            G.add_edge(del_id, plant_id, relationship="SHIPPED_FROM", properties={})

    # Delivery --[BILLED_IN]--> BillingDoc (via billing_document_items.referenceSdDocument)
    cursor.execute(
        "SELECT DISTINCT bdi.referenceSdDocument, bdi.billingDocument "
        "FROM billing_document_items bdi"
    )
    for row in cursor.fetchall():
        del_id = f"DEL_{row['referenceSdDocument']}"
        bill_id = f"BILL_{row['billingDocument']}"
        if del_id in G and bill_id in G:
            G.add_edge(del_id, bill_id, relationship="BILLED_IN", properties={})

    # BillingDoc --[POSTED_TO]--> JournalEntry (via accountingDocument)
    cursor.execute(
        "SELECT DISTINCT billingDocument, accountingDocument FROM billing_document_headers"
    )
    for row in cursor.fetchall():
        bill_id = f"BILL_{row['billingDocument']}"
        je_id = f"JE_{row['accountingDocument']}"
        if bill_id in G and je_id in G:
            G.add_edge(bill_id, je_id, relationship="POSTED_TO", properties={})

    # JournalEntry --[CLEARED_BY]--> Payment (via clearingAccountingDocument)
    cursor.execute(
        "SELECT DISTINCT accountingDocument, clearingAccountingDocument "
        "FROM journal_entry_items "
        "WHERE clearingAccountingDocument IS NOT NULL AND clearingAccountingDocument != ''"
    )
    for row in cursor.fetchall():
        je_id = f"JE_{row['accountingDocument']}"
        pay_id = f"PAY_{row['clearingAccountingDocument']}"
        if je_id in G and pay_id in G:
            G.add_edge(je_id, pay_id, relationship="CLEARED_BY", properties={})

    # BillingDoc --[CANCELLED_BY]--> BillingDoc (S1 → F2 cancellation reference)
    cursor.execute(
        "SELECT billingDocument, cancelledBillingDocument "
        "FROM billing_document_headers "
        "WHERE cancelledBillingDocument IS NOT NULL AND cancelledBillingDocument != ''"
    )
    for row in cursor.fetchall():
        s1_id = f"BILL_{row['billingDocument']}"
        f2_id = f"BILL_{row['cancelledBillingDocument']}"
        if s1_id in G and f2_id in G:
            G.add_edge(s1_id, f2_id, relationship="CANCELLED", properties={})

    # Customer --[BILLED_BY]--> BillingDoc (via soldToParty)
    cursor.execute(
        "SELECT billingDocument, soldToParty FROM billing_document_headers"
    )
    for row in cursor.fetchall():
        cust_id = f"CUST_{row['soldToParty']}"
        bill_id = f"BILL_{row['billingDocument']}"
        if cust_id in G and bill_id in G:
            G.add_edge(cust_id, bill_id, relationship="BILLED_BY", properties={})

    conn.close()

    # Compute degrees
    for node_id in G.nodes():
        G.nodes[node_id]["degree"] = G.degree(node_id)

    logger.info(
        f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
    )
    return G


def generate_schema_context(db_path: str = DB_PATH) -> dict:
    """Generate schema context JSON for LLM injection."""
    schema = {
        "tables": {
            "sales_order_headers": {
                "description": "SAP Sales Orders - top-level order records with 100 records",
                "primary_key": "salesOrder",
                "columns": {
                    "salesOrder": "TEXT PK - Order number e.g. 740506",
                    "soldToParty": "TEXT FK -> business_partners.businessPartner",
                    "totalNetAmount": "REAL - Order total in INR",
                    "overallDeliveryStatus": "TEXT - C=Completed",
                    "overallOrdReltdBillgStatus": "TEXT - Billing status",
                    "creationDate": "TEXT ISO8601",
                    "requestedDeliveryDate": "TEXT ISO8601",
                    "transactionCurrency": "TEXT - always INR",
                    "customerPaymentTerms": "TEXT e.g. Z009",
                },
                "relationships": [
                    "-> sales_order_items via salesOrder",
                    "-> outbound_delivery_items via salesOrder = referenceSdDocument",
                    "-> business_partners via soldToParty = businessPartner",
                ],
            },
            "sales_order_items": {
                "description": "Line items within sales orders - 167 records",
                "primary_key": "(salesOrder, salesOrderItem)",
                "columns": {
                    "salesOrder": "TEXT FK -> sales_order_headers.salesOrder",
                    "salesOrderItem": "TEXT - Item number e.g. 10, 20",
                    "material": "TEXT FK -> products.product",
                    "requestedQuantity": "REAL",
                    "netAmount": "REAL",
                    "productionPlant": "TEXT FK -> plants.plant",
                    "storageLocation": "TEXT",
                },
                "relationships": [
                    "-> sales_order_headers via salesOrder",
                    "-> products via material = product",
                    "-> plants via productionPlant = plant",
                ],
            },
            "outbound_delivery_headers": {
                "description": "Outbound delivery documents - 86 records",
                "primary_key": "deliveryDocument",
                "columns": {
                    "deliveryDocument": "TEXT PK e.g. 80737721",
                    "shippingPoint": "TEXT",
                    "overallGoodsMovementStatus": "TEXT - A=Not processed, C=Completed",
                    "overallPickingStatus": "TEXT - C=Completed",
                    "creationDate": "TEXT ISO8601",
                },
            },
            "outbound_delivery_items": {
                "description": "Line items in outbound deliveries - 137 records",
                "primary_key": "(deliveryDocument, deliveryDocumentItem)",
                "columns": {
                    "deliveryDocument": "TEXT FK -> outbound_delivery_headers.deliveryDocument",
                    "deliveryDocumentItem": "TEXT - Item number",
                    "referenceSdDocument": "TEXT FK -> sales_order_headers.salesOrder",
                    "referenceSdDocumentItem": "TEXT",
                    "plant": "TEXT FK -> plants.plant",
                    "storageLocation": "TEXT",
                    "actualDeliveryQuantity": "REAL",
                },
                "relationships": [
                    "-> outbound_delivery_headers via deliveryDocument",
                    "-> sales_order_headers via referenceSdDocument = salesOrder",
                    "-> plants via plant",
                ],
            },
            "billing_document_headers": {
                "description": "Billing documents (invoices and cancellations) - 163 records",
                "primary_key": "billingDocument",
                "columns": {
                    "billingDocument": "TEXT PK e.g. 90504248",
                    "billingDocumentType": "TEXT - F2=Invoice, S1=Cancellation",
                    "billingDocumentDate": "TEXT ISO8601",
                    "billingDocumentIsCancelled": "INTEGER - 1 if cancelled",
                    "cancelledBillingDocument": "TEXT - For S1 docs, the F2 doc it cancels",
                    "totalNetAmount": "REAL",
                    "accountingDocument": "TEXT FK -> journal_entry_items.accountingDocument",
                    "soldToParty": "TEXT FK -> business_partners.businessPartner",
                },
                "relationships": [
                    "-> billing_document_items via billingDocument",
                    "-> journal_entry_items via accountingDocument",
                    "-> business_partners via soldToParty = businessPartner",
                ],
            },
            "billing_document_items": {
                "description": "Line items in billing documents - 245 records",
                "primary_key": "(billingDocument, billingDocumentItem)",
                "columns": {
                    "billingDocument": "TEXT FK -> billing_document_headers.billingDocument",
                    "billingDocumentItem": "TEXT - Item number",
                    "material": "TEXT FK -> products.product",
                    "billingQuantity": "REAL",
                    "netAmount": "REAL",
                    "referenceSdDocument": "TEXT FK -> outbound_delivery_headers.deliveryDocument",
                    "referenceSdDocumentItem": "TEXT",
                },
                "relationships": [
                    "-> billing_document_headers via billingDocument",
                    "-> outbound_delivery_headers via referenceSdDocument = deliveryDocument",
                    "-> products via material = product",
                ],
            },
            "journal_entry_items": {
                "description": "Accounting journal entry line items - 123 records",
                "primary_key": "(accountingDocument, accountingDocumentItem)",
                "columns": {
                    "accountingDocument": "TEXT - Accounting doc number",
                    "referenceDocument": "TEXT FK -> billing_document_headers.billingDocument",
                    "amountInTransactionCurrency": "REAL - Positive=invoice, negative=reversal",
                    "customer": "TEXT FK -> business_partners.businessPartner",
                    "postingDate": "TEXT ISO8601",
                    "clearingDate": "TEXT ISO8601 or NULL if unpaid",
                    "clearingAccountingDocument": "TEXT - Payment doc that cleared this",
                    "glAccount": "TEXT - always 15500020 (AR subledger)",
                },
                "relationships": [
                    "-> billing_document_headers via referenceDocument = billingDocument",
                    "-> payments via clearingAccountingDocument",
                ],
            },
            "payments": {
                "description": "Accounts receivable payment clearing records - 120 records",
                "primary_key": "(accountingDocument, accountingDocumentItem)",
                "columns": {
                    "accountingDocument": "TEXT - The invoice's accounting doc",
                    "clearingAccountingDocument": "TEXT - The payment doc",
                    "clearingDate": "TEXT ISO8601",
                    "amountInTransactionCurrency": "REAL",
                    "customer": "TEXT FK -> business_partners.businessPartner",
                    "glAccount": "TEXT - AR subledger account",
                },
                "relationships": [
                    "-> journal_entry_items via clearingAccountingDocument",
                    "-> business_partners via customer = businessPartner",
                ],
            },
            "business_partners": {
                "description": "Customer master data - 8 records",
                "primary_key": "businessPartner",
                "columns": {
                    "businessPartner": "TEXT PK e.g. 310000108, 320000083",
                    "businessPartnerFullName": "TEXT - Company name",
                    "businessPartnerCategory": "TEXT - 2=Organization",
                    "businessPartnerGrouping": "TEXT e.g. Y101, Y102",
                },
            },
            "products": {
                "description": "Product/material master data - 69 records",
                "primary_key": "product",
                "columns": {
                    "product": "TEXT PK e.g. S8907367001003, 3001456",
                    "productType": "TEXT e.g. ZPKG, ZF01, ZFS1",
                    "productGroup": "TEXT e.g. ZPKG004, ZFG1001",
                    "grossWeight": "REAL",
                    "baseUnit": "TEXT - always PC",
                },
            },
            "product_descriptions": {
                "description": "Product descriptions by language - 69 records",
                "primary_key": "(product, language)",
                "columns": {
                    "product": "TEXT FK -> products.product",
                    "language": "TEXT - always EN",
                    "productDescription": "TEXT - Human-readable name",
                },
            },
            "plants": {
                "description": "Plant/warehouse master data - 44 records",
                "primary_key": "plant",
                "columns": {
                    "plant": "TEXT PK e.g. 1920, WB05",
                    "plantName": "TEXT",
                    "salesOrganization": "TEXT - always ABCD",
                },
            },
        },
        "join_paths": {
            "order_to_delivery": (
                "sales_order_headers.salesOrder = outbound_delivery_items.referenceSdDocument "
                "JOIN outbound_delivery_headers ON outbound_delivery_items.deliveryDocument = outbound_delivery_headers.deliveryDocument"
            ),
            "delivery_to_billing": (
                "outbound_delivery_headers.deliveryDocument = billing_document_items.referenceSdDocument "
                "JOIN billing_document_headers ON billing_document_items.billingDocument = billing_document_headers.billingDocument"
            ),
            "billing_to_journal": (
                "billing_document_headers.accountingDocument = journal_entry_items.accountingDocument "
                "AND journal_entry_items.referenceDocument = billing_document_headers.billingDocument"
            ),
            "journal_to_payment": (
                "journal_entry_items.clearingAccountingDocument = payments.clearingAccountingDocument"
            ),
            "full_o2c_chain": (
                "sales_order_headers -> outbound_delivery_items -> outbound_delivery_headers "
                "-> billing_document_items -> billing_document_headers -> journal_entry_items -> payments"
            ),
            "order_to_product": (
                "sales_order_items.material = products.product "
                "JOIN product_descriptions ON products.product = product_descriptions.product AND product_descriptions.language = 'EN'"
            ),
        },
    }

    # Save to file
    import json

    os.makedirs("app/db", exist_ok=True)
    with open("app/db/schema_context.json", "w") as f:
        json.dump(schema, f, indent=2)

    logger.info("Schema context generated at app/db/schema_context.json")
    return schema


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(ingest_all())
    G = build_graph()
    schema = generate_schema_context()
    print(f"Done. Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
