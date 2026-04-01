"""Template-based summary generation with LLM interface placeholder."""

from __future__ import annotations


class Summarizer:
    """Generates 1-2 sentence summaries for guide sections."""

    def summarize(
        self,
        title: str,
        section_code: str,
        domains: list[str],
        key_terms: list[str],
    ) -> str:
        """Generate a template-based summary. No external API calls."""
        domain_readable = ", ".join(
            d.split(".")[-1].replace("_", " ") for d in domains[:3]
        )
        top_terms = ", ".join(key_terms[:5]) if key_terms else "general guidelines"

        summary = f"{section_code} ({title}) covers {domain_readable}."
        if top_terms:
            summary += f" Key topics: {top_terms}."

        if len(summary) > 200:
            summary = summary[:197] + "..."

        return summary

    def summarize_llm(self, content: str, section_code: str) -> str:
        """Generate an LLM-powered summary.

        NOT IMPLEMENTED in this environment. Configure an LLM provider
        (e.g., OpenAI, Anthropic) and implement this method to generate
        richer summaries from the full section content.

        Expected signature for implementation:
            - Call LLM with prompt: "Summarize this mortgage guideline section
              in 1-2 sentences for retrieval purposes: {content}"
            - Return the summary string
        """
        raise NotImplementedError(
            "LLM summaries are not enabled in this environment. "
            "Set enable_llm_summaries=True in config and implement "
            "the LLM provider integration in summarizer.py."
        )
