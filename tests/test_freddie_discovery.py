"""Tests for Freddie Mac URL discovery from sitemap."""

from __future__ import annotations

import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from gse_guides.config import ScraperConfig
from gse_guides.freddie_mac.discovery import FreddieMacDiscovery, _is_valid_url
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
    return FreddieMacDiscovery(config)


# ---------------------------------------------------------------------------
# Helpers
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


def _section_url(number: str) -> str:
    return f"https://guide.freddiemac.com/app/guide/section/{number}"


# ---------------------------------------------------------------------------
# _is_valid_url
# ---------------------------------------------------------------------------

class TestIsValidUrl:
    def test_valid_https_same_domain(self):
        assert _is_valid_url(
            "https://guide.freddiemac.com/app/guide/section/5703.1",
            "https://guide.freddiemac.com",
        )

    def test_rejects_http(self):
        assert not _is_valid_url(
            "http://guide.freddiemac.com/app/guide/section/5703.1",
            "https://guide.freddiemac.com",
        )

    def test_rejects_different_domain(self):
        assert not _is_valid_url(
            "https://evil.example.com/app/guide/section/5703.1",
            "https://guide.freddiemac.com",
        )

    def test_rejects_empty_string(self):
        assert not _is_valid_url("", "https://guide.freddiemac.com")


# ---------------------------------------------------------------------------
# Section number extraction
# ---------------------------------------------------------------------------

class TestExtractSectionNumber:
    @pytest.mark.parametrize(
        "url, expected",
        [
            (_section_url("5703.1"), "5703.1"),
            (_section_url("5703"), "5703"),
            (_section_url("1"), "1"),
            (_section_url("4201.15"), "4201.15"),
        ],
    )
    def test_extracts_numbers(self, discovery, url, expected):
        assert discovery._extract_section_number(url) == expected

    def test_returns_none_for_non_section_url(self, discovery):
        url = "https://guide.freddiemac.com/app/guide/chapter/42"
        assert discovery._extract_section_number(url) is None

    def test_returns_none_for_unrelated_url(self, discovery):
        url = "https://guide.freddiemac.com/app/guide/"
        assert discovery._extract_section_number(url) is None


# ---------------------------------------------------------------------------
# Chapter classification
# ---------------------------------------------------------------------------

class TestClassifyChapter:
    def test_single_part_number(self, discovery):
        assert discovery._classify_chapter("5703") == "chapter_5703"

    def test_decimal_section_number(self, discovery):
        assert discovery._classify_chapter("5703.1") == "chapter_5703"

    def test_small_number(self, discovery):
        assert discovery._classify_chapter("1") == "chapter_1"


# ---------------------------------------------------------------------------
# Sort key generation
# ---------------------------------------------------------------------------

class TestSortKey:
    def test_major_only(self, discovery):
        assert discovery._sort_key("5703") == (5703, 0)

    def test_major_and_minor(self, discovery):
        assert discovery._sort_key("5703.1") == (5703, 1)

    def test_ordering(self, discovery):
        keys = [
            discovery._sort_key("5703.2"),
            discovery._sort_key("5703.1"),
            discovery._sort_key("1.3"),
            discovery._sort_key("5703"),
        ]
        assert sorted(keys) == [
            (1, 3),
            (5703, 0),
            (5703, 1),
            (5703, 2),
        ]

    def test_non_numeric_returns_zero_tuple(self, discovery):
        assert discovery._sort_key("abc") == (0, 0)

    def test_partially_numeric(self, discovery):
        # "42.abc" — minor part is non-numeric
        assert discovery._sort_key("42.abc") == (0, 0)


# ---------------------------------------------------------------------------
# Sitemap XML parsing (_parse_sitemap_xml)
# ---------------------------------------------------------------------------

class TestParseSitemapXml:
    def test_filters_section_urls(self, discovery):
        xml = _sitemap_xml([
            (_section_url("5703.1"), "2026-01-01"),
            ("https://guide.freddiemac.com/app/guide/chapter/42", None),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert len(result) == 1
        assert result[0].section_code == "5703.1"

    def test_skips_untrusted_domain(self, discovery):
        xml = _sitemap_xml([
            ("https://evil.example.com/app/guide/section/5703.1", None),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert result == []

    def test_captures_lastmod(self, discovery):
        xml = _sitemap_xml([
            (_section_url("5703.1"), "2026-03-15"),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert result[0].last_modified == "2026-03-15"

    def test_lastmod_none_when_missing(self, discovery):
        xml = _sitemap_xml([
            (_section_url("5703.1"), None),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert result[0].last_modified is None

    def test_source_is_freddie_mac(self, discovery):
        xml = _sitemap_xml([
            (_section_url("5703.1"), None),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert result[0].source == GuideSource.FREDDIE_MAC

    def test_slug_is_section_number(self, discovery):
        xml = _sitemap_xml([
            (_section_url("5703.1"), None),
        ])
        result = discovery._parse_sitemap_xml(xml)
        assert result[0].slug == "5703.1"

    def test_empty_sitemap(self, discovery):
        xml = _sitemap_xml([])
        assert discovery._parse_sitemap_xml(xml) == []

    def test_url_tag_without_loc(self, discovery):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><lastmod>2026-01-01</lastmod></url>'
            '</urlset>'
        )
        assert discovery._parse_sitemap_xml(xml) == []


# ---------------------------------------------------------------------------
# discover() end-to-end
# ---------------------------------------------------------------------------

class TestDiscover:
    @responses.activate
    def test_returns_sorted_section_urls(self, discovery, config):
        xml = _sitemap_xml([
            (_section_url("5703.2"), None),
            (_section_url("1.3"), None),
            (_section_url("5703.1"), None),
        ])
        responses.add(responses.GET, config.freddie_sitemap_url, body=xml, status=200)

        result = discovery.discover()
        codes = [u.section_code for u in result]
        assert codes == ["1.3", "5703.1", "5703.2"]

    @responses.activate
    def test_returns_section_url_objects(self, discovery, config):
        xml = _sitemap_xml([
            (_section_url("5703.1"), "2026-03-15"),
        ])
        responses.add(responses.GET, config.freddie_sitemap_url, body=xml, status=200)

        result = discovery.discover()
        assert len(result) == 1
        s = result[0]
        assert s.source == GuideSource.FREDDIE_MAC
        assert s.section_code == "5703.1"
        assert s.url == _section_url("5703.1")

    @responses.activate
    def test_multiple_sections_all_returned(self, discovery, config):
        entries = [(_section_url(str(i)), None) for i in range(1, 51)]
        xml = _sitemap_xml(entries)
        responses.add(responses.GET, config.freddie_sitemap_url, body=xml, status=200)

        result = discovery.discover()
        assert len(result) == 50


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @responses.activate
    def test_network_failure_returns_empty(self, discovery, config):
        responses.add(
            responses.GET, config.freddie_sitemap_url,
            body=RequestsConnectionError("DNS failure"),
        )
        result = discovery.discover()
        assert result == []

    @responses.activate
    def test_http_500_returns_empty(self, discovery, config):
        responses.add(
            responses.GET, config.freddie_sitemap_url,
            body="server error", status=500,
        )
        result = discovery.discover()
        assert result == []

    @responses.activate
    def test_malformed_xml_returns_empty(self, discovery, config):
        responses.add(
            responses.GET, config.freddie_sitemap_url,
            body="<broken xml &&&",
            status=200,
        )
        result = discovery.discover()
        assert result == []
