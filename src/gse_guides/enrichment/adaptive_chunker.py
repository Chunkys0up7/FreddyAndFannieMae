"""Content-type-aware adaptive chunking at the lowest heading level."""

from __future__ import annotations

import re
from dataclasses import dataclass

from gse_guides.config import ScraperConfig


@dataclass
class RawChunk:
    """An intermediate chunk before enrichment metadata is attached."""

    heading: str | None
    content: str
    word_count: int
    has_table: bool


class AdaptiveChunker:
    """
    Splits markdown content at the lowest heading level (H2/H3/H4) while
    keeping tables intact. Chunk size targets vary by content type.
    """

    def __init__(self, config: ScraperConfig) -> None:
        self.min_words = config.enrich_chunk_min_words
        self.max_words = config.enrich_chunk_max_words
        self.table_max = config.enrich_table_max_words

    def chunk(self, content_markdown: str, content_type: str) -> list[RawChunk]:
        """Split markdown into chunks appropriate for the content type."""
        if content_type == "definition":
            return self._chunk_definitions(content_markdown)

        # Default: heading-based splitting
        raw = self._split_by_headings(content_markdown)
        raw = self._split_oversized(raw)
        raw = self._merge_undersized(raw)
        return raw

    # --- Heading-based splitting ---

    def _split_by_headings(self, markdown: str) -> list[RawChunk]:
        """Split at H2, H3, and H4 boundaries."""
        # Pattern matches ## Heading, ### Heading, #### Heading at line start
        heading_pattern = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(markdown))

        if not matches:
            return [self._make_chunk(None, markdown)]

        chunks: list[RawChunk] = []

        # Intro text before first heading
        intro = markdown[: matches[0].start()].strip()
        if intro:
            chunks.append(self._make_chunk(None, intro))

        # Each heading + content until next heading
        for i, match in enumerate(matches):
            heading_text = match.group(2).strip()
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            content = markdown[start:end].strip()
            chunks.append(self._make_chunk(heading_text, content))

        return chunks

    # --- Definition-specific splitting ---

    def _chunk_definitions(self, markdown: str) -> list[RawChunk]:
        """Split glossary content at bold term patterns."""
        # Glossary entries typically start with a bold term on its own line
        # Pattern: **term** or __term__ at start of line, or a standalone bold line
        term_pattern = re.compile(
            r"^(?:\*\*(.+?)\*\*|__(.+?)__)\s*$", re.MULTILINE
        )
        matches = list(term_pattern.finditer(markdown))

        if not matches or len(matches) < 3:
            # Not enough structure; fall back to heading-based
            raw = self._split_by_headings(markdown)
            return self._merge_undersized(raw)

        chunks: list[RawChunk] = []

        # Intro before first term
        intro = markdown[: matches[0].start()].strip()
        if intro and len(intro.split()) > 10:
            chunks.append(self._make_chunk(None, intro))

        # Each term + definition until next term
        for i, match in enumerate(matches):
            term = match.group(1) or match.group(2)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            content = markdown[start:end].strip()
            chunks.append(self._make_chunk(term, content))

        return self._merge_undersized(chunks)

    # --- Oversized chunk splitting ---

    def _split_oversized(self, chunks: list[RawChunk]) -> list[RawChunk]:
        """Split chunks that exceed max_words at paragraph boundaries."""
        result: list[RawChunk] = []
        for chunk in chunks:
            max_w = self.table_max if chunk.has_table else self.max_words
            if chunk.word_count <= max_w:
                result.append(chunk)
                continue

            # Don't split tables
            if chunk.has_table:
                result.append(chunk)
                continue

            # Split at double newlines (paragraph boundaries)
            paragraphs = re.split(r"\n\n+", chunk.content)
            current_parts: list[str] = []
            current_words = 0

            for para in paragraphs:
                para_words = len(para.split())
                if current_words + para_words > self.max_words and current_parts:
                    result.append(self._make_chunk(
                        chunk.heading,
                        "\n\n".join(current_parts),
                    ))
                    current_parts = [para]
                    current_words = para_words
                else:
                    current_parts.append(para)
                    current_words += para_words

            if current_parts:
                result.append(self._make_chunk(
                    chunk.heading,
                    "\n\n".join(current_parts),
                ))

        return result

    # --- Undersized chunk merging ---

    def _merge_undersized(self, chunks: list[RawChunk]) -> list[RawChunk]:
        """Merge chunks below min_words with their neighbor."""
        if len(chunks) <= 1:
            return chunks

        merged: list[RawChunk] = []
        i = 0
        while i < len(chunks):
            current = chunks[i]
            # Merge forward while undersized
            while current.word_count < self.min_words and i + 1 < len(chunks):
                i += 1
                nxt = chunks[i]
                combined = current.content + "\n\n" + nxt.content
                current = self._make_chunk(current.heading, combined)

            merged.append(current)
            i += 1

        return merged

    # --- Utility ---

    def _make_chunk(self, heading: str | None, content: str) -> RawChunk:
        """Create a RawChunk with computed metadata."""
        content = content.strip()
        return RawChunk(
            heading=heading,
            content=content,
            word_count=len(content.split()),
            has_table=bool(re.search(r"\|.*\|.*\|", content)),
        )
