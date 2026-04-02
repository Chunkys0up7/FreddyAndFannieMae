"""Abstract base scraper with shared retry, rate limiting, and resume logic."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import time
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Rate limiting constants
_ADAPTIVE_RATE_SUCCESS_THRESHOLD = 3  # Consecutive 200s before reducing delay
_RATE_LIMIT_JITTER_PCT = 0.15  # ±15% jitter on delays
_RATE_LIMIT_REDUCE_FACTOR = 0.75  # Reduce delay by 25% on consecutive successes
_RETRY_JITTER_PCT = 0.25  # ±25% jitter on backoff delays
_MIN_RATE_DELAY = 0.1  # Floor for rate limiting delay (seconds)

# Content validation
_MIN_HTML_BYTES = 500  # Minimum response size to consider valid


class BaseScraper(ABC):
    """
    Abstract base class for guide scrapers.

    Provides:
    - Rate limiting with configurable delay (adaptive or fixed)
    - Retry with exponential backoff
    - Progress tracking and logging
    - Resume capability (skip already-scraped sections)
    - Error collection and reporting
    - Manifest management with atomic writes and batched saves
    - Circuit breaker for consecutive failure detection
    - Content quality gate with retry on low word count
    - Parallel scraping via ThreadPoolExecutor
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.manifest: ScrapeManifest | None = None
        self.errors: list[ScrapeError] = []
        self._writer = MarkdownWriter(config)
        self._chunker = SemanticChunker(config)

        # Thread safety
        self._lock = threading.Lock()
        self._sections_since_save = 0

        # Circuit breaker state
        self._consecutive_failures = 0

        # Adaptive rate limit state (thread-local to avoid shared dict access)
        self._rate_local = threading.local()

    @property
    @abstractmethod
    def source(self) -> GuideSource:
        """The guide source this scraper handles."""
        ...

    @property
    @abstractmethod
    def request_delay(self) -> float:
        """Base delay between requests in seconds."""
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

        Supports both sequential (max_workers=1) and parallel execution.
        """
        self.setup()
        try:
            sections = self.discover_sections()
            self.manifest = self._load_manifest()
            self.manifest.total_discovered = len(sections)

            # Apply max_sections limit for testing
            if self.config.max_sections:
                sections = sections[: self.config.max_sections]

            # Filter to sections that need scraping
            to_scrape: list[SectionURL] = []
            for s in sections:
                if self._should_skip(s):
                    self.manifest.total_skipped += 1
                else:
                    to_scrape.append(s)

            logger.info(
                "%d sections to scrape (%d skipped)",
                len(to_scrape), self.manifest.total_skipped,
            )

            if not to_scrape:
                self._save_manifest()
                return self.manifest

            workers = self.config.max_workers
            if workers > 1:
                self._scrape_parallel(to_scrape, workers)
            else:
                self._scrape_sequential(to_scrape)

            self.manifest.errors = self.errors
            self._save_manifest()
            return self.manifest

        finally:
            self.teardown()

    def _scrape_sequential(self, sections: list[SectionURL]) -> None:
        """Original sequential scraping loop."""
        with tqdm(total=len(sections), desc=f"Scraping {self.source.value}") as pbar:
            for section_url in sections:
                pbar.set_postfix_str(section_url.section_code)
                self._process_one_section(section_url)
                pbar.update(1)

    def _scrape_parallel(self, sections: list[SectionURL], workers: int) -> None:
        """Parallel scraping using ThreadPoolExecutor."""
        logger.info("Starting parallel scrape with %d workers", workers)

        with tqdm(total=len(sections), desc=f"Scraping {self.source.value}") as pbar:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(self._process_one_section, s): s
                    for s in sections
                }
                for future in as_completed(futures):
                    section_url = futures[future]
                    try:
                        future.result()
                    except _CircuitBreakerTripped:
                        logger.critical(
                            "Circuit breaker tripped — aborting remaining sections"
                        )
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    except Exception as e:
                        logger.error(
                            "Unhandled error for %s: %s",
                            section_url.section_code, e,
                        )
                    pbar.update(1)

    def _process_one_section(self, section_url: SectionURL) -> None:
        """Process a single section: scrape, validate, write, update manifest."""
        worker_id = threading.get_ident()

        # Circuit breaker check
        if self._consecutive_failures >= self.config.circuit_breaker_threshold:
            self._handle_circuit_breaker()

        result = self._retry_with_backoff(self.scrape_section, section_url)

        if result:
            # Content quality gate
            if result.word_count < self.config.quality_min_words:
                logger.warning(
                    "[Worker %d] Low content for %s (%d words), retrying with fresh context...",
                    worker_id, section_url.section_code, result.word_count,
                )
                retry_result = self._retry_with_backoff(
                    self.scrape_section, section_url, max_retries=1,
                )
                if retry_result and retry_result.word_count > result.word_count:
                    result = retry_result

                if result.word_count < self.config.quality_min_words:
                    logger.warning(
                        "[Worker %d] %s still low content (%d words) — marking quality_warning",
                        worker_id, section_url.section_code, result.word_count,
                    )
                    self._record_result(
                        section_url, result,
                        ScrapeStatus.QUALITY_WARNING,
                    )
                    self._reset_consecutive_failures()
                    self._adaptive_rate_limit(200)
                    return

            # Normal success path
            self._record_result(section_url, result, ScrapeStatus.SUCCESS)
            self._reset_consecutive_failures()
            self._adaptive_rate_limit(200)
        else:
            self._record_failure(section_url)
            self._adaptive_rate_limit(None)

    def _record_result(
        self,
        section_url: SectionURL,
        section: GuideSection,
        status: ScrapeStatus,
    ) -> None:
        """Write section to disk and update manifest (thread-safe)."""
        chunks = self._chunker.chunk_section(section)
        filepath = self._writer.write_section(section, chunks)

        # Compute content hash
        content = filepath.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        with self._lock:
            self.manifest.sections[section_url.section_code] = status.value
            self.manifest.content_hashes[section_url.section_code] = content_hash
            if status == ScrapeStatus.SUCCESS:
                self.manifest.total_scraped += 1
            elif status == ScrapeStatus.QUALITY_WARNING:
                self.manifest.total_quality_warnings += 1
            self.manifest.last_updated = datetime.now(timezone.utc).isoformat()
            self._sections_since_save += 1
            if self._sections_since_save >= self.config.manifest_save_interval:
                self._save_manifest()
                self._sections_since_save = 0

    def _record_failure(self, section_url: SectionURL) -> None:
        """Record a failed section in manifest (thread-safe)."""
        with self._lock:
            self.manifest.sections[
                section_url.section_code
            ] = ScrapeStatus.FAILED.value
            self.manifest.total_failed += 1
            self.manifest.last_updated = datetime.now(timezone.utc).isoformat()
            self._consecutive_failures += 1
            self._sections_since_save += 1
            if self._sections_since_save >= self.config.manifest_save_interval:
                self._save_manifest()
                self._sections_since_save = 0

    def _reset_consecutive_failures(self) -> None:
        with self._lock:
            self._consecutive_failures = 0

    def _handle_circuit_breaker(self) -> None:
        """Pause on consecutive failures. Raise if failures continue after cooldown."""
        with self._lock:
            if self._consecutive_failures < self.config.circuit_breaker_threshold:
                return  # Another thread already reset it
            logger.critical(
                "Circuit breaker: %d consecutive failures. "
                "Pausing for %.0fs...",
                self._consecutive_failures,
                self.config.circuit_breaker_cooldown_seconds,
            )
            self._consecutive_failures = 0  # Reset before cooldown

        time.sleep(self.config.circuit_breaker_cooldown_seconds)

    # --- Adaptive rate limiting ---

    def _adaptive_rate_limit(self, status_code: int | None) -> None:
        """
        Adaptive delay between requests.

        - On 429/503: double delay (capped at max_rate_limit_delay)
        - On 3 consecutive 200s: reduce delay by 25% (floor at base delay)
        - Otherwise: use current delay
        - Adds ±15% jitter to avoid thundering herd
        """
        if not self.config.adaptive_rate_limit:
            time.sleep(self.request_delay)
            return

        # Thread-local state — no locks needed
        current = getattr(self._rate_local, "delay", self.request_delay)
        successes = getattr(self._rate_local, "successes", 0)

        if status_code in (429, 503):
            current = min(current * 2, self.config.max_rate_limit_delay)
            self._rate_local.successes = 0
            logger.info(
                "Rate limit hit, delay increased to %.1fs", current,
            )
        elif status_code == 200:
            successes += 1
            self._rate_local.successes = successes
            if successes >= _ADAPTIVE_RATE_SUCCESS_THRESHOLD:
                current = max(current * _RATE_LIMIT_REDUCE_FACTOR, self.request_delay)
                self._rate_local.successes = 0
        # else: failure or None — keep current delay

        self._rate_local.delay = current

        jitter = current * _RATE_LIMIT_JITTER_PCT * (2 * random.random() - 1)
        time.sleep(max(_MIN_RATE_DELAY, current + jitter))

    # --- Existing infrastructure (updated) ---

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
        if status in (ScrapeStatus.SUCCESS.value, ScrapeStatus.QUALITY_WARNING.value):
            # Check exact path first (fast path)
            output_path = self._writer._build_output_path_from_code(
                section_url.section_code, section_url.slug, self.source
            )
            if output_path.exists():
                return True

            # Filename slug may differ from discovery slug — check by prefix
            parent = output_path.parent
            if parent.exists():
                from gse_guides import safe_path_component
                prefix = safe_path_component(section_url.section_code) + "_"
                for f in parent.iterdir():
                    if f.name.startswith(prefix) and f.suffix == ".md":
                        return True

        return False

    def _retry_with_backoff(self, fn, *args, max_retries: int | None = None) -> GuideSection | None:
        """Execute fn with exponential backoff on retryable failures."""
        retries = max_retries if max_retries is not None else self.config.max_retries
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
                    # Add jitter to backoff
                    delay += random.uniform(0, delay * _RETRY_JITTER_PCT)
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
                    total_quality_warnings=data.get("total_quality_warnings", 0),
                    sections=data.get("sections", {}),
                    content_hashes=data.get("content_hashes", {}),
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
        """Persist manifest to disk with atomic write (write-then-rename)."""
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
            "total_quality_warnings": self.manifest.total_quality_warnings,
            "sections": self.manifest.sections,
            "content_hashes": self.manifest.content_hashes,
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

        # Atomic write: write to .tmp then rename
        tmp_path = manifest_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(tmp_path), str(manifest_path))

    def _manifest_path(self) -> Path:
        """Path to manifest file for this source."""
        return self.config.output_dir / self.source.value / "manifest.json"


class _NonRetryableError(Exception):
    """Raised for errors that should not be retried (404, parse errors)."""
    pass


class _CircuitBreakerTripped(Exception):
    """Raised when circuit breaker aborts after cooldown still fails."""
    pass
