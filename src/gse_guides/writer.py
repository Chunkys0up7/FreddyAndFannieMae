"""Markdown file writer with YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from gse_guides import slugify
from gse_guides.config import ScraperConfig
from gse_guides.models import Chunk, GuideSection, GuideSource


class MarkdownWriter:
    """
    Writes GuideSection objects to markdown files with YAML frontmatter.

    File naming: {section_code}_{slug}.md
    Directory structure mirrors guide hierarchy.
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.output_dir = config.output_dir

    def write_section(self, section: GuideSection, chunks: list[Chunk]) -> Path:
        """Write a single section to a markdown file."""
        output_path = self._build_output_path(section)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        frontmatter = self._build_frontmatter(section, chunks)
        content = self._insert_chunk_markers(section.content_markdown, chunks)

        # Build the full file
        lines = [
            "---",
            frontmatter.rstrip(),
            "---",
            "",
            f"# {section.section_code}: {section.title}",
            "",
            content,
        ]

        # Add related announcements footer if present
        if section.related_announcements:
            lines.append("")
            lines.append("---")
            lines.append("")
            ann_strs = [
                f"{a.code} ({a.date})" if a.date else a.code
                for a in section.related_announcements
            ]
            lines.append(f"*Related Announcements: {', '.join(ann_strs)}*")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def _build_output_path(self, section: GuideSection) -> Path:
        """Determine file path from section hierarchy."""
        if section.source == GuideSource.FANNIE_MAE:
            part_dir = f"part_{section.part_code.lower()}"
            slug = slugify(section.title)
            filename = f"{section.section_code.lower()}_{slug}.md"
            return self.output_dir / "fannie_mae" / part_dir / filename

        else:  # FREDDIE_MAC
            chapter = section.chapter_code
            chapter_dir = f"chapter_{chapter}"
            slug = slugify(section.title)
            filename = f"{section.section_code}_{slug}.md"
            return self.output_dir / "freddie_mac" / chapter_dir / filename

    def _build_output_path_from_code(
        self, section_code: str, slug: str, source: GuideSource
    ) -> Path:
        """Build output path from just the section code (for skip checking)."""
        if source == GuideSource.FANNIE_MAE:
            part_letter = section_code[0].lower() if section_code else "x"
            part_dir = f"part_{part_letter}"
            filename_slug = slugify(slug) if slug else section_code.lower()
            filename = f"{section_code.lower()}_{filename_slug}.md"
            return self.output_dir / "fannie_mae" / part_dir / filename

        else:
            chapter = section_code.split(".")[0] if "." in section_code else section_code
            chapter_dir = f"chapter_{chapter}"
            filename_slug = slugify(slug) if slug else section_code
            filename = f"{section_code}_{filename_slug}.md"
            return self.output_dir / "freddie_mac" / chapter_dir / filename

    def _build_frontmatter(self, section: GuideSection, chunks: list[Chunk]) -> str:
        """Create YAML frontmatter block."""
        data = {
            "source": section.source.value,
            "section_code": section.section_code,
            "title": section.title,
            "url": section.url,
            "part": section.part_code,
            "part_name": section.part_name,
            "chapter": section.chapter_code,
            "chapter_name": section.chapter_name,
        }

        if section.subpart_code:
            data["subpart"] = section.subpart_code
        if section.subpart_name:
            data["subpart_name"] = section.subpart_name
        if section.effective_date:
            data["effective_date"] = section.effective_date

        data["word_count"] = section.word_count
        data["table_count"] = section.table_count

        if section.subsections:
            data["subsections"] = [s.heading for s in section.subsections]

        if section.cross_references:
            data["cross_references"] = list(
                {r.target_section_code for r in section.cross_references}
            )

        if section.related_announcements:
            data["related_announcements"] = [
                {"code": a.code, "date": a.date}
                for a in section.related_announcements
            ]

        if chunks:
            data["chunk_ids"] = [c.chunk_id for c in chunks]

        data["scraped_at"] = section.scraped_at

        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def _insert_chunk_markers(self, markdown: str, chunks: list[Chunk]) -> str:
        """Insert chunk markers at appropriate positions."""
        if not chunks:
            return markdown

        # Add section-level chunk marker at the top
        section_chunks = [c for c in chunks if c.chunk_type == "section"]
        subsection_chunks = [c for c in chunks if c.chunk_type == "subsection"]

        if section_chunks:
            marker = f"<!-- chunk: {section_chunks[0].chunk_id} -->"
            markdown = marker + "\n\n" + markdown

        # Add subsection chunk markers before their headings
        for chunk in subsection_chunks:
            heading = chunk.metadata.subsection_heading
            if heading:
                marker = f"<!-- chunk: {chunk.chunk_id} -->"
                # Find the heading in markdown and insert marker before it
                # Match ## or ### heading lines
                pattern = re.compile(
                    r"^(#{2,3}\s+" + re.escape(heading) + r")",
                    re.MULTILINE,
                )
                markdown = pattern.sub(marker + "\n" + r"\1", markdown, count=1)

        return markdown

