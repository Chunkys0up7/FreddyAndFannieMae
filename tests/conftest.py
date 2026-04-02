"""Shared test fixtures for the GSE Guide Scraper test suite."""

from __future__ import annotations

import pytest

from gse_guides.config import ScraperConfig
from gse_guides.models import (
    GuideSection,
    GuideSource,
    SectionURL,
    SubSection,
)


@pytest.fixture
def config(tmp_path):
    """ScraperConfig with output pointing to a temp directory."""
    return ScraperConfig(
        output_dir=tmp_path / "output",
        enriched_dir=tmp_path / "enriched",
    )


@pytest.fixture
def fannie_section_url():
    """Sample Fannie Mae SectionURL."""
    return SectionURL(
        url="https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income-information",
        source=GuideSource.FANNIE_MAE,
        section_code="B3-3.1-01",
        slug="general-income-information",
        last_modified="2026-03-04",
    )


@pytest.fixture
def freddie_section_url():
    """Sample Freddie Mac SectionURL."""
    return SectionURL(
        url="https://guide.freddiemac.com/app/guide/section/5703.1",
        source=GuideSource.FREDDIE_MAC,
        section_code="5703.1",
        slug="5703-1",
    )


@pytest.fixture
def sample_guide_section():
    """A minimal GuideSection for unit tests."""
    return GuideSection(
        source=GuideSource.FANNIE_MAE,
        section_code="B3-3.1-01",
        title="General Income Information",
        url="https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income-information",
        part_code="B",
        part_name="Origination Through Closing",
        chapter_code="B3-3",
        chapter_name="Income Assessment",
        subpart_code="B3-3.1",
        subpart_name="General Income Requirements",
        content_html="<p>Test content about income verification.</p>",
        content_markdown="Test content about income verification.",
        subsections=[
            SubSection(
                heading="Stable Income",
                heading_level=2,
                anchor_id="stable-income",
                content_html="<p>Stable income requirements paragraph one.</p>",
                content_markdown="Stable income requirements paragraph one.",
                word_count=60,
                has_tables=False,
                has_lists=False,
            ),
            SubSection(
                heading="Continuance of Income",
                heading_level=2,
                anchor_id="continuance",
                content_html="<p>Income must be likely to continue for at least three years.</p>",
                content_markdown="Income must be likely to continue for at least three years.",
                word_count=80,
                has_tables=True,
                has_lists=False,
            ),
        ],
        effective_date="2026-03-04",
        word_count=3000,
        has_tables=True,
        table_count=1,
    )


SAMPLE_FANNIE_HTML = """\
<html>
<head><title>B3-3.1-01, General Income Information (03/04/2026)</title></head>
<body>
<nav class="breadcrumb">
  <a href="/">Home</a> &gt;
  <a href="/sel/b3-3">Part B - Origination</a> &gt;
  <a href="/sel/b3-3.1">Income Assessment</a>
</nav>
<div class="field field--name-body">
  <h1>B3-3.1-01, General Income Information</h1>
  <p>The lender must determine that the borrower has stable income.</p>
  <h2 id="stable-income">Stable and Predictable Income</h2>
  <p>Income must be stable and predictable to be considered qualifying.</p>
  <p>See also: <a href="/sel/b3-3.1-02/documentation">B3-3.1-02</a></p>
  <h2 id="continuance">Continuance of Income</h2>
  <p>The lender must verify that income is likely to continue.</p>
  <table><tr><th>Scenario</th><th>Required</th></tr>
  <tr><td>Employment</td><td>VOE</td></tr></table>
</div>
<div class="related-announcements">
  <h3>Related Announcements</h3>
  <table><tr><td>SEL-2026-02</td><td>03/04/2026</td><td>Income Update</td></tr></table>
</div>
</body>
</html>
"""
