"""Tests for Fannie Mae URL discovery from sitemap."""

from __future__ import annotations

import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from gse_guides.config import ScraperConfig
from gse_guides.fannie_mae.discovery import FannieMaeDiscovery, _is_valid_url
from gse_guides.models import GuideSource


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config(tmp_path):
    return ScraperConfig(
        output_dir=tmp_path / "output",
        enriched_dir=tmp_path / "enriched",
    )


@pytest.fixture
def discovery(config):
    return FannieMaeDiscovery(config)


# ---------------------------------------------------------------------------
# Helpers — XML builders
# ---------------------------------------------------------------------------

SITEMAP_HEADER = '<?xml version="1.0" encoding="UTF-8"?>'


def _sitemap_xml(entries: list[tuple[str, str | None]]) -> str:
    """Build a <urlset> sitemap with (url, lastmod|None) entries."""
    urls = ""
    for url, lastmod in entries:
        lastmod_tag = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        urls += f"<url><loc>{url}</loc>{lastmod_tag}</url>\n"
    return (
        f'{SITEMAP_HEADER}\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{urls}'
        f'</urlset>'
    )


def _sitemap_index_xml(sitemap_urls: list[str]) -> str:
    """Build a <sitemapindex> pointing to sub-sitemaps."""
    sitemaps = ""
    for url in sitemap_urls:
        sitemaps += f"<sitemap><loc>{url}</loc></sitemap>\n"
    return (
        f'{SITEMAP_HEADER}\n'
        f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{sitemaps}'
        f'</sitemapindex>'
    )


def _make_fannie_url(code: str, slug: str) -> str:
    return f"https://selling-guide.fanniemae.com/sel/{code.lower()}/{slug}"


# ---------------------------------------------------------------------------
# _is_valid_url
# ---------------------------------------------------------------------------

class TestIsValidUrl:
    def test_valid_https_same_domain(self):
        assert _is_valid_url(
            "https://selling-guide.fanniemae.com/sel/b3-3.1-01/slug",
            "https://selling-guide.fanniemae.com",
        )

    def test_rejects_http(self):
        assert not _is_valid_url(
            "http://selling-guide.fanniemae.com/sel/b3-3.1-01/slug",
            "https://selling-guide.fanniemae.com",
        )

    def test_rejects_different_domain(self):
        assert not _is_valid_url(
            "https://evil.example.com/sel/b3-3.1-01/slug",
            "https://selling-guide.fanniemae.com",
        )

    def test_rejects_empty_string(self):
        assert not _is_valid_url("", "https://selling-guide.fanniemae.com")


# ---------------------------------------------------------------------------
# Section code extraction
# ---------------------------------------------------------------------------

class TestExtractSectionCode:
    @pytest.mark.parametrize(
        "url, expected",
        [
            # Standard codes with various prefixes
            (
                "https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income",
                "B3-3.1-01",
            ),
            (
                "https://selling-guide.fanniemae.com/sel/a2-2-01/allowable-age",
                "A2-2-01",
            ),
            (
                "https://selling-guide.fanniemae.com/sel/e-1-01/purpose",
                "E-1-01",
            ),
            (
                "https://selling-guide.fanniemae.com/sel/d1-2-01/lender-qc",
                "D1-2-01",
            ),
            (
                "https://selling-guide.fanniemae.com/sel/c3-1-01/property",
                "C3-1-01",
            ),
            # Code without trailing slug (URL ends after code)
            (
                "https://selling-guide.fanniemae.com/sel/b3-3.1-01",
                "B3-3.1-01",
            ),
        ],
    )
    def test_extracts_known_codes(self, discovery, url, expected):
        assert discovery._extract_section_code(url) == expected

    def test_returns_none_for_non_section_path(self, discovery):
        """Codes that don't start with A-E are rejected."""
        url = "https://selling-guide.fanniemae.com/sel/selling-guide"
        assert discovery._extract_section_code(url) is None

    def test_returns_none_for_numeric_only_code(self, discovery):
        url = "https://selling-guide.fanniemae.com/sel/12345/foo"
        assert discovery._extract_section_code(url) is None


# ---------------------------------------------------------------------------
# Slug extraction
# ---------------------------------------------------------------------------

class TestExtractSlug:
    def test_extracts_trailing_slug(self, discovery):
        url = "https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income-information"
        assert discovery._extract_slug(url) == "general-income-information"

    def test_extracts_code_as_slug_when_no_trailing(self, discovery):
        url = "https://selling-guide.fanniemae.com/sel/b3-3.1-01"
        assert discovery._extract_slug(url) == "b3-3.1-01"

    def test_strips_trailing_slash(self, discovery):
        url = "https://selling-guide.fanniemae.com/sel/b3-3.1-01/slug/"
        assert discovery._extract_slug(url) == "slug"


# ---------------------------------------------------------------------------
# Sitemap XML parsing (_parse_sitemap_xml)
# ---------------------------------------------------------------------------

class TestParseSitemapXml:
    def test_filters_sel_urls(self, discovery):
        xml = _sitemap_xml([
            ("https://selling-guide.fanniemae.com/sel/b3-3.1-01/slug", "2026-01-01"),
            ("https://selling-guide.fanniemae.com/svc/something", None),  # not /sel/
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert len(result) == 1
        assert result[0].section_code == "B3-3.1-01"

    def test_skips_toc_page(self, discovery):
        xml = _sitemap_xml([
            ("https://selling-guide.fanniemae.com/sel/selling-guide", None),
            ("https://selling-guide.fanniemae.com/sel/b3-3.1-01/slug", None),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert len(result) == 1

    def test_captures_lastmod(self, discovery):
        xml = _sitemap_xml([
            ("https://selling-guide.fanniemae.com/sel/a2-2-01/slug", "2026-03-15"),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert result[0].last_modified == "2026-03-15"

    def test_lastmod_is_none_when_missing(self, discovery):
        xml = _sitemap_xml([
            ("https://selling-guide.fanniemae.com/sel/a2-2-01/slug", None),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert result[0].last_modified is None

    def test_source_is_fannie_mae(self, discovery):
        xml = _sitemap_xml([
            ("https://selling-guide.fanniemae.com/sel/b3-3.1-01/slug", None),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert result[0].source == GuideSource.FANNIE_MAE

    def test_empty_sitemap_returns_empty_list(self, discovery):
        xml = _sitemap_xml([])
        assert discovery._parse_sitemap_xml(xml) == []

    def test_malformed_xml_returns_empty_list(self, discovery):
        result = discovery._parse_sitemap_xml("<not><valid>xml")
        assert result == []

    def test_url_tag_without_loc_skipped(self, discovery):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><lastmod>2026-01-01</lastmod></url>'
            '</urlset>'
        )
        assert discovery._parse_sitemap_xml(xml) == []


# ---------------------------------------------------------------------------
# Sitemap index handling
# ---------------------------------------------------------------------------

class TestSitemapIndexHandling:
    @responses.activate
    def test_index_fetches_sub_sitemaps(self, discovery, config):
        """A sitemap index should cause sub-sitemaps to be fetched and merged."""
        sub_url = "https://selling-guide.fanniemae.com/sitemap-sel.xml"
        index_xml = _sitemap_index_xml([sub_url])
        sub_xml = _sitemap_xml([
            ("https://selling-guide.fanniemae.com/sel/b3-3.1-01/income", "2026-01-01"),
            ("https://selling-guide.fanniemae.com/sel/a2-2-01/age", None),
        ])

        responses.add(responses.GET, config.fannie_sitemap_url, body=index_xml, status=200)
        responses.add(responses.GET, sub_url, body=sub_xml, status=200)

        import requests
        with requests.Session() as session:
            session.headers.update({"User-Agent": config.user_agent})
            result = discovery._fetch_sitemap_urls(session)

        assert len(result) == 2

    @responses.activate
    def test_index_skips_untrusted_sub_sitemap(self, discovery, config):
        """Sub-sitemap URLs on a different domain should be skipped."""
        evil_url = "https://evil.example.com/sitemap.xml"
        index_xml = _sitemap_index_xml([evil_url])

        responses.add(responses.GET, config.fannie_sitemap_url, body=index_xml, status=200)

        import requests
        with requests.Session() as session:
            session.headers.update({"User-Agent": config.user_agent})
            result = discovery._fetch_sitemap_urls(session)

        assert result == []

    @responses.activate
    def test_index_handles_sub_sitemap_failure(self, discovery, config):
        """If a sub-sitemap fails to fetch, it is skipped without crashing."""
        sub_url = "https://selling-guide.fanniemae.com/sitemap-broken.xml"
        index_xml = _sitemap_index_xml([sub_url])

        responses.add(responses.GET, config.fannie_sitemap_url, body=index_xml, status=200)
        responses.add(responses.GET, sub_url, body="", status=500)

        import requests
        with requests.Session() as session:
            session.headers.update({"User-Agent": config.user_agent})
            result = discovery._fetch_sitemap_urls(session)

        assert result == []


# ---------------------------------------------------------------------------
# discover() end-to-end
# ---------------------------------------------------------------------------

class TestDiscover:
    def _build_large_sitemap(self, n: int = 250) -> str:
        """Build a sitemap with n valid /sel/ entries."""
        entries = []
        for i in range(n):
            code = f"b3-3.1-{i:02d}"
            entries.append((_make_fannie_url(code, "slug"), "2026-01-01"))
        return _sitemap_xml(entries)

    @responses.activate
    def test_returns_sorted_section_urls(self, discovery, config):
        """discover() should return SectionURL list sorted by section_code."""
        xml = _sitemap_xml([
            (_make_fannie_url("b3-3.1-02", "b"), None),
            (_make_fannie_url("a2-2-01", "a"), None),
            (_make_fannie_url("b3-3.1-01", "c"), None),
        ])
        responses.add(responses.GET, config.fannie_sitemap_url, body=xml, status=200)

        result = discovery.discover()
        codes = [u.section_code for u in result]
        assert codes == sorted(codes)

    @responses.activate
    def test_returns_section_url_objects(self, discovery, config):
        xml = _sitemap_xml([
            (_make_fannie_url("b3-3.1-01", "income"), "2026-01-15"),
        ])
        responses.add(responses.GET, config.fannie_sitemap_url, body=xml, status=200)

        result = discovery.discover()
        assert len(result) == 1
        section = result[0]
        assert section.source == GuideSource.FANNIE_MAE
        assert section.section_code == "B3-3.1-01"
        assert section.slug == "income"
        assert section.last_modified == "2026-01-15"

    @responses.activate
    def test_no_toc_fallback_when_sitemap_large_enough(self, discovery, config):
        """When sitemap has >= 200 URLs, the TOC fallback should NOT be called."""
        xml = self._build_large_sitemap(250)
        responses.add(responses.GET, config.fannie_sitemap_url, body=xml, status=200)

        result = discovery.discover()
        # Only the sitemap GET should have been made (no TOC request)
        assert len(responses.calls) == 1
        assert len(result) == 250

    @responses.activate
    def test_toc_fallback_triggered_when_sitemap_small(self, discovery, config):
        """When sitemap has < 200 URLs, TOC fallback is attempted."""
        small_xml = _sitemap_xml([
            (_make_fannie_url("b3-3.1-01", "income"), None),
        ])
        toc_html = """
        <html><body>
            <a href="/sel/b3-3.1-01/income">B3-3.1-01</a>
            <a href="/sel/a2-2-01/age">A2-2-01</a>
        </body></html>
        """
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"

        responses.add(responses.GET, config.fannie_sitemap_url, body=small_xml, status=200)
        responses.add(responses.GET, toc_url, body=toc_html, status=200)

        result = discovery.discover()
        # Should have merged: B3-3.1-01 from sitemap + A2-2-01 from TOC
        codes = {u.section_code for u in result}
        assert "B3-3.1-01" in codes
        assert "A2-2-01" in codes

    @responses.activate
    def test_toc_fallback_does_not_duplicate_existing(self, discovery, config):
        """TOC fallback should not add section codes already in sitemap results."""
        small_xml = _sitemap_xml([
            (_make_fannie_url("b3-3.1-01", "income"), "2026-01-01"),
        ])
        toc_html = """
        <html><body>
            <a href="/sel/b3-3.1-01/income">B3-3.1-01</a>
        </body></html>
        """
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"

        responses.add(responses.GET, config.fannie_sitemap_url, body=small_xml, status=200)
        responses.add(responses.GET, toc_url, body=toc_html, status=200)

        result = discovery.discover()
        assert len(result) == 1
        # The one from sitemap should be kept (it has lastmod)
        assert result[0].last_modified == "2026-01-01"

    @responses.activate
    def test_session_context_manager_used(self, discovery, config):
        """discover() uses a Session context manager, ensuring cleanup."""
        xml = _sitemap_xml([
            (_make_fannie_url("b3-3.1-01", "slug"), None),
        ])
        responses.add(responses.GET, config.fannie_sitemap_url, body=xml, status=200)

        # If session is used as context manager, no resource leak occurs.
        # We verify discover() completes without error (session.__exit__ called).
        result = discovery.discover()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @responses.activate
    def test_network_error_on_sitemap_returns_empty(self, discovery, config):
        """Network failure fetching sitemap should return empty (with fallback)."""
        responses.add(
            responses.GET, config.fannie_sitemap_url,
            body=RequestsConnectionError("DNS failure"),
        )
        # TOC fallback will also fail
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"
        responses.add(
            responses.GET, toc_url,
            body=RequestsConnectionError("DNS failure"),
        )

        result = discovery.discover()
        assert result == []

    @responses.activate
    def test_http_500_on_sitemap_returns_empty(self, discovery, config):
        responses.add(responses.GET, config.fannie_sitemap_url, body="error", status=500)
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"
        responses.add(responses.GET, toc_url, body="error", status=500)

        result = discovery.discover()
        assert result == []

    @responses.activate
    def test_malformed_sitemap_xml(self, discovery, config):
        """Badly formed XML should not crash; returns empty (with TOC fallback)."""
        responses.add(
            responses.GET, config.fannie_sitemap_url,
            body="<this is not valid xml &&&",
            status=200,
        )
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"
        responses.add(responses.GET, toc_url, body="<html></html>", status=200)

        result = discovery.discover()
        assert result == []

    @responses.activate
    def test_toc_fallback_network_failure(self, discovery, config):
        """If sitemap is small AND TOC fails, we still get sitemap results."""
        small_xml = _sitemap_xml([
            (_make_fannie_url("b3-3.1-01", "slug"), None),
        ])
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"

        responses.add(responses.GET, config.fannie_sitemap_url, body=small_xml, status=200)
        responses.add(
            responses.GET, toc_url,
            body=RequestsConnectionError("timeout"),
        )

        result = discovery.discover()
        assert len(result) == 1
        assert result[0].section_code == "B3-3.1-01"


# ---------------------------------------------------------------------------
# TOC crawl fallback
# ---------------------------------------------------------------------------

class TestTocCrawlFallback:
    @responses.activate
    def test_extracts_sel_links(self, discovery, config):
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"
        html = """
        <html><body>
            <a href="/sel/b3-3.1-01/income-info">B3-3.1-01</a>
            <a href="/sel/a2-2-01/allowable-age">A2-2-01</a>
            <a href="/other/page">Other</a>
        </body></html>
        """
        responses.add(responses.GET, toc_url, body=html, status=200)

        import requests
        with requests.Session() as session:
            session.headers.update({"User-Agent": config.user_agent})
            result = discovery._crawl_toc_fallback(session)

        assert len(result) == 2
        codes = {u.section_code for u in result}
        assert codes == {"B3-3.1-01", "A2-2-01"}

    @responses.activate
    def test_deduplicates_codes(self, discovery, config):
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"
        html = """
        <html><body>
            <a href="/sel/b3-3.1-01/income-info">Link 1</a>
            <a href="/sel/b3-3.1-01/income-info">Link 2</a>
        </body></html>
        """
        responses.add(responses.GET, toc_url, body=html, status=200)

        import requests
        with requests.Session() as session:
            session.headers.update({"User-Agent": config.user_agent})
            result = discovery._crawl_toc_fallback(session)

        assert len(result) == 1

    @responses.activate
    def test_skips_selling_guide_toc_link(self, discovery, config):
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"
        html = """
        <html><body>
            <a href="/sel/selling-guide">TOC</a>
            <a href="/sel/b3-3.1-01/slug">Section</a>
        </body></html>
        """
        responses.add(responses.GET, toc_url, body=html, status=200)

        import requests
        with requests.Session() as session:
            session.headers.update({"User-Agent": config.user_agent})
            result = discovery._crawl_toc_fallback(session)

        assert len(result) == 1

    @responses.activate
    def test_makes_relative_urls_absolute(self, discovery, config):
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"
        html = '<html><body><a href="/sel/b3-3.1-01/slug">X</a></body></html>'
        responses.add(responses.GET, toc_url, body=html, status=200)

        import requests
        with requests.Session() as session:
            session.headers.update({"User-Agent": config.user_agent})
            result = discovery._crawl_toc_fallback(session)

        assert result[0].url.startswith("https://")

    @responses.activate
    def test_toc_results_have_no_lastmod(self, discovery, config):
        toc_url = f"{config.fannie_base_url}/sel/selling-guide"
        html = '<html><body><a href="/sel/b3-3.1-01/slug">X</a></body></html>'
        responses.add(responses.GET, toc_url, body=html, status=200)

        import requests
        with requests.Session() as session:
            session.headers.update({"User-Agent": config.user_agent})
            result = discovery._crawl_toc_fallback(session)

        assert result[0].last_modified is None
