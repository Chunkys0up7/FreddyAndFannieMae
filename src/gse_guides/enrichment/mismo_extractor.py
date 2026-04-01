"""Regex-based MISMO enumeration extraction from content."""

from __future__ import annotations

import re

from gse_guides.enrichment.taxonomy import MISMO_PATTERNS


class MismoExtractor:
    """Scans content for MISMO enumeration values using multi-word regex patterns."""

    def extract(self, content: str) -> dict[str, list[str]]:
        """Return dict of enum_name -> list of matched enum values."""
        results: dict[str, list[str]] = {}
        for enum_name, value_patterns in MISMO_PATTERNS.items():
            matched_values: list[str] = []
            for value_name, pattern in value_patterns.items():
                if re.search(pattern, content, re.IGNORECASE):
                    matched_values.append(value_name)
            if matched_values:
                results[enum_name] = sorted(matched_values)
        return results
