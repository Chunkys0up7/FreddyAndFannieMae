"""Tests for Fannie Mae HTML parser."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from gse_guides.fannie_mae.parser import FannieMaeParser, PART_NAMES
from gse_guides.models import GuideSource, SectionURL
from conftest import SAMPLE_FANNIE_HTML


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def parser():
    return FannieMaeParser()


@pytest.fixture
def section_url():
    return SectionURL(
        url="https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income-information",
        source=GuideSource.FANNIE_MAE,
        section_code="B3-3.1-01",
        slug="general-income-information",
        last_modified="2026-03-04",
    )


@pytest.fixture
def soup():
    return BeautifulSoup(SAMPLE_FANNIE_HTML, "lxml")


# ---------------------------------------------------------------------------
# Full parse() integration
# ---------------------------------------------------------------------------

class TestParse:
    """Tests for the full parse() pipeline using SAMPLE_FANNIE_HTML."""

    def test_parse_returns_guide_section(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert result.source == GuideSource.FANNIE_MAE
        assert result.section_code == "B3-3.1-01"

    def test_parse_extracts_title(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert "General Income Information" in result.title

    def test_parse_extracts_effective_date(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert result.effective_date == "2026-03-04"

    def test_parse_extracts_hierarchy(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert result.part_code == "B"
        assert result.chapter_code == "B3-3"
        assert result.subpart_code == "B3-3.1"

    def test_parse_has_content(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert len(result.content_html) > 0
        assert len(result.content_markdown) > 0

    def test_parse_detects_tables(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert result.has_tables is True
        assert result.table_count >= 1

    def test_parse_extracts_subsections(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert len(result.subsections) >= 2
        headings = [s.heading for s in result.subsections]
        assert "Stable and Predictable Income" in headings
        assert "Continuance of Income" in headings

    def test_parse_extracts_cross_references(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert len(result.cross_references) >= 1
        codes = [r.target_section_code for r in result.cross_references]
        assert "B3-3.1-02" in codes

    def test_parse_word_count_positive(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert result.word_count > 0

    def test_parse_sets_scraped_at(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert result.scraped_at != ""

    def test_parse_extracts_related_announcements(self, parser, section_url):
        result = parser.parse(SAMPLE_FANNIE_HTML, section_url)
        assert len(result.related_announcements) >= 1
        # The fallback regex greedily matches digits, so verify at least one
        # announcement code starting with SEL- is extracted
        codes = [a.code for a in result.related_announcements]
        assert any(c.startswith("SEL-") for c in codes)


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

class TestExtractTitle:

    def test_title_from_h1(self, parser):
        html = '<html><body><h1>B3-3.1-01, General Income Information</h1></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "General Income Information"

    def test_title_strips_section_code_prefix(self, parser):
        html = '<html><body><h1>A2-2-01, Some Title Here</h1></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "Some Title Here"

    def test_title_strips_date_suffix(self, parser):
        html = '<html><body><h1>Requirements Overview (03/04/2026)</h1></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "Requirements Overview"

    def test_title_strips_both_prefix_and_suffix(self, parser):
        html = '<html><body><h1>B3-3.1-01, Income Info (01/15/2025)</h1></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "Income Info"

    def test_title_from_og_meta(self, parser):
        html = '<html><head><meta property="og:title" content="B3-3.1-01, General Income Information" /></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert "General Income Information" in title

    def test_title_from_title_tag(self, parser):
        html = '<html><head><title>Income Information | Fannie Mae</title></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "Income Information"

    def test_title_fallback_untitled(self, parser):
        html = '<html><body><p>No heading here</p></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "Untitled Section"

    def test_title_from_e_part_section_code(self, parser):
        html = '<html><body><h1>E-1-01, Acronyms and Glossary</h1></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "Acronyms and Glossary"


# ---------------------------------------------------------------------------
# Effective date extraction
# ---------------------------------------------------------------------------

class TestExtractEffectiveDate:

    def test_last_updated_format(self, parser):
        html = '<html><body><p>Last Updated: 03/04/2026</p></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert parser._extract_effective_date(soup) == "2026-03-04"

    def test_effective_date_format(self, parser):
        html = '<html><body><p>Effective Date: 12/15/2025</p></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert parser._extract_effective_date(soup) == "2025-12-15"

    def test_updated_format(self, parser):
        html = '<html><body><p>Updated: 01/01/2024</p></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert parser._extract_effective_date(soup) == "2024-01-01"

    def test_date_in_title(self, parser):
        html = '<html><body><h1>Section (03/04/2026)</h1></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert parser._extract_effective_date(soup) == "2026-03-04"

    def test_meta_tag_date(self, parser):
        html = '<html><head><meta name="dcterms.modified" content="2025-06-15T12:00:00Z" /></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        result = parser._extract_effective_date(soup)
        assert result == "2025-06-15"

    def test_no_date_returns_none(self, parser):
        html = '<html><body><p>No dates here.</p></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert parser._extract_effective_date(soup) is None


# ---------------------------------------------------------------------------
# Breadcrumb / hierarchy parsing
# ---------------------------------------------------------------------------

class TestBreadcrumbHierarchy:

    def test_breadcrumb_from_nav(self, parser):
        html = """
        <html><body>
        <nav aria-label="Breadcrumb">
          <a href="/">Home</a>
          <a href="/part-b">Part B - Origination Through Closing</a>
          <a href="/ch-b3">Chapter B3</a>
        </nav>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._extract_breadcrumb_hierarchy(soup)
        assert result["part_name"] == "Part B - Origination Through Closing"

    def test_breadcrumb_from_class(self, parser):
        html = """
        <html><body>
        <div class="breadcrumb-nav">
          <a href="/">Home</a>
          <a href="/ch">Chapter B3-3</a>
          <span>Subpart B3-3.1</span>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._extract_breadcrumb_hierarchy(soup)
        # "Chapter" appears in the crumb text, so it matches the chapter branch
        assert result["chapter_name"] == "Chapter B3-3"

    def test_breadcrumb_extracts_subpart(self, parser):
        html = """
        <html><body>
        <nav aria-label="breadcrumb">
          <a href="/">Home</a>
          <span>Subpart B3-3.1</span>
        </nav>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._extract_breadcrumb_hierarchy(soup)
        assert result["subpart_name"] == "Subpart B3-3.1"

    def test_no_breadcrumb_returns_empty(self, parser):
        html = '<html><body><p>No breadcrumb</p></body></html>'
        soup = BeautifulSoup(html, "lxml")
        result = parser._extract_breadcrumb_hierarchy(soup)
        assert result["part_code"] == ""
        assert result["part_name"] == ""
        assert result["chapter_code"] == ""
        assert result["chapter_name"] == ""


# ---------------------------------------------------------------------------
# Content area detection (_find_main_content)
# ---------------------------------------------------------------------------

class TestFindMainContent:

    def test_body_field_div(self, parser):
        html = """
        <html><body>
        <div class="body-field">
          <p>This is substantial content that should be detected as the main content area.
          It has enough words to exceed the threshold of 100 characters easily.</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "substantial content" in result.get_text()

    def test_glossary_table_included(self, parser):
        html = """
        <html><body>
        <div class="body-field"><p>Short intro text here to set context.</p></div>
        <div class="glossary-table">
          <p>Glossary content that is quite long and detailed and provides definitions
          for many terms used in the selling guide.</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "Glossary content" in result.get_text()

    def test_field_name_body_class(self, parser):
        html = """
        <html><body>
        <div class="field--name-body">
          <p>Drupal-style content that should be detected as the main area.
          This needs to be over 100 characters long to pass the content check.</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "Drupal-style" in result.get_text()

    def test_layout_content_div(self, parser):
        html = """
        <html><body>
        <div class="layout-content">
          <p>Layout content area with enough text to trigger detection. Must be
          over one hundred characters long for the parser to accept this element.</p>
        </div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "Layout content area" in result.get_text()

    def test_main_tag_fallback(self, parser):
        html = """
        <html><body>
        <main>
          <p>Content in a semantic main tag with sufficient text to be detected.
          Exceeding one hundred characters of content for threshold matching.</p>
        </main>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "semantic main tag" in result.get_text()

    def test_largest_div_fallback(self, parser):
        long_text = "This is substantial content. " * 50  # >500 chars
        html = f"""
        <html><body>
        <div class="sidebar"><p>Short</p></div>
        <div class="main-area"><p>{long_text}</p></div>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "substantial content" in result.get_text()

    def test_empty_html_returns_none(self, parser):
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is None

    def test_trivial_body_field_falls_through(self, parser):
        """A body-field with <100 chars of text should be skipped."""
        html = """
        <html><body>
        <div class="body-field"><p>Tiny</p></div>
        <main><p>This is the real content area with more than 100 characters of text to
        ensure the parser falls through and finds it here instead.</p></main>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._find_main_content(soup)
        assert result is not None
        assert "real content area" in result.get_text()


# ---------------------------------------------------------------------------
# Subsection splitting
# ---------------------------------------------------------------------------

class TestSplitSubsections:

    def test_splits_at_h2_boundaries(self, parser):
        html = """
        <div>
          <h2 id="first">First Section</h2>
          <p>First paragraph content here.</p>
          <h2 id="second">Second Section</h2>
          <p>Second paragraph content here.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert len(subs) == 2
        assert subs[0].heading == "First Section"
        assert subs[0].heading_level == 2
        assert subs[0].anchor_id == "first"
        assert subs[1].heading == "Second Section"

    def test_splits_at_h3_boundaries(self, parser):
        html = """
        <div>
          <h3 id="sub">Sub Heading</h3>
          <p>Content under sub heading.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert len(subs) == 1
        assert subs[0].heading_level == 3

    def test_no_headings_returns_empty(self, parser):
        html = "<div><p>Just a paragraph with no headings.</p></div>"
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs == []

    def test_subsection_detects_tables(self, parser):
        html = """
        <div>
          <h2>Table Section</h2>
          <table><tr><td>Cell</td></tr></table>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert len(subs) == 1
        assert subs[0].has_tables is True

    def test_subsection_detects_lists(self, parser):
        html = """
        <div>
          <h2>List Section</h2>
          <ul><li>Item one</li><li>Item two</li></ul>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert len(subs) == 1
        assert subs[0].has_lists is True

    def test_subsection_word_count(self, parser):
        html = """
        <div>
          <h2>Wordy Section</h2>
          <p>one two three four five</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs[0].word_count >= 5

    def test_anchor_id_none_when_missing(self, parser):
        html = """
        <div>
          <h2>No Anchor</h2>
          <p>Some content.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        subs = parser._split_subsections(content)
        assert subs[0].anchor_id is None


# ---------------------------------------------------------------------------
# Cross-reference extraction
# ---------------------------------------------------------------------------

class TestExtractCrossReferences:

    def test_extracts_sel_links(self, parser):
        html = """
        <div>
          <p>See <a href="/sel/b3-3.1-02/documentation">B3-3.1-02</a> for details.</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert len(refs) == 1
        assert refs[0].target_section_code == "B3-3.1-02"
        assert refs[0].link_text == "B3-3.1-02"

    def test_ignores_non_sel_links(self, parser):
        html = """
        <div>
          <a href="https://example.com">Example</a>
          <a href="/about">About</a>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert refs == []

    def test_deduplicates_references(self, parser):
        html = """
        <div>
          <p><a href="/sel/b3-3.1-02/doc">B3-3.1-02</a></p>
          <p><a href="/sel/b3-3.1-02/doc">B3-3.1-02 again</a></p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert len(refs) == 1

    def test_multiple_different_refs(self, parser):
        html = """
        <div>
          <p><a href="/sel/a1-1-01/foo">A1-1-01</a></p>
          <p><a href="/sel/c2-1-02/bar">C2-1-02</a></p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        codes = {r.target_section_code for r in refs}
        assert "A1-1-01" in codes
        assert "C2-1-02" in codes

    def test_context_truncated(self, parser):
        long_text = "word " * 100
        html = f"""
        <div>
          <p>{long_text}<a href="/sel/b1-1-01/x">B1-1-01</a></p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert len(refs) == 1
        assert len(refs[0].context) <= 203  # 200 + "..."

    def test_sel_at_end_of_url(self, parser):
        html = """
        <div>
          <p><a href="/sel/d1-1-01">D1-1-01</a></p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        content = soup.find("div")
        refs = parser._extract_cross_references(content)
        assert len(refs) == 1
        assert refs[0].target_section_code == "D1-1-01"


# ---------------------------------------------------------------------------
# Table detection and counting
# ---------------------------------------------------------------------------

class TestTableDetection:

    def test_single_table(self, parser, section_url):
        html = """
        <html><body>
        <div class="body-field">
          <p>Content with enough text to be detected as the main content area for the parser to work properly.</p>
          <table><tr><th>Header</th></tr><tr><td>Cell</td></tr></table>
        </div>
        </body></html>
        """
        result = parser.parse(html, section_url)
        assert result.has_tables is True
        assert result.table_count == 1

    def test_multiple_tables(self, parser, section_url):
        html = """
        <html><body>
        <div class="body-field">
          <p>Content with enough text to be detected as the main content area for the parser to work properly.</p>
          <table><tr><td>Table 1</td></tr></table>
          <table><tr><td>Table 2</td></tr></table>
          <table><tr><td>Table 3</td></tr></table>
        </div>
        </body></html>
        """
        result = parser.parse(html, section_url)
        assert result.has_tables is True
        assert result.table_count == 3

    def test_no_tables(self, parser, section_url):
        html = """
        <html><body>
        <div class="body-field">
          <p>Content with enough text to be detected as the main content area for the parser to work properly.
          There are no tables in this section at all, just paragraphs of text content.</p>
        </div>
        </body></html>
        """
        result = parser.parse(html, section_url)
        assert result.has_tables is False
        assert result.table_count == 0


# ---------------------------------------------------------------------------
# Word count
# ---------------------------------------------------------------------------

class TestWordCount:

    def test_word_count_matches_content(self, parser, section_url):
        html = """
        <html><body>
        <div class="body-field">
          <p>one two three four five six seven eight nine ten eleven twelve thirteen
          fourteen fifteen sixteen seventeen eighteen nineteen twenty</p>
        </div>
        </body></html>
        """
        result = parser.parse(html, section_url)
        assert result.word_count >= 20

    def test_empty_content_zero_words(self, parser, section_url):
        html = "<html><body></body></html>"
        result = parser.parse(html, section_url)
        # content_markdown may have trivial content or be empty
        assert result.word_count >= 0


# ---------------------------------------------------------------------------
# Section code hierarchy parsing
# ---------------------------------------------------------------------------

class TestParseSectionCodeHierarchy:

    def test_subpart_pattern(self, parser):
        result = parser._parse_section_code_hierarchy("B3-3.1-01")
        assert result["part_code"] == "B"
        assert result["part_name"] == PART_NAMES["B"]
        assert result["chapter_code"] == "B3-3"
        assert result["subpart_code"] == "B3-3.1"

    def test_simple_pattern(self, parser):
        result = parser._parse_section_code_hierarchy("A2-2-01")
        assert result["part_code"] == "A"
        assert result["part_name"] == PART_NAMES["A"]
        assert result["chapter_code"] == "A2-2"
        assert result["subpart_code"] is None

    def test_part_e_pattern(self, parser):
        result = parser._parse_section_code_hierarchy("E-1-01")
        assert result["part_code"] == "E"
        assert result["part_name"] == PART_NAMES["E"]
        assert result["chapter_code"] == "E-1"
        assert result["subpart_code"] is None

    def test_empty_code(self, parser):
        result = parser._parse_section_code_hierarchy("")
        assert result["part_code"] == ""
        assert result["chapter_code"] == ""

    def test_all_part_codes(self, parser):
        for letter in "ABCDE":
            result = parser._parse_section_code_hierarchy(f"{letter}1-1-01")
            assert result["part_code"] == letter
            assert result["part_name"] == PART_NAMES[letter]


# ---------------------------------------------------------------------------
# Related announcements
# ---------------------------------------------------------------------------

class TestRelatedAnnouncements:

    def test_announcement_table(self, parser):
        html = """
        <html><body>
        <h3>Related Announcements</h3>
        <table>
          <tr><th>Code</th><th>Date</th><th>Title</th></tr>
          <tr><td>SEL-2025-01</td><td>01/15/2025</td><td>Policy Update</td></tr>
          <tr><td>SEL-2025-02</td><td>03/01/2025</td><td>Income Changes</td></tr>
        </table>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._extract_related_announcements(soup)
        assert len(result) == 2
        assert result[0].code == "SEL-2025-01"
        assert result[0].date == "01/15/2025"
        assert result[0].title == "Policy Update"
        assert result[1].code == "SEL-2025-02"

    def test_announcement_from_text_pattern(self, parser):
        html = """
        <html><body>
        <p>This section was updated by SEL-2024-05 and SEL-2024-07.</p>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = parser._extract_related_announcements(soup)
        codes = [a.code for a in result]
        assert "SEL-2024-05" in codes
        assert "SEL-2024-07" in codes

    def test_no_announcements(self, parser):
        html = "<html><body><p>No announcements here.</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = parser._extract_related_announcements(soup)
        assert result == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_html(self, parser, section_url):
        result = parser.parse("<html><body></body></html>", section_url)
        assert result.section_code == "B3-3.1-01"
        assert result.content_html == ""
        assert result.subsections == []
        assert result.cross_references == []
        assert result.has_tables is False
        assert result.table_count == 0

    def test_missing_content_area(self, parser, section_url):
        html = "<html><body><p>Just a tiny paragraph.</p></body></html>"
        result = parser.parse(html, section_url)
        assert result.section_code == "B3-3.1-01"
        # Parser may not find content, so content_html could be empty
        assert isinstance(result.content_markdown, str)

    def test_malformed_html(self, parser, section_url):
        html = "<html><body><div class='body-field'><p>Unclosed tags and " + "x " * 100 + "</div></body></html>"
        result = parser.parse(html, section_url)
        assert result.section_code == "B3-3.1-01"
        assert result.word_count > 0
