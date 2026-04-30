"""FastAPI server hosting the LangGraph agent + CopilotKit endpoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import load_config
from .graph import graph
from .tools.review_actions import (
    create_gap_note,
    flag_for_review,
    mark_reviewed,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
log = logging.getLogger(__name__)
cfg = load_config()
app = FastAPI(title="GSE Copilot Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": cfg.llm_provider}


# ---------------------------------------------------------------------------
# CopilotKit integration. We import lazily so a missing `copilotkit` dep does
# not break the rest of the agent during local pytest runs.
# ---------------------------------------------------------------------------
try:
    from copilotkit import CopilotKitRemoteEndpoint, LangGraphAgent
    from copilotkit.integrations.fastapi import add_fastapi_endpoint

    sdk = CopilotKitRemoteEndpoint(
        agents=[
            LangGraphAgent(
                name="gse_copilot",
                description="GSE guideline copilot — Q&A, comparison, bulletin impact.",
                graph=graph,
            )
        ]
    )
    add_fastapi_endpoint(app, sdk, "/copilotkit")
    log.info("CopilotKit endpoint mounted at /copilotkit")
except Exception as exc:  # pragma: no cover
    log.warning("CopilotKit SDK not available: %s — exposing /chat fallback only", exc)


# ---------------------------------------------------------------------------
# REST fallback for environments without CopilotKit.
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    selected_bulletin: dict | None = None
    current_section: str | None = None


@app.post("/chat")
def chat(req: ChatRequest):
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content=req.message)],
        "selected_bulletin": req.selected_bulletin,
        "current_section": req.current_section,
    }
    config = {"configurable": {"thread_id": "default"}}
    final = graph.invoke(state, config=config)
    last = final["messages"][-1] if final.get("messages") else None
    return {
        "response": getattr(last, "content", str(last)) if last else "",
        "query_type": final.get("query_type"),
        "citations": final.get("citations", []),
        "rendered_component": final.get("rendered_component"),
        "pending_action": final.get("pending_action"),
    }


# ---------------------------------------------------------------------------
# Action proxies (frontend can call these directly, or the agent can suggest them).
# ---------------------------------------------------------------------------
class FlagBody(BaseModel):
    section_number: str
    agency: str
    reason: str
    severity: str = "medium"
    reviewer: str | None = None


class ReviewedBody(BaseModel):
    section_number: str
    notes: str | None = None
    reviewer: str | None = None


class GapNoteBody(BaseModel):
    section_number: str
    agency: str
    current_sop: str
    change: str
    recommendation: str


@app.post("/actions/flag")
def action_flag(body: FlagBody):
    return flag_for_review(
        cfg, body.section_number, body.agency, body.reason, body.severity, body.reviewer
    )


@app.post("/actions/reviewed")
def action_reviewed(body: ReviewedBody):
    return mark_reviewed(cfg, body.section_number, body.notes, body.reviewer)


@app.post("/actions/gap-note")
def action_gap_note(body: GapNoteBody):
    return create_gap_note(
        cfg,
        body.section_number,
        body.agency,
        body.current_sop,
        body.change,
        body.recommendation,
    )
