"""LLM enrichment orchestrator — builds prompts, calls providers, caches results."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from tqdm import tqdm

from gse_guides.config import ScraperConfig
from gse_guides.models import (
    EnrichedChunk,
    LLMEnrichmentResult,
    NumericConstraint,
)
from gse_guides.enrichment.llm_cache import LLMCache
from gse_guides.enrichment.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class LLMEnricher:
    """Orchestrates LLM enrichment for enriched chunks."""

    PROMPT_VERSION = "1.0"

    SYSTEM_PROMPT = (
        "You are a mortgage underwriting expert analyzing GSE (Fannie Mae/Freddie Mac) "
        "guide sections. Extract structured metadata from the content provided. "
        "Respond ONLY with valid JSON matching the schema described in the user message. "
        "Do not include any text outside the JSON object."
    )

    USER_PROMPT_TEMPLATE = """\
Analyze this mortgage guide section and extract structured metadata.

SECTION: {section_code} - {title}
SOURCE: {source}
EXISTING ENTITIES (from rule-based extraction): {existing_entities}
EXISTING CONSTRAINTS: {existing_constraints}

CONTENT:
{content}

Respond with JSON matching this exact schema:
{{
  "summary": "1-2 sentence summary describing what this section REQUIRES (not just what it's about). Focus on who must do what.",
  "entities": {{
    "entity_type": ["Value1", "Value2"]
  }},
  "numeric_constraints": [
    {{
      "metric": "LTV|CLTV|HCLTV|DTI|credit_score|reserves_months|housing_expense_ratio",
      "operator": "<=|>=",
      "value": "80",
      "unit": "%|months|",
      "conditions": ["occupancy_types.Investment", "property_types.Condo"],
      "source_text": "exact text this was extracted from"
    }}
  ],
  "relationships": [
    {{
      "type": "REQUIRES|CONDITIONAL|EXCEPTION",
      "target_section": "B4-2.2-01",
      "condition": "when property is a condominium",
      "description": "brief explanation"
    }}
  ]
}}

Entity types to use: transaction_types, occupancy_types, property_types, loan_types, lien_positions, program_types, income_sources, asset_types, credit_events, project_types, valuation_types, documentation_types, aus_types.
Only include entities actually discussed in the content, not just mentioned in passing.
For numeric_constraints, extract ALL numeric thresholds (LTV, CLTV, DTI, credit scores, reserves) including from tables.
If a field has no values, use an empty object/array."""

    def __init__(self, provider: LLMProvider, config: ScraperConfig) -> None:
        self.provider = provider
        self.config = config
        self.cache = LLMCache(config.enriched_dir / ".llm_cache")
        self.total_tokens = 0
        self.total_cost = 0.0
        self.chunks_processed = 0
        self.chunks_cached = 0

    def enrich_chunk(self, chunk: EnrichedChunk) -> LLMEnrichmentResult:
        """Enhance a single chunk with LLM-generated metadata."""
        content_for_hash = chunk.content[:8000]  # Cap for hash stability

        # Check cache
        if self.config.llm_cache_enabled:
            cached = self.cache.get(
                content_for_hash,
                self.provider.model_name,
                self.PROMPT_VERSION,
            )
            if cached is not None:
                self.chunks_cached += 1
                self.chunks_processed += 1
                result = self._dict_to_result(cached)
                result.cached = True
                result.model = self.provider.model_name
                return result

        # Build prompt and call LLM
        prompt = self._build_prompt(chunk)
        try:
            response_text, tokens = self.provider.complete(
                prompt, system=self.SYSTEM_PROMPT
            )
        except Exception as e:
            logger.error(
                "LLM call failed for %s: %s", chunk.chunk_id, str(e)[:200]
            )
            self.chunks_processed += 1
            return LLMEnrichmentResult(model=self.provider.model_name)

        # Track tokens/cost
        self.total_tokens += tokens
        self.total_cost += self.provider.estimate_cost(
            tokens * 7 // 10,  # Rough input/output split: 70/30
            tokens * 3 // 10,
        )

        # Parse response
        parsed = self._parse_response(response_text)
        result = self._dict_to_result(parsed)
        result.model = self.provider.model_name
        result.tokens_used = tokens

        # Cache result
        if self.config.llm_cache_enabled:
            self.cache.set(
                content_for_hash,
                self.provider.model_name,
                self.PROMPT_VERSION,
                parsed,
                tokens_used=tokens,
            )

        self.chunks_processed += 1
        return result

    def enrich_batch(
        self,
        chunks: list[EnrichedChunk],
        progress: bool = True,
    ) -> list[LLMEnrichmentResult]:
        """Enrich multiple chunks with progress tracking and cost reporting."""
        # Respect max_chunks limit
        to_process = chunks
        if self.config.llm_max_chunks is not None:
            to_process = chunks[: self.config.llm_max_chunks]

        results: list[LLMEnrichmentResult] = []
        iterator = tqdm(to_process, desc="LLM enrichment") if progress else to_process

        for i, chunk in enumerate(iterator):
            result = self.enrich_chunk(chunk)
            results.append(result)

            # Log cost every 100 chunks
            if (i + 1) % 100 == 0:
                logger.info(
                    "LLM progress: %d/%d chunks, %d tokens, est. $%.2f",
                    i + 1,
                    len(to_process),
                    self.total_tokens,
                    self.total_cost,
                )

        # Pad with empty results if we limited processing
        while len(results) < len(chunks):
            results.append(LLMEnrichmentResult())

        logger.info(
            "LLM enrichment complete: %d chunks, %d cached, %d tokens, est. $%.2f",
            self.chunks_processed,
            self.chunks_cached,
            self.total_tokens,
            self.total_cost,
        )

        return results

    def dry_run(self, chunks: list[EnrichedChunk]) -> dict:
        """Estimate cost without calling the API."""
        to_process = chunks
        if self.config.llm_max_chunks is not None:
            to_process = chunks[: self.config.llm_max_chunks]

        cache_hits = 0
        cache_misses = 0
        total_input_tokens_est = 0

        for chunk in to_process:
            content_for_hash = chunk.content[:8000]
            if self.config.llm_cache_enabled:
                cached = self.cache.get(
                    content_for_hash,
                    self.provider.model_name,
                    self.PROMPT_VERSION,
                )
                if cached is not None:
                    cache_hits += 1
                    continue

            cache_misses += 1
            # Estimate tokens: ~1.3 tokens per word for English
            prompt = self._build_prompt(chunk)
            word_count = len(prompt.split())
            total_input_tokens_est += int(word_count * 1.3)

        # Estimate output tokens: ~300 per chunk
        output_tokens_est = cache_misses * 300
        est_cost = self.provider.estimate_cost(
            total_input_tokens_est, output_tokens_est
        )

        return {
            "total_chunks": len(to_process),
            "cache_hits": cache_hits,
            "chunks_to_process": cache_misses,
            "estimated_input_tokens": total_input_tokens_est,
            "estimated_output_tokens": output_tokens_est,
            "estimated_cost": round(est_cost, 4),
            "model": self.provider.model_name,
            "provider": type(self.provider).__name__,
        }

    def _build_prompt(self, chunk: EnrichedChunk) -> str:
        """Build the user prompt for a chunk."""
        # Format existing entities
        entity_str = "None"
        if chunk.entities:
            parts = [
                f"{k}: {', '.join(v)}" for k, v in chunk.entities.items()
            ]
            entity_str = "; ".join(parts)

        # Format existing constraints
        constraint_str = "None"
        if chunk.numeric_constraints:
            parts = [
                f"{c.metric}{c.operator}{c.value}{c.unit}"
                for c in chunk.numeric_constraints
            ]
            constraint_str = "; ".join(parts)

        # Truncate content to ~3000 words to keep within token limits
        content = chunk.content
        words = content.split()
        if len(words) > 3000:
            content = " ".join(words[:3000]) + "\n\n[Content truncated]"

        return self.USER_PROMPT_TEMPLATE.format(
            section_code=chunk.section_code,
            title=chunk.title,
            source=chunk.source.value,
            existing_entities=entity_str,
            existing_constraints=constraint_str,
            content=content,
        )

    def _parse_response(self, response: str) -> dict:
        """Parse LLM JSON response into structured dict."""
        text = response.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = text.index("\n") if "\n" in text else len(text)
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM response as JSON: %s", str(e)[:100])
            logger.debug("Raw response: %s", response[:500])
            return {}

        # Validate expected structure
        if not isinstance(data, dict):
            logger.warning("LLM response is not a JSON object")
            return {}

        # Normalize: ensure expected keys exist with correct types
        result = {
            "summary": str(data.get("summary", "")),
            "entities": {},
            "numeric_constraints": [],
            "relationships": [],
        }

        # Validate entities
        raw_entities = data.get("entities", {})
        if isinstance(raw_entities, dict):
            for k, v in raw_entities.items():
                if isinstance(v, list):
                    result["entities"][k] = [str(val) for val in v]

        # Validate constraints
        raw_constraints = data.get("numeric_constraints", [])
        if isinstance(raw_constraints, list):
            for c in raw_constraints:
                if isinstance(c, dict) and "metric" in c and "value" in c:
                    result["numeric_constraints"].append({
                        "metric": str(c.get("metric", "")),
                        "operator": str(c.get("operator", "<=")),
                        "value": str(c.get("value", "")),
                        "unit": str(c.get("unit", "%")),
                        "conditions": [
                            str(x) for x in c.get("conditions", [])
                            if isinstance(x, str)
                        ],
                        "source_text": str(c.get("source_text", "")),
                    })

        # Validate relationships
        raw_rels = data.get("relationships", [])
        if isinstance(raw_rels, list):
            for r in raw_rels:
                if isinstance(r, dict) and "type" in r:
                    result["relationships"].append({
                        "type": str(r.get("type", "")),
                        "target_section": str(r.get("target_section", "")),
                        "condition": str(r.get("condition", "")),
                        "description": str(r.get("description", "")),
                    })

        return result

    def _dict_to_result(self, data: dict) -> LLMEnrichmentResult:
        """Convert a parsed dict to LLMEnrichmentResult."""
        constraints = []
        for c in data.get("numeric_constraints", []):
            constraints.append(
                NumericConstraint(
                    metric=c.get("metric", ""),
                    operator=c.get("operator", "<="),
                    value=c.get("value", ""),
                    unit=c.get("unit", "%"),
                    conditions=c.get("conditions", []),
                    source_text=c.get("source_text", ""),
                )
            )

        return LLMEnrichmentResult(
            summary=data.get("summary", ""),
            entities=data.get("entities", {}),
            numeric_constraints=constraints,
            relationships=data.get("relationships", []),
        )
