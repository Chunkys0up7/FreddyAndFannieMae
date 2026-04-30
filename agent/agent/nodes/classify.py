"""Classify node: route to qa | bulletin_impact | compare."""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import AgentConfig
from ..llm import llm_for
from ..prompts.system import CLASSIFY_PROMPT
from ..state import AgentState
from .classify_heuristic import heuristic_classify as _heuristic


log = logging.getLogger(__name__)

_VALID = {"qa", "bulletin_impact", "compare"}


def classify(state: AgentState, cfg: AgentConfig) -> AgentState:
    messages = state.get("messages", [])
    if not messages:
        return {"query_type": "qa"}

    last = messages[-1]
    text = getattr(last, "content", "") if not isinstance(last, dict) else last.get("content", "")
    text = text or ""

    bulletin = state.get("selected_bulletin")
    section = state.get("current_section")

    # Fast heuristic first.
    label = _heuristic(text, bulletin is not None)

    # Defer to LLM for ambiguous short queries.
    if len(text.split()) > 4 and label == "qa" and (bulletin or "compare" in text.lower()):
        try:
            llm = llm_for(cfg)
            prompt = CLASSIFY_PROMPT.format(
                message=text, bulletin=bulletin, section=section
            )
            resp = llm.invoke([SystemMessage(content="Classifier."), HumanMessage(content=prompt)])
            content = (resp.content or "").strip().lower()
            if content in _VALID:
                label = content
        except Exception as exc:
            log.warning("Classifier LLM failed, using heuristic: %s", exc)

    log.info("Classified query as: %s", label)
    return {"query_type": label}
