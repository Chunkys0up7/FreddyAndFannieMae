"""Freddie Mac Guide DOM parser for Playwright-rendered pages."""

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
    SectionURL,
    SubSection,
)

logger = logging.getLogger(__name__)


class FreddieMacParser:
    """
    Parses Freddie Mac rendered HTML (from Playwright) into GuideSection objects.

    The DOM structure is from an Oracle RightNow SPA. The content selectors
    are determined by inspecting the rendered page during development.
    """

    # Content selectors to try (most specific first)
    CONTENT_SELECTORS = [
        ".rn_Answer",
        "#rn_AnswerDetail",
        ".rn_AnswerDetail",
        "[class*='answer']",
        "[class*='Answer']",
        "[class*='content']",
        "main",
        "#content",
    ]

    def __init__(self):
        self.converter = MarkdownConverter()

    def parse(self, html: str, section_url: SectionURL) -> GuideSection:
        """Parse rendered HTML into GuideSection."""
        soup = BeautifulSoup(html, "lxml")

        title = self._extract_title(soup, section_url.section_code)
        content_tag = self._find_main_content(soup)
        content_html = str(content_tag) if content_tag else ""
        content_markdown = self.converter.convert(
            content_html, GuideSource.FREDDIE_MAC
        )

        metadata = self._extract_section_metadata(soup, section_url.section_code)
        subsections = self._split_subsections(content_tag) if content_tag else []
        cross_refs = (
            self._extract_cross_references(content_tag) if content_tag else []
        )

        word_count = len(content_markdown.split())
        table_count = len(content_tag.find_all("table")) if content_tag else 0

        return GuideSection(
            source=GuideSource.FREDDIE_MAC,
            section_code=section_url.section_code,
            title=title,
            url=section_url.url,
            part_code=metadata.get("part_code", ""),
            part_name=metadata.get("part_name", ""),
            chapter_code=metadata.get("chapter_code", ""),
            chapter_name=metadata.get("chapter_name", ""),
            subpart_code=metadata.get("subpart_code"),
            subpart_name=metadata.get("subpart_name"),
            content_html=content_html,
            content_markdown=content_markdown,
            subsections=subsections,
            effective_date=metadata.get("effective_date"),
            word_count=word_count,
            has_tables=table_count > 0,
            table_count=table_count,
            cross_references=cross_refs,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    def _find_main_content(self, soup: BeautifulSoup) -> Tag | None:
        """Locate content in the rendered SPA DOM."""
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 100:
                return content

        # Fallback: find the div with the most text
        candidates = soup.find_all("div")
        best = None
        best_len = 0
        for div in candidates:
            text_len = len(div.get_text(strip=True))
            if text_len > best_len:
                best_len = text_len
                best = div

        if best and best_len > 200:
            return best

        logger.warning("Could not find main content in rendered DOM")
        return None

    # H1 text that is site branding, not a section title
    _SITE_BRANDING_RE = re.compile(
        r"seller/servicer\s*guide|freddie\s*mac\s*guide", re.IGNORECASE
    )

    def _extract_title(self, soup: BeautifulSoup, section_number: str) -> str:
        """Extract section title from rendered page."""
        # Try h1 — but skip if it's the site branding
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            if text and len(text) > 3 and not self._SITE_BRANDING_RE.search(text):
                return text

        # Try h2 (Freddie Mac SPA uses h2 for actual section titles)
        h2 = soup.find("h2")
        if h2:
            text = h2.get_text(strip=True)
            if text and len(text) > 3:
                return text

        # Try page title
        title = soup.find("title")
        if title:
            text = title.get_text(strip=True)
            if text:
                # Remove site name and "Guide Section" prefix
                text = re.sub(r"\s*[-|]\s*Freddie Mac.*$", "", text)
                text = re.sub(r"^Guide Section\s*", "", text)
                if text:
                    return text

        return f"Section {section_number}"

    def _extract_section_metadata(
        self, soup: BeautifulSoup, section_number: str
    ) -> dict:
        """Extract metadata from the rendered page."""
        result = {
            "part_code": "",
            "part_name": "",
            "chapter_code": "",
            "chapter_name": "",
            "subpart_code": None,
            "subpart_name": None,
            "effective_date": None,
        }

        # Chapter is the integer prefix of the section number
        parts = section_number.split(".")
        if parts:
            chapter_num = parts[0]
            result["chapter_code"] = chapter_num

            # Map chapter ranges to parts (approximate)
            num = int(chapter_num) if chapter_num.isdigit() else 0
            if 1000 <= num < 2000:
                result["part_code"] = "1"
                result["part_name"] = "General"
            elif 2000 <= num < 3000:
                result["part_code"] = "2"
                result["part_name"] = "Requirements"
            elif 3000 <= num < 4000:
                result["part_code"] = "3"
                result["part_name"] = "Underwriting"
            elif 4000 <= num < 5000:
                result["part_code"] = "4"
                result["part_name"] = "Origination"
            elif 5000 <= num < 6000:
                result["part_code"] = "5"
                result["part_name"] = "Special Programs"
            elif 6000 <= num < 7000:
                result["part_code"] = "6"
                result["part_name"] = "Quality Control"

        # Try to find effective date
        text = soup.get_text()
        date_match = re.search(
            r"(?:Effective|Updated|Published)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})", text
        )
        if date_match:
            try:
                dt = datetime.strptime(date_match.group(1), "%m/%d/%Y")
                result["effective_date"] = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # Try breadcrumb for hierarchy info
        breadcrumb = soup.find(class_=re.compile(r"breadcrumb|crumb", re.I))
        if breadcrumb:
            crumb_text = breadcrumb.get_text()
            result["chapter_name"] = crumb_text.strip()[:100]

        return result

    def _split_subsections(self, content_tag: Tag) -> list[SubSection]:
        """Split content at heading boundaries."""
        subsections: list[SubSection] = []
        headings = content_tag.find_all(["h2", "h3", "h4"])

        if not headings:
            return subsections

        for i, heading in enumerate(headings):
            heading_text = heading.get_text(strip=True)
            heading_level = int(heading.name[1])
            anchor_id = heading.get("id")

            # Collect elements until next heading
            elements: list[str] = []
            sibling = heading.next_sibling
            next_heading = headings[i + 1] if i + 1 < len(headings) else None

            while sibling:
                if sibling == next_heading:
                    break
                if isinstance(sibling, Tag):
                    if sibling.name in ("h2", "h3", "h4"):
                        break
                    elements.append(str(sibling))
                sibling = sibling.next_sibling

            sub_html = "".join(elements)
            sub_md = self.converter.convert(sub_html, GuideSource.FREDDIE_MAC)

            subsections.append(
                SubSection(
                    heading=heading_text,
                    heading_level=heading_level,
                    anchor_id=anchor_id,
                    content_html=sub_html,
                    content_markdown=sub_md,
                    word_count=len(sub_md.split()),
                    has_tables="<table" in sub_html.lower(),
                    has_lists=bool(re.search(r"<[uo]l", sub_html, re.IGNORECASE)),
                )
            )

        return subsections

    def _extract_cross_references(self, content_tag: Tag) -> list[CrossReference]:
        """Find cross-reference links to other guide sections."""
        refs: list[CrossReference] = []
        seen: set[str] = set()

        for link in content_tag.find_all("a", href=True):
            href = link["href"]
            if "/app/guide/section/" not in href:
                continue

            match = re.search(r"/section/([0-9]+(?:\.[0-9]+)?)", href)
            if not match:
                continue

            code = match.group(1)
            if code in seen:
                continue
            seen.add(code)

            link_text = link.get_text(strip=True)
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
