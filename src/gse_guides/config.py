"""Scraper configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


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

    # LLM enrichment (optional — triggered via --llm flag)
    llm_provider: str = "anthropic"           # "anthropic" or "openai"
    llm_model: str = ""                       # Empty = use provider default
    llm_batch_size: int = 10                  # Chunks per batch
    llm_max_chunks: int | None = None         # Limit chunks processed (cost control)
    llm_cache_enabled: bool = True            # Cache LLM results
    llm_dry_run: bool = False                 # Estimate cost without calling API
    llm_prompt_version: str = "1.0"           # Bump to invalidate cache
    llm_max_retries: int = 3                  # Retries on API errors
    llm_timeout_seconds: int = 60             # Per-request timeout

    # Concurrency
    max_workers: int = 1  # 1 = sequential (default for backwards compat)
    fannie_default_workers: int = 8
    freddie_default_workers: int = 1  # Playwright sync API requires single thread

    # Resilience
    quality_min_words: int = 50
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown_seconds: float = 60.0
    manifest_save_interval: int = 25

    # Adaptive rate limiting
    adaptive_rate_limit: bool = True
    max_rate_limit_delay: float = 30.0

    # Limits (for testing)
    max_sections: int | None = None

    def __post_init__(self) -> None:
        """Validate config parameter ranges."""
        if self.fannie_request_delay_seconds < 0:
            raise ValueError("fannie_request_delay_seconds must be >= 0")
        if self.freddie_request_delay_seconds < 0:
            raise ValueError("freddie_request_delay_seconds must be >= 0")
        if self.max_retries < 0 or self.max_retries > 10:
            raise ValueError("max_retries must be 0-10")
        if self.retry_backoff_factor < 1.0:
            raise ValueError("retry_backoff_factor must be >= 1.0")
        if self.request_timeout_seconds < 1:
            raise ValueError("request_timeout_seconds must be >= 1")
        if self.circuit_breaker_threshold < 1:
            raise ValueError("circuit_breaker_threshold must be >= 1")
        if self.circuit_breaker_cooldown_seconds < 0:
            raise ValueError("circuit_breaker_cooldown_seconds must be >= 0")
        if self.max_rate_limit_delay < 0.1:
            raise ValueError("max_rate_limit_delay must be >= 0.1")
        if self.max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if self.quality_min_words < 0:
            raise ValueError("quality_min_words must be >= 0")
        for url_field in (
            self.fannie_base_url, self.fannie_sitemap_url,
            self.freddie_base_url, self.freddie_sitemap_url,
        ):
            parsed = urlparse(url_field)
            if parsed.scheme != "https":
                raise ValueError(f"URL must use HTTPS: {url_field}")
