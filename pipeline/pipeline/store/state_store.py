"""SQLite-backed state store: bulletin IDs, guide hashes, run manifests."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..models import BulletinMeta


_SCHEMA = """
CREATE TABLE IF NOT EXISTS bulletins (
    id            TEXT PRIMARY KEY,
    agency        TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT,
    published     TEXT,
    discovered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guide_hashes (
    agency     TEXT PRIMARY KEY,
    hash       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bulletins_agency ON bulletins(agency);
CREATE INDEX IF NOT EXISTS idx_bulletins_discovered ON bulletins(discovered_at DESC);
"""


class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def has_bulletin(self, bulletin_id: str) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM bulletins WHERE id = ?", (bulletin_id,)
            ).fetchone()
        return row is not None

    def mark_bulletin(
        self,
        bulletin_id: str,
        agency: str,
        url: str,
        title: Optional[str] = None,
        published: Optional[str] = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO bulletins
                    (id, agency, url, title, published, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bulletin_id,
                    agency,
                    url,
                    title,
                    published,
                    datetime.utcnow().isoformat(),
                ),
            )

    def get_guide_hash(self, agency: str) -> Optional[str]:
        with self._conn() as c:
            row = c.execute(
                "SELECT hash FROM guide_hashes WHERE agency = ?", (agency,)
            ).fetchone()
        return row["hash"] if row else None

    def set_guide_hash(self, agency: str, hash_value: str) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO guide_hashes (agency, hash, updated_at)
                VALUES (?, ?, ?)
                """,
                (agency, hash_value, datetime.utcnow().isoformat()),
            )

    def list_recent_bulletins(
        self, agency: Optional[str] = None, days: int = 90
    ) -> list[BulletinMeta]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        query = (
            "SELECT id, agency, url, title, published, discovered_at "
            "FROM bulletins WHERE discovered_at >= ?"
        )
        params: list = [cutoff]
        if agency:
            query += " AND agency = ?"
            params.append(agency)
        query += " ORDER BY discovered_at DESC"
        with self._conn() as c:
            rows = c.execute(query, params).fetchall()
        return [
            BulletinMeta(
                id=r["id"],
                agency=r["agency"],
                url=r["url"],
                title=r["title"],
                published=r["published"],
                discovered_at=r["discovered_at"],
            )
            for r in rows
        ]

    def get_bulletin(self, bulletin_id: str) -> Optional[BulletinMeta]:
        with self._conn() as c:
            row = c.execute(
                "SELECT id, agency, url, title, published, discovered_at "
                "FROM bulletins WHERE id = ?",
                (bulletin_id,),
            ).fetchone()
        if not row:
            return None
        return BulletinMeta(
            id=row["id"],
            agency=row["agency"],
            url=row["url"],
            title=row["title"],
            published=row["published"],
            discovered_at=row["discovered_at"],
        )
