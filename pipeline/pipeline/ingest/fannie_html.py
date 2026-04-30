"""Track 1 — Fannie Mae HTML guide ingestion via Apify."""
from __future__ import annotations

import hashlib
import logging
from typing import Iterable

from apify_client import ApifyClient

from ..config import PipelineConfig
from ..models import Chunk, DocMeta, FanniePage
from ..processing.chunker import chunk_section
from ..processing.section_extractor import fannie_extract_from_url
from ..store.chroma_client import ChromaVectorStore
from ..store.state_store import StateStore


log = logging.getLogger(__name__)


def crawl_fannie_guide(cfg: PipelineConfig) -> list[FanniePage]:
    """Run the Apify Website Content Crawler against the Fannie Mae guide."""
    if not cfg.apify_token:
        raise RuntimeError("APIFY_TOKEN not configured")

    client = ApifyClient(token=cfg.apify_token)
    log.info("Starting Apify crawl: %s", cfg.fannie.start_url)
    run = client.actor(cfg.fannie.actor_id).call(
        run_input={
            "startUrls": [{"url": cfg.fannie.start_url}],
            "crawlerType": cfg.fannie.crawler_type,
            "maxCrawlDepth": cfg.fannie.max_crawl_depth,
            "maxCrawlPages": cfg.fannie.max_crawl_pages,
            "includeUrlGlobs": [{"glob": g} for g in cfg.fannie.include_globs],
            "saveMarkdown": True,
            "saveHtml": False,
        }
    )
    dataset_id = run["defaultDatasetId"]
    items = client.dataset(dataset_id).list_items().items
    log.info("Apify returned %d pages", len(items))

    pages: list[FanniePage] = []
    for item in items:
        url = item.get("url")
        markdown = item.get("markdown") or item.get("text") or ""
        title = (item.get("metadata") or {}).get("title")
        if not url or not markdown:
            continue
        pages.append(FanniePage(url=url, markdown=markdown, title=title))
    return pages


def process_fannie_dataset(
    pages: Iterable[FanniePage], cfg: PipelineConfig
) -> list[Chunk]:
    """Convert Markdown pages → typed chunks with section metadata."""
    chunks: list[Chunk] = []
    skipped = 0
    for page in pages:
        section_meta = fannie_extract_from_url(page.url)
        if not section_meta:
            skipped += 1
            continue
        if page.title:
            section_meta = section_meta.__class__(
                section_number=section_meta.section_number,
                section_title=page.title,
                agency=section_meta.agency,
                source_url=section_meta.source_url,
            )
        doc_meta = DocMeta(
            agency="fannie",
            doc_type="guide",
            source_url=page.url,
        )
        chunks.extend(chunk_section(page.markdown, section_meta, doc_meta, cfg.chunk))
    log.info(
        "Processed %d pages → %d chunks (%d skipped: no section in URL)",
        len(list(pages)) if not isinstance(pages, list) else len(pages),
        len(chunks),
        skipped,
    )
    return chunks


def _guide_hash(pages: list[FanniePage]) -> str:
    h = hashlib.sha256()
    for p in sorted(pages, key=lambda x: x.url):
        h.update(p.url.encode())
        h.update(b"\x00")
        h.update(hashlib.sha256(p.markdown.encode("utf-8")).digest())
    return h.hexdigest()


def ingest_fannie_guide(
    cfg: PipelineConfig,
    store: ChromaVectorStore,
    state: StateStore,
    dry_run: bool = False,
) -> dict:
    pages = crawl_fannie_guide(cfg)
    new_hash = _guide_hash(pages)
    if state.get_guide_hash("fannie") == new_hash:
        log.info("Fannie Mae guide unchanged (hash match) — skipping upsert")
        return {"agency": "fannie", "pages": len(pages), "chunks": 0, "skipped": True}

    chunks = process_fannie_dataset(pages, cfg)
    written = 0
    if not dry_run:
        written = store.upsert_chunks(chunks, cfg.chroma.fannie_collection)
        state.set_guide_hash("fannie", new_hash)
    return {
        "agency": "fannie",
        "pages": len(pages),
        "chunks": written,
        "dry_run": dry_run,
    }
