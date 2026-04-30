"""Track 3 — Bulletin detection and ingestion (both agencies)."""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

import requests
from apify_client import ApifyClient

from ..config import PipelineConfig
from ..models import BulletinRef, Chunk, DocMeta, SectionMeta
from ..processing.chunker import chunk_section
from ..processing.section_extractor import freddie_extract_from_text
from ..store.chroma_client import ChromaVectorStore
from ..store.state_store import StateStore


log = logging.getLogger(__name__)


_FANNIE_BULLETIN_RE = re.compile(r"\b(SEL|SVC|LL|RVS)-\d{4}-\d{2}\b", re.IGNORECASE)
_FREDDIE_BULLETIN_RE = re.compile(r"\bBulletin\s+\d{4}-\d{1,2}\b", re.IGNORECASE)


def _crawl_pages(cfg: PipelineConfig, start_url: str, max_pages: int) -> list[dict]:
    if not cfg.apify_token:
        raise RuntimeError("APIFY_TOKEN not configured")
    client = ApifyClient(token=cfg.apify_token)
    run = client.actor(cfg.fannie.actor_id).call(
        run_input={
            "startUrls": [{"url": start_url}],
            "crawlerType": "cheerio",
            "maxCrawlDepth": 1,
            "maxCrawlPages": max_pages,
            "saveMarkdown": True,
            "saveHtml": False,
        }
    )
    return client.dataset(run["defaultDatasetId"]).list_items().items


def _extract_fannie_bulletins(items: list[dict]) -> list[BulletinRef]:
    refs: dict[str, BulletinRef] = {}
    for item in items:
        text = item.get("markdown") or item.get("text") or ""
        url = item.get("url", "")
        for match in _FANNIE_BULLETIN_RE.finditer(text):
            bid = match.group(0).upper()
            if bid not in refs:
                refs[bid] = BulletinRef(id=bid, agency="fannie", url=url)
    return list(refs.values())


def _extract_freddie_bulletins(items: list[dict]) -> list[BulletinRef]:
    refs: dict[str, BulletinRef] = {}
    for item in items:
        text = item.get("markdown") or item.get("text") or ""
        url = item.get("url", "")
        for match in _FREDDIE_BULLETIN_RE.finditer(text):
            bid = match.group(0)
            normalized = re.sub(r"\s+", " ", bid).strip()
            if normalized not in refs:
                refs[normalized] = BulletinRef(
                    id=normalized, agency="freddie", url=url
                )
    return list(refs.values())


def detect_new_bulletins(cfg: PipelineConfig, state: StateStore, agency: str) -> list[BulletinRef]:
    if agency == "fannie":
        items = _crawl_pages(
            cfg, cfg.fannie.bulletin_announcements_url, cfg.fannie.bulletin_max_pages
        )
        candidates = _extract_fannie_bulletins(items)
    elif agency == "freddie":
        items = _crawl_pages(cfg, cfg.freddie.bulletin_url, cfg.freddie.bulletin_max_pages)
        candidates = _extract_freddie_bulletins(items)
    else:
        raise ValueError(f"Unknown agency: {agency}")

    new_refs = [ref for ref in candidates if not state.has_bulletin(ref.id)]
    log.info(
        "Bulletin scan (%s): %d candidates, %d new", agency, len(candidates), len(new_refs)
    )
    return new_refs


def _download_pdf(url: str) -> Optional[Path]:
    if not url.lower().endswith(".pdf"):
        return None
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    tmp = Path(tempfile.mkstemp(suffix=".pdf")[1])
    with tmp.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return tmp


def ingest_bulletin(
    ref: BulletinRef,
    cfg: PipelineConfig,
    store: ChromaVectorStore,
    state: StateStore,
    dry_run: bool = False,
) -> dict:
    pdf_path = None
    text = ""
    try:
        pdf_path = _download_pdf(ref.url)
    except Exception as exc:  # pragma: no cover
        log.warning("PDF download failed for %s: %s", ref.url, exc)

    if pdf_path:
        try:
            import pdfplumber

            with pdfplumber.open(str(pdf_path)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as exc:
            log.warning("Bulletin PDF parse failed: %s", exc)
        finally:
            pdf_path.unlink(missing_ok=True)

    if not text.strip():
        # Treat as a metadata-only bulletin: index a stub chunk so the agent can find it.
        text = f"Bulletin {ref.id} ({ref.agency}). Source: {ref.url}"

    sections = freddie_extract_from_text(text) if ref.agency == "freddie" else []
    chunks: list[Chunk] = []
    doc_meta = DocMeta(
        agency=ref.agency,
        doc_type="bulletin",
        source_url=ref.url,
        bulletin_id=ref.id,
    )

    if sections:
        for s in sections:
            meta = SectionMeta(
                section_number=s.section_number,
                section_title=s.section_title,
                agency=ref.agency,
                source_url=ref.url,
            )
            chunks.extend(chunk_section(s.text, meta, doc_meta, cfg.chunk))
    else:
        meta = SectionMeta(
            section_number=ref.id,
            section_title=ref.title or ref.id,
            agency=ref.agency,
            source_url=ref.url,
        )
        chunks.extend(chunk_section(text, meta, doc_meta, cfg.chunk))

    written = 0
    if not dry_run:
        written = store.upsert_chunks(chunks, cfg.chroma.bulletins_collection)
        state.mark_bulletin(ref.id, ref.agency, ref.url, ref.title)

    return {"bulletin_id": ref.id, "chunks": written, "dry_run": dry_run}


def monitor_bulletins(
    cfg: PipelineConfig,
    store: ChromaVectorStore,
    state: StateStore,
    dry_run: bool = False,
) -> dict:
    summary: dict = {"new_bulletins": [], "errors": []}
    for agency in ("fannie", "freddie"):
        try:
            new_refs = detect_new_bulletins(cfg, state, agency)
            for ref in new_refs:
                result = ingest_bulletin(ref, cfg, store, state, dry_run=dry_run)
                summary["new_bulletins"].append(result)
        except Exception as exc:
            log.exception("Bulletin monitor failed for %s", agency)
            summary["errors"].append({"agency": agency, "error": str(exc)})
    return summary
