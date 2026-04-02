"""Tests for the SemanticChunker."""

from __future__ import annotations

from gse_guides.chunker import SemanticChunker
from gse_guides.config import ScraperConfig
from gse_guides.models import GuideSection, GuideSource, SubSection


class TestSemanticChunker:
    def setup_method(self):
        self.config = ScraperConfig()
        self.chunker = SemanticChunker(self.config)

    def test_always_creates_section_chunk(self, sample_guide_section):
        chunks = self.chunker.chunk_section(sample_guide_section)
        assert len(chunks) >= 1
        assert chunks[0].chunk_type == "section"
        assert chunks[0].chunk_id == "fannie_mae/B3-3.1-01"

    def test_creates_subsection_chunks_when_large(self, sample_guide_section):
        # word_count=3000 > max_chunk_words=2000, and has 2 subsections
        chunks = self.chunker.chunk_section(sample_guide_section)
        subsection_chunks = [c for c in chunks if c.chunk_type == "subsection"]
        assert len(subsection_chunks) >= 1

    def test_no_subsection_chunks_when_small(self):
        section = GuideSection(
            source=GuideSource.FANNIE_MAE,
            section_code="B1-1-01",
            title="Small Section",
            url="https://example.com",
            part_code="B",
            part_name="Part B",
            chapter_code="B1-1",
            chapter_name="Chapter 1",
            content_markdown="Short content.",
            word_count=100,
            subsections=[
                SubSection(
                    heading="H1", heading_level=2, anchor_id=None,
                    content_html="", content_markdown="text",
                    word_count=50,
                ),
            ],
        )
        chunks = self.chunker.chunk_section(section)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "section"

    def test_hierarchy_path_built_correctly(self, sample_guide_section):
        chunks = self.chunker.chunk_section(sample_guide_section)
        path = chunks[0].metadata.hierarchy_path
        assert "Origination Through Closing" in path
        assert "B3-3.1-01" in path

    def test_subsection_chunk_has_context_prefix(self, sample_guide_section):
        chunks = self.chunker.chunk_section(sample_guide_section)
        subsection_chunks = [c for c in chunks if c.chunk_type == "subsection"]
        if subsection_chunks:
            assert "Section: B3-3.1-01" in subsection_chunks[0].content
