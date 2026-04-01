"""Writes enriched chunk .txt files and master index.json."""

from __future__ import annotations

import json
from pathlib import Path

from gse_guides import slugify
from gse_guides.config import ScraperConfig
from gse_guides.models import EnrichedChunk


class EnrichmentWriter:
    """Writes chunk text files with metadata headers and a master index."""

    def __init__(self, config: ScraperConfig) -> None:
        self.output_dir = config.enriched_dir

    def write_chunk(self, chunk: EnrichedChunk) -> Path:
        """Write a single chunk to a .txt file with metadata header."""
        chunks_dir = self.output_dir / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        heading_slug = slugify(chunk.heading) if chunk.heading else "intro"
        filename = f"{chunk.source.value}__{chunk.section_code}__{heading_slug}.txt"
        filepath = chunks_dir / filename

        # Avoid collisions by appending a counter
        if filepath.exists():
            counter = 2
            while filepath.exists():
                filename = f"{chunk.source.value}__{chunk.section_code}__{heading_slug}_{counter}.txt"
                filepath = chunks_dir / filename
                counter += 1

        header = self._build_header(chunk)
        filepath.write_text(header + chunk.content, encoding="utf-8")
        return filepath

    def write_index(self, chunks: list[EnrichedChunk]) -> Path:
        """Write the master index.json with metadata for every chunk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.output_dir / "index.json"

        entries = []
        for chunk in chunks:
            entries.append({
                "chunk_id": chunk.chunk_id,
                "source": chunk.source.value,
                "section_code": chunk.section_code,
                "title": chunk.title,
                "heading": chunk.heading,
                "domains": chunk.domains,
                "mismo_tags": chunk.mismo_tags,
                "key_terms": chunk.key_terms,
                "content_type": chunk.content_type,
                "summary": chunk.summary,
                "cross_source_links": [
                    {"source": l.source, "section_code": l.section_code,
                     "topic": l.topic, "relationship": l.relationship}
                    for l in chunk.cross_source_links
                ],
                "word_count": chunk.word_count,
                "has_table": chunk.has_table,
                "effective_date": chunk.effective_date,
                "url": chunk.url,
                "hierarchy_path": chunk.hierarchy_path,
            })

        # Build domain distribution
        domain_dist: dict[str, int] = {}
        for chunk in chunks:
            for d in chunk.domains:
                domain_dist[d] = domain_dist.get(d, 0) + 1

        content_dist: dict[str, int] = {}
        for chunk in chunks:
            content_dist[chunk.content_type] = content_dist.get(chunk.content_type, 0) + 1

        index = {
            "version": "1.0",
            "total_chunks": len(chunks),
            "domain_distribution": dict(sorted(domain_dist.items(), key=lambda x: -x[1])),
            "content_type_distribution": content_dist,
            "chunks": entries,
        }

        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        return index_path

    def _build_header(self, chunk: EnrichedChunk) -> str:
        """Build the YAML-like metadata header for a chunk file."""
        lines = [
            f"Source: {chunk.source.value}",
            f"Section: {chunk.section_code} - {chunk.title}",
        ]

        if chunk.heading:
            lines.append(f"Subsection: {chunk.heading}")

        lines.append(f"Domains: {', '.join(chunk.domains)}")

        if chunk.mismo_tags:
            mismo_parts = []
            for enum_name, values in chunk.mismo_tags.items():
                mismo_parts.append(f"{enum_name}({', '.join(values)})")
            lines.append(f"MISMO: {'; '.join(mismo_parts)}")

        if chunk.key_terms:
            lines.append(f"Key Terms: {', '.join(chunk.key_terms[:15])}")

        if chunk.cross_source_links:
            link_strs = [
                f"{l.source}/{l.section_code}" for l in chunk.cross_source_links[:5]
            ]
            lines.append(f"Cross-Source: {', '.join(link_strs)}")

        lines.append(f"Content Type: {chunk.content_type}")

        if chunk.summary:
            lines.append(f"Summary: {chunk.summary}")

        lines.append("---")
        lines.append("")

        return "\n".join(lines)
