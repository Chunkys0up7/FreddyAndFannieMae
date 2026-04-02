"""Fannie Mae Selling Guide scraper using requests + BeautifulSoup."""

from __future__ import annotations

import logging
import threading
import time

import requests

from gse_guides.base_scraper import BaseScraper
from gse_guides.config import ScraperConfig
from gse_guides.fannie_mae.discovery import FannieMaeDiscovery
from gse_guides.fannie_mae.parser import FannieMaeParser
from gse_guides.models import GuideSection, GuideSource, SectionURL

logger = logging.getLogger(__name__)


class FannieMaeScraper(BaseScraper):
    """
    Scrapes Fannie Mae Selling Guide using requests + BeautifulSoup.

    The site is a standard Drupal CMS serving static HTML.
    robots.txt allows crawling of /sel/ paths.

    Supports parallel scraping: each worker thread gets its own
    requests.Session via thread-local storage.
    """

    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self._shared_session: requests.Session | None = None
        self._thread_local = threading.local()
        self._thread_sessions: list[requests.Session] = []
        self._session_lock = threading.Lock()
        self.discovery = FannieMaeDiscovery(config)
        self.parser = FannieMaeParser()

    @property
    def source(self) -> GuideSource:
        return GuideSource.FANNIE_MAE

    @property
    def request_delay(self) -> float:
        return self.config.fannie_request_delay_seconds

    def setup(self) -> None:
        """Create a shared session (used in sequential mode) and configure headers."""
        self._shared_session = self._create_session()

    def teardown(self) -> None:
        """Close the shared session and all per-thread sessions."""
        if self._shared_session:
            self._shared_session.close()
            self._shared_session = None
        with self._session_lock:
            for session in self._thread_sessions:
                session.close()
            self._thread_sessions.clear()

    def discover_sections(self) -> list[SectionURL]:
        """Discover all section URLs from sitemap."""
        return self.discovery.discover()

    def _get_session(self) -> requests.Session:
        """Get a per-thread session (creates one on first call per thread)."""
        if self.config.max_workers <= 1:
            return self._shared_session

        # Thread-local session for parallel mode
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = self._create_session()
            self._thread_local.session = session
            with self._session_lock:
                self._thread_sessions.append(session)
        return session

    def _create_session(self) -> requests.Session:
        """Create a configured requests.Session."""
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            }
        )
        return session

    def scrape_section(self, section_url: SectionURL) -> GuideSection | None:
        """Fetch and parse a single Fannie Mae section."""
        session = self._get_session()
        if not session:
            raise RuntimeError("Scraper not set up. Call setup() first.")

        logger.info("Scraping %s: %s", section_url.section_code, section_url.url)
        start = time.time()

        try:
            resp = session.get(
                section_url.url, timeout=self.config.request_timeout_seconds
            )
            resp.raise_for_status()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("Section %s returned 404", section_url.section_code)
                return None
            raise
        except requests.RequestException as e:
            logger.error("Request failed for %s: %s", section_url.section_code, e)
            raise

        if not resp.text or len(resp.text) < 500:
            logger.warning(
                "Section %s returned very short content (%d bytes)",
                section_url.section_code,
                len(resp.text),
            )
            return None

        section = self.parser.parse(resp.text, section_url)
        section.scrape_duration_ms = int((time.time() - start) * 1000)

        logger.info(
            "Parsed %s: %d words, %d subsections, %d tables",
            section.section_code,
            section.word_count,
            len(section.subsections),
            section.table_count,
        )

        return section
