"""Tests for the HTML to Markdown converter."""

from __future__ import annotations

from gse_guides.markdown_converter import MarkdownConverter
from gse_guides.models import GuideSource


class TestMarkdownConverter:
    def setup_method(self):
        self.converter = MarkdownConverter()

    def test_basic_html(self):
        html = "<p>Hello <strong>world</strong></p>"
        result = self.converter.convert(html, GuideSource.FANNIE_MAE)
        assert "Hello" in result
        assert "**world**" in result

    def test_strips_scripts(self):
        html = "<p>Content</p><script>alert('xss')</script>"
        result = self.converter.convert(html, GuideSource.FANNIE_MAE)
        assert "alert" not in result
        assert "Content" in result

    def test_strips_hidden_elements(self):
        html = '<p>Visible</p><div aria-hidden="true">Hidden</div>'
        result = self.converter.convert(html, GuideSource.FANNIE_MAE)
        assert "Visible" in result
        assert "Hidden" not in result

    def test_strips_inline_styles(self):
        html = '<p style="color: red;" class="special">Text</p>'
        result = self.converter.convert(html, GuideSource.FANNIE_MAE)
        assert "color" not in result
        assert "Text" in result

    def test_fannie_cross_reference_normalization(self):
        html = '<p>See <a href="/sel/b3-3.1-02/doc-requirements">B3-3.1-02</a></p>'
        result = self.converter.convert(html, GuideSource.FANNIE_MAE)
        assert "(B3-3.1-02)" in result.upper()

    def test_freddie_cross_reference_normalization(self):
        html = '<p>See <a href="/app/guide/section/5703.1">Section 5703.1</a></p>'
        result = self.converter.convert(html, GuideSource.FREDDIE_MAC)
        assert "(5703.1)" in result

    def test_normalizes_excessive_blank_lines(self):
        html = "<p>A</p><br><br><br><br><br><p>B</p>"
        result = self.converter.convert(html, GuideSource.FANNIE_MAE)
        # Should not have more than 3 consecutive newlines
        assert "\n\n\n\n" not in result

    def test_table_preserved(self):
        html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        result = self.converter.convert(html, GuideSource.FANNIE_MAE)
        assert "|" in result
