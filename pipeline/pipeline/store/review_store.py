"""SQLite-backed review store: QI flags, review status, gap notes."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import GapNote, ReviewFlag, ReviewStatus


_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    section_number  TEXT NOT NULL,
    agency          TEXT NOT NULL,
    reason          TEXT NOT NULL,
    severity        TEXT NOT NULL,
    reviewer        TEXT,
    flagged_at      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'flagged'
);

CREATE TABLE IF NOT EXISTS review_status (
    section_number  TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    notes           TEXT,
    reviewer        TEXT,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gap_notes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    section_number  TEXT NOT NULL,
    agency          TEXT NOT NULL,
    current_sop     TEXT NOT NULL,
    change          TEXT NOT NULL,
    recommendation  TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_flags_section ON review_flags(section_number);
CREATE INDEX IF NOT EXISTS idx_flags_agency ON review_flags(agency);
CREATE INDEX IF NOT EXISTS idx_gaps_section ON gap_notes(section_number);
"""


class ReviewStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def flag_section(
        self,
        section_number: str,
        agency: str,
        reason: str,
        severity: str,
        reviewer: Optional[str] = None,
    ) -> int:
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO review_flags
                    (section_number, agency, reason, severity, reviewer, flagged_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (section_number, agency, reason, severity, reviewer, now),
            )
            c.execute(
                """
                INSERT OR REPLACE INTO review_status
                    (section_number, status, notes, reviewer, updated_at)
                VALUES (?, 'flagged', ?, ?, ?)
                """,
                (section_number, reason, reviewer, now),
            )
            return cur.lastrowid or 0

    def mark_reviewed(
        self,
        section_number: str,
        notes: Optional[str] = None,
        reviewer: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO review_status
                    (section_number, status, notes, reviewer, updated_at)
                VALUES (?, 'reviewed', ?, ?, ?)
                """,
                (section_number, notes, reviewer, now),
            )

    def get_review_status(self, section_number: str) -> ReviewStatus:
        with self._conn() as c:
            row = c.execute(
                "SELECT status, notes, reviewer, updated_at "
                "FROM review_status WHERE section_number = ?",
                (section_number,),
            ).fetchone()
        if not row:
            return ReviewStatus(section_number=section_number, status="new")
        return ReviewStatus(
            section_number=section_number,
            status=row["status"],
            notes=row["notes"],
            reviewer=row["reviewer"],
            updated_at=row["updated_at"],
        )

    def create_gap_note(
        self,
        section_number: str,
        agency: str,
        current_sop: str,
        change: str,
        recommendation: str,
    ) -> int:
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO gap_notes
                    (section_number, agency, current_sop, change, recommendation, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (section_number, agency, current_sop, change, recommendation, now),
            )
            return cur.lastrowid or 0

    def list_flags(self, agency: Optional[str] = None) -> list[ReviewFlag]:
        query = (
            "SELECT id, section_number, agency, reason, severity, reviewer, "
            "flagged_at, status FROM review_flags"
        )
        params: list = []
        if agency:
            query += " WHERE agency = ?"
            params.append(agency)
        query += " ORDER BY flagged_at DESC"
        with self._conn() as c:
            rows = c.execute(query, params).fetchall()
        return [
            ReviewFlag(
                id=r["id"],
                section_number=r["section_number"],
                agency=r["agency"],
                reason=r["reason"],
                severity=r["severity"],
                reviewer=r["reviewer"] or "",
                flagged_at=r["flagged_at"],
                status=r["status"],
            )
            for r in rows
        ]

    def list_gap_notes(self, section_number: Optional[str] = None) -> list[GapNote]:
        query = (
            "SELECT id, section_number, agency, current_sop, change, recommendation, "
            "created_at FROM gap_notes"
        )
        params: list = []
        if section_number:
            query += " WHERE section_number = ?"
            params.append(section_number)
        query += " ORDER BY created_at DESC"
        with self._conn() as c:
            rows = c.execute(query, params).fetchall()
        return [
            GapNote(
                id=r["id"],
                section_number=r["section_number"],
                agency=r["agency"],
                current_sop=r["current_sop"],
                change=r["change"],
                recommendation=r["recommendation"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
