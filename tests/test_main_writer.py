"""Tests for the main MarkdownWriter (src/gse_guides/writer.py)."""

from __future__ import annotations

import yaml

from gse_guides import safe_path_component
from gse_guides.config import ScraperConfig
from gse_guides.models import (
    Chunk,
    ChunkMetadata,
    CrossReference,
    GuideSection,
    GuideSource,
    RelatedAnnouncement,
    SubSection,
)
from gse_guides.writer import MarkdownWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_section(
    source: GuideSource = GuideSource.FANNIE_MAE,
    section_code: str = "B3-3.1-01",
    title: str = "General Income Information",
    part_code: str = "B",
    part_name: str = "Origination Through Closing",
    chapter_code: str = "B3-3",
    chapter_name: str = "Income Assessment",
    content_markdown: str = "Test content about income verification.",
    **overrides,
) -> GuideSection:
    defaults = dict(
        source=source,
        section_code=section_code,
        title=title,
        url="https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income-information",
        part_code=part_code,
        part_name=part_name,
        chapter_code=chapter_code,
        chapter_name=chapter_name,
        content_markdown=content_markdown,
    )
    defaults.update(overrides)
    return GuideSection(**defaults)


def _make_chunk(
    chunk_id: str = "B3-3.1-01/section",
    chunk_type: str = "section",
    subsection_heading: str | None = None,
) -> Chunk:
    meta = ChunkMetadata(
        chunk_id=chunk_id,
        source=GuideSource.FANNIE_MAE,
        section_code="B3-3.1-01",
        subsection_heading=subsection_heading,
        title="General Income Information",
        hierarchy_path="Part B > Income Assessment > B3-3.1-01",
        word_count=100,
        has_tables=False,
        effective_date=None,
        url="https://example.com",
    )
    return Chunk(
        chunk_id=chunk_id,
        metadata=meta,
        content="Chunk content.",
        parent_section_code="B3-3.1-01",
        chunk_type=chunk_type,
    )


# ---------------------------------------------------------------------------
# write_section
# ---------------------------------------------------------------------------


class TestWriteSection:
    """Tests for MarkdownWriter.write_section."""

    def test_creates_file_with_frontmatter_and_content(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer.write_section(sample_guide_section, [])
        assert path.exists()

        text = path.read_text(encoding="utf-8")
        assert text.startswith("---")
        # Should contain section heading
        assert "B3-3.1-01" in text
        assert "General Income Information" in text

    def test_file_content_has_yaml_frontmatter(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer.write_section(sample_guide_section, [])
        text = path.read_text(encoding="utf-8")

        # Extract and parse frontmatter
        assert text.startswith("---\n")
        end = text.index("---", 3)
        fm_text = text[3:end]
        fm = yaml.safe_load(fm_text)

        assert fm["source"] == "fannie_mae"
        assert fm["section_code"] == "B3-3.1-01"
        assert fm["title"] == "General Income Information"

    def test_includes_content_body(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer.write_section(sample_guide_section, [])
        text = path.read_text(encoding="utf-8")
        assert "Test content about income verification." in text

    def test_includes_related_announcements_footer(self, tmp_path):
        section = _make_section(
            related_announcements=[
                RelatedAnnouncement(code="SEL-2026-02", date="03/04/2026"),
                RelatedAnnouncement(code="SEL-2026-01", date="01/15/2026"),
            ],
        )
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer.write_section(section, [])
        text = path.read_text(encoding="utf-8")
        assert "Related Announcements" in text
        assert "SEL-2026-02 (03/04/2026)" in text

    def test_write_section_with_chunks(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        chunks = [_make_chunk()]
        path = writer.write_section(sample_guide_section, chunks)
        text = path.read_text(encoding="utf-8")
        assert "chunk_ids" in text  # frontmatter includes chunk ids


# ---------------------------------------------------------------------------
# _build_output_path
# ---------------------------------------------------------------------------


class TestBuildOutputPath:
    """Tests for MarkdownWriter._build_output_path."""

    def test_fannie_mae_path(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        section = _make_section(
            source=GuideSource.FANNIE_MAE,
            part_code="B",
            section_code="B3-3.1-01",
            title="General Income Information",
        )

        path = writer._build_output_path(section)
        assert "fannie_mae" in str(path)
        assert "part_b" in str(path)
        assert path.name.startswith("b3-3.1-01_")
        assert path.suffix == ".md"

    def test_freddie_mac_path(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        section = _make_section(
            source=GuideSource.FREDDIE_MAC,
            part_code="5700",
            chapter_code="5703",
            section_code="5703.1",
            title="Income Evaluation",
            url="https://guide.freddiemac.com/app/guide/section/5703.1",
        )

        path = writer._build_output_path(section)
        assert "freddie_mac" in str(path)
        assert "chapter_" in str(path)
        assert "5703.1" in path.name
        assert path.suffix == ".md"

    def test_fannie_path_uses_part_code_directory(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        section = _make_section(part_code="D")
        path = writer._build_output_path(section)
        assert "part_d" in str(path)


# ---------------------------------------------------------------------------
# _build_output_path_from_code
# ---------------------------------------------------------------------------


class TestBuildOutputPathFromCode:
    """Tests for MarkdownWriter._build_output_path_from_code."""

    def test_fannie_mae_from_code(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer._build_output_path_from_code(
            "B3-3.1-01", "general-income-information", GuideSource.FANNIE_MAE,
        )
        assert "fannie_mae" in str(path)
        assert "part_b" in str(path)
        assert path.name.startswith("b3-3.1-01_")
        assert path.suffix == ".md"

    def test_freddie_mac_from_code(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer._build_output_path_from_code(
            "5703.1", "income-evaluation", GuideSource.FREDDIE_MAC,
        )
        assert "freddie_mac" in str(path)
        assert "chapter_5703" in str(path)
        assert "5703.1" in path.name
        assert path.suffix == ".md"

    def test_from_code_empty_slug_uses_code(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer._build_output_path_from_code(
            "B1-1-01", "", GuideSource.FANNIE_MAE,
        )
        assert "b1-1-01" in path.name.lower()

    def test_freddie_code_without_dot(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer._build_output_path_from_code(
            "5703", "overview", GuideSource.FREDDIE_MAC,
        )
        # When no dot, the whole code is used as chapter
        assert "chapter_5703" in str(path)


# ---------------------------------------------------------------------------
# _build_frontmatter
# ---------------------------------------------------------------------------


class TestBuildFrontmatter:
    """Tests for MarkdownWriter._build_frontmatter."""

    def test_includes_all_expected_fields(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        fm_text = writer._build_frontmatter(sample_guide_section, [])
        fm = yaml.safe_load(fm_text)

        assert fm["source"] == "fannie_mae"
        assert fm["section_code"] == "B3-3.1-01"
        assert fm["title"] == "General Income Information"
        assert "url" in fm
        assert fm["part"] == "B"
        assert fm["part_name"] == "Origination Through Closing"
        assert fm["chapter"] == "B3-3"
        assert fm["chapter_name"] == "Income Assessment"
        assert fm["word_count"] == 3000
        assert fm["table_count"] == 1
        assert "scraped_at" in fm

    def test_includes_subpart_when_present(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        fm_text = writer._build_frontmatter(sample_guide_section, [])
        fm = yaml.safe_load(fm_text)

        assert fm["subpart"] == "B3-3.1"
        assert fm["subpart_name"] == "General Income Requirements"

    def test_excludes_subpart_when_none(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        section = _make_section(subpart_code=None, subpart_name=None)
        fm_text = writer._build_frontmatter(section, [])
        fm = yaml.safe_load(fm_text)

        assert "subpart" not in fm
        assert "subpart_name" not in fm

    def test_includes_effective_date_when_present(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        fm_text = writer._build_frontmatter(sample_guide_section, [])
        fm = yaml.safe_load(fm_text)
        assert fm["effective_date"] == "2026-03-04"

    def test_includes_subsection_headings(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        fm_text = writer._build_frontmatter(sample_guide_section, [])
        fm = yaml.safe_load(fm_text)

        assert "subsections" in fm
        assert "Stable Income" in fm["subsections"]
        assert "Continuance of Income" in fm["subsections"]

    def test_includes_chunk_ids(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        chunks = [_make_chunk("B3-3.1-01/section"), _make_chunk("B3-3.1-01/sub1")]
        fm_text = writer._build_frontmatter(sample_guide_section, chunks)
        fm = yaml.safe_load(fm_text)

        assert fm["chunk_ids"] == ["B3-3.1-01/section", "B3-3.1-01/sub1"]

    def test_includes_cross_references(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        section = _make_section(
            cross_references=[
                CrossReference(
                    target_section_code="B3-3.1-02",
                    target_url="https://example.com",
                    link_text="See B3-3.1-02",
                    context="related",
                ),
            ],
        )

        fm_text = writer._build_frontmatter(section, [])
        fm = yaml.safe_load(fm_text)
        assert "B3-3.1-02" in fm["cross_references"]

    def test_includes_related_announcements(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        section = _make_section(
            related_announcements=[
                RelatedAnnouncement(code="SEL-2026-02", date="03/04/2026"),
            ],
        )

        fm_text = writer._build_frontmatter(section, [])
        fm = yaml.safe_load(fm_text)
        assert fm["related_announcements"][0]["code"] == "SEL-2026-02"


# ---------------------------------------------------------------------------
# _insert_chunk_markers
# ---------------------------------------------------------------------------


class TestInsertChunkMarkers:
    """Tests for MarkdownWriter._insert_chunk_markers."""

    def test_no_chunks_returns_unchanged(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        md = "Some markdown content."
        result = writer._insert_chunk_markers(md, [])
        assert result == md

    def test_section_chunk_inserts_at_top(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        md = "Intro paragraph.\n\n## Heading\n\nMore content."
        chunk = _make_chunk("B3-3.1-01/section", chunk_type="section")

        result = writer._insert_chunk_markers(md, [chunk])
        assert result.startswith("<!-- chunk: B3-3.1-01/section -->")
        assert "Intro paragraph." in result

    def test_subsection_chunk_before_heading(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        md = "Intro.\n\n## Stable Income\n\nStable income paragraph."
        chunk = _make_chunk(
            "B3-3.1-01/stable-income",
            chunk_type="subsection",
            subsection_heading="Stable Income",
        )

        result = writer._insert_chunk_markers(md, [chunk])
        assert "<!-- chunk: B3-3.1-01/stable-income -->" in result
        # Marker should appear before the heading
        marker_pos = result.index("<!-- chunk:")
        heading_pos = result.index("## Stable Income")
        assert marker_pos < heading_pos

    def test_multiple_subsection_markers(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        md = "Intro.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B."
        chunks = [
            _make_chunk("c/section", chunk_type="section"),
            _make_chunk("c/a", chunk_type="subsection", subsection_heading="Section A"),
            _make_chunk("c/b", chunk_type="subsection", subsection_heading="Section B"),
        ]

        result = writer._insert_chunk_markers(md, chunks)
        assert "<!-- chunk: c/section -->" in result
        assert "<!-- chunk: c/a -->" in result
        assert "<!-- chunk: c/b -->" in result

    def test_h3_heading_marker(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        md = "Intro.\n\n### Sub Heading\n\nSub content."
        chunk = _make_chunk(
            "c/sub", chunk_type="subsection", subsection_heading="Sub Heading",
        )

        result = writer._insert_chunk_markers(md, [chunk])
        assert "<!-- chunk: c/sub -->" in result


# ---------------------------------------------------------------------------
# Path sanitization
# ---------------------------------------------------------------------------


class TestPathSanitization:
    """Tests that path traversal sequences are sanitized."""

    def test_safe_path_component_strips_traversal(self):
        assert ".." not in safe_path_component("../../etc/passwd")
        assert "/" not in safe_path_component("../../etc/passwd")
        assert "\\" not in safe_path_component("..\\..\\etc\\passwd")

    def test_safe_path_component_empty_becomes_unknown(self):
        assert safe_path_component("") == "_unknown"
        assert safe_path_component("..") == "_unknown"

    def test_safe_path_component_strips_null_bytes(self):
        assert "\x00" not in safe_path_component("test\x00file")

    def test_section_code_with_traversal_in_output_path(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        section = _make_section(section_code="../../etc/passwd")
        path = writer._build_output_path(section)
        # Path should not escape the output directory
        assert ".." not in str(path)
        assert str(path).startswith(str(tmp_path))

    def test_section_code_with_traversal_in_from_code(self, tmp_path):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer._build_output_path_from_code(
            "../../../etc/passwd", "exploit", GuideSource.FANNIE_MAE,
        )
        assert ".." not in str(path)

    def test_safe_path_component_import(self):
        """Verify safe_path_component is importable from the gse_guides package."""
        from gse_guides import safe_path_component as spc
        assert callable(spc)
        assert spc("normal") == "normal"


# ---------------------------------------------------------------------------
# File content structure
# ---------------------------------------------------------------------------


class TestFileContentStructure:
    """Tests that written files have correct structure."""

    def test_file_starts_with_frontmatter_delimiter(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer.write_section(sample_guide_section, [])
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), "File must start with YAML frontmatter delimiter"

    def test_frontmatter_is_valid_yaml(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer.write_section(sample_guide_section, [])
        text = path.read_text(encoding="utf-8")

        # Parse the frontmatter between the two --- delimiters
        end = text.index("---", 3)
        fm_text = text[3:end]
        fm = yaml.safe_load(fm_text)
        assert isinstance(fm, dict)

    def test_section_heading_after_frontmatter(self, tmp_path, sample_guide_section):
        config = ScraperConfig(output_dir=tmp_path / "output")
        writer = MarkdownWriter(config)

        path = writer.write_section(sample_guide_section, [])
        text = path.read_text(encoding="utf-8")

        # After the second ---, there should be a markdown heading
        end = text.index("---", 3)
        body = text[end + 3:]
        assert "# B3-3.1-01: General Income Information" in body
