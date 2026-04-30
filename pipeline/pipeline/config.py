"""Pipeline configuration: env-driven, typed."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ChunkConfig:
    chunk_size: int = 512
    chunk_overlap: int = 64
    encoding_name: str = "cl100k_base"


@dataclass(frozen=True)
class FannieConfig:
    start_url: str = "https://selling-guide.fanniemae.com/"
    include_globs: tuple[str, ...] = ("https://selling-guide.fanniemae.com/sel/**",)
    max_crawl_pages: int = 500
    max_crawl_depth: int = 4
    actor_id: str = "apify/website-content-crawler"
    crawler_type: str = "cheerio"
    bulletin_announcements_url: str = (
        "https://singlefamily.fanniemae.com/news-events/announcements"
    )
    bulletin_max_pages: int = 5


@dataclass(frozen=True)
class FreddieConfig:
    pdf_url: str = (
        "https://guide.freddiemac.com/ci/okcsFattach/get/1003170_8"
    )
    bulletin_url: str = "https://sf.freddiemac.com/content/guide-bulletins"
    bulletin_max_pages: int = 5
    section_patterns: tuple[str, ...] = (
        r"^(\d{4}\.\d+(?:\.\d+)?)\s+(.+)$",
        r"^Chapter\s+(\d+)\s*[—\-:]\s*(.+)$",
        r"^Section\s+(\d{4}\.\d+(?:\.\d+)?)\s*[—\-:]\s*(.+)$",
    )


@dataclass(frozen=True)
class ChromaConfig:
    host: str = field(default_factory=lambda: os.getenv("CHROMA_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("CHROMA_PORT", "8500")))
    fannie_collection: str = "fannie_sections"
    freddie_collection: str = "freddie_sections"
    bulletins_collection: str = "bulletins"


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "local"))
    model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))


@dataclass(frozen=True)
class ScheduleConfig:
    bulletin_poll_hours: int = field(
        default_factory=lambda: int(os.getenv("BULLETIN_POLL_HOURS", "6"))
    )
    guide_refresh_days: int = field(
        default_factory=lambda: int(os.getenv("GUIDE_REFRESH_DAYS", "7"))
    )


@dataclass(frozen=True)
class PipelineConfig:
    apify_token: str = field(default_factory=lambda: os.getenv("APIFY_TOKEN", ""))
    sqlite_path: Path = field(
        default_factory=lambda: Path(os.getenv("SQLITE_PATH", "/data/sqlite/gse.db"))
    )
    manifest_dir: Path = field(
        default_factory=lambda: Path(os.getenv("MANIFEST_DIR", "/data/manifests"))
    )
    chunk: ChunkConfig = field(default_factory=ChunkConfig)
    fannie: FannieConfig = field(default_factory=FannieConfig)
    freddie: FreddieConfig = field(default_factory=FreddieConfig)
    chroma: ChromaConfig = field(default_factory=ChromaConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    api_port: int = field(default_factory=lambda: int(os.getenv("PIPELINE_API_PORT", "8001")))


def load_config() -> PipelineConfig:
    return PipelineConfig()
