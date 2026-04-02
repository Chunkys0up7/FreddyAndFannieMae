"""Tests for the slugify utility."""

from __future__ import annotations

from gse_guides import slugify


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_characters(self):
        assert slugify("Income & Assets (2026)") == "income-assets-2026"

    def test_max_length(self):
        result = slugify("a" * 100, max_length=10)
        assert len(result) <= 10

    def test_strips_leading_trailing_dashes(self):
        assert slugify("--hello--") == "hello"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_collapses_whitespace(self):
        assert slugify("too   many   spaces") == "too-many-spaces"
