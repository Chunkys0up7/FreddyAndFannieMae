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

    def summarize_llm(
        self, content: str, section_code: str, provider=None,
    ) -> str:
        """Generate an LLM-powered summary.

        Args:
            content: The section content to summarize.
            section_code: The section code for context.
            provider: An LLMProvider instance. If None, raises NotImplementedError.

        Returns:
            A 1-2 sentence summary focused on requirements.
        """
        if provider is None:
            raise NotImplementedError(
                "LLM summaries require a provider. Use --llm flag or pass a provider."
            )

        prompt = (
            f"Summarize this mortgage guide section ({section_code}) in 1-2 sentences. "
            f"Focus on what the section REQUIRES, not just what it discusses.\n\n"
            f"{content[:4000]}"
        )
        system = (
            "You are a mortgage underwriting expert. "
            "Write concise summaries for retrieval-augmented generation."
        )
        text, _tokens = provider.complete(prompt, system=system)
        return text.strip()
