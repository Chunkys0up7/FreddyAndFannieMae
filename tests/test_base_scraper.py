"""Tests for BaseScraper resilience: retry, circuit breaker, rate limiting, quality gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from gse_guides.base_scraper import BaseScraper, _NonRetryableError
from gse_guides.config import ScraperConfig
from gse_guides.models import (
    GuideSection,
    GuideSource,
    ScrapeManifest,
    ScrapeStatus,
    SectionURL,
)


class ConcreteScraper(BaseScraper):
    """Minimal concrete scraper for testing base class logic."""

    def __init__(self, config, sections=None, scrape_fn=None):
        super().__init__(config)
        self._sections = sections or []
        self._scrape_fn = scrape_fn

    @property
    def source(self):
        return GuideSource.FANNIE_MAE

    @property
    def request_delay(self):
        return 0.01  # Fast for tests

    def setup(self):
        pass

    def teardown(self):
        pass

    def discover_sections(self):
        return self._sections

    def scrape_section(self, section_url):
        if self._scrape_fn:
            return self._scrape_fn(section_url)
        return _make_section(section_url.section_code)


def _make_section(code="B1-1-01", word_count=100):
    return GuideSection(
        source=GuideSource.FANNIE_MAE,
        section_code=code,
        title="Test",
        url="https://example.com",
        part_code="B",
        part_name="Part B",
        chapter_code="B1-1",
        chapter_name="Ch1",
        content_markdown="Test " * word_count,
        word_count=word_count,
    )


def _make_url(code="B1-1-01"):
    return SectionURL(
        url="https://example.com",
        source=GuideSource.FANNIE_MAE,
        section_code=code,
        slug="test",
    )


class TestRetryWithBackoff:
    def test_returns_on_first_success(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "out", max_retries=3)
        scraper = ConcreteScraper(config)
        result = scraper._retry_with_backoff(lambda x: "ok", "arg")
        assert result == "ok"

    def test_retries_on_failure(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "out", max_retries=2, retry_backoff_factor=1.0
        )
        scraper = ConcreteScraper(config)
        call_count = 0

        def flaky(x):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        result = scraper._retry_with_backoff(flaky, _make_url())
        assert result == "ok"
        assert call_count == 3

    def test_returns_none_after_exhaustion(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "out", max_retries=1, retry_backoff_factor=1.0
        )
        scraper = ConcreteScraper(config)

        def always_fail(x):
            raise ConnectionError("fail")

        result = scraper._retry_with_backoff(always_fail, _make_url())
        assert result is None
        assert len(scraper.errors) == 1

    def test_non_retryable_error_raises_immediately(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "out")
        scraper = ConcreteScraper(config)

        def non_retryable(x):
            raise _NonRetryableError("stop")

        with pytest.raises(_NonRetryableError):
            scraper._retry_with_backoff(non_retryable, "arg")


class TestShouldSkip:
    def test_skips_successful_section_with_file(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "out", skip_existing=True)
        scraper = ConcreteScraper(config)
        scraper.manifest = ScrapeManifest(source=GuideSource.FANNIE_MAE)
        scraper.manifest.sections["B1-1-01"] = ScrapeStatus.SUCCESS.value

        url = _make_url("B1-1-01")
        # Create the file so it exists
        path = scraper._writer._build_output_path_from_code("B1-1-01", "test", GuideSource.FANNIE_MAE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content", encoding="utf-8")

        assert scraper._should_skip(url) is True

    def test_does_not_skip_failed_section(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "out", skip_existing=True)
        scraper = ConcreteScraper(config)
        scraper.manifest = ScrapeManifest(source=GuideSource.FANNIE_MAE)
        scraper.manifest.sections["B1-1-01"] = ScrapeStatus.FAILED.value

        assert scraper._should_skip(_make_url("B1-1-01")) is False

    def test_does_not_skip_when_resume_disabled(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "out", skip_existing=False)
        scraper = ConcreteScraper(config)
        scraper.manifest = ScrapeManifest(source=GuideSource.FANNIE_MAE)
        scraper.manifest.sections["B1-1-01"] = ScrapeStatus.SUCCESS.value

        assert scraper._should_skip(_make_url("B1-1-01")) is False


class TestAtomicManifest:
    def test_manifest_roundtrip(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "out")
        scraper = ConcreteScraper(config)
        scraper.manifest = ScrapeManifest(
            source=GuideSource.FANNIE_MAE,
            total_scraped=5,
            total_quality_warnings=1,
            content_hashes={"B1-1-01": "abc123"},
        )

        scraper._save_manifest()

        # Verify no .tmp file lingering
        tmp_file = scraper._manifest_path().with_suffix(".json.tmp")
        assert not tmp_file.exists()

        # Reload
        loaded = scraper._load_manifest()
        assert loaded.total_scraped == 5
        assert loaded.total_quality_warnings == 1
        assert loaded.content_hashes == {"B1-1-01": "abc123"}


class TestQualityGate:
    def test_low_word_count_marked_quality_warning(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "out",
            quality_min_words=50,
            max_workers=1,
            manifest_save_interval=1,
        )

        def scrape_low(_url):
            return _make_section(_url.section_code, word_count=10)

        scraper = ConcreteScraper(
            config,
            sections=[_make_url("B1-1-01")],
            scrape_fn=scrape_low,
        )
        manifest = scraper.scrape_all()
        assert manifest.sections["B1-1-01"] == ScrapeStatus.QUALITY_WARNING.value
        assert manifest.total_quality_warnings >= 1


class TestCircuitBreaker:
    def test_circuit_breaker_increments_on_failure(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "out",
            circuit_breaker_threshold=100,  # High so it doesn't trip
        )
        scraper = ConcreteScraper(config)
        scraper.manifest = ScrapeManifest(source=GuideSource.FANNIE_MAE)
        scraper._record_failure(_make_url("B1-1-01"))
        assert scraper._consecutive_failures == 1

    def test_circuit_breaker_resets_on_success(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "out")
        scraper = ConcreteScraper(config)
        scraper._consecutive_failures = 3
        scraper._reset_consecutive_failures()
        assert scraper._consecutive_failures == 0
