"""Retrieve node: vector search + bulletin metadata, with progressive state emit."""
from __future__ import annotations

import logging

from ..config import AgentConfig
from ..state import AgentState
from ..tools.agency_compare import agency_compare
from ..tools.bulletin_lookup import get_bulletin
from ..tools.vector_search import vector_search


log = logging.getLogger(__name__)


def _get_user_text(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    return getattr(last, "content", "") if not isinstance(last, dict) else last.get("content", "")


def _emit(state_updates: dict) -> None:
    """Best-effort progressive state emit (CopilotKit AG-UI)."""
    try:
        from copilotkit.langgraph import copilotkit_emit_state

        copilotkit_emit_state(state_updates)
    except Exception:  # pragma: no cover
        pass


def retrieve(state: AgentState, cfg: AgentConfig) -> AgentState:
    text = _get_user_text(state)
    query_type = state.get("query_type", "qa")
    selected = state.get("selected_bulletin")

    updates: AgentState = {"retrieved_sections": [], "bulletin_meta": None, "citations": []}

    if query_type == "compare":
        _emit({"progress": "Searching both Fannie Mae and Freddie Mac…"})
        paired = agency_compare(cfg, text or "", top_k=3)
        flat = paired["fannie"] + paired["freddie"]
        updates["retrieved_sections"] = flat
        updates["citations"] = _citations(flat)
        updates["rendered_component"] = {
            "type": "comparison_table",
            "data": {"fannie": paired["fannie"], "freddie": paired["freddie"]},
        }
    elif query_type == "bulletin_impact":
        _emit({"progress": "Looking up bulletin metadata…"})
        bulletin_id = (selected or {}).get("id")
        bulletin_meta = get_bulletin(cfg, bulletin_id) if bulletin_id else None
        updates["bulletin_meta"] = bulletin_meta
        _emit({"progress": "Searching affected guide sections…"})
        sections = vector_search(cfg, text or bulletin_id or "", top_k=5, include_bulletins=True)
        updates["retrieved_sections"] = sections
        updates["citations"] = _citations(sections)
        if bulletin_meta:
            updates["rendered_component"] = {
                "type": "impact_summary",
                "data": {
                    "bulletin": bulletin_meta,
                    "sections": sections,
                },
            }
    else:  # qa
        _emit({"progress": "Searching guideline sections…"})
        sections = vector_search(cfg, text, top_k=5)
        updates["retrieved_sections"] = sections
        updates["citations"] = _citations(sections)

    log.info(
        "Retrieved %d sections for query_type=%s", len(updates["retrieved_sections"]), query_type
    )
    _emit({"progress": f"Found {len(updates['retrieved_sections'])} sections."})
    return updates


def _citations(sections: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for s in sections:
        meta = s.get("metadata", {})
        key = (meta.get("agency"), meta.get("section_number"))
        if key in seen or not all(key):
            continue
        seen.add(key)
        out.append(
            {
                "agency": meta.get("agency"),
                "section_number": meta.get("section_number"),
                "section_title": meta.get("section_title"),
                "source_url": meta.get("source_url"),
            }
        )
    return out
