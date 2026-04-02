"""Freddie Mac Guide URL discovery from sitemap."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from gse_guides.config import ScraperConfig
from gse_guides.models import GuideSource, SectionURL

logger = logging.getLogger(__name__)


def _is_valid_url(url: str, allowed_base: str) -> bool:
    """Validate URL is HTTPS and within the expected domain."""
    parsed = urlparse(url)
    base_parsed = urlparse(allowed_base)
    return parsed.scheme == "https" and parsed.netloc == base_parsed.netloc


class FreddieMacDiscovery:
    """
    Discovers all Freddie Mac Guide section URLs from their sitemap.
    Sitemap at: https://guide.freddiemac.com/euf/assets/fm/sitemap.xml
    """

    def __init__(self, config: ScraperConfig):
        self.config = config

    def discover(self) -> list[SectionURL]:
        """Return all guide section URLs sorted by section number."""
        logger.info("Discovering Freddie Mac section URLs from sitemap...")

        try:
            resp = requests.get(
                self.config.freddie_sitemap_url,
                headers={"User-Agent": self.config.user_agent},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch Freddie Mac sitemap: %s", e)
            return []

        urls = self._parse_sitemap_xml(resp.text)
        urls.sort(key=lambda u: self._sort_key(u.section_code))

        logger.info("Discovered %d Freddie Mac section URLs", len(urls))
        return urls

    def _parse_sitemap_xml(self, xml_content: str) -> list[SectionURL]:
        """Parse sitemap XML, filtering for /app/guide/section/ URLs."""
        soup = BeautifulSoup(xml_content, "lxml-xml")
        urls: list[SectionURL] = []

        for url_tag in soup.find_all("url"):
            loc = url_tag.find("loc")
            if not loc:
                continue
            url_str = loc.text.strip()

            # Only process section URLs from trusted domain
            if "/app/guide/section/" not in url_str:
                continue
            if not _is_valid_url(url_str, self.config.freddie_base_url):
                logger.warning("Skipping untrusted URL: %s", url_str)
                continue

            section_number = self._extract_section_number(url_str)
            if not section_number:
                continue

            lastmod_tag = url_tag.find("lastmod")
            lastmod = lastmod_tag.text.strip() if lastmod_tag else None

            urls.append(
                SectionURL(
                    url=url_str,
                    source=GuideSource.FREDDIE_MAC,
                    section_code=section_number,
                    slug=section_number,
                    last_modified=lastmod,
                )
            )

        return urls

    def _extract_section_number(self, url: str) -> str | None:
        """Extract section number from URL path."""
        path = urlparse(url).path
        match = re.search(r"/section/([0-9]+(?:\.[0-9]+)?)", path)
        if match:
            return match.group(1)
        return None

    def _classify_chapter(self, section_number: str) -> str:
        """Map section number to chapter grouping."""
        base = section_number.split(".")[0]
        return f"chapter_{base}"

    def _sort_key(self, section_code: str) -> tuple[int, int]:
        """Create sortable key from section number."""
        parts = section_code.split(".")
        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            return (major, minor)
        except ValueError:
            return (0, 0)
