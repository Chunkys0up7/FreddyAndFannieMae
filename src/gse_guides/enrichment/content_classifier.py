"""Classify guide sections by content type."""

from __future__ import annotations

import re

from gse_guides.models import GuideSource
from gse_guides.enrichment.taxonomy import CONTENT_TYPE_SIGNALS


class ContentClassifier:
    """Classifies sections as policy_rule, definition, procedure, eligibility_matrix, or reference."""

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
