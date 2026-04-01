"""Abstract base scraper with shared retry, rate limiting, and resume logic."""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from gse_guides.chunker import SemanticChunker
from gse_guides.config import ScraperConfig
from gse_guides.models import (
    GuideSection,
    GuideSource,
    ScrapeError,
    ScrapeManifest,
    ScrapeStatus,
    SectionURL,
)
from gse_guides.writer import MarkdownWriter

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for guide scrapers.

    Provides:
    - Rate limiting with configurable delay
    - Retry with exponential backoff
    - Progress tracking and logging
    - Resume capability (skip already-scraped sections)
    - Error collection and reporting
    - Manifest management for scrape state
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.manifest: ScrapeManifest | None = None
        self.errors: list[ScrapeError] = []
        self._writer = MarkdownWriter(config)
        self._chunker = SemanticChunker(config)

    @property
    @abstractmethod
    def source(self) -> GuideSource:
        """The guide source this scraper handles."""
        ...

    @property
    @abstractmethod
    def request_delay(self) -> float:
        """Delay between requests in seconds."""
        ...

    @abstractmethod
    def setup(self) -> None:
        """Initialize scraper resources (HTTP session, browser, etc.)."""
        ...

    @abstractmethod
    def teardown(self) -> None:
        """Clean up resources."""
        ...

    @abstractmethod
    def discover_sections(self) -> list[SectionURL]:
        """Parse sitemap and return all section URLs to scrape."""
        ...

    @abstractmethod
    def scrape_section(self, section_url: SectionURL) -> GuideSection | None:
        """Fetch and parse a single section."""
        ...

    def scrape_all(self) -> ScrapeManifest:
        """
        Main entry point. Discovers all sections and scrapes them.

        Handles setup/teardown, discovery, resume, rate limiting,
        retry logic, progress tracking, and manifest persistence.
        """
        self.setup()
        try:
            sections = self.discover_sections()
            self.manifest = self._load_manifest()
            self.manifest.total_discovered = len(sections)

            # Apply max_sections limit for testing
            if self.config.max_sections:
                sections = sections[: self.config.max_sections]

            with tqdm(total=len(sections), desc=f"Scraping {self.source.value}") as pbar:
                for section_url in sections:
                    pbar.set_postfix_str(section_url.section_code)

                    if self._should_skip(section_url):
                        self.manifest.total_skipped += 1
                        pbar.update(1)
                        continue

                    result = self._retry_with_backoff(
                        self.scrape_section, section_url
                    )

                    if result:
                        chunks = self._chunker.chunk_section(result)
                        self._writer.write_section(result, chunks)
                        self.manifest.sections[
                            section_url.section_code
                        ] = ScrapeStatus.SUCCESS.value
                        self.manifest.total_scraped += 1
                    else:
                        self.manifest.sections[
                            section_url.section_code
                        ] = ScrapeStatus.FAILED.value
                        self.manifest.total_failed += 1

                    self.manifest.last_updated = datetime.now(timezone.utc).isoformat()
                    self._save_manifest()
                    self._rate_limit()
                    pbar.update(1)

            self.manifest.errors = self.errors
            self._save_manifest()
            return self.manifest

        finally:
            self.teardown()

    def scrape_single(self, section_code: str) -> GuideSection | None:
        """Scrape a single section by code."""
        self.setup()
        try:
            sections = self.discover_sections()
            target = None
            for s in sections:
                if s.section_code.upper() == section_code.upper():
                    target = s
                    break

            if not target:
                logger.error("Section %s not found in discovered URLs", section_code)
                return None

            result = self.scrape_section(target)
            if result:
                chunks = self._chunker.chunk_section(result)
                self._writer.write_section(result, chunks)
            return result
        finally:
            self.teardown()

    def _should_skip(self, section_url: SectionURL) -> bool:
        """Check if section already scraped and up-to-date."""
        if not self.config.skip_existing:
            return False

        if not self.manifest:
            return False

        status = self.manifest.sections.get(section_url.section_code)
        if status == ScrapeStatus.SUCCESS.value:
            # Check if file exists on disk
            output_path = self._writer._build_output_path_from_code(
                section_url.section_code, section_url.slug, self.source
            )
            if output_path.exists():
                return True

        return False

    def _retry_with_backoff(self, fn, *args, max_retries: int | None = None):
        """Execute fn with exponential backoff on retryable failures."""
        retries = max_retries or self.config.max_retries
        last_error = None

        for attempt in range(retries + 1):
            try:
                return fn(*args)
            except _NonRetryableError:
                raise
            except Exception as e:
                last_error = e
                if attempt < retries:
                    delay = self.config.retry_backoff_factor ** attempt
                    logger.warning(
                        "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                        attempt + 1,
                        retries + 1,
                        str(e)[:100],
                        delay,
                    )
                    time.sleep(delay)

        # All retries exhausted
        if last_error and args:
            section_url = args[0]
            error = ScrapeError(
                url=section_url.url if hasattr(section_url, "url") else str(section_url),
                section_code=section_url.section_code if hasattr(section_url, "section_code") else "",
                error_type=type(last_error).__name__,
                error_message=str(last_error)[:500],
                timestamp=datetime.now(timezone.utc).isoformat(),
                retries_attempted=retries,
            )
            self.errors.append(error)
            logger.error(
                "All %d retries exhausted for %s: %s",
                retries,
                error.section_code,
                str(last_error)[:100],
            )

        return None

    def _rate_limit(self) -> None:
        """Sleep for configured delay between requests."""
        time.sleep(self.request_delay)

    def _load_manifest(self) -> ScrapeManifest:
        """Load manifest.json from output dir, or create new."""
        manifest_path = self._manifest_path()
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                return ScrapeManifest(
                    source=self.source,
                    total_discovered=data.get("total_discovered", 0),
                    total_scraped=data.get("total_scraped", 0),
                    total_failed=data.get("total_failed", 0),
                    total_skipped=data.get("total_skipped", 0),
                    sections=data.get("sections", {}),
                    errors=[],
                    started_at=data.get("started_at", ""),
                    last_updated=data.get("last_updated", ""),
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Corrupt manifest, starting fresh: %s", e)

        return ScrapeManifest(
            source=self.source,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    def _save_manifest(self) -> None:
        """Persist manifest to disk."""
        if not self.manifest:
            return
        manifest_path = self._manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "source": self.manifest.source.value,
            "total_discovered": self.manifest.total_discovered,
            "total_scraped": self.manifest.total_scraped,
            "total_failed": self.manifest.total_failed,
            "total_skipped": self.manifest.total_skipped,
            "sections": self.manifest.sections,
            "errors": [
                {
                    "url": e.url,
                    "section_code": e.section_code,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "status_code": e.status_code,
                    "timestamp": e.timestamp,
                    "retries_attempted": e.retries_attempted,
                }
                for e in self.manifest.errors
            ],
            "started_at": self.manifest.started_at,
            "last_updated": self.manifest.last_updated,
        }
        manifest_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _manifest_path(self) -> Path:
        """Path to manifest file for this source."""
        return self.config.output_dir / self.source.value / "manifest.json"


class _NonRetryableError(Exception):
    """Raised for errors that should not be retried (404, parse errors)."""
    pass
