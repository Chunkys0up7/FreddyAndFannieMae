"""Track 2 — Freddie Mac PDF guide ingestion."""
from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Optional

import requests

from ..config import PipelineConfig
from ..models import Chunk, DocMeta, ParsedSection, SectionMeta
from ..processing.chunker import chunk_section
from ..processing.section_extractor import freddie_extract_from_text
from ..store.chroma_client import ChromaVectorStore
from ..store.state_store import StateStore


log = logging.getLogger(__name__)


def download_freddie_guide(cfg: PipelineConfig) -> tuple[Optional[Path], str]:
    log.info("Downloading Freddie Mac PDF: %s", cfg.freddie.pdf_url)
    resp = requests.get(cfg.freddie.pdf_url, stream=True, timeout=120)
    resp.raise_for_status()
    h = hashlib.sha256()
    tmp = Path(tempfile.mkstemp(suffix=".pdf")[1])
    with tmp.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                h.update(chunk)
                f.write(chunk)
    return tmp, h.hexdigest()


def parse_freddie_pdf(path: Path) -> list[ParsedSection]:
    """Extract per-page text with pdfplumber, fall back to pymupdf, then split into sections."""
    sections: list[ParsedSection] = []
    page_texts: list[tuple[int, str]] = []

    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                page_texts.append((page_num, text))
    except Exception as exc:  # pragma: no cover
        log.warning("pdfplumber failed: %s — falling back to pymupdf", exc)

    if not any(t.strip() for _, t in page_texts):
        try:
            import fitz  # pymupdf

            doc = fitz.open(str(path))
            page_texts = [(i + 1, doc[i].get_text() or "") for i in range(doc.page_count)]
            doc.close()
        except Exception as exc:  # pragma: no cover
            log.error("pymupdf also failed: %s", exc)
            return []

    full_text = "\n".join(t for _, t in page_texts)
    detected = freddie_extract_from_text(full_text)

    if detected:
        sections.extend(detected)
    else:
        log.warning("No section headings detected; falling back to per-page pseudo-sections")
        for page_num, text in page_texts:
            if text.strip():
                sections.append(
                    ParsedSection(
                        section_number=f"PAGE-{page_num}",
                        section_title=f"Page {page_num}",
                        text=text,
                        page_number=page_num,
                    )
                )

    log.info("Parsed Freddie PDF: %d pages, %d sections", len(page_texts), len(sections))
    return sections


def _to_chunks(sections: list[ParsedSection], cfg: PipelineConfig, source_url: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    doc_meta = DocMeta(agency="freddie", doc_type="guide", source_url=source_url)
    for s in sections:
        meta = SectionMeta(
            section_number=s.section_number,
            section_title=s.section_title,
            agency="freddie",
            source_url=source_url,
            page_number=s.page_number,
        )
        chunks.extend(chunk_section(s.text, meta, doc_meta, cfg.chunk))
    return chunks


def ingest_freddie_guide(
    cfg: PipelineConfig,
    store: ChromaVectorStore,
    state: StateStore,
    dry_run: bool = False,
) -> dict:
    path, sha = download_freddie_guide(cfg)
    if path is None:
        return {"agency": "freddie", "skipped": True, "reason": "download_failed"}

    if state.get_guide_hash("freddie") == sha:
        log.info("Freddie Mac PDF unchanged (SHA-256 match) — skipping parse")
        path.unlink(missing_ok=True)
        return {"agency": "freddie", "chunks": 0, "skipped": True}

    sections = parse_freddie_pdf(path)
    chunks = _to_chunks(sections, cfg, cfg.freddie.pdf_url)
    written = 0
    if not dry_run:
        written = store.upsert_chunks(chunks, cfg.chroma.freddie_collection)
        state.set_guide_hash("freddie", sha)
    path.unlink(missing_ok=True)
    return {
        "agency": "freddie",
        "sections": len(sections),
        "chunks": written,
        "dry_run": dry_run,
    }
