"""Tests for the LLM enricher and cache modules."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gse_guides.config import ScraperConfig
from gse_guides.enrichment.llm_cache import LLMCache
from gse_guides.enrichment.llm_enricher import LLMEnricher
from gse_guides.models import (
    EnrichedChunk,
    GuideSource,
    LLMEnrichmentResult,
    NumericConstraint,
    RequirementMeta,
)


# --- Helpers ---


def _make_chunk(
    chunk_id: str = "fannie_mae/B3-3.1-01/intro",
    content: str = "The maximum LTV is 80% for investment properties.",
    section_code: str = "B3-3.1-01",
    title: str = "General Income Information",
    entities: dict | None = None,
    numeric_constraints: list | None = None,
) -> EnrichedChunk:
    return EnrichedChunk(
        chunk_id=chunk_id,
        source=GuideSource.FANNIE_MAE,
        section_code=section_code,
        title=title,
        heading=None,
        content=content,
        entities=entities or {},
        numeric_constraints=numeric_constraints or [],
    )


def _mock_provider(
    response_json: dict | None = None,
    model_name: str = "claude-haiku-4-20250414",
) -> MagicMock:
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.model_name = model_name
    provider.cost_per_1k_input_tokens = 0.00025
    provider.cost_per_1k_output_tokens = 0.00125

    if response_json is None:
        response_json = {
            "summary": "Section requires 80% max LTV for investment properties.",
            "entities": {"occupancy_types": ["Investment"]},
            "numeric_constraints": [
                {
                    "metric": "LTV",
                    "operator": "<=",
                    "value": "80",
                    "unit": "%",
                    "conditions": ["occupancy_types.Investment"],
                    "source_text": "maximum LTV is 80%",
                }
            ],
            "relationships": [],
        }

    provider.complete.return_value = (json.dumps(response_json), 150)
    provider.estimate_cost.return_value = 0.001
    return provider


# --- LLMCache Tests ---


class TestLLMCache:
    """Tests for the LLM cache module."""

    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.cache_dir = Path(self._tmpdir) / "llm_cache"
        self.cache = LLMCache(self.cache_dir)

    def test_miss_returns_none(self):
        result = self.cache.get("test content", "model", "1.0")
        assert result is None

    def test_set_then_get(self):
        data = {"summary": "test"}
        self.cache.set("content", "model", "1.0", data, tokens_used=100)
        result = self.cache.get("content", "model", "1.0")
        assert result == data

    def test_different_content_is_miss(self):
        self.cache.set("content_a", "model", "1.0", {"a": 1})
        result = self.cache.get("content_b", "model", "1.0")
        assert result is None

    def test_different_model_is_miss(self):
        self.cache.set("content", "model_a", "1.0", {"a": 1})
        result = self.cache.get("content", "model_b", "1.0")
        assert result is None

    def test_different_prompt_version_is_miss(self):
        self.cache.set("content", "model", "1.0", {"a": 1})
        result = self.cache.get("content", "model", "2.0")
        assert result is None

    def test_content_hash_deterministic(self):
        h1 = LLMCache.content_hash("test", "model", "1.0")
        h2 = LLMCache.content_hash("test", "model", "1.0")
        assert h1 == h2

    def test_content_hash_different_inputs(self):
        h1 = LLMCache.content_hash("a", "model", "1.0")
        h2 = LLMCache.content_hash("b", "model", "1.0")
        assert h1 != h2

    def test_stats(self):
        self.cache.set("c1", "m", "1.0", {"a": 1})
        self.cache.get("c1", "m", "1.0")  # hit
        self.cache.get("c2", "m", "1.0")  # miss

        stats = self.cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["total_entries"] == 1
        assert stats["hit_rate"] == 0.5

    def test_clear(self):
        self.cache.set("c1", "m", "1.0", {"a": 1})
        self.cache.set("c2", "m", "1.0", {"b": 2})

        count = self.cache.clear()
        assert count == 2

        result = self.cache.get("c1", "m", "1.0")
        assert result is None

    def test_stats_empty_cache(self):
        stats = self.cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total_entries"] == 0
        assert stats["hit_rate"] == 0.0


# --- LLMEnricher Tests ---


class TestLLMEnricher:
    """Tests for the LLM enricher orchestrator."""

    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.config = ScraperConfig(enriched_dir=Path(self._tmpdir) / "enriched")
        self.config.enriched_dir.mkdir(parents=True, exist_ok=True)

    def test_enrich_chunk_calls_provider(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunk = _make_chunk()

        result = enricher.enrich_chunk(chunk)

        provider.complete.assert_called_once()
        assert result.summary == "Section requires 80% max LTV for investment properties."
        assert result.model == "claude-haiku-4-20250414"
        assert result.tokens_used == 150
        assert not result.cached

    def test_enrich_chunk_caches_result(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunk = _make_chunk()

        # First call: API call
        result1 = enricher.enrich_chunk(chunk)
        assert not result1.cached

        # Second call: cache hit
        result2 = enricher.enrich_chunk(chunk)
        assert result2.cached
        assert result2.summary == result1.summary

        # Provider called only once
        assert provider.complete.call_count == 1

    def test_enrich_chunk_cache_disabled(self):
        self.config.llm_cache_enabled = False
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunk = _make_chunk()

        enricher.enrich_chunk(chunk)
        enricher.enrich_chunk(chunk)

        assert provider.complete.call_count == 2

    def test_enrich_chunk_api_error_returns_empty(self):
        provider = _mock_provider()
        provider.complete.side_effect = Exception("API Error")
        enricher = LLMEnricher(provider, self.config)
        chunk = _make_chunk()

        result = enricher.enrich_chunk(chunk)

        assert result.summary == ""
        assert result.entities == {}
        assert enricher.chunks_processed == 1

    def test_enrich_batch(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunks = [_make_chunk(chunk_id=f"chunk_{i}") for i in range(3)]

        results = enricher.enrich_batch(chunks, progress=False)

        assert len(results) == 3
        assert all(r.summary for r in results)
        assert enricher.chunks_processed == 3

    def test_enrich_batch_respects_max_chunks(self):
        self.config.llm_max_chunks = 2
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunks = [
            _make_chunk(chunk_id=f"chunk_{i}", content=f"Unique content number {i}")
            for i in range(5)
        ]

        results = enricher.enrich_batch(chunks, progress=False)

        assert len(results) == 5  # Padded with empties
        assert provider.complete.call_count == 2  # Only 2 processed
        assert results[0].summary != ""
        assert results[1].summary != ""
        assert results[2].summary == ""  # Padded

    def test_enrich_chunk_tracks_tokens(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunk = _make_chunk()

        enricher.enrich_chunk(chunk)

        assert enricher.total_tokens == 150
        assert enricher.total_cost > 0

    def test_dry_run(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunks = [_make_chunk(chunk_id=f"chunk_{i}") for i in range(5)]

        result = enricher.dry_run(chunks)

        assert result["total_chunks"] == 5
        assert result["chunks_to_process"] == 5
        assert result["cache_hits"] == 0
        assert result["estimated_cost"] >= 0
        assert result["model"] == "claude-haiku-4-20250414"
        # No API calls made
        provider.complete.assert_not_called()

    def test_dry_run_with_cache(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunks = [
            _make_chunk(chunk_id=f"chunk_{i}", content=f"Unique content {i}")
            for i in range(3)
        ]

        # Pre-cache first chunk
        enricher.enrich_chunk(chunks[0])

        # Dry run should detect cache hit
        result = enricher.dry_run(chunks)
        assert result["cache_hits"] == 1
        assert result["chunks_to_process"] == 2

    def test_build_prompt_includes_content(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunk = _make_chunk(content="Test content about LTV requirements")

        prompt = enricher._build_prompt(chunk)

        assert "Test content about LTV requirements" in prompt
        assert "B3-3.1-01" in prompt
        assert "General Income Information" in prompt

    def test_build_prompt_includes_existing_entities(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        chunk = _make_chunk(
            entities={"property_types": ["Condo"], "occupancy_types": ["Investment"]}
        )

        prompt = enricher._build_prompt(chunk)

        assert "Condo" in prompt
        assert "Investment" in prompt

    def test_build_prompt_truncates_long_content(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)
        long_content = " ".join(["word"] * 5000)
        chunk = _make_chunk(content=long_content)

        prompt = enricher._build_prompt(chunk)

        assert "[Content truncated]" in prompt

    def test_parse_response_valid_json(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)

        response = json.dumps({
            "summary": "Test summary",
            "entities": {"income_sources": ["SelfEmployment"]},
            "numeric_constraints": [
                {"metric": "LTV", "operator": "<=", "value": "80", "unit": "%",
                 "conditions": [], "source_text": "max LTV 80%"}
            ],
            "relationships": [
                {"type": "CONDITIONAL", "target_section": "B4-2.2-01",
                 "condition": "condo", "description": "see condo section"}
            ],
        })

        result = enricher._parse_response(response)

        assert result["summary"] == "Test summary"
        assert result["entities"] == {"income_sources": ["SelfEmployment"]}
        assert len(result["numeric_constraints"]) == 1
        assert len(result["relationships"]) == 1

    def test_parse_response_code_fenced(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)

        response = '```json\n{"summary": "fenced", "entities": {}, "numeric_constraints": [], "relationships": []}\n```'
        result = enricher._parse_response(response)
        assert result["summary"] == "fenced"

    def test_parse_response_invalid_json(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)

        result = enricher._parse_response("not json at all")
        assert result == {}

    def test_parse_response_missing_keys(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)

        result = enricher._parse_response('{"summary": "only summary"}')
        assert result["summary"] == "only summary"
        assert result["entities"] == {}
        assert result["numeric_constraints"] == []
        assert result["relationships"] == []

    def test_parse_response_bad_entity_types(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)

        # entities should be dict, not list
        result = enricher._parse_response('{"entities": "not a dict"}')
        assert result["entities"] == {}

    def test_dict_to_result(self):
        provider = _mock_provider()
        enricher = LLMEnricher(provider, self.config)

        data = {
            "summary": "Test",
            "entities": {"income_sources": ["W2Employment"]},
            "numeric_constraints": [
                {"metric": "DTI", "operator": "<=", "value": "45", "unit": "%"}
            ],
            "relationships": [{"type": "REQUIRES", "target_section": "B1-1-01"}],
        }

        result = enricher._dict_to_result(data)

        assert isinstance(result, LLMEnrichmentResult)
        assert result.summary == "Test"
        assert result.entities == {"income_sources": ["W2Employment"]}
        assert len(result.numeric_constraints) == 1
        assert isinstance(result.numeric_constraints[0], NumericConstraint)
        assert result.numeric_constraints[0].metric == "DTI"
        assert len(result.relationships) == 1


class TestLLMEnricherCostTracking:
    """Tests for cost tracking across multiple chunks."""

    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.config = ScraperConfig(enriched_dir=Path(self._tmpdir) / "enriched")
        self.config.enriched_dir.mkdir(parents=True, exist_ok=True)

    def test_cost_accumulates(self):
        provider = _mock_provider()
        provider.estimate_cost.return_value = 0.005
        enricher = LLMEnricher(provider, self.config)

        for i in range(3):
            chunk = _make_chunk(chunk_id=f"chunk_{i}", content=f"Unique content {i}")
            enricher.enrich_chunk(chunk)

        assert enricher.total_tokens == 450  # 150 * 3
        assert enricher.total_cost == pytest.approx(0.015)
        assert enricher.chunks_processed == 3
        assert enricher.chunks_cached == 0

    def test_cached_chunks_dont_add_cost(self):
        provider = _mock_provider()
        provider.estimate_cost.return_value = 0.005
        enricher = LLMEnricher(provider, self.config)
        chunk = _make_chunk()

        enricher.enrich_chunk(chunk)  # API call
        enricher.enrich_chunk(chunk)  # Cache hit

        assert enricher.total_tokens == 150  # Only one API call
        assert enricher.chunks_processed == 2
        assert enricher.chunks_cached == 1
