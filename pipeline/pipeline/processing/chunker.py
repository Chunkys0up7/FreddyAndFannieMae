"""Token-aware chunker producing deterministic Chunk IDs."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Optional

import tiktoken

from ..config import ChunkConfig
from ..models import Chunk, DocMeta, SectionMeta


@lru_cache(maxsize=4)
def _encoding(name: str):
    return tiktoken.get_encoding(name)


def _chunk_id(agency: str, section_number: str, chunk_index: int, doc_type: str,
              bulletin_id: Optional[str] = None) -> str:
    payload = f"{agency}::{doc_type}::{section_number}::{chunk_index}::{bulletin_id or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def chunk_text(
    text: str,
    section_meta: SectionMeta,
    doc_meta: DocMeta,
    cfg: ChunkConfig,
) -> list[Chunk]:
    """Split `text` into overlapping token windows; carry section metadata."""
    if not text or not text.strip():
        return []

    enc = _encoding(cfg.encoding_name)
    token_ids = enc.encode(text)
    chunks: list[Chunk] = []
    step = max(1, cfg.chunk_size - cfg.chunk_overlap)
    chunk_index = 0

    for start in range(0, len(token_ids), step):
        window = token_ids[start : start + cfg.chunk_size]
        if not window:
            break
        chunk_text_str = enc.decode(window)
        chunks.append(
            Chunk(
                id=_chunk_id(
                    section_meta.agency,
                    section_meta.section_number,
                    chunk_index,
                    doc_meta.doc_type,
                    doc_meta.bulletin_id,
                ),
                text=chunk_text_str,
                section_number=section_meta.section_number,
                section_title=section_meta.section_title,
                agency=section_meta.agency,
                doc_type=doc_meta.doc_type,
                source_url=doc_meta.source_url,
                chunk_index=chunk_index,
                page_number=section_meta.page_number,
                bulletin_id=doc_meta.bulletin_id,
            )
        )
        chunk_index += 1
        if start + cfg.chunk_size >= len(token_ids):
            break
    return chunks


def chunk_section(
    text: str,
    section_meta: SectionMeta,
    doc_meta: DocMeta,
    cfg: ChunkConfig,
) -> list[Chunk]:
    """Public alias matching the spec naming."""
    return chunk_text(text, section_meta, doc_meta, cfg)
