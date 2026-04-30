from pipeline.processing.section_extractor import (
    fannie_extract_from_url,
    freddie_extract_from_text,
)


def test_fannie_extract_personal_gifts():
    meta = fannie_extract_from_url(
        "https://selling-guide.fanniemae.com/sel/b3-4.3-04/personal-gifts"
    )
    assert meta is not None
    assert meta.section_number == "B3-4.3-04"
    assert "Personal Gifts" in meta.section_title
    assert meta.agency == "fannie"


def test_fannie_extract_multi_word_slug():
    meta = fannie_extract_from_url(
        "https://selling-guide.fanniemae.com/sel/b1-1-03/allowable-age-of-credit-documents"
    )
    assert meta is not None
    assert meta.section_number == "B1-1-03"
    assert "Allowable" in meta.section_title


def test_fannie_extract_returns_none_for_non_section_url():
    assert fannie_extract_from_url("https://selling-guide.fanniemae.com/about") is None


def test_freddie_section_detection():
    text = "1101.1 General Authority\nThis section establishes…\n\n1101.2 Definitions\nKey terms used…"
    sections = freddie_extract_from_text(text)
    assert len(sections) == 2
    assert sections[0].section_number == "1101.1"
    assert "General Authority" in sections[0].section_title


def test_freddie_section_detection_with_chapter():
    text = "Chapter 11 — Originator Approval\nIntro text\n\n1101.1 Authority\nDetails"
    sections = freddie_extract_from_text(text)
    assert any(s.section_number == "11" for s in sections)
    assert any(s.section_number == "1101.1" for s in sections)
