import aiosqlite
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("Gaia")

class PersistenceService:
    def __init__(self, db_path: str = "data/state.db"):
        self.db_path = db_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def init_db(self):
        """Initialize DB Schema and WAL mode"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            
            # Key-Value Store for simple metrics (Balance, Last Heartbeat)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
            """)
            
            # Positions Table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    size REAL,
                    entry_price REAL,
                    updated_at TEXT
                )
            """)
            
            # Orders Table (Simplified)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    size REAL,
                    status TEXT,
                    created_at TEXT
                )
            """)
            await db.commit()
            logger.info(f"DB Initialized at {self.db_path} (WAL Mode)")

    async def set_value(self, key: str, value: str):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO kv_store (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, str(value), now))
            await db.commit()

    async def get_value(self, key: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM kv_store WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def update_position(self, symbol: str, size: float, entry_price: float):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO positions (symbol, size, entry_price, updated_at)
                VALUES (?, ?, ?, ?)
            """, (symbol, size, entry_price, now))
            await db.commit()

    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT size, entry_price FROM positions WHERE symbol = ?", (symbol,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"size": row[0], "entry_price": row[1]}
                return None

    async def get_active_orders(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM orders WHERE status = 'OPEN'") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def save_order(self, order: Dict[str, Any]):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO orders (order_id, symbol, side, size, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order['order_id'], order['symbol'], order.get('side'), order.get('size'), order.get('status', 'OPEN'), now))
            await db.commit()

    async def update_order_status(self, order_id: str, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
            await db.commit()

# Singleton Instance
persistence = PersistenceService()
