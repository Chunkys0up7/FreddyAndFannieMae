"""Data models for the GSE Guide Scraper."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GuideSource(Enum):
    FANNIE_MAE = "fannie_mae"
    FREDDIE_MAC = "freddie_mac"


class ScrapeStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SectionURL:
    """Discovered section URL from sitemap."""

    url: str
    source: GuideSource
    section_code: str
    slug: str
    last_modified: str | None = None


@dataclass
class SubSection:
    """A heading-delimited chunk within a section."""

    heading: str
    heading_level: int
    anchor_id: str | None
    content_html: str
    content_markdown: str
    word_count: int = 0
    has_tables: bool = False
    has_lists: bool = False


@dataclass
class CrossReference:
    """A link to another guide section."""

    target_section_code: str
    target_url: str
    link_text: str
    context: str


@dataclass
class RelatedAnnouncement:
    """A policy announcement linked to this section."""

    code: str
    date: str
    title: str | None = None


@dataclass
class GuideSection:
    """Complete parsed content of one guide section."""

    # Identity
    source: GuideSource
    section_code: str
    title: str
    url: str

    # Hierarchy
    part_code: str
    part_name: str
    chapter_code: str
    chapter_name: str
    subpart_code: str | None = None
    subpart_name: str | None = None

    # Content
    content_html: str = ""
    content_markdown: str = ""
    subsections: list[SubSection] = field(default_factory=list)

    # Metadata
    effective_date: str | None = None
    word_count: int = 0
    has_tables: bool = False
    table_count: int = 0

    # References
    cross_references: list[CrossReference] = field(default_factory=list)
    related_announcements: list[RelatedAnnouncement] = field(default_factory=list)

    # Scraping metadata
    scraped_at: str = ""
    scrape_duration_ms: int = 0


@dataclass
class ScrapeError:
    """Record of a failed scrape attempt."""

    url: str
    section_code: str
    error_type: str
    error_message: str
    status_code: int | None = None
    timestamp: str = ""
    retries_attempted: int = 0


@dataclass
class ScrapeManifest:
    """Tracks overall scraping state for resume capability."""

    source: GuideSource
    total_discovered: int = 0
    total_scraped: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    sections: dict[str, str] = field(default_factory=dict)  # section_code -> status string
    errors: list[ScrapeError] = field(default_factory=list)
    started_at: str = ""
    last_updated: str = ""


@dataclass
class ChunkMetadata:
    """Metadata for a semantic chunk."""

    chunk_id: str
    source: GuideSource
    section_code: str
    subsection_heading: str | None
    title: str
    hierarchy_path: str
    word_count: int
    has_tables: bool
    effective_date: str | None
    url: str


@dataclass
class Chunk:
    """A single retrievable chunk for RAG."""

    chunk_id: str
    metadata: ChunkMetadata
    content: str
    parent_section_code: str
    chunk_type: str  # "section" or "subsection"


# --- Enrichment models ---


@dataclass
class CrossSourceLink:
    """A link between equivalent/related sections across GSE sources."""

    source: str
    section_code: str
    topic: str
    relationship: str  # "equivalent" or "related"


@dataclass
class EnrichedChunk:
    """A fully enriched chunk ready for embedding."""

    chunk_id: str
    source: GuideSource
    section_code: str
    title: str
    heading: str | None  # Subsection heading, None for intro/section-level
    domains: list[str] = field(default_factory=list)
    mismo_tags: dict[str, list[str]] = field(default_factory=dict)
    key_terms: list[str] = field(default_factory=list)
    content_type: str = "policy_rule"
    summary: str = ""
    cross_source_links: list[CrossSourceLink] = field(default_factory=list)
    word_count: int = 0
    has_table: bool = False
    effective_date: str | None = None
    url: str = ""
    hierarchy_path: str = ""
    content: str = ""


@dataclass
class EnrichmentResult:
    """Summary of an enrichment pipeline run."""

    total_sections: int = 0
    total_chunks: int = 0
    domain_distribution: dict[str, int] = field(default_factory=dict)
    content_type_distribution: dict[str, int] = field(default_factory=dict)
    cross_source_link_count: int = 0
    avg_chunk_words: int = 0
    errors: list[str] = field(default_factory=list)
