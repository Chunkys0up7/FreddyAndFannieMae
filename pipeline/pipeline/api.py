"""Lightweight REST API exposing state + review stores to the frontend."""
from __future__ import annotations

import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import load_config
from .store.chroma_client import ChromaVectorStore
from .store.review_store import ReviewStore
from .store.state_store import StateStore


log = logging.getLogger(__name__)
cfg = load_config()
app = FastAPI(title="GSE Copilot Pipeline API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

state = StateStore(cfg.sqlite_path)
reviews = ReviewStore(cfg.sqlite_path)
vector = ChromaVectorStore(cfg.chroma, cfg.embedding)


class FlagRequest(BaseModel):
    section_number: str
    agency: str
    reason: str
    severity: str = "medium"
    reviewer: Optional[str] = None


class ReviewedRequest(BaseModel):
    section_number: str
    notes: Optional[str] = None
    reviewer: Optional[str] = None


class GapNoteRequest(BaseModel):
    section_number: str
    agency: str
    current_sop: str
    change: str
    recommendation: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/bulletins")
def list_bulletins(agency: Optional[str] = None, days: int = 90):
    bulletins = state.list_recent_bulletins(agency=agency, days=days)
    return [
        {
            "id": b.id,
            "agency": b.agency,
            "url": b.url,
            "title": b.title,
            "published": b.published,
            "discovered_at": b.discovered_at,
            "status": reviews.get_review_status(b.id).status,
        }
        for b in bulletins
    ]


@app.get("/bulletins/{bulletin_id}")
def get_bulletin(bulletin_id: str):
    bulletin = state.get_bulletin(bulletin_id)
    if not bulletin:
        raise HTTPException(404, "Bulletin not found")
    return {
        "id": bulletin.id,
        "agency": bulletin.agency,
        "url": bulletin.url,
        "title": bulletin.title,
        "published": bulletin.published,
        "discovered_at": bulletin.discovered_at,
    }


@app.get("/sections/search")
def search_sections(q: str, agency: Optional[str] = None, top_k: int = 5):
    if agency == "fannie":
        col = cfg.chroma.fannie_collection
    elif agency == "freddie":
        col = cfg.chroma.freddie_collection
    else:
        # Search both — return blended top_k.
        a = vector.search(q, cfg.chroma.fannie_collection, top_k=top_k)
        b = vector.search(q, cfg.chroma.freddie_collection, top_k=top_k)
        merged = sorted(a + b, key=lambda r: r.distance)[:top_k]
        return [{"id": r.id, "text": r.text, "metadata": r.metadata, "distance": r.distance} for r in merged]
    results = vector.search(q, col, top_k=top_k, agency=agency)
    return [{"id": r.id, "text": r.text, "metadata": r.metadata, "distance": r.distance} for r in results]


@app.get("/reviews")
def list_reviews(agency: Optional[str] = None):
    flags = reviews.list_flags(agency=agency)
    return [
        {
            "id": f.id,
            "section_number": f.section_number,
            "agency": f.agency,
            "reason": f.reason,
            "severity": f.severity,
            "reviewer": f.reviewer,
            "flagged_at": f.flagged_at,
            "status": f.status,
        }
        for f in flags
    ]


@app.get("/reviews/status/{section_number}")
def review_status(section_number: str):
    status = reviews.get_review_status(section_number)
    return {
        "section_number": status.section_number,
        "status": status.status,
        "notes": status.notes,
        "reviewer": status.reviewer,
        "updated_at": status.updated_at,
    }


@app.post("/reviews/flag")
def flag_section(req: FlagRequest):
    flag_id = reviews.flag_section(
        req.section_number, req.agency, req.reason, req.severity, req.reviewer
    )
    return {"id": flag_id, "section_number": req.section_number, "status": "flagged"}


@app.post("/reviews/mark-reviewed")
def mark_reviewed(req: ReviewedRequest):
    reviews.mark_reviewed(req.section_number, req.notes, req.reviewer)
    return {"section_number": req.section_number, "status": "reviewed"}


@app.post("/reviews/gap-note")
def gap_note(req: GapNoteRequest):
    note_id = reviews.create_gap_note(
        req.section_number, req.agency, req.current_sop, req.change, req.recommendation
    )
    return {"id": note_id, "section_number": req.section_number}


@app.get("/reviews/gap-notes")
def list_gap_notes(section_number: Optional[str] = None):
    notes = reviews.list_gap_notes(section_number=section_number)
    return [
        {
            "id": n.id,
            "section_number": n.section_number,
            "agency": n.agency,
            "current_sop": n.current_sop,
            "change": n.change,
            "recommendation": n.recommendation,
            "created_at": n.created_at,
        }
        for n in notes
    ]


@app.get("/stats")
def stats():
    return {
        "fannie_chunks": vector.count(cfg.chroma.fannie_collection),
        "freddie_chunks": vector.count(cfg.chroma.freddie_collection),
        "bulletin_chunks": vector.count(cfg.chroma.bulletins_collection),
        "bulletins": len(state.list_recent_bulletins(days=3650)),
        "review_flags": len(reviews.list_flags()),
    }


def run() -> None:
    uvicorn.run(
        "pipeline.api:app",
        host="0.0.0.0",
        port=cfg.api_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
