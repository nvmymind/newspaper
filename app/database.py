"""SQLite DB 연결 및 초기화."""
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "editorials.db"


async def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS editorials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            summary TEXT,
            content TEXT,
            published_date TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
    """)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_editorials_date ON editorials(published_date)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_editorials_source ON editorials(source)"
    )
    await db.commit()
