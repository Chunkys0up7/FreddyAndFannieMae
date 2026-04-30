"""Pure heuristic classifier (no LLM dependency) — extracted for unit testing."""
from __future__ import annotations

import re


_KEYWORDS_COMPARE = re.compile(
    r"\b(compare|vs\.?|versus|both|fannie\s+and\s+freddie|freddie\s+and\s+fannie|"
    r"differ|difference)\b",
    re.IGNORECASE,
)
_KEYWORDS_BULLETIN = re.compile(
    r"\b(bulletin|announcement|sel-\d|svc-\d|changed|update[sd]?|impact|what\s+changed)\b",
    re.IGNORECASE,
)


def heuristic_classify(message: str, has_bulletin: bool) -> str:
    if _KEYWORDS_COMPARE.search(message):
        return "compare"
    if has_bulletin or _KEYWORDS_BULLETIN.search(message):
        return "bulletin_impact"
    return "qa"
