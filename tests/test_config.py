"""Tests for gse_guides.config.ScraperConfig."""

from __future__ import annotations

from pathlib import Path

import pytest

from gse_guides.config import ScraperConfig


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

class TestDefaults:
    """Verify that default field values are correct."""

    def test_output_dir_default(self):
        cfg = ScraperConfig()
        assert cfg.output_dir == Path("output")

    def test_enriched_dir_default(self):
        cfg = ScraperConfig()
        assert cfg.enriched_dir == Path("enriched")

    def test_fannie_delay_default(self):
        cfg = ScraperConfig()
        assert cfg.fannie_request_delay_seconds == 1.0

    def test_freddie_delay_default(self):
        cfg = ScraperConfig()
        assert cfg.freddie_request_delay_seconds == 3.0

    def test_max_retries_default(self):
        cfg = ScraperConfig()
        assert cfg.max_retries == 3

    def test_retry_backoff_factor_default(self):
        cfg = ScraperConfig()
        assert cfg.retry_backoff_factor == 2.0

    def test_request_timeout_default(self):
        cfg = ScraperConfig()
        assert cfg.request_timeout_seconds == 30

    def test_playwright_headless_default(self):
        cfg = ScraperConfig()
        assert cfg.playwright_headless is True

    def test_skip_existing_default(self):
        cfg = ScraperConfig()
        assert cfg.skip_existing is True

    def test_max_workers_default(self):
        cfg = ScraperConfig()
        assert cfg.max_workers == 1

    def test_fannie_default_workers(self):
        cfg = ScraperConfig()
        assert cfg.fannie_default_workers == 8

    def test_freddie_default_workers(self):
        cfg = ScraperConfig()
        assert cfg.freddie_default_workers == 4

    def test_max_sections_default_none(self):
        cfg = ScraperConfig()
        assert cfg.max_sections is None

    def test_fannie_urls_use_https(self):
        cfg = ScraperConfig()
        assert cfg.fannie_base_url.startswith("https://")
        assert cfg.fannie_sitemap_url.startswith("https://")

    def test_freddie_urls_use_https(self):
        cfg = ScraperConfig()
        assert cfg.freddie_base_url.startswith("https://")
        assert cfg.freddie_sitemap_url.startswith("https://")

    def test_adaptive_rate_limit_default(self):
        cfg = ScraperConfig()
        assert cfg.adaptive_rate_limit is True

    def test_circuit_breaker_threshold_default(self):
        cfg = ScraperConfig()
        assert cfg.circuit_breaker_threshold == 5

    def test_quality_min_words_default(self):
        cfg = ScraperConfig()
        assert cfg.quality_min_words == 50

    def test_enable_llm_summaries_default(self):
        cfg = ScraperConfig()
        assert cfg.enable_llm_summaries is False


# ---------------------------------------------------------------------------
# Valid configurations
# ---------------------------------------------------------------------------

class TestValidConfigs:
    """Configs that should pass validation without error."""

    def test_all_defaults(self):
        cfg = ScraperConfig()
        assert cfg is not None

    def test_custom_output_dir(self, tmp_path):
        cfg = ScraperConfig(output_dir=tmp_path / "custom")
        assert cfg.output_dir == tmp_path / "custom"

    def test_zero_delay_fannie(self):
        cfg = ScraperConfig(fannie_request_delay_seconds=0.0)
        assert cfg.fannie_request_delay_seconds == 0.0

    def test_zero_delay_freddie(self):
        cfg = ScraperConfig(freddie_request_delay_seconds=0.0)
        assert cfg.freddie_request_delay_seconds == 0.0

    def test_max_retries_zero(self):
        cfg = ScraperConfig(max_retries=0)
        assert cfg.max_retries == 0

    def test_max_retries_ten(self):
        cfg = ScraperConfig(max_retries=10)
        assert cfg.max_retries == 10

    def test_backoff_factor_exactly_one(self):
        cfg = ScraperConfig(retry_backoff_factor=1.0)
        assert cfg.retry_backoff_factor == 1.0

    def test_timeout_one_second(self):
        cfg = ScraperConfig(request_timeout_seconds=1)
        assert cfg.request_timeout_seconds == 1

    def test_circuit_breaker_threshold_one(self):
        cfg = ScraperConfig(circuit_breaker_threshold=1)
        assert cfg.circuit_breaker_threshold == 1

    def test_circuit_breaker_cooldown_zero(self):
        cfg = ScraperConfig(circuit_breaker_cooldown_seconds=0.0)
        assert cfg.circuit_breaker_cooldown_seconds == 0.0

    def test_max_rate_limit_delay_at_boundary(self):
        cfg = ScraperConfig(max_rate_limit_delay=0.1)
        assert cfg.max_rate_limit_delay == 0.1

    def test_max_workers_one(self):
        cfg = ScraperConfig(max_workers=1)
        assert cfg.max_workers == 1

    def test_quality_min_words_zero(self):
        cfg = ScraperConfig(quality_min_words=0)
        assert cfg.quality_min_words == 0

    def test_max_sections_set(self):
        cfg = ScraperConfig(max_sections=50)
        assert cfg.max_sections == 50


# ---------------------------------------------------------------------------
# Validation rejects invalid values
# ---------------------------------------------------------------------------

class TestValidationRejectsInvalid:
    """__post_init__ should raise ValueError for out-of-range parameters."""

    def test_negative_fannie_delay(self):
        with pytest.raises(ValueError, match="fannie_request_delay_seconds"):
            ScraperConfig(fannie_request_delay_seconds=-0.1)

    def test_negative_freddie_delay(self):
        with pytest.raises(ValueError, match="freddie_request_delay_seconds"):
            ScraperConfig(freddie_request_delay_seconds=-1.0)

    def test_max_retries_negative(self):
        with pytest.raises(ValueError, match="max_retries"):
            ScraperConfig(max_retries=-1)

    def test_max_retries_above_ten(self):
        with pytest.raises(ValueError, match="max_retries"):
            ScraperConfig(max_retries=11)

    def test_backoff_factor_below_one(self):
        with pytest.raises(ValueError, match="retry_backoff_factor"):
            ScraperConfig(retry_backoff_factor=0.5)

    def test_request_timeout_zero(self):
        with pytest.raises(ValueError, match="request_timeout_seconds"):
            ScraperConfig(request_timeout_seconds=0)

    def test_request_timeout_negative(self):
        with pytest.raises(ValueError, match="request_timeout_seconds"):
            ScraperConfig(request_timeout_seconds=-5)

    def test_circuit_breaker_threshold_zero(self):
        with pytest.raises(ValueError, match="circuit_breaker_threshold"):
            ScraperConfig(circuit_breaker_threshold=0)

    def test_circuit_breaker_cooldown_negative(self):
        with pytest.raises(ValueError, match="circuit_breaker_cooldown_seconds"):
            ScraperConfig(circuit_breaker_cooldown_seconds=-0.1)

    def test_max_rate_limit_delay_too_small(self):
        with pytest.raises(ValueError, match="max_rate_limit_delay"):
            ScraperConfig(max_rate_limit_delay=0.05)

    def test_max_workers_zero(self):
        with pytest.raises(ValueError, match="max_workers"):
            ScraperConfig(max_workers=0)

    def test_max_workers_negative(self):
        with pytest.raises(ValueError, match="max_workers"):
            ScraperConfig(max_workers=-1)

    def test_quality_min_words_negative(self):
        with pytest.raises(ValueError, match="quality_min_words"):
            ScraperConfig(quality_min_words=-1)

    def test_fannie_base_url_http(self):
        with pytest.raises(ValueError, match="HTTPS"):
            ScraperConfig(fannie_base_url="http://selling-guide.fanniemae.com")

    def test_fannie_sitemap_url_http(self):
        with pytest.raises(ValueError, match="HTTPS"):
            ScraperConfig(fannie_sitemap_url="http://selling-guide.fanniemae.com/sitemap.xml")

    def test_freddie_base_url_http(self):
        with pytest.raises(ValueError, match="HTTPS"):
            ScraperConfig(freddie_base_url="http://guide.freddiemac.com")

    def test_freddie_sitemap_url_http(self):
        with pytest.raises(ValueError, match="HTTPS"):
            ScraperConfig(freddie_sitemap_url="http://guide.freddiemac.com/euf/assets/fm/sitemap.xml")

    def test_url_with_no_scheme(self):
        with pytest.raises(ValueError, match="HTTPS"):
            ScraperConfig(fannie_base_url="selling-guide.fanniemae.com")

    def test_url_with_ftp_scheme(self):
        with pytest.raises(ValueError, match="HTTPS"):
            ScraperConfig(freddie_base_url="ftp://guide.freddiemac.com")
