"""Shared dataclasses used across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class SectionMeta:
    section_number: str
    section_title: str
    agency: str  # "fannie" | "freddie"
    source_url: Optional[str] = None
    page_number: Optional[int] = None


@dataclass(frozen=True)
class DocMeta:
    agency: str
    doc_type: str  # "guide" | "bulletin"
    source_url: str
    ingest_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    bulletin_id: Optional[str] = None


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    section_number: str
    section_title: str
    agency: str
    doc_type: str
    source_url: str
    chunk_index: int
    page_number: Optional[int] = None
    bulletin_id: Optional[str] = None
    ingest_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def metadata(self) -> dict:
        meta = {
            "section_number": self.section_number,
            "section_title": self.section_title,
            "agency": self.agency,
            "doc_type": self.doc_type,
            "source_url": self.source_url,
            "chunk_index": self.chunk_index,
            "ingest_timestamp": self.ingest_timestamp,
        }
        if self.page_number is not None:
            meta["page_number"] = self.page_number
        if self.bulletin_id is not None:
            meta["bulletin_id"] = self.bulletin_id
        return meta


@dataclass(frozen=True)
class ChunkResult:
    id: str
    text: str
    metadata: dict
    distance: float


@dataclass(frozen=True)
class BulletinMeta:
    id: str
    agency: str
    url: str
    title: Optional[str]
    published: Optional[str]
    discovered_at: str


@dataclass(frozen=True)
class BulletinRef:
    id: str
    agency: str
    url: str
    title: Optional[str] = None


@dataclass
class ReviewFlag:
    id: int
    section_number: str
    agency: str
    reason: str
    severity: str
    reviewer: str
    flagged_at: str
    status: str = "flagged"


@dataclass
class GapNote:
    id: int
    section_number: str
    agency: str
    current_sop: str
    change: str
    recommendation: str
    created_at: str


@dataclass
class ReviewStatus:
    section_number: str
    status: str  # "new" | "reviewing" | "reviewed" | "flagged"
    notes: Optional[str] = None
    reviewer: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class FanniePage:
    url: str
    markdown: str
    title: Optional[str] = None


@dataclass
class ParsedSection:
    section_number: str
    section_title: str
    text: str
    page_number: Optional[int] = None
