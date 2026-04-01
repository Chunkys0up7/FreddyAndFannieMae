"""GSE Guide Scraper - Extract Fannie Mae & Freddie Mac lending guidelines."""

from __future__ import annotations

import re


def slugify(text: str, max_length: int = 60) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    text = text.strip("-")
    return text[:max_length]
