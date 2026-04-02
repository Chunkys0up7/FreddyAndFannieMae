"""Tests for gse_guides.cli — Click commands and helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gse_guides.cli import _create_scrapers, cli
from gse_guides.config import ScraperConfig
from gse_guides.models import (
    EnrichmentResult,
    GuideSource,
    SectionURL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_fannie_scraper():
    scraper = MagicMock()
    scraper.source = GuideSource.FANNIE_MAE
    return scraper


@pytest.fixture
def mock_freddie_scraper():
    scraper = MagicMock()
    scraper.source = GuideSource.FREDDIE_MAC
    return scraper


def _make_manifest_mock(**overrides):
    """Return a MagicMock pretending to be a ScrapeManifest."""
    defaults = dict(
        total_discovered=10,
        total_scraped=8,
        total_skipped=1,
        total_quality_warnings=0,
        total_failed=1,
        errors=[],
    )
    defaults.update(overrides)
    m = MagicMock(**defaults)
    return m


# ---------------------------------------------------------------------------
# scrape command — argument / option parsing
# ---------------------------------------------------------------------------

class TestScrapeCommand:
    """Test the `scrape` CLI command."""

    def test_source_fannie_mae(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            result = runner.invoke(cli, ["scrape", "fannie-mae"])
            assert result.exit_code == 0
            mock_cs.assert_called_once()
            call_args = mock_cs.call_args
            assert call_args[0][0] == "fannie-mae"

    def test_source_freddie_mac(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            result = runner.invoke(cli, ["scrape", "freddie-mac"])
            assert result.exit_code == 0
            assert mock_cs.call_args[0][0] == "freddie-mac"

    def test_source_all(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            result = runner.invoke(cli, ["scrape", "all"])
            assert result.exit_code == 0
            assert mock_cs.call_args[0][0] == "all"

    def test_invalid_source_rejected(self, runner):
        result = runner.invoke(cli, ["scrape", "invalid-source"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid-source" in result.output

    def test_verbose_flag(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]):
            result = runner.invoke(cli, ["scrape", "fannie-mae", "--verbose"])
            assert result.exit_code == 0

    def test_verbose_short_flag(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]):
            result = runner.invoke(cli, ["scrape", "fannie-mae", "-v"])
            assert result.exit_code == 0

    def test_delay_option(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            runner.invoke(cli, ["scrape", "all", "--delay", "5.0"])
            config: ScraperConfig = mock_cs.call_args[0][1]
            assert config.fannie_request_delay_seconds == 5.0
            assert config.freddie_request_delay_seconds == 5.0

    def test_no_resume_flag(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            runner.invoke(cli, ["scrape", "all", "--no-resume"])
            config: ScraperConfig = mock_cs.call_args[0][1]
            assert config.skip_existing is False

    def test_max_sections_option(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            runner.invoke(cli, ["scrape", "all", "--max-sections", "10"])
            config: ScraperConfig = mock_cs.call_args[0][1]
            assert config.max_sections == 10

    def test_workers_option(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            runner.invoke(cli, ["scrape", "all", "--workers", "4"])
            config: ScraperConfig = mock_cs.call_args[0][1]
            assert config.max_workers == 4

    def test_workers_short_flag(self, runner):
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            runner.invoke(cli, ["scrape", "all", "-w", "6"])
            config: ScraperConfig = mock_cs.call_args[0][1]
            assert config.max_workers == 6

    def test_output_option(self, runner, tmp_path):
        out = str(tmp_path / "custom_output")
        with patch("gse_guides.cli._create_scrapers", return_value=[]) as mock_cs:
            runner.invoke(cli, ["scrape", "all", "--output", out])
            config: ScraperConfig = mock_cs.call_args[0][1]
            assert config.output_dir == Path(out)

    def test_section_option_with_scraper(self, runner, mock_fannie_scraper):
        section_result = MagicMock(
            section_code="B3-3.1-01",
            title="General Income",
            word_count=500,
            subsections=["a", "b"],
            table_count=1,
        )
        mock_fannie_scraper.scrape_single.return_value = section_result

        with patch("gse_guides.cli._create_scrapers", return_value=[mock_fannie_scraper]):
            result = runner.invoke(cli, ["scrape", "fannie-mae", "--section", "B3-3.1-01"])
            assert result.exit_code == 0
            assert "B3-3.1-01" in result.output
            mock_fannie_scraper.scrape_single.assert_called_once_with("B3-3.1-01")

    def test_section_scrape_failure_exits_nonzero(self, runner, mock_fannie_scraper):
        mock_fannie_scraper.scrape_single.return_value = None

        with patch("gse_guides.cli._create_scrapers", return_value=[mock_fannie_scraper]):
            result = runner.invoke(cli, ["scrape", "fannie-mae", "--section", "INVALID"])
            assert result.exit_code != 0

    def test_scrape_all_shows_manifest(self, runner, mock_fannie_scraper):
        manifest = _make_manifest_mock()
        mock_fannie_scraper.scrape_all.return_value = manifest

        with patch("gse_guides.cli._create_scrapers", return_value=[mock_fannie_scraper]):
            result = runner.invoke(cli, ["scrape", "fannie-mae"])
            assert result.exit_code == 0
            assert "Discovered" in result.output
            assert "Scraped" in result.output
            assert "Failed" in result.output

    def test_scrape_all_shows_errors(self, runner, mock_fannie_scraper):
        err = MagicMock(section_code="B1-1", error_type="Timeout", error_message="Timed out after 30s")
        manifest = _make_manifest_mock(errors=[err])
        mock_fannie_scraper.scrape_all.return_value = manifest

        with patch("gse_guides.cli._create_scrapers", return_value=[mock_fannie_scraper]):
            result = runner.invoke(cli, ["scrape", "fannie-mae"])
            assert "Errors" in result.output
            assert "B1-1" in result.output


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------

class TestStatusCommand:
    """Test the `status` CLI command."""

    def test_status_missing_output_dir(self, runner, tmp_path):
        result = runner.invoke(cli, ["status", "--output", str(tmp_path / "nope")])
        assert result.exit_code == 0
        assert "No manifest found" in result.output

    def test_status_no_manifest_files(self, runner, tmp_path):
        (tmp_path / "fannie_mae").mkdir()
        (tmp_path / "freddie_mac").mkdir()
        result = runner.invoke(cli, ["status", "--output", str(tmp_path)])
        assert "No manifest found" in result.output

    def test_status_with_manifest(self, runner, tmp_path):
        source_dir = tmp_path / "fannie_mae"
        source_dir.mkdir()
        manifest_data = {
            "total_discovered": 100,
            "total_scraped": 90,
            "total_skipped": 5,
            "total_failed": 5,
            "started_at": "2026-01-01T00:00:00",
            "last_updated": "2026-01-02T00:00:00",
            "errors": [],
        }
        (source_dir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
        # Create a sample markdown file so file count works
        (source_dir / "section.md").write_text("# Test", encoding="utf-8")

        result = runner.invoke(cli, ["status", "--output", str(tmp_path)])
        assert result.exit_code == 0
        assert "fannie_mae" in result.output
        assert "100" in result.output  # discovered
        assert "90" in result.output   # scraped
        assert "Files:" in result.output

    def test_status_shows_errors(self, runner, tmp_path):
        source_dir = tmp_path / "freddie_mac"
        source_dir.mkdir()
        manifest_data = {
            "total_discovered": 50,
            "total_scraped": 45,
            "total_skipped": 0,
            "total_failed": 5,
            "errors": [
                {"section_code": "5703.1", "error_type": "ParseError", "error_message": "Could not parse content"},
            ],
        }
        (source_dir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        result = runner.invoke(cli, ["status", "--output", str(tmp_path)])
        assert "5703.1" in result.output
        assert "ParseError" in result.output


# ---------------------------------------------------------------------------
# discover command
# ---------------------------------------------------------------------------

class TestDiscoverCommand:
    """Test the `discover` CLI command."""

    def test_discover_fannie_mae(self, runner):
        sample_urls = [
            SectionURL(
                url="https://selling-guide.fanniemae.com/sel/b3-3.1-01/income",
                source=GuideSource.FANNIE_MAE,
                section_code="B3-3.1-01",
                slug="income",
                last_modified="2026-03-04",
            ),
        ]
        with patch("gse_guides.fannie_mae.discovery.FannieMaeDiscovery") as MockDisc:
            MockDisc.return_value.discover.return_value = sample_urls
            result = runner.invoke(cli, ["discover", "fannie-mae"])
            assert "Discovered 1 sections" in result.output
            assert "B3-3.1-01" in result.output

    def test_discover_freddie_mac(self, runner):
        sample_urls = [
            SectionURL(
                url="https://guide.freddiemac.com/app/guide/section/5703.1",
                source=GuideSource.FREDDIE_MAC,
                section_code="5703.1",
                slug="5703-1",
            ),
        ]
        with patch("gse_guides.freddie_mac.discovery.FreddieMacDiscovery") as MockDisc:
            MockDisc.return_value.discover.return_value = sample_urls
            result = runner.invoke(cli, ["discover", "freddie-mac"])
            assert "Discovered 1 sections" in result.output
            assert "5703.1" in result.output

    def test_discover_invalid_source(self, runner):
        result = runner.invoke(cli, ["discover", "all"])
        assert result.exit_code != 0

    def test_discover_verbose(self, runner):
        with patch("gse_guides.fannie_mae.discovery.FannieMaeDiscovery") as MockDisc:
            MockDisc.return_value.discover.return_value = []
            result = runner.invoke(cli, ["discover", "fannie-mae", "-v"])
            assert "Discovered 0 sections" in result.output


# ---------------------------------------------------------------------------
# enrich command
# ---------------------------------------------------------------------------

class TestEnrichCommand:
    """Test the `enrich` CLI command."""

    def _make_enrichment_result(self, **overrides):
        defaults = dict(
            total_sections=20,
            total_chunks=100,
            avg_chunk_words=300,
            cross_source_link_count=5,
            errors=[],
            domain_distribution={"income": 10, "appraisal": 8},
            content_type_distribution={"policy": 12, "procedure": 6},
        )
        defaults.update(overrides)
        return EnrichmentResult(**defaults)

    def test_enrich_basic(self, runner):
        result_obj = self._make_enrichment_result()
        with patch("gse_guides.enrichment.pipeline.EnrichmentPipeline") as MockPipeline:
            MockPipeline.return_value.run.return_value = result_obj
            result = runner.invoke(cli, ["enrich", "--source", "fannie-mae"])
            assert result.exit_code == 0
            assert "Enrichment Complete" in result.output
            assert "20" in result.output  # total_sections

    def test_enrich_incremental_flag(self, runner):
        result_obj = self._make_enrichment_result()
        with patch("gse_guides.enrichment.pipeline.EnrichmentPipeline") as MockPipeline:
            MockPipeline.return_value.run.return_value = result_obj
            result = runner.invoke(cli, ["enrich", "--source", "fannie-mae", "--incremental"])
            assert result.exit_code == 0
            MockPipeline.return_value.run.assert_called_once_with("fannie_mae", incremental=True)

    def test_enrich_stats_flag_shows_distributions(self, runner):
        result_obj = self._make_enrichment_result()
        with patch("gse_guides.enrichment.pipeline.EnrichmentPipeline") as MockPipeline:
            MockPipeline.return_value.run.return_value = result_obj
            result = runner.invoke(cli, ["enrich", "--source", "freddie-mac", "--stats"])
            assert result.exit_code == 0
            assert "Domain Distribution" in result.output
            assert "income" in result.output
            assert "Content Type Distribution" in result.output
            assert "policy" in result.output

    def test_enrich_without_source_passes_none(self, runner):
        result_obj = self._make_enrichment_result()
        with patch("gse_guides.enrichment.pipeline.EnrichmentPipeline") as MockPipeline:
            MockPipeline.return_value.run.return_value = result_obj
            result = runner.invoke(cli, ["enrich"])
            assert result.exit_code == 0
            MockPipeline.return_value.run.assert_called_once_with(None, incremental=False)

    def test_enrich_shows_errors(self, runner):
        result_obj = self._make_enrichment_result(errors=["Failed to parse section X"])
        with patch("gse_guides.enrichment.pipeline.EnrichmentPipeline") as MockPipeline:
            MockPipeline.return_value.run.return_value = result_obj
            result = runner.invoke(cli, ["enrich", "--source", "fannie-mae"])
            assert "Errors" in result.output
            assert "Failed to parse section X" in result.output

    def test_enrich_custom_directories(self, runner, tmp_path):
        result_obj = self._make_enrichment_result()
        with patch("gse_guides.enrichment.pipeline.EnrichmentPipeline") as MockPipeline:
            MockPipeline.return_value.run.return_value = result_obj
            out = str(tmp_path / "out")
            enriched = str(tmp_path / "enr")
            result = runner.invoke(cli, ["enrich", "--output", out, "--enriched", enriched])
            assert result.exit_code == 0
            # Verify config was constructed with correct paths
            call_config = MockPipeline.call_args[0][0]
            assert call_config.output_dir == Path(out)
            assert call_config.enriched_dir == Path(enriched)


# ---------------------------------------------------------------------------
# _create_scrapers helper
# ---------------------------------------------------------------------------

class TestCreateScrapers:
    """Test the _create_scrapers helper function."""

    def test_fannie_mae_creates_one_scraper(self):
        config = ScraperConfig()
        with patch("gse_guides.fannie_mae.scraper.FannieMaeScraper") as MockFannie:
            scrapers = _create_scrapers("fannie-mae", config)
            assert len(scrapers) == 1
            MockFannie.assert_called_once()

    def test_freddie_mac_creates_one_scraper(self):
        config = ScraperConfig()
        with patch("gse_guides.freddie_mac.scraper.FreddieMacScraper") as MockFreddie:
            scrapers = _create_scrapers("freddie-mac", config)
            assert len(scrapers) == 1
            MockFreddie.assert_called_once()

    def test_all_creates_two_scrapers(self):
        config = ScraperConfig()
        with patch("gse_guides.fannie_mae.scraper.FannieMaeScraper") as MockFannie, \
             patch("gse_guides.freddie_mac.scraper.FreddieMacScraper") as MockFreddie:
            scrapers = _create_scrapers("all", config)
            assert len(scrapers) == 2
            MockFannie.assert_called_once()
            MockFreddie.assert_called_once()

    def test_workers_propagates_to_config_when_set(self):
        config = ScraperConfig(max_workers=12)
        with patch("gse_guides.fannie_mae.scraper.FannieMaeScraper") as MockFannie:
            _create_scrapers("fannie-mae", config, user_set_workers=True)
            call_config = MockFannie.call_args[0][0]
            # When user explicitly set workers, their value is used as-is
            assert call_config.max_workers == 12

    def test_default_workers_used_when_not_set(self):
        config = ScraperConfig()  # max_workers=1 (default)
        with patch("gse_guides.fannie_mae.scraper.FannieMaeScraper") as MockFannie:
            _create_scrapers("fannie-mae", config, user_set_workers=False)
            call_config = MockFannie.call_args[0][0]
            assert call_config.max_workers == config.fannie_default_workers

    def test_freddie_default_workers_when_not_set(self):
        config = ScraperConfig()
        with patch("gse_guides.freddie_mac.scraper.FreddieMacScraper") as MockFreddie:
            _create_scrapers("freddie-mac", config, user_set_workers=False)
            call_config = MockFreddie.call_args[0][0]
            assert call_config.max_workers == config.freddie_default_workers

    def test_all_uses_per_source_defaults(self):
        config = ScraperConfig()
        with patch("gse_guides.fannie_mae.scraper.FannieMaeScraper") as MockFannie, \
             patch("gse_guides.freddie_mac.scraper.FreddieMacScraper") as MockFreddie:
            _create_scrapers("all", config, user_set_workers=False)
            fannie_cfg = MockFannie.call_args[0][0]
            freddie_cfg = MockFreddie.call_args[0][0]
            assert fannie_cfg.max_workers == 8
            assert freddie_cfg.max_workers == 1  # Playwright requires single thread
