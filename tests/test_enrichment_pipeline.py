"""Tests for the enrichment pipeline orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from gse_guides.config import ScraperConfig
from gse_guides.enrichment.pipeline import EnrichmentPipeline
from gse_guides.models import GuideSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_FRONTMATTER = {
    "source": "fannie_mae",
    "section_code": "B3-3.1-01",
    "title": "General Income Information",
    "url": "https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income-information",
    "part": "B",
    "part_name": "Origination Through Closing",
    "chapter": "B3-3",
    "chapter_name": "Income Assessment",
    "subpart": "B3-3.1",
    "subpart_name": "General Income Requirements",
    "effective_date": "2026-03-04",
    "word_count": 500,
    "table_count": 1,
}


def _build_md_file(frontmatter: dict, body: str = "Test body content.") -> str:
    """Build a markdown string with YAML frontmatter."""
    fm_text = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    return f"---\n{fm_text}---\n\n{body}"


def _write_sample_md(
    output_dir: Path,
    source_dir: str = "fannie_mae",
    filename: str = "b3-3.1-01_general-income-information.md",
    frontmatter: dict | None = None,
    body: str = "The lender must verify income.",
) -> Path:
    """Write a sample markdown file under the given source directory."""
    fm = frontmatter or SAMPLE_FRONTMATTER
    src_dir = output_dir / source_dir
    src_dir.mkdir(parents=True, exist_ok=True)
    md_path = src_dir / filename
    md_path.write_text(_build_md_file(fm, body), encoding="utf-8")
    return md_path


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    """Tests for EnrichmentPipeline._parse_frontmatter."""

    def setup_method(self):
        self.config = ScraperConfig()
        self.pipeline = EnrichmentPipeline(self.config)

    def test_valid_yaml(self):
        text = _build_md_file({"title": "Hello", "section_code": "A1"}, "Body here.")
        fm, body = self.pipeline._parse_frontmatter(text)
        assert fm["title"] == "Hello"
        assert fm["section_code"] == "A1"
        assert "Body here." in body

    def test_malformed_yaml(self):
        text = "---\n: :\nbad: [unclosed\n---\n\nBody text."
        fm, body = self.pipeline._parse_frontmatter(text)
        # Malformed YAML returns empty dict but still parses body
        assert fm == {}
        assert "Body text." in body

    def test_missing_closing_delimiter(self):
        text = "---\ntitle: Oops\nNo closing delimiter here"
        fm, body = self.pipeline._parse_frontmatter(text)
        # No closing --- => returns empty fm and full text as body
        assert fm == {}
        assert body == text

    def test_empty_input(self):
        fm, body = self.pipeline._parse_frontmatter("")
        assert fm == {}
        assert body == ""

    def test_no_frontmatter_prefix(self):
        text = "Just plain markdown without frontmatter."
        fm, body = self.pipeline._parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_empty_frontmatter_block(self):
        text = "---\n---\n\nBody."
        fm, body = self.pipeline._parse_frontmatter(text)
        assert fm == {}
        assert "Body." in body


# ---------------------------------------------------------------------------
# _build_hierarchy
# ---------------------------------------------------------------------------


class TestBuildHierarchy:
    """Tests for EnrichmentPipeline._build_hierarchy."""

    def setup_method(self):
        self.config = ScraperConfig()
        self.pipeline = EnrichmentPipeline(self.config)

    def test_full_hierarchy(self):
        fm = {
            "part_name": "Part B",
            "chapter_name": "Chapter 3",
            "subpart_name": "Subpart 3.1",
            "section_code": "B3-3.1-01",
        }
        result = self.pipeline._build_hierarchy(fm)
        assert result == "Part B > Chapter 3 > Subpart 3.1 > B3-3.1-01"

    def test_chapter_number_fallback(self):
        fm = {"chapter": "B3-3", "section_code": "B3-3.1-01"}
        result = self.pipeline._build_hierarchy(fm)
        assert "Chapter B3-3" in result
        assert "B3-3.1-01" in result

    def test_chapter_name_takes_precedence_over_chapter(self):
        fm = {"chapter": "B3-3", "chapter_name": "Income Assessment"}
        result = self.pipeline._build_hierarchy(fm)
        assert "Income Assessment" in result
        assert "Chapter B3-3" not in result

    def test_empty_dict(self):
        result = self.pipeline._build_hierarchy({})
        assert result == ""

    def test_only_section_code(self):
        result = self.pipeline._build_hierarchy({"section_code": "X1"})
        assert result == "X1"

    def test_part_and_section_only(self):
        fm = {"part_name": "Part A", "section_code": "A1-1-01"}
        result = self.pipeline._build_hierarchy(fm)
        assert result == "Part A > A1-1-01"


# ---------------------------------------------------------------------------
# _resolve_sources
# ---------------------------------------------------------------------------


class TestResolveSources:
    """Tests for EnrichmentPipeline._resolve_sources."""

    def setup_method(self):
        self.config = ScraperConfig()
        self.pipeline = EnrichmentPipeline(self.config)

    def test_none_returns_both(self):
        result = self.pipeline._resolve_sources(None)
        assert len(result) == 2
        names = [name for name, _ in result]
        assert "fannie_mae" in names
        assert "freddie_mac" in names

    def test_fannie_mae_filter(self):
        result = self.pipeline._resolve_sources("fannie-mae")
        assert len(result) == 1
        assert result[0][0] == "fannie_mae"
        assert result[0][1] == GuideSource.FANNIE_MAE

    def test_freddie_mac_filter(self):
        result = self.pipeline._resolve_sources("freddie-mac")
        assert len(result) == 1
        assert result[0][0] == "freddie_mac"
        assert result[0][1] == GuideSource.FREDDIE_MAC

    def test_unknown_source_returns_empty(self):
        result = self.pipeline._resolve_sources("unknown-source")
        assert result == []

    def test_underscore_format(self):
        result = self.pipeline._resolve_sources("fannie_mae")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _discover_section_codes
# ---------------------------------------------------------------------------


class TestDiscoverSectionCodes:
    """Tests for EnrichmentPipeline._discover_section_codes using tmp_path."""

    def test_discovers_codes_from_disk(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path)
        pipeline = EnrichmentPipeline(config)

        # Create fannie_mae and freddie_mac files on disk
        _write_sample_md(
            tmp_path,
            source_dir="fannie_mae",
            filename="b3-3.1-01.md",
            frontmatter={"section_code": "B3-3.1-01"},
        )
        _write_sample_md(
            tmp_path,
            source_dir="freddie_mac",
            filename="5703.1.md",
            frontmatter={"section_code": "5703.1"},
        )

        codes = pipeline._discover_section_codes(None)
        assert "B3-3.1-01" in codes["fannie_mae"]
        assert "5703.1" in codes["freddie_mac"]

    def test_filter_by_source(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path)
        pipeline = EnrichmentPipeline(config)

        _write_sample_md(
            tmp_path,
            source_dir="fannie_mae",
            filename="a1.md",
            frontmatter={"section_code": "A1"},
        )
        _write_sample_md(
            tmp_path,
            source_dir="freddie_mac",
            filename="f1.md",
            frontmatter={"section_code": "F1"},
        )

        codes = pipeline._discover_section_codes("fannie-mae")
        assert "A1" in codes["fannie_mae"]
        assert codes["freddie_mac"] == []

    def test_missing_source_dir(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path)
        pipeline = EnrichmentPipeline(config)
        # No directories created
        codes = pipeline._discover_section_codes(None)
        assert codes["fannie_mae"] == []
        assert codes["freddie_mac"] == []

    def test_file_without_section_code(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path)
        pipeline = EnrichmentPipeline(config)

        _write_sample_md(
            tmp_path,
            source_dir="fannie_mae",
            filename="no_code.md",
            frontmatter={"title": "No Code Here"},
        )

        codes = pipeline._discover_section_codes(None)
        assert codes["fannie_mae"] == []

    def test_file_without_frontmatter(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path)
        pipeline = EnrichmentPipeline(config)

        src_dir = tmp_path / "fannie_mae"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "plain.md").write_text("No frontmatter at all.", encoding="utf-8")

        codes = pipeline._discover_section_codes(None)
        assert codes["fannie_mae"] == []


# ---------------------------------------------------------------------------
# _process_file
# ---------------------------------------------------------------------------


class TestProcessFile:
    """Tests for EnrichmentPipeline._process_file."""

    def test_produces_enriched_chunks(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path, enriched_dir=tmp_path / "enriched")
        pipeline = EnrichmentPipeline(config)
        # CrossLinker needs to be initialized
        pipeline.linker = __import__(
            "gse_guides.enrichment.cross_linker", fromlist=["CrossLinker"]
        ).CrossLinker()

        md_path = _write_sample_md(
            tmp_path,
            body="The borrower must have stable income.\n\n## Verification\n\nEmployment must be verified.",
        )

        chunks = pipeline._process_file(md_path, GuideSource.FANNIE_MAE)
        assert len(chunks) >= 1
        first = chunks[0]
        assert first.source == GuideSource.FANNIE_MAE
        assert first.section_code == "B3-3.1-01"
        assert first.title == "General Income Information"
        assert first.content  # Non-empty content
        assert first.word_count > 0

    def test_chunk_id_format(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path, enriched_dir=tmp_path / "enriched")
        pipeline = EnrichmentPipeline(config)
        pipeline.linker = __import__(
            "gse_guides.enrichment.cross_linker", fromlist=["CrossLinker"]
        ).CrossLinker()

        md_path = _write_sample_md(tmp_path, body="Simple content.")
        chunks = pipeline._process_file(md_path, GuideSource.FANNIE_MAE)
        assert chunks[0].chunk_id.startswith("fannie_mae/B3-3.1-01/")

    def test_hierarchy_path_populated(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path, enriched_dir=tmp_path / "enriched")
        pipeline = EnrichmentPipeline(config)
        pipeline.linker = __import__(
            "gse_guides.enrichment.cross_linker", fromlist=["CrossLinker"]
        ).CrossLinker()

        md_path = _write_sample_md(tmp_path, body="Content here.")
        chunks = pipeline._process_file(md_path, GuideSource.FANNIE_MAE)
        assert "Origination Through Closing" in chunks[0].hierarchy_path

    def test_effective_date_propagated(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path, enriched_dir=tmp_path / "enriched")
        pipeline = EnrichmentPipeline(config)
        pipeline.linker = __import__(
            "gse_guides.enrichment.cross_linker", fromlist=["CrossLinker"]
        ).CrossLinker()

        md_path = _write_sample_md(tmp_path, body="Content.")
        chunks = pipeline._process_file(md_path, GuideSource.FANNIE_MAE)
        assert chunks[0].effective_date == "2026-03-04"


# ---------------------------------------------------------------------------
# run() — end-to-end
# ---------------------------------------------------------------------------


class TestRunEndToEnd:
    """Tests for EnrichmentPipeline.run() with tmp_path."""

    def test_run_processes_files(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "output",
            enriched_dir=tmp_path / "enriched",
        )
        pipeline = EnrichmentPipeline(config)

        _write_sample_md(
            config.output_dir,
            source_dir="fannie_mae",
            body="Income verification requirements for all borrowers.",
        )

        result = pipeline.run(source="fannie-mae")
        assert result.total_sections >= 1
        assert result.total_chunks >= 1
        assert result.errors == []

    def test_run_with_no_files(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "output",
            enriched_dir=tmp_path / "enriched",
        )
        pipeline = EnrichmentPipeline(config)

        result = pipeline.run()
        assert result.total_sections == 0
        assert result.total_chunks == 0

    def test_run_both_sources(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "output",
            enriched_dir=tmp_path / "enriched",
        )
        pipeline = EnrichmentPipeline(config)

        _write_sample_md(
            config.output_dir,
            source_dir="fannie_mae",
            body="Fannie Mae income content.",
        )
        _write_sample_md(
            config.output_dir,
            source_dir="freddie_mac",
            filename="5703.1.md",
            frontmatter={
                "section_code": "5703.1",
                "title": "Income Evaluation",
                "url": "https://guide.freddiemac.com/app/guide/section/5703.1",
                "word_count": 100,
                "table_count": 0,
            },
            body="Freddie Mac income requirements.",
        )

        result = pipeline.run(source=None)
        assert result.total_sections >= 2

    def test_run_writes_enriched_output(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "output",
            enriched_dir=tmp_path / "enriched",
        )
        pipeline = EnrichmentPipeline(config)

        _write_sample_md(
            config.output_dir,
            source_dir="fannie_mae",
            body="Stable income must be documented.",
        )

        pipeline.run(source="fannie-mae")
        # Enriched directory should contain chunk .txt files
        enriched_files = list(config.enriched_dir.rglob("*.txt"))
        assert len(enriched_files) >= 1


# ---------------------------------------------------------------------------
# Incremental mode: _load_state / _save_state / skip unchanged
# ---------------------------------------------------------------------------


class TestIncrementalMode:
    """Tests for incremental enrichment state management."""

    def test_save_and_load_state(self, tmp_path):
        config = ScraperConfig(enriched_dir=tmp_path / "enriched")
        pipeline = EnrichmentPipeline(config)

        hashes = {"fannie_mae/b3.md": "abc123", "freddie_mac/f1.md": "def456"}
        pipeline._save_state(hashes)

        loaded = pipeline._load_state()
        assert loaded == hashes

    def test_load_state_missing_file(self, tmp_path):
        config = ScraperConfig(enriched_dir=tmp_path / "enriched")
        pipeline = EnrichmentPipeline(config)
        loaded = pipeline._load_state()
        assert loaded == {}

    def test_load_state_corrupt_json(self, tmp_path):
        config = ScraperConfig(enriched_dir=tmp_path / "enriched")
        pipeline = EnrichmentPipeline(config)

        state_path = config.enriched_dir / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("not valid json {{{", encoding="utf-8")

        loaded = pipeline._load_state()
        assert loaded == {}

    def test_incremental_skips_unchanged(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "output",
            enriched_dir=tmp_path / "enriched",
        )
        pipeline = EnrichmentPipeline(config)

        md_path = _write_sample_md(
            config.output_dir,
            source_dir="fannie_mae",
            body="Income content for incremental test.",
        )

        # First run: processes the file
        result1 = pipeline.run(source="fannie-mae", incremental=True)
        assert result1.total_sections == 1

        # Second run without changes: should skip
        pipeline2 = EnrichmentPipeline(config)
        result2 = pipeline2.run(source="fannie-mae", incremental=True)
        assert result2.total_sections == 0  # Skipped unchanged

    def test_incremental_detects_changes(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "output",
            enriched_dir=tmp_path / "enriched",
        )
        pipeline = EnrichmentPipeline(config)

        md_path = _write_sample_md(
            config.output_dir,
            source_dir="fannie_mae",
            body="Original content.",
        )

        # First run
        pipeline.run(source="fannie-mae", incremental=True)

        # Modify the file
        md_path.write_text(
            _build_md_file(SAMPLE_FRONTMATTER, "Updated content with changes."),
            encoding="utf-8",
        )

        # Second run: should re-process
        pipeline2 = EnrichmentPipeline(config)
        result2 = pipeline2.run(source="fannie-mae", incremental=True)
        assert result2.total_sections == 1

    def test_state_path_location(self, tmp_path):
        config = ScraperConfig(enriched_dir=tmp_path / "enriched")
        pipeline = EnrichmentPipeline(config)
        assert pipeline._state_path() == tmp_path / "enriched" / "state.json"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling in the processing loop."""

    def test_error_in_process_file_is_captured(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "output",
            enriched_dir=tmp_path / "enriched",
        )
        pipeline = EnrichmentPipeline(config)

        # Write a valid file first (so _discover_section_codes can read it),
        # then replace it with broken content before _process_file runs.
        _write_sample_md(
            config.output_dir,
            source_dir="fannie_mae",
            filename="good.md",
            body="Valid content.",
        )

        # Also write a file that will cause _process_file to fail:
        # valid UTF-8 frontmatter but body triggers an error via mock
        bad_path = _write_sample_md(
            config.output_dir,
            source_dir="fannie_mae",
            filename="bad.md",
            body="Bad content.",
        )

        # Patch _process_file to raise on the bad file only
        original_process = pipeline._process_file

        def patched_process(md_path, source):
            if md_path.name == "bad.md":
                raise RuntimeError("Simulated processing error")
            return original_process(md_path, source)

        pipeline._process_file = patched_process

        result = pipeline.run(source="fannie-mae")
        assert len(result.errors) >= 1
        assert "bad.md" in result.errors[0]

    def test_missing_source_directory_logged(self, tmp_path):
        config = ScraperConfig(
            output_dir=tmp_path / "output",
            enriched_dir=tmp_path / "enriched",
        )
        pipeline = EnrichmentPipeline(config)
        # Don't create any directories
        result = pipeline.run(source="fannie-mae")
        # Should not crash, just return empty results
        assert result.total_sections == 0
        assert result.total_chunks == 0
