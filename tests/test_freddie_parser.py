"""Tests for Freddie Mac rendered-HTML parser."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from gse_guides.freddie_mac.parser import FreddieMacParser
from gse_guides.models import GuideSource, SectionURL


# ---------------------------------------------------------------------------
# Realistic HTML fixtures
# ---------------------------------------------------------------------------

SAMPLE_FREDDIE_HTML = """\
<html>
<head><title>Section 5703.1 - Freddie Mac Single-Family Seller/Servicer Guide</title></head>
<body>
<div class="breadcrumb-trail">
  <a href="/">Home</a> &gt;
  <a href="/app/guide/chapter/5703">Chapter 5703</a> &gt;
  <span>Section 5703.1</span>
</div>
<div class="rn_Answer">
  <h1>5703.1: Mortgage Insurance Requirements</h1>
  <p>Effective: 01/15/2025</p>
  <p>The Seller must ensure that mortgage insurance coverage meets Freddie Mac requirements
  for all loans with an LTV ratio exceeding 80 percent. This section describes the
  requirements for private mortgage insurance including coverage amounts and approved
  insurers that Freddie Mac accepts for conventional conforming mortgages.</p>
  <h2 id="coverage">Coverage Requirements</h2>
  <p>Mortgage insurance coverage must be obtained from an approved mortgage insurer.
  The required coverage percentage depends on the LTV ratio of the mortgage.</p>
  <table>
    <tr><th>LTV Range</th><th>Required Coverage</th></tr>
    <tr><td>80.01% - 85%</td><td>12%</td></tr>
    <tr><td>85.01% - 90%</td><td>25%</td></tr>
    <tr><td>90.01% - 95%</td><td>30%</td></tr>
  </table>
  <h3 id="approved-insurers">Approved Insurers</h3>
  <p>Freddie Mac maintains a list of approved mortgage insurers. See
  <a href="/app/guide/section/5703.2">Section 5703.2</a> for the current list.</p>
  <ul>
    <li>Insurer must maintain required ratings</li>
    <li>Master policy must be on file</li>
  </ul>
  <h2 id="cancellation">Cancellation of MI</h2>
  <p>Mortgage insurance may be cancelled when the LTV ratio reaches 78 percent based
  on the original value of the property. See also
  <a href="/app/guide/section/4601.9">Section 4601.9</a> for servicing requirements.</p>
</div>
</body>
</html>
"""

MINIMAL_FREDDIE_HTML = """\
<html>
<head><title>Section 1301.1 - Freddie Mac Guide</title></head>
<body>
<div class="rn_Answer">
  <h1>1301.1: General Requirements</h1>
  <p>This section contains general seller requirements for doing business with
  Freddie Mac. These requirements apply to all Sellers and Servicers regardless
  of loan type or program.</p>
</div>
</body>
</html>
"""

EMPTY_FREDDIE_HTML = """\
<html><body><p>Tiny page.</p></body></html>
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def parser():
    return FreddieMacParser()


@pytest.fixture
def section_url():
    return SectionURL(
        url="https://guide.freddiemac.com/app/guide/section/5703.1",
        source=GuideSource.FREDDIE_MAC,
        section_code="5703.1",
        slug="5703-1",
    )


@pytest.fixture
def section_url_1301():
    return SectionURL(
        url="https://guide.freddiemac.com/app/guide/section/1301.1",
        source=GuideSource.FREDDIE_MAC,
        section_code="1301.1",
        slug="1301-1",
    )


# ---------------------------------------------------------------------------
# Full parse() integration
# ---------------------------------------------------------------------------

class TestParse:
    """Tests for the full parse() pipeline."""

    def test_parse_returns_guide_section(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert result.source == GuideSource.FREDDIE_MAC
        assert result.section_code == "5703.1"

    def test_parse_extracts_title(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert "Mortgage Insurance Requirements" in result.title

    def test_parse_has_content(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert len(result.content_html) > 0
        assert len(result.content_markdown) > 0
        assert "mortgage insurance" in result.content_markdown.lower()

    def test_parse_detects_tables(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert result.has_tables is True
        assert result.table_count >= 1

    def test_parse_extracts_subsections(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert len(result.subsections) >= 2
        headings = [s.heading for s in result.subsections]
        assert "Coverage Requirements" in headings

    def test_parse_extracts_cross_references(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert len(result.cross_references) >= 1
        codes = [r.target_section_code for r in result.cross_references]
        assert "5703.2" in codes

    def test_parse_word_count_positive(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert result.word_count > 0

    def test_parse_sets_scraped_at(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert result.scraped_at != ""

    def test_parse_url_preserved(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert result.url == "https://guide.freddiemac.com/app/guide/section/5703.1"


# ---------------------------------------------------------------------------
# Content extraction (_find_main_content)
# ---------------------------------------------------------------------------

class TestFindMainContent:

    def test_rn_answer_selector(self, parser):
        soup = BeautifulSoup(SAMPLE_FREDDIE_HTML, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "mortgage insurance" in result.get_text().lower()

    def test_rn_answer_detail_id(self, parser):
        html = """
        <html><body>
        <div id="rn_AnswerDetail">
          <p>Content with sufficient length to meet the hundred-character threshold
          so the parser will accept this element as the main content area.</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "sufficient length" in result.get_text()

    def test_answer_class_wildcard(self, parser):
        html = """
        <html><body>
        <div class="some-answer-container">
          <p>Answer container content that is long enough to pass the parser threshold
          of at least one hundred characters of stripped text content.</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None

    def test_content_class_wildcard(self, parser):
        html = """
        <html><body>
        <div class="main-content-area">
          <p>Main content area with quite a lot of text inside to ensure the character
          threshold is met. This should be the largest block of text on the page.</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None

    def test_main_tag_selector(self, parser):
        html = """
        <html><body>
        <main>
          <p>Semantic main element with enough content to be detected. This paragraph
          has plenty of text to pass the one hundred character threshold easily.</p>
        </main>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None

    def test_content_id_selector(self, parser):
        html = """
        <html><body>
        <div id="content">
          <p>Content div identified by its ID attribute. This paragraph is written
          to exceed one hundred characters so the parser can detect it properly.</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None

    def test_largest_div_fallback(self, parser):
        long_text = "Detailed guide content. " * 30
        html = f"""
        <html><body>
        <div class="sidebar"><p>Short</p></div>
        <div class="unknown-class"><p>{long_text}</p></div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "Detailed guide content" in result.get_text()

    def test_empty_page_returns_none(self, parser):
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is None

    def test_small_content_returns_none(self, parser):
        html = "<html><body><div class='rn_Answer'><p>Hi</p></div></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is None


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

class TestExtractTitle:

    def test_title_from_h1(self, parser):
        soup = BeautifulSoup(SAMPLE_FREDDIE_HTML, "lxml")
        title = parser._extract_title(soup, "5703.1")
        assert "Mortgage Insurance Requirements" in title

    def test_title_from_h2(self, parser):
        html = "<html><body><h2>Underwriting Standards</h2></body></html>"
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup, "3000.1")
        assert title == "Underwriting Standards"

    def test_title_from_title_tag(self, parser):
        html = "<html><head><title>Eligibility Requirements - Freddie Mac Guide</title></head><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup, "4000.1")
        assert title == "Eligibility Requirements"

    def test_title_fallback_section_number(self, parser):
        html = "<html><body><p>No headings</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup, "9999.1")
        assert title == "Section 9999.1"

    def test_short_h1_skipped(self, parser):
        html = "<html><body><h1>Hi</h1><h2>Actual Title Here</h2></body></html>"
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup, "1000.1")
        assert title == "Actual Title Here"

    def test_pipe_stripped_from_title_tag(self, parser):
        html = "<html><head><title>Section 5703.1 | Freddie Mac Guide</title></head><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup, "5703.1")
        # The regex strips " - Freddie Mac..." but the pipe is in the original text
        # The title tag fallback doesn't split on pipe, only strips " - Freddie Mac..."
        assert "5703.1" in title

    def test_dash_stripped_from_title_tag(self, parser):
        html = "<html><head><title>Property Standards - Freddie Mac Single-Family</title></head><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup, "5703.1")
        assert title == "Property Standards"


# ---------------------------------------------------------------------------
# Section metadata extraction
# ---------------------------------------------------------------------------

class TestExtractSectionMetadata:

    def test_chapter_5000_range(self, parser):
        soup = BeautifulSoup(SAMPLE_FREDDIE_HTML, "lxml")
        metadata = parser._extract_section_metadata(soup, "5703.1")
        assert metadata["chapter_code"] == "5703"
        assert metadata["part_code"] == "5"
        assert metadata["part_name"] == "Special Programs"

    def test_chapter_1000_range(self, parser, section_url_1301):
        soup = BeautifulSoup(MINIMAL_FREDDIE_HTML, "lxml")
        metadata = parser._extract_section_metadata(soup, "1301.1")
        assert metadata["chapter_code"] == "1301"
        assert metadata["part_code"] == "1"
        assert metadata["part_name"] == "General"

    def test_chapter_2000_range(self, parser):
        html = "<html><body><p>Content</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        metadata = parser._extract_section_metadata(soup, "2501.3")
        assert metadata["part_code"] == "2"
        assert metadata["part_name"] == "Requirements"

    def test_chapter_3000_range(self, parser):
        html = "<html><body><p>Content</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        metadata = parser._extract_section_metadata(soup, "3401.2")
        assert metadata["part_code"] == "3"
        assert metadata["part_name"] == "Underwriting"

    def test_chapter_4000_range(self, parser):
        html = "<html><body><p>Content</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        metadata = parser._extract_section_metadata(soup, "4601.9")
        assert metadata["part_code"] == "4"
        assert metadata["part_name"] == "Origination"

    def test_chapter_6000_range(self, parser):
        html = "<html><body><p>Content</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        metadata = parser._extract_section_metadata(soup, "6100.1")
        assert metadata["part_code"] == "6"
        assert metadata["part_name"] == "Quality Control"

    def test_non_numeric_chapter(self, parser):
        html = "<html><body><p>Content</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        metadata = parser._extract_section_metadata(soup, "abc.1")
        assert metadata["chapter_code"] == "abc"
        assert metadata["part_code"] == ""

    def test_effective_date_extraction(self, parser):
        soup = BeautifulSoup(SAMPLE_FREDDIE_HTML, "lxml")
        metadata = parser._extract_section_metadata(soup, "5703.1")
        assert metadata["effective_date"] == "2025-01-15"

    def test_no_effective_date(self, parser):
        html = "<html><body><p>No dates in this page at all.</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        metadata = parser._extract_section_metadata(soup, "1000.1")
        assert metadata["effective_date"] is None

    def test_breadcrumb_chapter_name(self, parser):
        soup = BeautifulSoup(SAMPLE_FREDDIE_HTML, "lxml")
        metadata = parser._extract_section_metadata(soup, "5703.1")
        # The breadcrumb div should provide chapter_name
        assert metadata["chapter_name"] != ""


# ---------------------------------------------------------------------------
# Table detection
# ---------------------------------------------------------------------------

class TestTableDetection:

    def test_tables_in_content(self, parser, section_url):
        result = parser.parse(SAMPLE_FREDDIE_HTML, section_url)
        assert result.has_tables is True
        assert result.table_count >= 1

    def test_no_tables(self, parser, section_url_1301):
        result = parser.parse(MINIMAL_FREDDIE_HTML, section_url_1301)
        assert result.has_tables is False
        assert result.table_count == 0


# ---------------------------------------------------------------------------
# Subsection splitting
# ---------------------------------------------------------------------------

class TestSplitSubsections:

    def test_splits_h2_and_h3(self, parser):
        html = """
        <div>
          <h2 id="sec-a">Section A</h2>
          <p>Paragraph under section A with some text.</p>
          <h3 id="sub-b">Sub Section B</h3>
          <p>Paragraph under sub section B.</p>
          <h2 id="sec-c">Section C</h2>
          <p>Paragraph under section C.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert len(subs) == 3
        assert subs[0].heading == "Section A"
        assert subs[0].heading_level == 2
        assert subs[1].heading == "Sub Section B"
        assert subs[1].heading_level == 3
        assert subs[2].heading == "Section C"

    def test_h4_also_captured(self, parser):
        """Freddie parser includes h4 unlike Fannie which only does h2/h3."""
        html = """
        <div>
          <h4 id="detail">Detail Heading</h4>
          <p>Content under h4 heading.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert len(subs) == 1
        assert subs[0].heading_level == 4

    def test_no_headings_returns_empty(self, parser):
        html = "<div><p>Just paragraphs, no headings at all.</p></div>"
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs == []

    def test_subsection_table_detection(self, parser):
        html = """
        <div>
          <h2>Table Section</h2>
          <table><tr><td>Data</td></tr></table>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs[0].has_tables is True

    def test_subsection_list_detection(self, parser):
        html = """
        <div>
          <h2>List Section</h2>
          <ol><li>First</li><li>Second</li></ol>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs[0].has_lists is True

    def test_anchor_id_captured(self, parser):
        html = """
        <div>
          <h2 id="my-anchor">Anchored Heading</h2>
          <p>Content here.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs[0].anchor_id == "my-anchor"

    def test_anchor_id_none_when_missing(self, parser):
        html = """
        <div>
          <h2>No Anchor</h2>
          <p>Content here.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs[0].anchor_id is None

    def test_word_count_per_subsection(self, parser):
        html = """
        <div>
          <h2>Counted Section</h2>
          <p>one two three four five six seven eight</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs[0].word_count >= 8


# ---------------------------------------------------------------------------
# Cross-reference extraction
# ---------------------------------------------------------------------------

class TestExtractCrossReferences:

    def test_extracts_guide_section_links(self, parser):
        html = """
        <div>
          <p>See <a href="/app/guide/section/5703.2">Section 5703.2</a> for details.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert len(refs) == 1
        assert refs[0].target_section_code == "5703.2"
        assert refs[0].link_text == "Section 5703.2"

    def test_ignores_non_guide_links(self, parser):
        html = """
        <div>
          <a href="https://freddiemac.com/about">About</a>
          <a href="/app/guide/chapter/5703">Chapter Link</a>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert refs == []

    def test_deduplicates_refs(self, parser):
        html = """
        <div>
          <p><a href="/app/guide/section/4601.9">4601.9</a></p>
          <p><a href="/app/guide/section/4601.9">4601.9 again</a></p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert len(refs) == 1

    def test_multiple_different_refs(self, parser):
        html = """
        <div>
          <p><a href="/app/guide/section/5703.2">5703.2</a></p>
          <p><a href="/app/guide/section/4601.9">4601.9</a></p>
          <p><a href="/app/guide/section/1301.1">1301.1</a></p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        codes = {r.target_section_code for r in refs}
        assert codes == {"5703.2", "4601.9", "1301.1"}

    def test_context_truncation(self, parser):
        long_text = "word " * 100
        html = f"""
        <div>
          <p>{long_text}<a href="/app/guide/section/1000.1">1000.1</a></p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert len(refs) == 1
        assert len(refs[0].context) <= 203  # 200 + "..."

    def test_integer_section_code(self, parser):
        """Sections without a dot (e.g., pure integer) should still match."""
        html = """
        <div>
          <p><a href="/app/guide/section/5703">Section 5703</a></p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert len(refs) == 1
        assert refs[0].target_section_code == "5703"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_html(self, parser, section_url):
        result = parser.parse("<html><body></body></html>", section_url)
        assert result.section_code == "5703.1"
        assert result.content_html == ""
        assert result.subsections == []
        assert result.cross_references == []
        assert result.has_tables is False
        assert result.table_count == 0

    def test_no_matching_selectors(self, parser, section_url):
        html = "<html><body><p>Tiny snippet.</p></body></html>"
        result = parser.parse(html, section_url)
        assert result.section_code == "5703.1"
        assert isinstance(result.content_markdown, str)

    def test_minimal_valid_page(self, parser, section_url_1301):
        result = parser.parse(MINIMAL_FREDDIE_HTML, section_url_1301)
        assert result.source == GuideSource.FREDDIE_MAC
        assert result.section_code == "1301.1"
        assert "General Requirements" in result.title
        assert result.word_count > 0
        assert result.has_tables is False

    def test_content_selectors_priority(self, parser):
        """rn_Answer should be preferred over a larger div."""
        html = """
        <html><body>
        <div class="rn_Answer">
          <p>This is the answer content that should be selected because rn_Answer
          is the highest priority selector in the list and has enough text.</p>
        </div>
        <div class="large-other-div">
          <p>""" + "Extra content. " * 50 + """</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "answer content" in result.get_text().lower()

    def test_malformed_html(self, parser, section_url):
        html = "<html><body><div class='rn_Answer'><p>Unclosed tags " + "x " * 100 + "</div></body></html>"
        result = parser.parse(html, section_url)
        assert result.section_code == "5703.1"
        assert result.word_count > 0
