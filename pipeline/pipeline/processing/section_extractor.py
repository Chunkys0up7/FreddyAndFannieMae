"""Section metadata extraction for both agencies."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from ..models import ParsedSection, SectionMeta


_FANNIE_URL_RE = re.compile(r"^/sel/([a-z]\d[\w\.\-]*)/(.+?)/?$", re.IGNORECASE)


def fannie_extract_from_url(url: str) -> Optional[SectionMeta]:
    """Parse `/sel/b3-4.3-04/personal-gifts` → SectionMeta('B3-4.3-04', 'Personal Gifts')."""
    path = urlparse(url).path
    match = _FANNIE_URL_RE.match(path)
    if not match:
        return None
    section_number = match.group(1).upper()
    slug = match.group(2)
    title = " ".join(part.capitalize() for part in slug.replace("/", "-").split("-"))
    return SectionMeta(
        section_number=section_number,
        section_title=title,
        agency="fannie",
        source_url=url,
    )


_FREDDIE_PATTERNS = [
    # 1101.1, 3201.2.a, 5103.5
    re.compile(r"^\s*(\d{4}\.\d+(?:\.[\w]+)?)\s+(.{3,})$"),
    # Section 3201.2 — Title
    re.compile(r"^\s*Section\s+(\d{4}\.\d+(?:\.[\w]+)?)\s*[—\-:]\s*(.+)$", re.IGNORECASE),
    # Chapter 11 — Title
    re.compile(r"^\s*Chapter\s+(\d+)\s*[—\-:]\s*(.+)$", re.IGNORECASE),
]


def freddie_extract_from_text(text: str) -> list[ParsedSection]:
    """Detect Freddie Mac section headings in extracted PDF text.

    Falls back to a single pseudo-section per page if nothing matches.
    """
    sections: list[ParsedSection] = []
    current_number: Optional[str] = None
    current_title: Optional[str] = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            current_lines.append(line)
            continue

        matched = None
        for pattern in _FREDDIE_PATTERNS:
            m = pattern.match(line)
            if m:
                matched = m
                break

        if matched:
            if current_number and current_lines:
                sections.append(
                    ParsedSection(
                        section_number=current_number,
                        section_title=current_title or "",
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_number = matched.group(1)
            current_title = matched.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_number and current_lines:
        sections.append(
            ParsedSection(
                section_number=current_number,
                section_title=current_title or "",
                text="\n".join(current_lines).strip(),
            )
        )

    return sections
