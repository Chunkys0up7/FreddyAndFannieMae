"""Rule-based domain tagging for guide sections."""

from __future__ import annotations

from gse_guides.models import GuideSource
from gse_guides.enrichment.taxonomy import (
    FANNIE_DOMAIN_MAP,
    FREDDIE_DOMAIN_MAP,
)


class DomainTagger:
    """Tags sections with domains using section-code mapping + keyword scanning."""

    def tag(self, section_code: str, source: GuideSource, content: str) -> list[str]:
        """Return a list of domain tags for a section."""
        domains = self._match_by_code(section_code, source)
        if not domains:
            domains = self._match_by_keywords(content)
        if not domains:
            domains = ["COMPLIANCE.regulatory"]  # Safe fallback
        return sorted(set(domains))

    def _match_by_code(self, section_code: str, source: GuideSource) -> list[str]:
        """Deterministic mapping from section code prefix."""
        if source == GuideSource.FANNIE_MAE:
            return self._match_fannie(section_code)
        return self._match_freddie(section_code)

    def _match_fannie(self, section_code: str) -> list[str]:
        """Longest-prefix match against FANNIE_DOMAIN_MAP."""
        code = section_code.upper()
        best_match: list[str] = []
        best_len = 0
        for prefix, domains in FANNIE_DOMAIN_MAP.items():
            if code.startswith(prefix.upper()) and len(prefix) > best_len:
                best_match = domains
                best_len = len(prefix)
        return list(best_match)

    def _match_freddie(self, section_code: str) -> list[str]:
        """Range match against FREDDIE_DOMAIN_MAP."""
        parts = section_code.split(".")
        try:
            chapter = int(parts[0])
        except ValueError:
            return []
        for start, end, domains in FREDDIE_DOMAIN_MAP:
            if start <= chapter <= end:
                return list(domains)
        return []

    def _match_by_keywords(self, content: str) -> list[str]:
        """Scan content for domain-indicating keywords as fallback."""
        content_lower = content.lower()
        matches: list[str] = []

        keyword_map = {
            "BORROWER.borrower_income": ["income", "employment", "self-employed", "w-2", "tax return"],
            "BORROWER.borrower_assets": ["asset", "reserves", "gift funds", "deposit"],
            "BORROWER.borrower_credit": ["credit score", "credit report", "fico", "derogatory"],
            "BORROWER.borrower_liabilities": ["debt-to-income", "dti", "liability", "monthly obligation"],
            "PROPERTY.property_valuation": ["appraisal", "appraised value", "comparable"],
            "PROPERTY.property_insurance": ["hazard insurance", "flood insurance", "mortgage insurance"],
            "LOAN.loan_purpose": ["purchase transaction", "refinance", "cash-out"],
            "UNDERWRITING.du_automated": ["desktop underwriter", "du finding", "automated underwriting"],
        }

        for domain, keywords in keyword_map.items():
            if any(kw in content_lower for kw in keywords):
                matches.append(domain)

        return matches
