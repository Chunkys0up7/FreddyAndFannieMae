"""Builds the ontology knowledge graph from enriched chunks."""

from __future__ import annotations

from gse_guides.models import EnrichedChunk
from gse_guides.enrichment.taxonomy import ENTITY_TYPES, IMPLICATION_RULES


class RelationshipBuilder:
    """Builds the ontology knowledge graph from enriched chunks."""

    def build(self, chunks: list[EnrichedChunk]) -> dict:
        """Build the full ontology graph from all enriched chunks.

        Returns a dict with:
          - entity_types: formal entity vocabulary with value lists
          - edges: list of edge dicts (type, source, target, metadata)
          - sections_by_entity: entity_value -> [chunk_ids] reverse index
          - implication_rules: static rules from taxonomy
          - numeric_constraints: aggregated constraints with source sections
        """
        edges: list[dict] = []

        # Layer 1: APPLIES_TO edges (chunk -> entity)
        edges.extend(self._build_applies_to_edges(chunks))

        # Layer 2: REQUIRES edges (cross-references)
        edges.extend(self._build_requires_edges(chunks))

        # Layer 3: IMPLIES edges (static rules)
        edges.extend(self._build_implication_edges())

        # Layer 4: CONSTRAINS edges (entity -> numeric constraint)
        edges.extend(self._build_constrains_edges(chunks))

        # Layer 5: EQUIVALENT edges (cross-source links)
        edges.extend(self._build_equivalent_edges(chunks))

        # Build reverse index
        sections_by_entity = self._build_sections_by_entity(chunks)

        # Aggregate constraints
        aggregated_constraints = self._aggregate_constraints(chunks)

        # Build entity type vocabulary for output
        entity_type_vocab = self._build_entity_type_vocab()

        return {
            "version": "1.0",
            "entity_types": entity_type_vocab,
            "edges": edges,
            "sections_by_entity": sections_by_entity,
            "implication_rules": [
                {
                    "if": r["if_entity"],
                    "then": r["then_type"],
                    "target": r["then_target"],
                    "description": r["description"],
                }
                for r in IMPLICATION_RULES
            ],
            "numeric_constraints": aggregated_constraints,
            "stats": {
                "total_edges": len(edges),
                "total_entity_values": sum(
                    len(vals) for vals in sections_by_entity.values()
                ),
                "total_constraints": len(aggregated_constraints),
            },
        }

    def _build_applies_to_edges(self, chunks: list[EnrichedChunk]) -> list[dict]:
        """For each chunk, create edges from chunk_id to each entity value found."""
        edges: list[dict] = []
        for chunk in chunks:
            for etype, values in chunk.entities.items():
                for val in values:
                    edges.append({
                        "type": "APPLIES_TO",
                        "source": chunk.chunk_id,
                        "target": f"{etype}.{val}",
                    })
        return edges

    def _build_requires_edges(self, chunks: list[EnrichedChunk]) -> list[dict]:
        """Create edges from cross-references and conditional refs."""
        edges: list[dict] = []
        for chunk in chunks:
            # From conditional refs
            for ref in chunk.conditional_refs:
                edges.append({
                    "type": "CONDITIONAL",
                    "source": chunk.chunk_id,
                    "target": ref.get("then_see", ""),
                    "metadata": {"if_entity": ref.get("if_entity", "")},
                })
        return edges

    def _build_implication_edges(self) -> list[dict]:
        """Create edges from static IMPLICATION_RULES."""
        edges: list[dict] = []
        for rule in IMPLICATION_RULES:
            target = rule["then_target"]
            # Serialize dict targets (numeric constraints) to string
            if isinstance(target, dict):
                target_str = f"{target.get('metric', '')} {target.get('op', '')} {target.get('value', '')}"
            else:
                target_str = str(target)

            edges.append({
                "type": "IMPLIES",
                "source": rule["if_entity"],
                "target": target_str,
                "metadata": {
                    "relationship": rule["then_type"],
                    "description": rule["description"],
                },
            })
        return edges

    def _build_constrains_edges(self, chunks: list[EnrichedChunk]) -> list[dict]:
        """Create CONSTRAINS edges from numeric constraints with entity conditions."""
        edges: list[dict] = []
        for chunk in chunks:
            for constraint in chunk.numeric_constraints:
                for condition in constraint.conditions:
                    edges.append({
                        "type": "CONSTRAINS",
                        "source": condition,
                        "target": f"{constraint.metric} {constraint.operator} {constraint.value}{constraint.unit}",
                        "metadata": {
                            "chunk_id": chunk.chunk_id,
                            "source_text": constraint.source_text,
                        },
                    })
        return edges

    def _build_equivalent_edges(self, chunks: list[EnrichedChunk]) -> list[dict]:
        """Create EQUIVALENT edges from existing cross-source links."""
        edges: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for chunk in chunks:
            for link in chunk.cross_source_links:
                edge_key = (chunk.section_code, link.section_code)
                reverse_key = (link.section_code, chunk.section_code)
                if edge_key in seen or reverse_key in seen:
                    continue
                seen.add(edge_key)

                edges.append({
                    "type": "EQUIVALENT",
                    "source": f"{chunk.source.value}/{chunk.section_code}",
                    "target": f"{link.source}/{link.section_code}",
                    "metadata": {
                        "topic": link.topic,
                        "relationship": link.relationship,
                    },
                })
        return edges

    def _build_sections_by_entity(
        self, chunks: list[EnrichedChunk]
    ) -> dict[str, list[str]]:
        """Reverse index: entity_value -> [chunk_ids that discuss it]."""
        index: dict[str, list[str]] = {}
        for chunk in chunks:
            for etype, values in chunk.entities.items():
                for val in values:
                    key = f"{etype}.{val}"
                    if key not in index:
                        index[key] = []
                    if chunk.chunk_id not in index[key]:
                        index[key].append(chunk.chunk_id)
        return dict(sorted(index.items()))

    def _aggregate_constraints(self, chunks: list[EnrichedChunk]) -> list[dict]:
        """Collect all numeric constraints, deduplicate, and add source sections."""
        constraint_map: dict[tuple, dict] = {}

        for chunk in chunks:
            for c in chunk.numeric_constraints:
                key = (c.metric, c.operator, c.value, c.unit)
                if key not in constraint_map:
                    constraint_map[key] = {
                        "metric": c.metric,
                        "operator": c.operator,
                        "value": c.value,
                        "unit": c.unit,
                        "conditions": [],
                        "source_sections": [],
                    }
                entry = constraint_map[key]
                if chunk.section_code not in entry["source_sections"]:
                    entry["source_sections"].append(chunk.section_code)
                for cond in c.conditions:
                    if cond not in entry["conditions"]:
                        entry["conditions"].append(cond)

        return sorted(
            constraint_map.values(),
            key=lambda x: (x["metric"], x["value"]),
        )

    def _build_entity_type_vocab(self) -> dict:
        """Build entity type vocabulary for ontology output."""
        vocab: dict[str, dict] = {}
        for etype, values in ENTITY_TYPES.items():
            vocab[etype] = {
                "values": sorted(values.keys()),
                "count": len(values),
            }
        return vocab
