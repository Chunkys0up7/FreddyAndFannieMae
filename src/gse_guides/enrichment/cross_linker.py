"""Cross-source linking between Fannie Mae and Freddie Mac sections."""

from __future__ import annotations

from gse_guides.models import CrossSourceLink, GuideSource
from gse_guides.enrichment.taxonomy import CROSS_SOURCE_MAP


class CrossLinker:
    """Connects equivalent/related sections across GSE sources."""

    def __init__(self, all_section_codes: dict[str, list[str]] | None = None) -> None:
        """
        Args:
            all_section_codes: Optional map of source_name -> list of section codes,
                used to resolve Freddie Mac chapter ranges to actual section codes.
        """
        self._section_codes = all_section_codes or {}

    def link(self, section_code: str, source: GuideSource) -> list[CrossSourceLink]:
        """Return cross-source links for a given section."""
        if source == GuideSource.FANNIE_MAE:
            return self._link_fannie_to_freddie(section_code)
        return self._link_freddie_to_fannie(section_code)

    def _link_fannie_to_freddie(self, section_code: str) -> list[CrossSourceLink]:
        """Find Freddie Mac equivalents for a Fannie Mae section."""
        code_upper = section_code.upper()
        links: list[CrossSourceLink] = []

        for mapping in CROSS_SOURCE_MAP:
            prefix = mapping["fannie_prefix"].upper()
            if code_upper.startswith(prefix):
                start, end = mapping["freddie_range"]
                # Resolve to actual Freddie Mac section codes if available
                freddie_codes = self._resolve_freddie_range(start, end)
                if freddie_codes:
                    for fc in freddie_codes:
                        links.append(CrossSourceLink(
                            source="freddie_mac",
                            section_code=fc,
                            topic=mapping["topic"],
                            relationship=mapping["relationship"],
                        ))
                else:
                    # No resolved codes; use chapter range as reference
                    links.append(CrossSourceLink(
                        source="freddie_mac",
                        section_code=f"{start}-{end}",
                        topic=mapping["topic"],
                        relationship=mapping["relationship"],
                    ))

        return links

    def _link_freddie_to_fannie(self, section_code: str) -> list[CrossSourceLink]:
        """Find Fannie Mae equivalents for a Freddie Mac section."""
        parts = section_code.split(".")
        try:
            chapter = int(parts[0])
        except ValueError:
            return []

        links: list[CrossSourceLink] = []
        for mapping in CROSS_SOURCE_MAP:
            start, end = mapping["freddie_range"]
            if start <= chapter <= end:
                # Find all Fannie Mae sections matching the prefix
                fannie_codes = self._resolve_fannie_prefix(mapping["fannie_prefix"])
                if fannie_codes:
                    for fc in fannie_codes:
                        links.append(CrossSourceLink(
                            source="fannie_mae",
                            section_code=fc,
                            topic=mapping["topic"],
                            relationship=mapping["relationship"],
                        ))
                else:
                    links.append(CrossSourceLink(
                        source="fannie_mae",
                        section_code=mapping["fannie_prefix"],
                        topic=mapping["topic"],
                        relationship=mapping["relationship"],
                    ))

        return links

    def _resolve_freddie_range(self, start: int, end: int) -> list[str]:
        """Resolve a chapter range to actual section codes."""
        codes = self._section_codes.get("freddie_mac", [])
        result: list[str] = []
        for code in codes:
            parts = code.split(".")
            try:
                chapter = int(parts[0])
            except ValueError:
                continue
            if start <= chapter <= end:
                result.append(code)
        return result

    def _resolve_fannie_prefix(self, prefix: str) -> list[str]:
        """Resolve a Fannie Mae prefix to actual section codes."""
        codes = self._section_codes.get("fannie_mae", [])
        prefix_upper = prefix.upper()
        return [c for c in codes if c.upper().startswith(prefix_upper)]
