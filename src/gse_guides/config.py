"""Scraper configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScraperConfig:
    """Configuration for the GSE Guide Scraper."""

    # Output
    output_dir: Path = field(default_factory=lambda: Path("output"))

    # Rate limiting
    fannie_request_delay_seconds: float = 1.0
    freddie_request_delay_seconds: float = 3.0
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    request_timeout_seconds: int = 30

    # Playwright (Freddie Mac)
    playwright_headless: bool = True
    playwright_page_load_timeout_ms: int = 30000
    playwright_content_wait_selector: str = ".rn_Answer"  # Best guess; refined during dev

    # HTTP
    user_agent: str = "GSEGuideResearchBot/1.0 (mortgage-guideline-research)"

    # Chunking
    min_chunk_words: int = 50
    max_chunk_words: int = 2000
    subsection_chunk_enabled: bool = True

    # Resume
    skip_existing: bool = True

    # Fannie Mae
    fannie_sitemap_url: str = "https://selling-guide.fanniemae.com/sitemap.xml"
    fannie_base_url: str = "https://selling-guide.fanniemae.com"

    # Freddie Mac
    freddie_sitemap_url: str = "https://guide.freddiemac.com/euf/assets/fm/sitemap.xml"
    freddie_base_url: str = "https://guide.freddiemac.com"

    # Enrichment
    enriched_dir: Path = field(default_factory=lambda: Path("enriched"))
    enrich_chunk_min_words: int = 30
    enrich_chunk_max_words: int = 800
    enrich_table_max_words: int = 1500  # Tables get wider allowance
    enable_llm_summaries: bool = False

    # Limits (for testing)
    max_sections: int | None = None
