"""Agent shared state."""
from __future__ import annotations

from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    selected_bulletin: Optional[dict]
    current_section: Optional[str]
    review_status_map: Optional[dict]
    query_type: Optional[str]
    retrieved_sections: list[dict]
    bulletin_meta: Optional[dict]
    citations: list[dict]
    pending_action: Optional[dict]
    rendered_component: Optional[dict]
