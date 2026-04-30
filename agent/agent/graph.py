"""LangGraph StateGraph wiring the three reasoning nodes."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .config import AgentConfig, load_config
from .nodes.classify import classify
from .nodes.respond import respond
from .nodes.retrieve import retrieve
from .state import AgentState


def build_graph(cfg: AgentConfig | None = None):
    cfg = cfg or load_config()

    def _classify(state: AgentState) -> AgentState:
        return classify(state, cfg)

    def _retrieve(state: AgentState) -> AgentState:
        return retrieve(state, cfg)

    def _respond(state: AgentState) -> AgentState:
        return respond(state, cfg)

    graph = StateGraph(AgentState)
    graph.add_node("classify", _classify)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("respond", _respond)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "respond")
    graph.add_edge("respond", END)

    return graph.compile(checkpointer=MemorySaver())


graph = build_graph()
