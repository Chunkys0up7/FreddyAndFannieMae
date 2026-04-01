"""HTML to Markdown conversion engine with guide-specific handling."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup
from markdownify import markdownify

from gse_guides.models import GuideSource


class MarkdownConverter:
    """
    Converts guide HTML content to clean markdown.

    Handles:
    - Tables with proper alignment
    - Cross-reference links normalized to section codes
    - Nested lists with correct indentation
    - Stripping of inline styles and classes
    - Cleaning script/style/hidden elements
    """

    def convert(self, html: str, source: GuideSource) -> str:
        """Convert HTML fragment to clean markdown."""
        html = self._preprocess_html(html)
        md = markdownify(
            html,
            heading_style="ATX",
            bullets="-",
            strip=["img"],
        )
        md = self._convert_cross_references(md, source)
        md = self._normalize_whitespace(md)
        return md.strip()

    def _preprocess_html(self, html: str) -> str:
        """Remove script, style, hidden elements, and inline styles."""
        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted tags
        for tag_name in ("script", "style", "noscript", "iframe"):
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Remove hidden elements
        for tag in soup.find_all(attrs={"aria-hidden": "true"}):
            tag.decompose()
        for tag in soup.find_all(style=re.compile(r"display\s*:\s*none")):
            tag.decompose()

        # Strip inline styles from all elements
        for tag in soup.find_all(True):
            if tag.has_attr("style"):
                del tag["style"]
            if tag.has_attr("class"):
                del tag["class"]

        # Convert &nbsp; to space
        result = str(soup)
        result = result.replace("\xa0", " ")
        return result

    def _convert_cross_references(self, markdown: str, source: GuideSource) -> str:
        """Normalize guide cross-reference links to section codes."""
        if source == GuideSource.FANNIE_MAE:
            # [text](/sel/b3-3.1-01/slug) -> [text](B3-3.1-01)
            pattern = r"\[([^\]]+)\]\(/sel/([a-z0-9\-\.]+)/[^)]*\)"

            def _replace_fannie(m):
                text = m.group(1)
                code = m.group(2).upper()
                return f"[{text}]({code})"

            markdown = re.sub(pattern, _replace_fannie, markdown, flags=re.IGNORECASE)

        elif source == GuideSource.FREDDIE_MAC:
            # [text](/app/guide/section/1101.1) -> [text](1101.1)
            pattern = r"\[([^\]]+)\]\(/app/guide/section/([0-9\.]+)\)"

            def _replace_freddie(m):
                text = m.group(1)
                code = m.group(2)
                return f"[{text}]({code})"

            markdown = re.sub(pattern, _replace_freddie, markdown)

        return markdown

    def _normalize_whitespace(self, markdown: str) -> str:
        """Clean up excessive blank lines and trailing spaces."""
        # Collapse 3+ consecutive blank lines to 2
        markdown = re.sub(r"\n{4,}", "\n\n\n", markdown)
        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in markdown.split("\n")]
        return "\n".join(lines)
