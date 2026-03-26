import aiosqlite
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)

DB_PATH = get_settings().database_path


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db
