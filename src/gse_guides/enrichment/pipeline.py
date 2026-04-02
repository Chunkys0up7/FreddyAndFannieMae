"""Enrichment pipeline orchestrator."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import yaml
from tqdm import tqdm

from gse_guides import slugify
from gse_guides.config import ScraperConfig
from gse_guides.models import (
    EnrichedChunk,
    EnrichmentResult,
    GuideSource,
)
from gse_guides.enrichment.adaptive_chunker import AdaptiveChunker
from gse_guides.enrichment.content_classifier import ContentClassifier
from gse_guides.enrichment.cross_linker import CrossLinker
from gse_guides.enrichment.domain_tagger import DomainTagger
from gse_guides.enrichment.mismo_extractor import MismoExtractor
from gse_guides.enrichment.summarizer import Summarizer
from gse_guides.enrichment.term_extractor import TermExtractor
from gse_guides.enrichment.writer import EnrichmentWriter

logger = logging.getLogger(__name__)


class EnrichmentPipeline:
    """Reads scraped markdown, applies all enrichment steps, writes chunk files."""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.tagger = DomainTagger()
        self.mismo = MismoExtractor()
        self.terms = TermExtractor()
        self.classifier = ContentClassifier()
        self.summarizer = Summarizer()
        self.chunker = AdaptiveChunker(config)
        self.writer = EnrichmentWriter(config)

    def run(
        self, source: str | None = None, incremental: bool = False,
    ) -> EnrichmentResult:
        """Run enrichment on all scraped output files."""
        result = EnrichmentResult()
        all_chunks: list[EnrichedChunk] = []

        # Load previous state for incremental mode
        prev_hashes: dict[str, str] = {}
        new_hashes: dict[str, str] = {}
        if incremental:
            prev_hashes = self._load_state()

        # Discover all section codes for cross-linking resolution
        section_codes = self._discover_section_codes(source)
        self.linker = CrossLinker(section_codes)

        # Process each source
        sources_to_process = self._resolve_sources(source)
        for src_name, src_enum in sources_to_process:
            src_dir = self.config.output_dir / src_name
            if not src_dir.exists():
                logger.warning("Source directory not found: %s", src_dir)
                continue

            md_files = sorted(src_dir.rglob("*.md"))
            logger.info("Enriching %d files from %s", len(md_files), src_name)

            for md_path in tqdm(md_files, desc=f"Enriching {src_name}"):
                try:
                    # Incremental: skip unchanged files
                    if incremental:
                        content_bytes = md_path.read_bytes()
                        file_hash = hashlib.sha256(content_bytes).hexdigest()
                        file_key = str(md_path.relative_to(self.config.output_dir))
                        new_hashes[file_key] = file_hash

                        if prev_hashes.get(file_key) == file_hash:
                            continue  # Unchanged, skip

                    chunks = self._process_file(md_path, src_enum)
                    all_chunks.extend(chunks)
                    result.total_sections += 1
                except Exception as e:
                    result.errors.append(f"{md_path.name}: {e}")
                    logger.error("Failed to enrich %s: %s", md_path.name, e)

        result.total_chunks = len(all_chunks)

        # Compute stats
        if all_chunks:
            total_words = sum(c.word_count for c in all_chunks)
            result.avg_chunk_words = total_words // len(all_chunks)
            result.cross_source_link_count = sum(
                len(c.cross_source_links) for c in all_chunks
            )
            for chunk in all_chunks:
                for d in chunk.domains:
                    result.domain_distribution[d] = result.domain_distribution.get(d, 0) + 1
                result.content_type_distribution[chunk.content_type] = (
                    result.content_type_distribution.get(chunk.content_type, 0) + 1
                )

        # Write output
        if all_chunks:
            logger.info("Writing %d chunk files...", len(all_chunks))
            for chunk in all_chunks:
                self.writer.write_chunk(chunk)

            if incremental:
                # In incremental mode, rebuild index from all chunk files on disk
                existing_chunks = self._load_existing_chunks_for_index()
                # Merge: new chunks override existing for same chunk_id
                chunk_map = {c["chunk_id"]: c for c in existing_chunks}
                for chunk in all_chunks:
                    chunk_map[chunk.chunk_id] = None  # Will be written by write_index
                index_path = self.writer.write_index(all_chunks)
            else:
                index_path = self.writer.write_index(all_chunks)
            logger.info("Index written to %s", index_path)
        elif not incremental:
            # Non-incremental with no chunks: write empty index
            index_path = self.writer.write_index(all_chunks)
            logger.info("Index written to %s", index_path)
        else:
            logger.info("No files changed — skipping index rebuild")

        # Save state for incremental mode
        if incremental:
            # Merge new hashes with previous (keep unchanged files)
            merged_hashes = {**prev_hashes, **new_hashes}
            self._save_state(merged_hashes)

        return result

    def _process_file(
        self, md_path: Path, source: GuideSource
    ) -> list[EnrichedChunk]:
        """Process a single scraped markdown file into enriched chunks."""
        text = md_path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_frontmatter(text)

        section_code = frontmatter.get("section_code", "")
        title = frontmatter.get("title", "")
        has_tables = frontmatter.get("table_count", 0) > 0
        effective_date = frontmatter.get("effective_date")
        url = frontmatter.get("url", "")
        hierarchy_path = self._build_hierarchy(frontmatter)

        # Step 1: Classify content type
        content_type = self.classifier.classify(
            section_code, title, body, has_tables, source
        )

        # Step 2: Tag domains (at section level — propagates to all chunks)
        domains = self.tagger.tag(section_code, source, body)

        # Step 3: Extract MISMO enums from full section
        mismo_section = self.mismo.extract(body)

        # Step 4: Get cross-source links (section level)
        cross_links = self.linker.link(section_code, source)

        # Step 5: Run adaptive chunker
        raw_chunks = self.chunker.chunk(body, content_type)

        # Step 6: Build enriched chunks
        enriched: list[EnrichedChunk] = []
        for i, raw in enumerate(raw_chunks):
            # Extract per-chunk terms and MISMO (more precise than section-level)
            chunk_terms = self.terms.extract(raw.content)
            chunk_mismo = self.mismo.extract(raw.content)
            # Merge section-level MISMO with chunk-level
            merged_mismo = {**mismo_section}
            for k, v in chunk_mismo.items():
                if k in merged_mismo:
                    merged_mismo[k] = sorted(set(merged_mismo[k] + v))
                else:
                    merged_mismo[k] = v

            # Generate summary (only for first chunk / section intro)
            summary = self.summarizer.summarize(
                title, section_code, domains, chunk_terms,
            ) if i == 0 else ""

            heading_slug = slugify(raw.heading) if raw.heading else "intro"
            chunk_id = f"{source.value}/{section_code}/{heading_slug}"
            if i > 0 and not raw.heading:
                chunk_id = f"{source.value}/{section_code}/part-{i + 1}"

            enriched.append(EnrichedChunk(
                chunk_id=chunk_id,
                source=source,
                section_code=section_code,
                title=title,
                heading=raw.heading,
                domains=domains,
                mismo_tags=merged_mismo,
                key_terms=chunk_terms,
                content_type=content_type,
                summary=summary,
                cross_source_links=cross_links,
                word_count=raw.word_count,
                has_table=raw.has_table,
                effective_date=effective_date,
                url=url,
                hierarchy_path=hierarchy_path,
                content=raw.content,
            ))

        return enriched

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        """Parse YAML frontmatter and body from a markdown file."""
        if not text.startswith("---"):
            return {}, text

        try:
            end = text.index("---", 3)
        except ValueError:
            logger.warning("Malformed frontmatter: no closing delimiter")
            return {}, text

        fm_text = text[3:end]
        body = text[end + 3:].strip()
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError as e:
            logger.warning("YAML parse failed: %s", e)
            fm = {}
        return fm, body

    def _build_hierarchy(self, fm: dict) -> str:
        """Build hierarchy path from frontmatter."""
        parts: list[str] = []
        if fm.get("part_name"):
            parts.append(fm["part_name"])
        if fm.get("chapter_name"):
            parts.append(fm["chapter_name"])
        elif fm.get("chapter"):
            parts.append(f"Chapter {fm['chapter']}")
        if fm.get("subpart_name"):
            parts.append(fm["subpart_name"])
        if fm.get("section_code"):
            parts.append(fm["section_code"])
        return " > ".join(parts)

    def _discover_section_codes(self, source: str | None) -> dict[str, list[str]]:
        """Scan output directories to collect all section codes per source."""
        codes: dict[str, list[str]] = {"fannie_mae": [], "freddie_mac": []}
        for src_name in codes:
            if source and src_name != source.replace("-", "_"):
                continue
            src_dir = self.config.output_dir / src_name
            if not src_dir.exists():
                continue
            for md_path in src_dir.rglob("*.md"):
                text = md_path.read_text(encoding="utf-8")
                if text.startswith("---"):
                    try:
                        end = text.index("---", 3)
                        fm = yaml.safe_load(text[3:end]) or {}
                        code = fm.get("section_code", "")
                        if code:
                            codes[src_name].append(code)
                    except (yaml.YAMLError, ValueError):
                        pass
        return codes

    def _resolve_sources(
        self, source: str | None
    ) -> list[tuple[str, GuideSource]]:
        """Map CLI source arg to (dir_name, GuideSource) pairs."""
        all_sources = [
            ("fannie_mae", GuideSource.FANNIE_MAE),
            ("freddie_mac", GuideSource.FREDDIE_MAC),
        ]
        if not source:
            return all_sources
        normalized = source.replace("-", "_")
        return [(name, gs) for name, gs in all_sources if name == normalized]

    # --- Incremental state management ---

    def _state_path(self) -> Path:
        return self.config.enriched_dir / "state.json"

    def _load_state(self) -> dict[str, str]:
        """Load previous enrichment state (file hashes)."""
        path = self._state_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return data.get("file_hashes", {})
            except (json.JSONDecodeError, KeyError):
                logger.warning("Corrupt state.json, starting fresh")
        return {}

    def _save_state(self, file_hashes: dict[str, str]) -> None:
        """Save enrichment state for incremental runs."""
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"file_hashes": file_hashes}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_existing_chunks_for_index(self) -> list[dict]:
        """Load existing index entries for incremental merge."""
        index_path = self.config.enriched_dir / "index.json"
        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                return data.get("chunks", [])
            except (json.JSONDecodeError, KeyError):
                pass
        return []
