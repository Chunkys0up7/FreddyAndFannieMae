"""Structured entity extraction from guide content."""

from __future__ import annotations

import re

from gse_guides.models import NumericConstraint
from gse_guides.enrichment.taxonomy import (
    ENTITY_TYPES,
    NUMERIC_CONSTRAINT_PATTERNS,
    CONSTRAINT_METRICS,
)


class EntityExtractor:
    """Extracts typed entity values from content using formalized patterns."""

    def __init__(self) -> None:
        # Pre-compile all entity patterns at init time for performance
        self._compiled: dict[str, dict[str, list[re.Pattern]]] = {}
        for etype, values in ENTITY_TYPES.items():
            self._compiled[etype] = {}
            for vname, vdef in values.items():
                self._compiled[etype][vname] = [
                    re.compile(p, re.IGNORECASE) for p in vdef["patterns"]
                ]

        # Pre-compile metric pattern for constraint context tagging
        self._metric_re = re.compile(
            "|".join(
                re.escape(m) if " " not in m else m.replace(" ", r"\s+")
                for m in CONSTRAINT_METRICS
            ),
            re.IGNORECASE,
        )

        # Conditional reference patterns
        self._cond_ref_patterns = [
            re.compile(
                r"(?:if|when|where)\s+(?:the\s+)?(?:property|propert(?:y|ies))\s+(?:is|are)\s+(?:a\s+)?(\w[\w\s-]{2,30}),?\s+(?:see|refer\s+to|review)\s+(?:Section\s+)?([A-Z0-9][\w.-]+)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:for|regarding)\s+(\w[\w\s-]{2,30})\s+(?:properties|loans|transactions),?\s+(?:see|refer\s+to|review)\s+(?:Section\s+)?([A-Z0-9][\w.-]+)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:see|refer\s+to)\s+(?:Section\s+)?([A-Z0-9][\w.-]+)\s+for\s+(?:additional\s+)?(?:requirements?|guidance|information)\s+(?:on|about|regarding|for)\s+(\w[\w\s-]{2,30})",
                re.IGNORECASE,
            ),
        ]

    def extract_entities(self, content: str) -> dict[str, list[str]]:
        """Return {entity_type: [matched_values]} for all entity types.

        Empty types are omitted from the result.
        """
        if not content:
            return {}

        result: dict[str, list[str]] = {}
        for etype, values in self._compiled.items():
            matched: list[str] = []
            for vname, patterns in values.items():
                for pat in patterns:
                    if pat.search(content):
                        matched.append(vname)
                        break  # One pattern match is enough per value
            if matched:
                result[etype] = sorted(set(matched))
        return result

    def extract_constraints(
        self, content: str, entity_context: dict[str, list[str]]
    ) -> list[NumericConstraint]:
        """Extract numeric constraints, tagged with entity context.

        Args:
            content: The text to scan for constraints.
            entity_context: Entity values found in this content (from extract_entities),
                used to tag constraints with their applicable conditions.
        """
        if not content:
            return []

        constraints: list[NumericConstraint] = []
        seen: set[tuple[str, str, str]] = set()  # Dedupe by (metric, op, value)

        for pattern in NUMERIC_CONSTRAINT_PATTERNS:
            for match in pattern.finditer(content):
                # Extract the numeric value from the first capture group
                value = match.group(1) if match.lastindex else None
                if not value:
                    continue

                # Determine which metric was matched
                metric = self._identify_metric(match.group(0))
                if not metric:
                    continue

                # Determine operator from context
                full_text = match.group(0).lower()
                operator = self._infer_operator(full_text, metric)

                # Determine unit
                unit = self._infer_unit(metric, full_text)

                # Deduplicate
                dedup_key = (metric, operator, value)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Build condition list from entity context
                conditions = self._build_conditions(
                    content, match.start(), entity_context
                )

                constraints.append(NumericConstraint(
                    metric=metric,
                    operator=operator,
                    value=value,
                    unit=unit,
                    conditions=conditions,
                    source_text=match.group(0).strip(),
                ))

        return constraints

    def extract_conditional_refs(
        self, content: str, section_code: str
    ) -> list[dict]:
        """Detect 'if [entity], then see [section]' patterns.

        Returns list of dicts: [{if_entity: str, then_see: str}]
        """
        if not content:
            return []

        refs: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for pattern in self._cond_ref_patterns:
            for match in pattern.finditer(content):
                groups = match.groups()
                if len(groups) < 2:
                    continue

                # Patterns 1 & 2: (entity_text, section_code)
                # Pattern 3: (section_code, entity_text) — reversed
                if pattern == self._cond_ref_patterns[2]:
                    ref_section = groups[0]
                    entity_text = groups[1]
                else:
                    entity_text = groups[0]
                    ref_section = groups[1]

                entity_text = entity_text.strip().rstrip(".,;:")
                ref_section = ref_section.strip().rstrip(".,;:")

                # Skip self-references
                if ref_section == section_code:
                    continue

                dedup_key = (entity_text, ref_section)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Try to map entity_text to a known entity value
                entity_value = self._resolve_entity(entity_text)

                refs.append({
                    "if_entity": entity_value or entity_text,
                    "then_see": ref_section,
                })

        return refs

    def _identify_metric(self, match_text: str) -> str:
        """Identify which metric was matched in the text."""
        text_lower = match_text.lower()

        # Check specific metrics in order of specificity
        metric_map = [
            ("hcltv", "HCLTV"),
            ("cltv", "CLTV"),
            ("ltv", "LTV"),
            ("loan-to-value", "LTV"),
            ("combined loan-to-value", "CLTV"),
            ("dti", "DTI"),
            ("debt-to-income", "DTI"),
            ("housing expense", "housing_expense_ratio"),
            ("credit score", "credit_score"),
            ("fico", "credit_score"),
            ("reserves", "reserves_months"),
        ]

        for keyword, metric in metric_map:
            if keyword in text_lower:
                return metric

        return ""

    def _infer_operator(self, text: str, metric: str) -> str:
        """Infer the comparison operator from surrounding text."""
        if any(w in text for w in ("maximum", "not exceed", "or less", "limited to", "no more than")):
            return "<="
        if any(w in text for w in ("minimum", "at least", "no less than")):
            return ">="
        # Default based on metric type
        if metric in ("LTV", "CLTV", "HCLTV", "DTI", "housing_expense_ratio"):
            return "<="  # These are typically caps
        if metric in ("credit_score",):
            return ">="  # Credit scores are typically floors
        return "<="

    def _infer_unit(self, metric: str, text: str) -> str:
        """Determine the unit for a constraint."""
        if metric == "reserves_months":
            return "months"
        if metric == "credit_score":
            return ""
        if "%" in text:
            return "%"
        return "%"

    def _build_conditions(
        self, content: str, match_pos: int, entity_context: dict[str, list[str]]
    ) -> list[str]:
        """Extract condition context for a constraint.

        Looks at the surrounding paragraph for entity values that scope
        this constraint (e.g., "for investment properties, maximum LTV is 85%").
        """
        # Get the surrounding context (~300 chars before and after)
        start = max(0, match_pos - 300)
        end = min(len(content), match_pos + 300)
        context = content[start:end]

        conditions: list[str] = []
        for etype, values in entity_context.items():
            for val in values:
                # Check if entity value appears in the local context
                val_info = ENTITY_TYPES.get(etype, {}).get(val, {})
                for alias in val_info.get("aliases", []):
                    if alias.lower() in context.lower():
                        conditions.append(f"{etype}.{val}")
                        break

        return sorted(set(conditions))

    def _resolve_entity(self, text: str) -> str | None:
        """Try to map a free-text entity mention to a canonical entity value."""
        text_lower = text.lower().strip()
        for etype, values in self._compiled.items():
            for vname, patterns in values.items():
                for pat in patterns:
                    if pat.search(text_lower):
                        return f"{etype}.{vname}"
        return None
