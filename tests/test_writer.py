"""Tests for MarkdownWriter and EnrichmentWriter."""

from __future__ import annotations

import json

from gse_guides.config import ScraperConfig
from gse_guides.enrichment.writer import EnrichmentWriter
from gse_guides.models import (
    EnrichedChunk,
    GuideSource,
)


class TestEnrichmentWriter:
    def test_write_chunk_creates_file(self, tmp_path):
        config = ScraperConfig(enriched_dir=tmp_path / "enriched")
        writer = EnrichmentWriter(config)

        chunk = EnrichedChunk(
            chunk_id="fannie_mae/B3-3.1-01/intro",
            source=GuideSource.FANNIE_MAE,
            section_code="B3-3.1-01",
            title="General Income",
            heading=None,
            domains=["BORROWER.borrower_income"],
            content_type="policy_rule",
            content="Test content here.",
        )

        path = writer.write_chunk(chunk)
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "Source: fannie_mae" in text
        assert "Test content here." in text

    def test_write_index_creates_json(self, tmp_path):
        config = ScraperConfig(enriched_dir=tmp_path / "enriched")
        writer = EnrichmentWriter(config)

        chunk = EnrichedChunk(
            chunk_id="fannie_mae/B3-3.1-01/intro",
            source=GuideSource.FANNIE_MAE,
            section_code="B3-3.1-01",
            title="General Income",
            heading=None,
            domains=["BORROWER.borrower_income"],
            content="Content.",
            word_count=50,
        )

        path = writer.write_index([chunk])
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["total_chunks"] == 1
        assert data["chunks"][0]["chunk_id"] == "fannie_mae/B3-3.1-01/intro"

    def test_collision_handling(self, tmp_path):
        config = ScraperConfig(enriched_dir=tmp_path / "enriched")
        writer = EnrichmentWriter(config)

        chunk = EnrichedChunk(
            chunk_id="fannie_mae/B3-3.1-01/intro",
            source=GuideSource.FANNIE_MAE,
            section_code="B3-3.1-01",
            title="Test",
            heading=None,
            content="Content.",
        )

        path1 = writer.write_chunk(chunk)
        path2 = writer.write_chunk(chunk)
        assert path1 != path2
        assert path1.exists()
        assert path2.exists()
