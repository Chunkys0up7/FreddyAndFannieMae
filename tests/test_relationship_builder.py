"""Tests for the relationship builder module."""

from __future__ import annotations

import pytest

from gse_guides.enrichment.relationship_builder import RelationshipBuilder
from gse_guides.models import (
    CrossSourceLink,
    EnrichedChunk,
    GuideSource,
    NumericConstraint,
    RequirementMeta,
)


def _make_chunk(
    chunk_id: str = "fannie_mae/B3-3.1-01/intro",
    source: GuideSource = GuideSource.FANNIE_MAE,
    section_code: str = "B3-3.1-01",
    entities: dict | None = None,
    numeric_constraints: list | None = None,
    conditional_refs: list | None = None,
    cross_source_links: list | None = None,
) -> EnrichedChunk:
    return EnrichedChunk(
        chunk_id=chunk_id,
        source=source,
        section_code=section_code,
        title="Test Section",
        heading=None,
        entities=entities or {},
        numeric_constraints=numeric_constraints or [],
        conditional_refs=conditional_refs or [],
        cross_source_links=cross_source_links or [],
        content="Test content.",
    )


class TestRelationshipBuilder:
    """Tests for RelationshipBuilder.build."""

    def setup_method(self):
        self.builder = RelationshipBuilder()

    def test_empty_chunks(self):
        result = self.builder.build([])
        assert result["version"] == "1.0"
        # Static IMPLIES edges are always present (from implication rules)
        implies = [e for e in result["edges"] if e["type"] == "IMPLIES"]
        assert len(implies) >= 15
        # No APPLIES_TO edges without chunks
        applies = [e for e in result["edges"] if e["type"] == "APPLIES_TO"]
        assert applies == []
        assert result["sections_by_entity"] == {}

    def test_applies_to_edges(self):
        chunk = _make_chunk(
            entities={"property_types": ["Condo"], "income_sources": ["SelfEmployment"]},
        )
        result = self.builder.build([chunk])
        applies_to = [e for e in result["edges"] if e["type"] == "APPLIES_TO"]
        targets = {e["target"] for e in applies_to}
        assert "property_types.Condo" in targets
        assert "income_sources.SelfEmployment" in targets

    def test_sections_by_entity_reverse_index(self):
        chunk1 = _make_chunk(
            chunk_id="fannie_mae/B3-3.5-01/intro",
            entities={"income_sources": ["SelfEmployment"]},
        )
        chunk2 = _make_chunk(
            chunk_id="fannie_mae/B3-3.1-01/intro",
            entities={"income_sources": ["SelfEmployment", "W2Employment"]},
        )
        result = self.builder.build([chunk1, chunk2])
        idx = result["sections_by_entity"]
        assert "income_sources.SelfEmployment" in idx
        assert len(idx["income_sources.SelfEmployment"]) == 2

    def test_implication_edges_present(self):
        result = self.builder.build([])
        implies = [e for e in result["edges"] if e["type"] == "IMPLIES"]
        assert len(implies) >= 15  # At least as many as IMPLICATION_RULES

    def test_conditional_edges(self):
        chunk = _make_chunk(
            conditional_refs=[{"if_entity": "property_types.Condo", "then_see": "B4-2.2-01"}],
        )
        result = self.builder.build([chunk])
        cond = [e for e in result["edges"] if e["type"] == "CONDITIONAL"]
        assert len(cond) == 1
        assert cond[0]["target"] == "B4-2.2-01"

    def test_constrains_edges(self):
        constraint = NumericConstraint(
            metric="LTV", operator="<=", value="80", unit="%",
            conditions=["occupancy_types.Investment"],
        )
        chunk = _make_chunk(numeric_constraints=[constraint])
        result = self.builder.build([chunk])
        constrains = [e for e in result["edges"] if e["type"] == "CONSTRAINS"]
        assert len(constrains) == 1
        assert constrains[0]["source"] == "occupancy_types.Investment"

    def test_equivalent_edges(self):
        link = CrossSourceLink(
            source="freddie_mac", section_code="3101.1",
            topic="Income", relationship="equivalent",
        )
        chunk = _make_chunk(cross_source_links=[link])
        result = self.builder.build([chunk])
        equiv = [e for e in result["edges"] if e["type"] == "EQUIVALENT"]
        assert len(equiv) == 1
        assert "freddie_mac/3101.1" in equiv[0]["target"]

    def test_equivalent_edges_deduplication(self):
        link = CrossSourceLink(
            source="freddie_mac", section_code="3101.1",
            topic="Income", relationship="equivalent",
        )
        chunk1 = _make_chunk(chunk_id="fannie_mae/B3-3.1-01/intro", cross_source_links=[link])
        chunk2 = _make_chunk(chunk_id="fannie_mae/B3-3.1-01/verification", cross_source_links=[link])
        result = self.builder.build([chunk1, chunk2])
        equiv = [e for e in result["edges"] if e["type"] == "EQUIVALENT"]
        assert len(equiv) == 1  # Deduped

    def test_aggregate_constraints(self):
        c1 = NumericConstraint(metric="LTV", operator="<=", value="80", unit="%")
        c2 = NumericConstraint(metric="LTV", operator="<=", value="80", unit="%")
        chunk1 = _make_chunk(chunk_id="chunk1", section_code="B2-1.2-01", numeric_constraints=[c1])
        chunk2 = _make_chunk(chunk_id="chunk2", section_code="B2-1.2-02", numeric_constraints=[c2])
        result = self.builder.build([chunk1, chunk2])
        agg = result["numeric_constraints"]
        ltv_80 = [c for c in agg if c["metric"] == "LTV" and c["value"] == "80"]
        assert len(ltv_80) == 1  # Aggregated
        assert len(ltv_80[0]["source_sections"]) == 2

    def test_entity_type_vocab(self):
        result = self.builder.build([])
        vocab = result["entity_types"]
        assert "income_sources" in vocab
        assert "property_types" in vocab
        assert vocab["income_sources"]["count"] >= 10

    def test_stats_populated(self):
        chunk = _make_chunk(
            entities={"property_types": ["Condo"]},
        )
        result = self.builder.build([chunk])
        assert result["stats"]["total_edges"] > 0
        assert result["stats"]["total_entity_values"] > 0

    def test_multi_entity_intersection_query(self):
        """Verify the index supports intersection queries."""
        chunk_condo = _make_chunk(
            chunk_id="fannie_mae/B4-2.2-01/intro",
            entities={"property_types": ["Condo"], "transaction_types": ["CashOutRefinance"]},
        )
        chunk_se = _make_chunk(
            chunk_id="fannie_mae/B3-3.5-01/intro",
            entities={"income_sources": ["SelfEmployment"], "transaction_types": ["CashOutRefinance"]},
        )
        chunk_both = _make_chunk(
            chunk_id="fannie_mae/B5-1-01/intro",
            entities={
                "property_types": ["Condo"],
                "income_sources": ["SelfEmployment"],
                "transaction_types": ["CashOutRefinance"],
            },
        )
        result = self.builder.build([chunk_condo, chunk_se, chunk_both])
        idx = result["sections_by_entity"]

        # Intersection: Condo + SelfEmployment + CashOutRefinance
        condo_chunks = set(idx.get("property_types.Condo", []))
        se_chunks = set(idx.get("income_sources.SelfEmployment", []))
        cashout_chunks = set(idx.get("transaction_types.CashOutRefinance", []))
        intersection = condo_chunks & se_chunks & cashout_chunks

        assert "fannie_mae/B5-1-01/intro" in intersection
        assert "fannie_mae/B4-2.2-01/intro" not in intersection
        assert "fannie_mae/B3-3.5-01/intro" not in intersection
