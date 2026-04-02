"""Tests for data models and enums."""

from __future__ import annotations

from gse_guides.models import (
    EnrichedChunk,
    EnrichmentResult,
    GuideSection,
    GuideSource,
    ScrapeManifest,
    ScrapeStatus,
    SectionURL,
)


class TestGuideSource:
    def test_values(self):
        assert GuideSource.FANNIE_MAE.value == "fannie_mae"
        assert GuideSource.FREDDIE_MAC.value == "freddie_mac"


class TestScrapeStatus:
    def test_all_statuses_present(self):
        expected = {"pending", "success", "failed", "skipped", "quality_warning"}
        actual = {s.value for s in ScrapeStatus}
        assert actual == expected


class TestSectionURL:
    def test_construction(self, fannie_section_url):
        assert fannie_section_url.section_code == "B3-3.1-01"
        assert fannie_section_url.source == GuideSource.FANNIE_MAE


class TestScrapeManifest:
    def test_defaults(self):
        m = ScrapeManifest(source=GuideSource.FANNIE_MAE)
        assert m.total_scraped == 0
        assert m.total_quality_warnings == 0
        assert m.content_hashes == {}
        assert m.sections == {}
        assert m.errors == []


class TestGuideSection:
    def test_defaults(self):
        s = GuideSection(
            source=GuideSource.FANNIE_MAE,
            section_code="B1-1-01",
            title="Test",
            url="https://example.com",
            part_code="B",
            part_name="Part B",
            chapter_code="B1-1",
            chapter_name="Chapter 1",
        )
        assert s.word_count == 0
        assert s.subsections == []
        assert s.cross_references == []


class TestEnrichedChunk:
    def test_defaults(self):
        c = EnrichedChunk(
            chunk_id="test/chunk",
            source=GuideSource.FANNIE_MAE,
            section_code="B1-1-01",
            title="Test",
            heading=None,
        )
        assert c.domains == []
        assert c.mismo_tags == {}
        assert c.content_type == "policy_rule"


class TestEnrichmentResult:
    def test_defaults(self):
        r = EnrichmentResult()
        assert r.total_sections == 0
        assert r.total_chunks == 0
        assert r.domain_distribution == {}
