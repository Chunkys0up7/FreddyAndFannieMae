"""Semantic chunking logic for guide sections."""

from __future__ import annotations

from gse_guides import slugify
from gse_guides.config import ScraperConfig
from gse_guides.models import Chunk, ChunkMetadata, GuideSection, SubSection


class SemanticChunker:
    """
    Creates semantic chunks from GuideSection objects.

    Dual-level strategy:
    1. Section-level: entire section as one chunk (always created)
    2. Subsection-level: split at H2/H3 headings when section > threshold

    Rules:
    - Never split mid-table or mid-list
    - Minimum chunk size: config.min_chunk_words
    - Maximum chunk size: config.max_chunk_words
    - Subsection chunks include parent context
    """

    def __init__(self, config: ScraperConfig):
        self.config = config

    def chunk_section(self, section: GuideSection) -> list[Chunk]:
        """Create chunks from a parsed section."""
        chunks: list[Chunk] = []

        # Always create a section-level chunk
        section_chunk = self._create_section_chunk(section)
        chunks.append(section_chunk)

        # Create subsection chunks if warranted
        if self._should_split(section):
            merged = self._merge_small_subsections(section.subsections)
            for sub in merged:
                sub_chunk = self._create_subsection_chunk(section, sub)
                chunks.append(sub_chunk)

        return chunks

    def _should_split(self, section: GuideSection) -> bool:
        """Determine if section needs subsection-level chunking."""
        return (
            self.config.subsection_chunk_enabled
            and section.word_count > self.config.max_chunk_words
            and len(section.subsections) > 1
        )

    def _create_section_chunk(self, section: GuideSection) -> Chunk:
        """Create a section-level chunk."""
        chunk_id = f"{section.source.value}/{section.section_code}"
        hierarchy_path = self._build_hierarchy_path(section)

        metadata = ChunkMetadata(
            chunk_id=chunk_id,
            source=section.source,
            section_code=section.section_code,
            subsection_heading=None,
            title=section.title,
            hierarchy_path=hierarchy_path,
            word_count=section.word_count,
            has_tables=section.has_tables,
            effective_date=section.effective_date,
            url=section.url,
        )

        return Chunk(
            chunk_id=chunk_id,
            metadata=metadata,
            content=section.content_markdown,
            parent_section_code=section.section_code,
            chunk_type="section",
        )

    def _create_subsection_chunk(
        self, section: GuideSection, sub: SubSection
    ) -> Chunk:
        """Create a subsection-level chunk with parent context."""
        slug = self._slugify_heading(sub.heading)
        chunk_id = f"{section.source.value}/{section.section_code}/{slug}"

        hierarchy_path = self._build_hierarchy_path(section)
        hierarchy_path += f" > {sub.heading}"

        # Add context prefix
        context = self._build_context_prefix(section, sub)
        content = context + sub.content_markdown

        metadata = ChunkMetadata(
            chunk_id=chunk_id,
            source=section.source,
            section_code=section.section_code,
            subsection_heading=sub.heading,
            title=f"{section.section_code}: {sub.heading}",
            hierarchy_path=hierarchy_path,
            word_count=sub.word_count,
            has_tables=sub.has_tables,
            effective_date=section.effective_date,
            url=section.url,
        )

        return Chunk(
            chunk_id=chunk_id,
            metadata=metadata,
            content=content,
            parent_section_code=section.section_code,
            chunk_type="subsection",
        )

    def _merge_small_subsections(
        self, subsections: list[SubSection]
    ) -> list[SubSection]:
        """Merge consecutive subsections that are too small to stand alone."""
        if not subsections:
            return []

        merged: list[SubSection] = []
        current = subsections[0]

        for next_sub in subsections[1:]:
            if current.word_count < self.config.min_chunk_words:
                # Merge into current
                current = SubSection(
                    heading=current.heading,
                    heading_level=current.heading_level,
                    anchor_id=current.anchor_id,
                    content_html=current.content_html + next_sub.content_html,
                    content_markdown=(
                        current.content_markdown
                        + f"\n\n## {next_sub.heading}\n\n"
                        + next_sub.content_markdown
                    ),
                    word_count=current.word_count + next_sub.word_count,
                    has_tables=current.has_tables or next_sub.has_tables,
                    has_lists=current.has_lists or next_sub.has_lists,
                )
            else:
                merged.append(current)
                current = next_sub

        merged.append(current)
        return merged

    def _build_hierarchy_path(self, section: GuideSection) -> str:
        """Build human-readable hierarchy path."""
        parts = []
        if section.part_name:
            parts.append(section.part_name)
        if section.chapter_name:
            parts.append(section.chapter_name)
        elif section.chapter_code:
            parts.append(f"Chapter {section.chapter_code}")
        if section.subpart_name:
            parts.append(section.subpart_name)
        elif section.subpart_code:
            parts.append(f"Section {section.subpart_code}")
        parts.append(section.section_code)
        return " > ".join(parts)

    def _build_context_prefix(
        self, section: GuideSection, sub: SubSection
    ) -> str:
        """Create context header for subsection chunks."""
        return (
            f"*Section: {section.section_code} - {section.title}*\n"
            f"*Subsection: {sub.heading}*\n\n"
        )

    @staticmethod
    def _slugify_heading(heading: str) -> str:
        """Convert heading text to slug for chunk IDs."""
        return slugify(heading)
