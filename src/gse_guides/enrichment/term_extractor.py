"""Key mortgage term extraction from content."""

from __future__ import annotations

import re

from gse_guides.enrichment.taxonomy import MORTGAGE_TERMS

# Pre-compile case-insensitive patterns for each term.
# Use word boundaries for short terms to avoid false matches.
_TERM_PATTERNS: list[tuple[str, re.Pattern[str]]] = []
for _term in MORTGAGE_TERMS:
    if len(_term) <= 4:
        _TERM_PATTERNS.append((_term, re.compile(r"\b" + re.escape(_term) + r"\b", re.IGNORECASE)))
    else:
        _TERM_PATTERNS.append((_term, re.compile(re.escape(_term), re.IGNORECASE)))


class TermExtractor:
    """Scans content for domain-specific mortgage terms."""

    def extract(self, content: str) -> list[str]:
        """Return deduplicated list of terms found in content."""
        found: list[str] = []
        for term, pattern in _TERM_PATTERNS:
            if pattern.search(content):
                found.append(term)
        return found
