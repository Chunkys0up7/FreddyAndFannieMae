"""Freddie Mac Guide scraper using Playwright browser automation."""

from __future__ import annotations

import logging
import time

from gse_guides.base_scraper import BaseScraper
from gse_guides.config import ScraperConfig
from gse_guides.freddie_mac.discovery import FreddieMacDiscovery
from gse_guides.freddie_mac.parser import FreddieMacParser
from gse_guides.models import GuideSection, GuideSource, SectionURL

logger = logging.getLogger(__name__)


class FreddieMacScraper(BaseScraper):
    """
    Scrapes Freddie Mac Guide using Playwright browser automation.

    The site is a JavaScript SPA (Oracle RightNow/YUI framework).
    No content is available in static HTML - must render in browser.
    """

    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.playwright = None
        self.browser = None
        self.page = None
        self.discovery = FreddieMacDiscovery(config)
        self.parser = FreddieMacParser()

    @property
    def source(self) -> GuideSource:
        return GuideSource.FREDDIE_MAC

    @property
    def request_delay(self) -> float:
        return self.config.freddie_request_delay_seconds

    def setup(self) -> None:
        """Launch Playwright with headless Chromium."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is required for Freddie Mac scraping. "
                "Install with: pip install playwright && playwright install chromium"
            )

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.config.playwright_headless
        )
        context = self.browser.new_context(
            user_agent=self.config.user_agent,
            viewport={"width": 1280, "height": 800},
        )
        self.page = context.new_page()

        # Set default timeout
        self.page.set_default_timeout(self.config.playwright_page_load_timeout_ms)

        # Establish session by visiting the guide home page
        logger.info("Establishing Freddie Mac session...")
        try:
            self.page.goto(
                f"{self.config.freddie_base_url}/app/guide/",
                wait_until="networkidle",
            )
            # Wait a moment for the SPA to fully initialize
            self.page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning("Initial page load had issues: %s", e)

    def teardown(self) -> None:
        """Close browser and Playwright."""
        if self.browser:
            try:
                self.browser.close()
            except OSError:
                pass  # Browser process may already be gone
            self.browser = None

        if self.playwright:
            try:
                self.playwright.stop()
            except OSError:
                pass  # Playwright process cleanup
            self.playwright = None

        self.page = None

    def discover_sections(self) -> list[SectionURL]:
        """Discover section URLs from sitemap (doesn't need browser)."""
        return self.discovery.discover()

    def scrape_section(self, section_url: SectionURL) -> GuideSection | None:
        """Navigate to section URL and extract rendered content."""
        if not self.page:
            raise RuntimeError("Scraper not set up. Call setup() first.")

        logger.info(
            "Scraping %s: %s", section_url.section_code, section_url.url
        )
        start = time.time()

        try:
            # Navigate to section
            self.page.goto(section_url.url, wait_until="networkidle")

            # Wait for content to render
            if not self._wait_for_content():
                logger.warning(
                    "Content did not load for %s", section_url.section_code
                )
                return None

            # Extract the rendered HTML
            html = self.page.content()

        except Exception as e:
            logger.error(
                "Playwright error for %s: %s", section_url.section_code, e
            )
            raise

        if not html or len(html) < 500:
            logger.warning(
                "Section %s rendered very short content", section_url.section_code
            )
            return None

        section = self.parser.parse(html, section_url)
        section.scrape_duration_ms = int((time.time() - start) * 1000)

        logger.info(
            "Parsed %s: %d words, %d subsections, %d tables",
            section.section_code,
            section.word_count,
            len(section.subsections),
            section.table_count,
        )

        return section

    def _wait_for_content(self) -> bool:
        """
        Wait for the SPA to finish rendering content.

        Tries multiple strategies to detect content loading.
        """
        try:
            # Strategy 1: Wait for known content selectors
            for selector in FreddieMacParser.CONTENT_SELECTORS[:4]:
                try:
                    self.page.wait_for_selector(selector, timeout=5000)
                    # Give a bit more time for content to fully populate
                    self.page.wait_for_timeout(1000)
                    return True
                except Exception:
                    continue

            # Strategy 2: Wait for any substantial text content
            self.page.wait_for_timeout(3000)
            text = self.page.inner_text("body")
            if len(text) > 200:
                return True

            # Strategy 3: Last resort - wait longer
            self.page.wait_for_timeout(5000)
            text = self.page.inner_text("body")
            return len(text) > 200

        except Exception as e:
            logger.warning("Content wait failed: %s", e)
            return False
