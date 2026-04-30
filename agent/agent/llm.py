"""LLM provider factory: anthropic | openai."""
from __future__ import annotations

from functools import lru_cache

from .config import AgentConfig


@lru_cache(maxsize=4)
def get_llm(provider: str, anthropic_model: str, openai_model: str):
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=openai_model, temperature=0)
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=anthropic_model, temperature=0)


def llm_for(cfg: AgentConfig):
    return get_llm(cfg.llm_provider, cfg.anthropic_model, cfg.openai_model)
