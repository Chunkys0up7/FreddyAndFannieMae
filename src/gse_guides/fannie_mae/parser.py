"""Fannie Mae Selling Guide HTML parser."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from gse_guides.markdown_converter import MarkdownConverter
from gse_guides.models import (
    CrossReference,
    GuideSection,
    GuideSource,
    RelatedAnnouncement,
    SectionURL,
    SubSection,
)

logger = logging.getLogger(__name__)

# Mapping of part codes to part names
PART_NAMES = {
    "A": "Doing Business with Fannie Mae",
    "B": "Origination Through Closing",
    "C": "Selling, Securitizing, and Delivering Loans",
    "D": "Ensuring Quality Control",
    "E": "Quick Reference Materials",
}


class FannieMaeParser:
    """
    Parses Fannie Mae Selling Guide HTML pages into GuideSection objects.

    Extracts:
    - Main content area (excluding nav, sidebar, footer)
    - Section metadata (code, title, effective date, hierarchy)
    - Subsections by heading tags
    - Cross-references to other guide sections
    - Related announcements
    """

    def __init__(self):
        self.converter = MarkdownConverter()

    def parse(self, html: str, section_url: SectionURL) -> GuideSection:
        """Parse a complete HTML page into a GuideSection."""
        soup = BeautifulSoup(html, "lxml")

        title = self._extract_title(soup)
        effective_date = self._extract_effective_date(soup)
        hierarchy = self._parse_section_code_hierarchy(section_url.section_code)
        breadcrumb = self._extract_breadcrumb_hierarchy(soup)

        # Merge breadcrumb info into hierarchy
        hierarchy.update(
            {k: v for k, v in breadcrumb.items() if v and not hierarchy.get(k)}
        )

        content_tag = self._find_main_content(soup)
        content_html = str(content_tag) if content_tag else ""
        content_markdown = self.converter.convert(content_html, GuideSource.FANNIE_MAE)

        subsections = self._split_subsections(content_tag) if content_tag else []
        cross_refs = (
            self._extract_cross_references(content_tag) if content_tag else []
        )
        announcements = self._extract_related_announcements(soup)

        word_count = len(content_markdown.split())
        table_count = len(content_tag.find_all("table")) if content_tag else 0

        return GuideSection(
            source=GuideSource.FANNIE_MAE,
            section_code=section_url.section_code,
            title=title,
            url=section_url.url,
            part_code=hierarchy.get("part_code", ""),
            part_name=hierarchy.get("part_name", ""),
            chapter_code=hierarchy.get("chapter_code", ""),
            chapter_name=hierarchy.get("chapter_name", ""),
            subpart_code=hierarchy.get("subpart_code"),
            subpart_name=hierarchy.get("subpart_name"),
            content_html=content_html,
            content_markdown=content_markdown,
            subsections=subsections,
            effective_date=effective_date,
            word_count=word_count,
            has_tables=table_count > 0,
            table_count=table_count,
            cross_references=cross_refs,
            related_announcements=announcements,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    def _find_main_content(self, soup: BeautifulSoup) -> Tag | None:
        """Locate the main content element, trying multiple strategies."""
        # Strategy 1: Collect all content-bearing divs (body-field + glossary-table)
        # Some pages (e.g. E-3 glossary) have a tiny body-field but a large glossary-table
        content_divs = soup.find_all("div", class_="body-field")
        glossary = soup.find("div", class_="glossary-table")
        if glossary:
            content_divs.append(glossary)

        if content_divs:
            total_text = sum(len(d.get_text(strip=True)) for d in content_divs)
            if total_text > 100:
                if len(content_divs) == 1:
                    return content_divs[0]
                wrapper = soup.new_tag("div")
                for div in content_divs:
                    wrapper.append(div.__copy__() if hasattr(div, '__copy__') else div.extract())
                return wrapper
            # body-field exists but has trivial content - fall through to other strategies

        # Strategy 2: Drupal field--name-body class
        content = soup.find("div", class_=re.compile(r"field--name-body"))
        if content and len(content.get_text(strip=True)) > 100:
            return content

        # Strategy 3: layout-content div
        content = soup.find("div", class_="layout-content")
        if content and len(content.get_text(strip=True)) > 100:
            return content

        # Strategy 4: main tag
        content = soup.find("main")
        if content and len(content.get_text(strip=True)) > 100:
            return content

        # Strategy 5: largest div with substantial text
        candidates = soup.find_all("div")
        best = None
        best_len = 0
        for div in candidates:
            text_len = len(div.get_text(strip=True))
            if text_len > best_len:
                best_len = text_len
                best = div

        if best and best_len > 500:
            return best

        logger.warning("Could not find main content area")
        return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract section title from page."""
        # Try h1
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            # Clean up: remove section code prefix and date suffix
            text = re.sub(r"^[A-E][\d\-\.]+\s*,?\s*", "", text)
            text = re.sub(r"\s*\(\d{2}/\d{2}/\d{4}\)\s*$", "", text)
            if text:
                return text.strip()

        # Try og:title meta
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            text = og["content"]
            text = re.sub(r"^[A-E][\d\-\.]+\s*,?\s*", "", text)
            text = re.sub(r"\s*\(\d{2}/\d{2}/\d{4}\)\s*$", "", text)
            return text.strip() if text.strip() else og["content"]

        # Try title tag
        title = soup.find("title")
        if title:
            text = title.get_text(strip=True)
            if "|" in text:
                text = text.split("|")[0].strip()
            return text

        return "Untitled Section"

    def _extract_effective_date(self, soup: BeautifulSoup) -> str | None:
        """Look for effective/update date in the page."""
        # Look for text pattern "Last Updated: MM/DD/YYYY" or similar
        text = soup.get_text()
        patterns = [
            r"(?:Last\s+Updated|Effective\s+Date|Updated)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                try:
                    dt = datetime.strptime(date_str, "%m/%d/%Y")
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        # Check meta tags
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            if "date" in name or "modified" in name:
                content = meta.get("content", "")
                if content:
                    return content[:10]  # Take first 10 chars (YYYY-MM-DD)

        return None

    def _extract_breadcrumb_hierarchy(self, soup: BeautifulSoup) -> dict:
        """Parse breadcrumb navigation to extract hierarchy."""
        result = {
            "part_code": "",
            "part_name": "",
            "chapter_code": "",
            "chapter_name": "",
            "subpart_code": None,
            "subpart_name": None,
        }

        breadcrumb = soup.find("nav", attrs={"aria-label": re.compile(r"breadcrumb", re.I)})
        if not breadcrumb:
            breadcrumb = soup.find(class_=re.compile(r"breadcrumb"))

        if not breadcrumb:
            return result

        crumbs = [
            a.get_text(strip=True) for a in breadcrumb.find_all("a")
        ]
        crumbs += [
            span.get_text(strip=True)
            for span in breadcrumb.find_all("span")
            if span.get_text(strip=True) and span.get_text(strip=True) not in crumbs
        ]

        for crumb in crumbs:
            if crumb.startswith("Part "):
                result["part_name"] = crumb
            elif "Chapter" in crumb or "Subpart" in crumb:
                if "Chapter" in crumb:
                    result["chapter_name"] = crumb
                else:
                    result["subpart_name"] = crumb

        return result

    def _split_subsections(self, content_tag: Tag) -> list[SubSection]:
        """Split content at H2 and H3 heading boundaries."""
        subsections: list[SubSection] = []
        headings = content_tag.find_all(["h2", "h3"])

        if not headings:
            return subsections

        for i, heading in enumerate(headings):
            heading_text = heading.get_text(strip=True)
            heading_level = int(heading.name[1])
            anchor_id = heading.get("id")

            # Collect elements between this heading and the next
            elements: list[str] = []
            sibling = heading.next_sibling
            next_heading = headings[i + 1] if i + 1 < len(headings) else None

            while sibling:
                if sibling == next_heading:
                    break
                if isinstance(sibling, Tag):
                    if sibling.name in ("h2", "h3"):
                        break
                    elements.append(str(sibling))
                sibling = sibling.next_sibling

            sub_html = "".join(elements)
            sub_md = self.converter.convert(sub_html, GuideSource.FANNIE_MAE)

            has_tables = "<table" in sub_html.lower()
            has_lists = bool(re.search(r"<[uo]l", sub_html, re.IGNORECASE))

            subsections.append(
                SubSection(
                    heading=heading_text,
                    heading_level=heading_level,
                    anchor_id=anchor_id,
                    content_html=sub_html,
                    content_markdown=sub_md,
                    word_count=len(sub_md.split()),
                    has_tables=has_tables,
                    has_lists=has_lists,
                )
            )

        return subsections

    def _extract_cross_references(self, content_tag: Tag) -> list[CrossReference]:
        """Find all cross-reference links to other guide sections."""
        refs: list[CrossReference] = []
        seen: set[str] = set()

        for link in content_tag.find_all("a", href=True):
            href = link["href"]
            if "/sel/" not in href:
                continue

            match = re.search(r"/sel/([a-z0-9\-\.]+)/", href, re.IGNORECASE)
            if not match:
                match = re.search(r"/sel/([a-z0-9\-\.]+)$", href, re.IGNORECASE)
            if not match:
                continue

            code = match.group(1).upper()
            if code in seen:
                continue
            seen.add(code)

            link_text = link.get_text(strip=True)

            # Get surrounding sentence for context
            parent = link.parent
            context = parent.get_text(strip=True) if parent else link_text
            if len(context) > 200:
                context = context[:200] + "..."

            refs.append(
                CrossReference(
                    target_section_code=code,
                    target_url=href,
                    link_text=link_text,
                    context=context,
                )
            )

        return refs

    def _extract_related_announcements(
        self, soup: BeautifulSoup
    ) -> list[RelatedAnnouncement]:
        """Find related announcements section and extract entries."""
        announcements: list[RelatedAnnouncement] = []

        # Look for "Related Announcements" heading or table
        for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
            if "related" in heading.get_text(strip=True).lower() and "announcement" in heading.get_text(strip=True).lower():
                # Find the next table after this heading
                table = heading.find_next("table")
                if table:
                    for row in table.find_all("tr")[1:]:  # Skip header
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2:
                            code = cells[0].get_text(strip=True)
                            date = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                            title = (
                                cells[2].get_text(strip=True) if len(cells) > 2 else None
                            )
                            if code:
                                announcements.append(
                                    RelatedAnnouncement(
                                        code=code, date=date, title=title
                                    )
                                )
                break

        # Also try pattern matching for SEL-YYYY-NN in page text
        if not announcements:
            text = soup.get_text()
            for match in re.finditer(r"(SEL-\d{4}-\d+)", text):
                code = match.group(1)
                if not any(a.code == code for a in announcements):
                    announcements.append(
                        RelatedAnnouncement(code=code, date="", title=None)
                    )

        return announcements

    def _parse_section_code_hierarchy(self, code: str) -> dict:
        """
        Parse section code into hierarchy components.

        Examples:
          'B3-3.1-01' -> part=B, chapter=B3-3, subpart=B3-3.1
          'A2-2-01'   -> part=A, chapter=A2-2, subpart=None
          'E-1-01'    -> part=E, chapter=E-1, subpart=None
        """
        result = {
            "part_code": "",
            "part_name": "",
            "chapter_code": "",
            "chapter_name": "",
            "subpart_code": None,
            "subpart_name": None,
        }

        if not code:
            return result

        # Part is always the first letter
        part_letter = code[0].upper()
        result["part_code"] = part_letter
        result["part_name"] = PART_NAMES.get(part_letter, f"Part {part_letter}")

        # Check for subpart pattern: X#-#.#-## (has a dot before the last dash-number)
        # B3-3.1-01 -> chapter B3-3, subpart B3-3.1
        # A2-2-01 -> chapter A2-2, no subpart
        subpart_match = re.match(
            r"^([A-E]\d*-\d+)\.(\d+)-(\d+)$", code, re.IGNORECASE
        )
        if subpart_match:
            chapter_base = subpart_match.group(1).upper()
            sub_num = subpart_match.group(2)
            result["chapter_code"] = chapter_base
            result["subpart_code"] = f"{chapter_base}.{sub_num}"
            return result

        # Simple pattern: X#-#-## (no dot, no subpart)
        simple_match = re.match(r"^([A-E]\d*-\d+)-(\d+)$", code, re.IGNORECASE)
        if simple_match:
            result["chapter_code"] = simple_match.group(1).upper()
            return result

        # Part E pattern: E-#-##
        e_match = re.match(r"^(E-\d+)-(\d+)$", code, re.IGNORECASE)
        if e_match:
            result["chapter_code"] = e_match.group(1).upper()
            return result

        # Fallback: use the code as chapter
        result["chapter_code"] = code
        return result
