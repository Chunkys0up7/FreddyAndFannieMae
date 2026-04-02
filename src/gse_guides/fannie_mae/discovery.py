"""Fannie Mae Selling Guide URL discovery from sitemap."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

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


class FannieMaeDiscovery:
    """
    Discovers all Fannie Mae Selling Guide section URLs.

    Primary: Parse sitemap.xml for /sel/ URLs.
    Fallback: Crawl the TOC page to find all section links.
    """

    def __init__(self, config: ScraperConfig):
        self.config = config

    def discover(self) -> list[SectionURL]:
        """Return all section URLs sorted by section code."""
        logger.info("Discovering Fannie Mae section URLs from sitemap...")

        with requests.Session() as session:
            session.headers.update({"User-Agent": self.config.user_agent})

            urls = self._fetch_sitemap_urls(session)

            # If sitemap returned too few, try the TOC fallback
            if len(urls) < 200:
                logger.info(
                    "Sitemap returned only %d URLs, trying TOC fallback...", len(urls)
                )
                toc_urls = self._crawl_toc_fallback(session)
                # Merge: keep sitemap URLs (have lastmod) and add any new from TOC
                existing_codes = {u.section_code for u in urls}
                for u in toc_urls:
                    if u.section_code not in existing_codes:
                        urls.append(u)

        # Sort by section code
        urls.sort(key=lambda u: u.section_code)
        logger.info("Discovered %d Fannie Mae section URLs", len(urls))
        return urls

    def _fetch_sitemap_urls(self, session: requests.Session) -> list[SectionURL]:
        """Fetch and parse sitemap.xml, handling sitemap index files."""
        try:
            resp = session.get(self.config.fannie_sitemap_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch sitemap: %s", e)
            return []

        xml = resp.text
        soup = BeautifulSoup(xml, "lxml-xml")

        # Check if this is a sitemap index
        sitemap_index = soup.find("sitemapindex")
        if sitemap_index:
            all_urls: list[SectionURL] = []
            for sitemap_tag in sitemap_index.find_all("sitemap"):
                loc = sitemap_tag.find("loc")
                if loc:
                    sub_urls = self._parse_single_sitemap(session, loc.text.strip())
                    all_urls.extend(sub_urls)
            return all_urls

        # It's a regular sitemap
        return self._parse_sitemap_xml(xml)

    def _parse_single_sitemap(
        self, session: requests.Session, url: str
    ) -> list[SectionURL]:
        """Fetch and parse a single sitemap XML file."""
        if not _is_valid_url(url, self.config.fannie_base_url):
            logger.warning("Skipping untrusted sitemap URL: %s", url)
            return []
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return self._parse_sitemap_xml(resp.text)
        except requests.RequestException as e:
            logger.warning("Failed to fetch sub-sitemap %s: %s", url, e)
            return []

    def _parse_sitemap_xml(self, xml_content: str) -> list[SectionURL]:
        """Parse sitemap XML into SectionURL objects, filtering for /sel/ paths."""
        soup = BeautifulSoup(xml_content, "lxml-xml")
        urls: list[SectionURL] = []

        for url_tag in soup.find_all("url"):
            loc = url_tag.find("loc")
            if not loc:
                continue
            url_str = loc.text.strip()

            # Only process /sel/ paths (not /svc/ or other)
            if "/sel/" not in url_str:
                continue

            # Skip the TOC page itself
            if url_str.endswith("/sel/selling-guide"):
                continue

            section_code = self._extract_section_code(url_str)
            if not section_code:
                continue

            slug = self._extract_slug(url_str)

            lastmod_tag = url_tag.find("lastmod")
            lastmod = lastmod_tag.text.strip() if lastmod_tag else None

            urls.append(
                SectionURL(
                    url=url_str,
                    source=GuideSource.FANNIE_MAE,
                    section_code=section_code,
                    slug=slug,
                    last_modified=lastmod,
                )
            )

        return urls

    def _extract_section_code(self, url: str) -> str | None:
        """
        Extract section code from URL path.
        '/sel/b3-3.1-01/general-income-information' -> 'B3-3.1-01'
        """
        path = urlparse(url).path
        # Match /sel/{code}/{slug}
        match = re.search(r"/sel/([a-z0-9\-\.]+)/", path, re.IGNORECASE)
        if not match:
            # Try without trailing slug
            match = re.search(r"/sel/([a-z0-9\-\.]+)$", path, re.IGNORECASE)
        if match:
            code = match.group(1).upper()
            # Validate it looks like a section code (starts with letter, has dash)
            if re.match(r"^[A-E]", code):
                return code
        return None

    def _extract_slug(self, url: str) -> str:
        """Extract the slug portion from a URL."""
        path = urlparse(url).path.rstrip("/")
        parts = path.split("/")
        if len(parts) >= 2:
            return parts[-1]
        return ""

    def _crawl_toc_fallback(self, session: requests.Session) -> list[SectionURL]:
        """Crawl the TOC page to discover section URLs."""
        toc_url = f"{self.config.fannie_base_url}/sel/selling-guide"
        logger.info("Crawling TOC at %s", toc_url)

        try:
            resp = session.get(toc_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch TOC: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        urls: list[SectionURL] = []
        seen_codes: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/sel/" not in href:
                continue
            if href.endswith("/sel/selling-guide"):
                continue

            # Make absolute
            if href.startswith("/"):
                href = urljoin(self.config.fannie_base_url, href)

            code = self._extract_section_code(href)
            if code and code not in seen_codes:
                seen_codes.add(code)
                urls.append(
                    SectionURL(
                        url=href,
                        source=GuideSource.FANNIE_MAE,
                        section_code=code,
                        slug=self._extract_slug(href),
                        last_modified=None,
                    )
                )

        logger.info("TOC crawl found %d section URLs", len(urls))
        return urls
