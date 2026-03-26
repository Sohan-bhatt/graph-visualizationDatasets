import aiosqlite
import logging
import json
from typing import Optional
import re

logger = logging.getLogger(__name__)


async def execute_sql(db_path: str, sql: str) -> dict:
    """Execute a SELECT SQL query and return results safely."""
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql)
            rows = await cursor.fetchall()

            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            result_rows = [dict(row) for row in rows]

            truncated = len(result_rows) > 100
            result_rows = result_rows[:100]

            return {
                "rows": result_rows,
                "row_count": len(result_rows),
                "columns": columns,
                "truncated": truncated,
            }
    except Exception as e:
        logger.error(f"SQL execution error: {e}\nSQL: {sql}")
        return {"rows": [], "row_count": 0, "columns": [], "error": str(e)}


def normalize_entity_id(value: str, key: Optional[str] = None) -> Optional[str]:
    """Convert a raw value into a graph node ID when it matches a known entity pattern."""
    val_str = str(value).strip()
    key_lower = (key or "").lower()

    if re.match(r"^SO_\d{6}$", val_str):
        return val_str
    if re.match(r"^DEL_\d{8}$", val_str):
        return val_str
    if re.match(r"^BILL_\d{8}$", val_str):
        return val_str
    if re.match(r"^JE_94\d{8}$", val_str):
        return val_str
    if re.match(r"^PAY_\w+$", val_str):
        return val_str
    if re.match(r"^CUST_\d{9}$", val_str):
        return val_str
    if re.match(r"^PROD_[A-Z0-9]+$", val_str):
        return val_str
    if re.match(r"^PLANT_[A-Z0-9]+$", val_str):
        return val_str

    # Sales order numbers (6 digits starting with 7)
    if re.match(r"^7\d{5}$", val_str):
        return f"SO_{val_str}"
    # Delivery documents (8 digits starting with 8)
    if re.match(r"^8\d{7}$", val_str):
        return f"DEL_{val_str}"
    # Billing documents (8 digits starting with 9)
    if re.match(r"^9\d{7}$", val_str):
        return f"BILL_{val_str}"
    # Accounting documents (10 digits starting with 94)
    if re.match(r"^94\d{8}$", val_str):
        return f"JE_{val_str}"
    # Customer IDs (9 digits starting with 3)
    if re.match(r"^3\d{8}$", val_str):
        return f"CUST_{val_str}"
    # Product IDs
    if re.match(r"^[SB]\d{13,}$", val_str):
        return f"PROD_{val_str}"
    if re.match(r"^\d{7}$", val_str) and key_lower in ("product", "material"):
        return f"PROD_{val_str}"
    # Plant codes
    if re.match(r"^[A-Z]{2}\d{2,3}$", val_str) or (
        re.match(r"^\d{4}$", val_str) and key_lower in ("plant", "productionplant", "shippingpoint")
    ):
        return f"PLANT_{val_str}"
    return None


def extract_entity_ids(rows: list[dict]) -> list[str]:
    """Extract known entity IDs from result rows for graph highlighting."""
    ids = set()
    for row in rows:
        for key, value in row.items():
            if value is None:
                continue
            node_id = normalize_entity_id(str(value), key)
            if node_id:
                ids.add(node_id)

    return list(ids)


def extract_entity_ids_from_text(text: str) -> list[str]:
    """Extract known entity IDs from free text so queried entities can stay highlighted."""
    ids: list[str] = []
    for token in re.findall(r"[A-Z0-9_]+", text.upper()):
        node_id = normalize_entity_id(token)
        if node_id and node_id not in ids:
            ids.append(node_id)
    return ids
