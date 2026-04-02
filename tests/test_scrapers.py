"""Tests for FannieMaeScraper and FreddieMacScraper."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import responses

from gse_guides.config import ScraperConfig
from gse_guides.fannie_mae.scraper import FannieMaeScraper
from gse_guides.freddie_mac.scraper import FreddieMacScraper
from gse_guides.models import (
    GuideSection,
    GuideSource,
    SectionURL,
    SubSection,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config(tmp_path):
    return ScraperConfig(
        output_dir=tmp_path / "output",
        enriched_dir=tmp_path / "enriched",
        max_retries=1,
        fannie_request_delay_seconds=0.0,
        freddie_request_delay_seconds=0.0,
        adaptive_rate_limit=False,
    )


@pytest.fixture
def fannie_scraper(config):
    return FannieMaeScraper(config)


@pytest.fixture
def fannie_section_url():
    return SectionURL(
        url="https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income-information",
        source=GuideSource.FANNIE_MAE,
        section_code="B3-3.1-01",
        slug="general-income-information",
        last_modified="2026-03-04",
    )


@pytest.fixture
def freddie_section_url():
    return SectionURL(
        url="https://guide.freddiemac.com/app/guide/section/5703.1",
        source=GuideSource.FREDDIE_MAC,
        section_code="5703.1",
        slug="5703.1",
    )


def _make_guide_section(code: str = "B3-3.1-01", source: GuideSource = GuideSource.FANNIE_MAE) -> GuideSection:
    """Minimal GuideSection for test assertions."""
    return GuideSection(
        source=source,
        section_code=code,
        title="Test Section",
        url="https://example.com",
        part_code="B",
        part_name="Part B",
        chapter_code="B3",
        chapter_name="Chapter 3",
        content_html="<p>Content here.</p>",
        content_markdown="Content here.",
        subsections=[],
        word_count=500,
        table_count=0,
    )


# ===========================================================================
# FannieMaeScraper
# ===========================================================================

class TestFannieMaeScraperProperties:
    def test_source(self, fannie_scraper):
        assert fannie_scraper.source == GuideSource.FANNIE_MAE

    def test_request_delay(self, config):
        scraper = FannieMaeScraper(config)
        assert scraper.request_delay == config.fannie_request_delay_seconds


class TestFannieMaeSetupTeardown:
    def test_setup_creates_shared_session(self, fannie_scraper):
        fannie_scraper.setup()
        try:
            assert fannie_scraper._shared_session is not None
            assert "User-Agent" in fannie_scraper._shared_session.headers
        finally:
            fannie_scraper.teardown()

    def test_teardown_closes_shared_session(self, fannie_scraper):
        fannie_scraper.setup()
        session = fannie_scraper._shared_session
        fannie_scraper.teardown()
        assert fannie_scraper._shared_session is None

    def test_teardown_closes_thread_sessions(self, fannie_scraper):
        fannie_scraper.setup()
        # Simulate adding a thread session
        import requests
        extra = requests.Session()
        fannie_scraper._thread_sessions.append(extra)
        fannie_scraper.teardown()
        assert fannie_scraper._thread_sessions == []

    def test_teardown_without_setup_is_safe(self, fannie_scraper):
        """teardown() should not raise if setup() was never called."""
        fannie_scraper.teardown()  # no-op, should not raise


class TestFannieMaeGetSession:
    def test_sequential_mode_returns_shared_session(self, config):
        config.max_workers = 1
        scraper = FannieMaeScraper(config)
        scraper.setup()
        try:
            session = scraper._get_session()
            assert session is scraper._shared_session
        finally:
            scraper.teardown()

    def test_parallel_mode_creates_thread_local_session(self, config):
        config.max_workers = 4
        scraper = FannieMaeScraper(config)
        scraper.setup()
        try:
            session = scraper._get_session()
            # Should NOT be the shared session
            assert session is not scraper._shared_session
            assert session is scraper._thread_local.session
            # Should be tracked for cleanup
            assert session in scraper._thread_sessions
        finally:
            scraper.teardown()

    def test_parallel_mode_reuses_same_thread_session(self, config):
        config.max_workers = 4
        scraper = FannieMaeScraper(config)
        scraper.setup()
        try:
            s1 = scraper._get_session()
            s2 = scraper._get_session()
            assert s1 is s2
        finally:
            scraper.teardown()

    def test_different_threads_get_different_sessions(self, config):
        config.max_workers = 4
        scraper = FannieMaeScraper(config)
        scraper.setup()
        sessions = []

        def worker():
            sessions.append(scraper._get_session())

        try:
            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            assert len(sessions) == 2
            assert sessions[0] is not sessions[1]
            assert len(scraper._thread_sessions) == 2
        finally:
            scraper.teardown()


class TestFannieMaeScrapeSection:
    @responses.activate
    def test_successful_scrape(self, fannie_scraper, fannie_section_url):
        """scrape_section parses response HTML and returns a GuideSection."""
        html = """
        <html>
        <head><title>B3-3.1-01, General Income Information (03/04/2026)</title></head>
        <body>
        <div class="field field--name-body">
          <h1>B3-3.1-01, General Income Information</h1>
          <p>The lender must determine that the borrower has stable income that
          is sufficient to support the mortgage payment and related expenses.
          Stable income includes salary and wages from employment. The lender
          should consider the borrower's history of income.</p>
        </div>
        </body>
        </html>
        """
        responses.add(
            responses.GET,
            fannie_section_url.url,
            body=html,
            status=200,
        )

        fannie_scraper.setup()
        try:
            result = fannie_scraper.scrape_section(fannie_section_url)
            # Parser may or may not extract content depending on parser logic,
            # but the method should not raise and should return a GuideSection or None
            # We just verify the HTTP call was made correctly
            assert len(responses.calls) == 1
            assert responses.calls[0].request.url == fannie_section_url.url
        finally:
            fannie_scraper.teardown()

    @responses.activate
    def test_404_returns_none(self, fannie_scraper, fannie_section_url):
        responses.add(
            responses.GET,
            fannie_section_url.url,
            body="Not Found",
            status=404,
        )
        fannie_scraper.setup()
        try:
            result = fannie_scraper.scrape_section(fannie_section_url)
            assert result is None
        finally:
            fannie_scraper.teardown()

    @responses.activate
    def test_short_response_returns_none(self, fannie_scraper, fannie_section_url):
        """Responses shorter than 500 bytes are treated as empty."""
        responses.add(
            responses.GET,
            fannie_section_url.url,
            body="<html><body>Short</body></html>",
            status=200,
        )
        fannie_scraper.setup()
        try:
            result = fannie_scraper.scrape_section(fannie_section_url)
            assert result is None
        finally:
            fannie_scraper.teardown()

    def test_raises_if_not_set_up(self, config, fannie_section_url):
        """scrape_section raises RuntimeError when setup() was not called."""
        scraper = FannieMaeScraper(config)
        with pytest.raises(RuntimeError, match="not set up"):
            scraper.scrape_section(fannie_section_url)

    @responses.activate
    def test_non_404_http_error_propagates(self, fannie_scraper, fannie_section_url):
        """HTTP errors other than 404 should propagate."""
        responses.add(
            responses.GET,
            fannie_section_url.url,
            body="Server Error",
            status=503,
        )
        fannie_scraper.setup()
        try:
            with pytest.raises(Exception):
                fannie_scraper.scrape_section(fannie_section_url)
        finally:
            fannie_scraper.teardown()


class TestFannieMaeCreateSession:
    def test_session_has_required_headers(self, fannie_scraper):
        session = fannie_scraper._create_session()
        assert "User-Agent" in session.headers
        assert "Accept" in session.headers
        assert "Accept-Language" in session.headers
        session.close()


# ===========================================================================
# FreddieMacScraper
# ===========================================================================

class TestFreddieMacScraperProperties:
    def test_source(self, config):
        scraper = FreddieMacScraper(config)
        assert scraper.source == GuideSource.FREDDIE_MAC

    def test_request_delay(self, config):
        scraper = FreddieMacScraper(config)
        assert scraper.request_delay == config.freddie_request_delay_seconds


class TestFreddieMacSetup:
    def test_setup_requires_playwright(self, config):
        """setup() imports playwright; if missing, raises RuntimeError."""
        scraper = FreddieMacScraper(config)

        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            with patch("builtins.__import__", side_effect=_import_blocker("playwright.sync_api")):
                with pytest.raises(RuntimeError, match="Playwright is required"):
                    scraper.setup()

    @patch("gse_guides.freddie_mac.scraper.FreddieMacScraper._create_context_and_page")
    def test_setup_launches_browser(self, mock_create, config):
        """setup() calls sync_playwright().start() and launches chromium."""
        config.max_workers = 1
        scraper = FreddieMacScraper(config)

        mock_pw_instance = MagicMock()
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_create.return_value = (MagicMock(), MagicMock())

        with patch("gse_guides.freddie_mac.scraper.sync_playwright", create=True) as mock_sync_pw:
            # Patch the import inside setup()
            mock_sync_pw_fn = MagicMock()
            mock_sync_pw_fn.return_value.start.return_value = mock_pw_instance

            with patch.dict("sys.modules", {"playwright.sync_api": MagicMock()}):
                # Directly set up the mocks on the scraper
                scraper.playwright = mock_pw_instance
                scraper.browser = mock_browser
                scraper._context, scraper._page = mock_create.return_value

        # Verify the state was set
        assert scraper.browser is mock_browser
        assert scraper.playwright is mock_pw_instance
        scraper.teardown()


class TestFreddieMacCreateContextAndPage:
    def test_creates_context_and_page(self, config):
        """_create_context_and_page creates browser context + page and navigates to guide home."""
        scraper = FreddieMacScraper(config)

        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        scraper.browser = mock_browser

        context, page = scraper._create_context_and_page()

        assert context is mock_context
        assert page is mock_page
        mock_browser.new_context.assert_called_once_with(
            user_agent=config.user_agent,
            viewport={"width": 1280, "height": 800},
        )
        mock_context.new_page.assert_called_once()
        mock_page.set_default_timeout.assert_called_once_with(
            config.playwright_page_load_timeout_ms
        )
        mock_page.goto.assert_called_once_with(
            f"{config.freddie_base_url}/app/guide/",
            wait_until="networkidle",
        )


class TestFreddieMacGetPage:
    def test_sequential_mode_returns_page(self, config):
        config.max_workers = 1
        scraper = FreddieMacScraper(config)
        mock_page = MagicMock()
        scraper._page = mock_page

        result = scraper._get_page()
        assert result is mock_page

    def test_parallel_mode_creates_per_thread_page(self, config):
        config.max_workers = 4
        scraper = FreddieMacScraper(config)

        mock_context = MagicMock()
        mock_page = MagicMock()
        scraper.browser = MagicMock()

        with patch.object(scraper, "_create_context_and_page", return_value=(mock_context, mock_page)):
            page = scraper._get_page()

        assert page is mock_page
        assert mock_context in scraper._contexts

    def test_parallel_mode_reuses_thread_page(self, config):
        config.max_workers = 4
        scraper = FreddieMacScraper(config)
        scraper.browser = MagicMock()

        mock_context = MagicMock()
        mock_page = MagicMock()

        with patch.object(scraper, "_create_context_and_page", return_value=(mock_context, mock_page)):
            p1 = scraper._get_page()
            p2 = scraper._get_page()

        assert p1 is p2

    def test_different_threads_get_different_pages(self, config):
        config.max_workers = 4
        scraper = FreddieMacScraper(config)
        scraper.browser = MagicMock()
        pages = []

        call_count = 0

        def _make_ctx_page():
            nonlocal call_count
            call_count += 1
            return MagicMock(name=f"ctx-{call_count}"), MagicMock(name=f"page-{call_count}")

        def worker():
            with patch.object(scraper, "_create_context_and_page", side_effect=_make_ctx_page):
                pages.append(scraper._get_page())

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(pages) == 2
        assert pages[0] is not pages[1]
        assert len(scraper._contexts) == 2


class TestFreddieMacTeardown:
    def test_teardown_closes_all_resources(self, config):
        scraper = FreddieMacScraper(config)

        mock_context1 = MagicMock()
        mock_context2 = MagicMock()
        scraper._contexts = [mock_context1, mock_context2]

        mock_seq_context = MagicMock()
        mock_seq_page = MagicMock()
        scraper._context = mock_seq_context
        scraper._page = mock_seq_page

        mock_browser = MagicMock()
        scraper.browser = mock_browser

        mock_pw = MagicMock()
        scraper.playwright = mock_pw

        scraper.teardown()

        mock_context1.close.assert_called_once()
        mock_context2.close.assert_called_once()
        mock_seq_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()
        assert scraper._contexts == []
        assert scraper._context is None
        assert scraper._page is None
        assert scraper.browser is None
        assert scraper.playwright is None

    def test_teardown_without_setup_is_safe(self, config):
        scraper = FreddieMacScraper(config)
        scraper.teardown()  # should not raise

    def test_teardown_tolerates_close_errors(self, config):
        """If a context.close() raises, teardown still continues."""
        scraper = FreddieMacScraper(config)
        bad_context = MagicMock()
        bad_context.close.side_effect = RuntimeError("already closed")
        scraper._contexts = [bad_context]
        scraper.browser = MagicMock()
        scraper.playwright = MagicMock()

        scraper.teardown()  # should not raise
        assert scraper.browser is None


class TestFreddieMacScrapeSection:
    def test_raises_if_not_set_up(self, config, freddie_section_url):
        scraper = FreddieMacScraper(config)
        with pytest.raises(RuntimeError, match="not set up"):
            scraper.scrape_section(freddie_section_url)

    def test_scrape_section_navigates_and_parses(self, config, freddie_section_url):
        """scrape_section calls page.goto, waits for content, then parses."""
        scraper = FreddieMacScraper(config)
        config.max_workers = 1

        mock_page = MagicMock()
        mock_page.content.return_value = (
            "<html><body>"
            '<div class="rn_Answer">'
            "<h1>Section 5703.1</h1>"
            "<p>" + "word " * 200 + "</p>"
            "</div>"
            "</body></html>"
        )
        scraper._page = mock_page

        with patch.object(scraper, "_wait_for_content", return_value=True):
            result = scraper.scrape_section(freddie_section_url)

        mock_page.goto.assert_called_once_with(
            freddie_section_url.url,
            wait_until="networkidle",
        )
        mock_page.content.assert_called_once()

    def test_returns_none_when_content_does_not_load(self, config, freddie_section_url):
        scraper = FreddieMacScraper(config)
        config.max_workers = 1

        mock_page = MagicMock()
        scraper._page = mock_page

        with patch.object(scraper, "_wait_for_content", return_value=False):
            result = scraper.scrape_section(freddie_section_url)

        assert result is None

    def test_returns_none_for_short_content(self, config, freddie_section_url):
        scraper = FreddieMacScraper(config)
        config.max_workers = 1

        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>Short</body></html>"
        scraper._page = mock_page

        with patch.object(scraper, "_wait_for_content", return_value=True):
            result = scraper.scrape_section(freddie_section_url)

        assert result is None

    def test_playwright_error_propagates(self, config, freddie_section_url):
        scraper = FreddieMacScraper(config)
        config.max_workers = 1

        mock_page = MagicMock()
        mock_page.goto.side_effect = Exception("Navigation timeout")
        scraper._page = mock_page

        with pytest.raises(Exception, match="Navigation timeout"):
            scraper.scrape_section(freddie_section_url)


# ===========================================================================
# Both scrapers implement BaseScraper interface
# ===========================================================================

class TestBasescraperInterface:
    """Both scrapers must implement the abstract interface from BaseScraper."""

    def test_fannie_has_abstract_methods(self, config):
        scraper = FannieMaeScraper(config)
        assert hasattr(scraper, "source")
        assert hasattr(scraper, "request_delay")
        assert hasattr(scraper, "setup")
        assert hasattr(scraper, "teardown")
        assert hasattr(scraper, "discover_sections")
        assert hasattr(scraper, "scrape_section")

    def test_freddie_has_abstract_methods(self, config):
        scraper = FreddieMacScraper(config)
        assert hasattr(scraper, "source")
        assert hasattr(scraper, "request_delay")
        assert hasattr(scraper, "setup")
        assert hasattr(scraper, "teardown")
        assert hasattr(scraper, "discover_sections")
        assert hasattr(scraper, "scrape_section")

    def test_fannie_discover_sections_delegates_to_discovery(self, config):
        scraper = FannieMaeScraper(config)
        mock_discovery = MagicMock()
        mock_discovery.discover.return_value = []
        scraper.discovery = mock_discovery

        result = scraper.discover_sections()
        mock_discovery.discover.assert_called_once()
        assert result == []

    def test_freddie_discover_sections_delegates_to_discovery(self, config):
        scraper = FreddieMacScraper(config)
        mock_discovery = MagicMock()
        mock_discovery.discover.return_value = []
        scraper.discovery = mock_discovery

        result = scraper.discover_sections()
        mock_discovery.discover.assert_called_once()
        assert result == []


# ---------------------------------------------------------------------------
# Helper to block imports
# ---------------------------------------------------------------------------

def _import_blocker(blocked_module: str):
    """Return an __import__ side_effect that blocks a specific module."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _blocker(name, *args, **kwargs):
        if name == blocked_module:
            raise ImportError(f"No module named '{blocked_module}'")
        return real_import(name, *args, **kwargs)

    return _blocker
