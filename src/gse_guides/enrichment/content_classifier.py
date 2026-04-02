"""Classify guide sections by content type."""

from __future__ import annotations

import re

from gse_guides.models import GuideSource, RequirementMeta
from gse_guides.enrichment.taxonomy import (
    CONTENT_TYPE_SIGNALS,
    SEVERITY_SIGNALS,
    REQUIREMENT_TYPE_SIGNALS,
)


class ContentClassifier:
    """Classifies sections as policy_rule, definition, procedure, eligibility_matrix, or reference.

    Also classifies requirement severity (must_comply, should_comply, best_practice, info_only)
    and requirement type (eligibility, documentation, calculation, guideline).
    """

    # Severity levels in order of strength (strongest first)
    _SEVERITY_ORDER = ["must_comply", "should_comply", "best_practice", "info_only"]

    def __init__(self) -> None:
        # Pre-compile severity patterns
        self._severity_compiled: dict[str, list[re.Pattern]] = {}
        for level, patterns in SEVERITY_SIGNALS.items():
            self._severity_compiled[level] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        # Pre-compile requirement type patterns
        self._req_type_compiled: dict[str, list[re.Pattern]] = {}
        for rtype, patterns in REQUIREMENT_TYPE_SIGNALS.items():
            self._req_type_compiled[rtype] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def classify_severity(self, content: str) -> RequirementMeta:
        """Classify requirement type and severity from content signals.

        Severity is determined by the strongest signal found — a section with
        both "must" and "should" gets must_comply because the strictest
        constraint governs.

        Returns RequirementMeta with matched signals for transparency.
        """
        if not content:
            return RequirementMeta()

        # Count matches per severity level and track signal phrases
        severity_counts: dict[str, int] = {}
        severity_signals_found: list[str] = []

        for level, patterns in self._severity_compiled.items():
            count = 0
            for pat in patterns:
                matches = pat.findall(content)
                if matches:
                    count += len(matches)
                    # Track first occurrence of each pattern
                    severity_signals_found.append(f"{level}:{pat.pattern}")
            if count > 0:
                severity_counts[level] = count

        # Determine severity: strongest level with matches wins
        severity = "info_only"
        for level in self._SEVERITY_ORDER:
            if level in severity_counts:
                severity = level
                break

        # Determine requirement type: most specific match wins
        req_type = "guideline"
        best_count = 0
        for rtype, patterns in self._req_type_compiled.items():
            count = sum(1 for p in patterns if p.search(content))
            if count > best_count:
                best_count = count
                req_type = rtype

        return RequirementMeta(
            requirement_type=req_type,
            severity=severity,
            severity_signals=severity_signals_found[:10],  # Cap at 10 for readability
        )

    def classify(
        self,
        section_code: str,
        title: str,
        content: str,
        has_tables: bool,
        source: GuideSource,
    ) -> str:
        """Return the content type string for a section."""
        code_upper = section_code.upper()
        title_lower = title.lower()
        content_sample = content[:3000].lower()  # Scan first 3k chars

        # Deterministic overrides
        if source == GuideSource.FANNIE_MAE:
            if code_upper.startswith("E-3"):
                return "definition"
            if code_upper.startswith("E-1") or code_upper.startswith("E-2"):
                return "reference"

        # Signal-based classification
        for content_type, patterns in CONTENT_TYPE_SIGNALS.items():
            for pattern in patterns:
                if re.search(pattern, title_lower) or re.search(pattern, content_sample):
                    return content_type

        # Heuristic: tables + eligibility-related title
        if has_tables and any(w in title_lower for w in ("eligib", "requirement", "limit", "matrix")):
            return "eligibility_matrix"

        # Heuristic: numbered steps suggest a procedure
        if re.search(r"(?:^|\n)\s*(?:step\s+)?\d+\.\s+\w", content_sample):
            step_count = len(re.findall(r"(?:^|\n)\s*\d+\.\s+\w", content_sample))
            if step_count >= 3:
                return "procedure"

        return "policy_rule"
