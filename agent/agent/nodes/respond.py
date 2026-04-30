"""Respond node: generate cited response, propose actions, render component."""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..config import AgentConfig
from ..llm import llm_for
from ..prompts.system import SYSTEM_PROMPT
from ..state import AgentState


log = logging.getLogger(__name__)


def _format_sections(sections: list[dict]) -> str:
    lines = []
    for s in sections:
        meta = s.get("metadata", {})
        lines.append(
            f"[{meta.get('agency')}] {meta.get('section_number')} — {meta.get('section_title')}\n"
            f"{(s.get('text') or '')[:600].strip()}"
        )
    return "\n\n---\n\n".join(lines) if lines else "(no sections retrieved)"


def respond(state: AgentState, cfg: AgentConfig) -> AgentState:
    messages = state.get("messages", [])
    retrieved = state.get("retrieved_sections", [])
    citations = state.get("citations", [])
    rendered = state.get("rendered_component")
    query_type = state.get("query_type", "qa")
    bulletin_meta = state.get("bulletin_meta")

    user_text = ""
    if messages:
        last = messages[-1]
        user_text = (
            getattr(last, "content", "")
            if not isinstance(last, dict)
            else last.get("content", "")
        )

    prompt_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Retrieved guideline sections:\n\n{_format_sections(retrieved)}\n\n"
                f"User query: {user_text}\n\n"
                f"Query type: {query_type}\n"
                + (f"Bulletin: {bulletin_meta}\n" if bulletin_meta else "")
                + "\nRespond per the system prompt rules. Conclude with a 'Citations:' "
                "line listing each cited section."
            )
        ),
    ]

    try:
        llm = llm_for(cfg)
        ai = llm.invoke(prompt_messages)
        content = ai.content if hasattr(ai, "content") else str(ai)
    except Exception as exc:  # pragma: no cover
        log.exception("LLM invocation failed")
        content = (
            "I couldn't reach the language model right now. Retrieved sections "
            f"({len(retrieved)}) — please retry."
        )

    pending_action = None
    if query_type == "bulletin_impact" and bulletin_meta:
        pending_action = {
            "type": "flag_for_qi_review",
            "label": "Flag for QI review",
            "section_number": (citations[0]["section_number"] if citations else None),
            "agency": bulletin_meta.get("agency") if bulletin_meta else None,
            "reason": f"Affected by {bulletin_meta.get('id') if bulletin_meta else 'bulletin'}",
        }

    return {
        "messages": [AIMessage(content=content)],
        "pending_action": pending_action,
        "rendered_component": rendered,
    }
