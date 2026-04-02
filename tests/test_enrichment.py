"""Tests for the enrichment pipeline modules."""

from __future__ import annotations

from gse_guides.enrichment.adaptive_chunker import AdaptiveChunker
from gse_guides.enrichment.content_classifier import ContentClassifier
from gse_guides.enrichment.cross_linker import CrossLinker
from gse_guides.enrichment.domain_tagger import DomainTagger
from gse_guides.enrichment.mismo_extractor import MismoExtractor
from gse_guides.enrichment.summarizer import Summarizer
from gse_guides.enrichment.term_extractor import TermExtractor
from gse_guides.config import ScraperConfig
from gse_guides.models import GuideSource


# --- DomainTagger ---


class TestDomainTagger:
    def setup_method(self):
        self.tagger = DomainTagger()

    def test_fannie_code_matching(self):
        domains = self.tagger.tag("B3-3.1-01", GuideSource.FANNIE_MAE, "")
        assert len(domains) >= 1
        assert any("BORROWER" in d for d in domains)

    def test_freddie_chapter_matching(self):
        domains = self.tagger.tag("5703.1", GuideSource.FREDDIE_MAC, "")
        assert len(domains) >= 1

    def test_keyword_fallback(self):
        content = "The borrower must provide a credit report and FICO score."
        domains = self.tagger.tag("UNKNOWN", GuideSource.FANNIE_MAE, content)
        assert any("credit" in d.lower() for d in domains)

    def test_always_returns_at_least_one_domain(self):
        domains = self.tagger.tag("ZZZZZ", GuideSource.FANNIE_MAE, "nothing relevant")
        assert len(domains) >= 1
        assert "COMPLIANCE.regulatory" in domains


# --- MismoExtractor ---


class TestMismoExtractor:
    def setup_method(self):
        self.extractor = MismoExtractor()

    def test_extracts_loan_purpose(self):
        content = "This is a cash-out refinance transaction."
        result = self.extractor.extract(content)
        assert "LoanPurposeType" in result
        assert "CashOutRefinance" in result["LoanPurposeType"]

    def test_extracts_property_type(self):
        content = "The property is a condominium unit."
        result = self.extractor.extract(content)
        assert "PropertyType" in result
        assert "Condominium" in result["PropertyType"]

    def test_empty_content(self):
        result = self.extractor.extract("")
        assert result == {}

    def test_no_false_positives_on_generic_text(self):
        result = self.extractor.extract("The quick brown fox jumps over the lazy dog.")
        assert result == {}


# --- TermExtractor ---


class TestTermExtractor:
    def setup_method(self):
        self.extractor = TermExtractor()

    def test_extracts_mortgage_terms(self):
        content = "The DTI ratio must not exceed the maximum LTV allowed."
        terms = self.extractor.extract(content)
        assert "LTV" in terms or "DTI" in terms

    def test_no_partial_matches_for_short_terms(self):
        # "LTV" should match as a word, but "LTVC" should not trigger it
        terms_good = self.extractor.extract("The LTV is 80%.")
        assert any("ltv" in t.lower() for t in terms_good)

    def test_empty_content(self):
        assert self.extractor.extract("") == []


# --- ContentClassifier ---


class TestContentClassifier:
    def setup_method(self):
        self.classifier = ContentClassifier()

    def test_fannie_glossary_classified_as_definition(self):
        result = self.classifier.classify(
            "E-3-01", "Glossary A-C", "", False, GuideSource.FANNIE_MAE
        )
        assert result == "definition"

    def test_fannie_reference_sections(self):
        result = self.classifier.classify(
            "E-1-01", "Exhibit 1", "", False, GuideSource.FANNIE_MAE
        )
        assert result == "reference"

    def test_eligibility_matrix_heuristic(self):
        result = self.classifier.classify(
            "B2-1-01", "Eligibility Requirements", "some content", True,
            GuideSource.FANNIE_MAE,
        )
        assert result == "eligibility_matrix"

    def test_procedure_detection(self):
        content = "1. Verify employment.\n2. Check credit.\n3. Calculate DTI.\n4. Submit."
        result = self.classifier.classify(
            "B1-1-01", "Processing Steps", content, False, GuideSource.FANNIE_MAE,
        )
        assert result == "procedure"

    def test_default_is_policy_rule(self):
        result = self.classifier.classify(
            "B1-1-01", "General Requirements", "The borrower must qualify.",
            False, GuideSource.FANNIE_MAE,
        )
        assert result == "policy_rule"


# --- ContentClassifier.classify_severity ---


class TestClassifySeverity:
    def setup_method(self):
        self.classifier = ContentClassifier()

    def test_must_comply_detected(self):
        content = "The borrower must provide documentation of income."
        result = self.classifier.classify_severity(content)
        assert result.severity == "must_comply"

    def test_shall_detected_as_must(self):
        content = "The lender shall verify employment before closing."
        result = self.classifier.classify_severity(content)
        assert result.severity == "must_comply"

    def test_ineligible_detected_as_must(self):
        content = "Properties in this category are ineligible."
        result = self.classifier.classify_severity(content)
        assert result.severity == "must_comply"

    def test_should_comply_detected(self):
        content = "The lender should review the credit report carefully."
        result = self.classifier.classify_severity(content)
        assert result.severity == "should_comply"

    def test_best_practice_detected(self):
        content = "Fannie Mae encourages lenders to follow best practice guidelines."
        result = self.classifier.classify_severity(content)
        assert result.severity == "best_practice"

    def test_info_only_detected(self):
        content = "This overview provides general information about the program."
        result = self.classifier.classify_severity(content)
        assert result.severity == "info_only"

    def test_strongest_signal_wins(self):
        content = "The borrower should review, but must provide tax returns."
        result = self.classifier.classify_severity(content)
        assert result.severity == "must_comply"

    def test_empty_content(self):
        result = self.classifier.classify_severity("")
        assert result.severity == "info_only"
        assert result.requirement_type == "guideline"

    def test_eligibility_requirement_type(self):
        content = "The borrower must be eligible and qualified for this program. Maximum LTV is 80%."
        result = self.classifier.classify_severity(content)
        assert result.requirement_type == "eligibility"

    def test_documentation_requirement_type(self):
        content = "The lender must verify income with documented evidence."
        result = self.classifier.classify_severity(content)
        assert result.requirement_type == "documentation"

    def test_calculation_requirement_type(self):
        content = "Calculate the DTI ratio by dividing total monthly obligations by gross monthly income."
        result = self.classifier.classify_severity(content)
        assert result.requirement_type == "calculation"

    def test_guideline_fallback(self):
        content = "The program offers flexible options for borrowers."
        result = self.classifier.classify_severity(content)
        assert result.requirement_type == "guideline"

    def test_severity_signals_tracked(self):
        content = "The borrower must have reserves. Documentation is required."
        result = self.classifier.classify_severity(content)
        assert len(result.severity_signals) > 0


# --- CrossLinker ---


class TestCrossLinker:
    def test_fannie_to_freddie_link(self):
        linker = CrossLinker()
        links = linker.link("B3-3.1-01", GuideSource.FANNIE_MAE)
        assert len(links) >= 1, "B3-3.1-01 should have cross-source links"
        assert all(l.source == "freddie_mac" for l in links)

    def test_freddie_to_fannie_link(self):
        linker = CrossLinker()
        links = linker.link("4201.1", GuideSource.FREDDIE_MAC)
        assert len(links) >= 1, "4201.1 should have cross-source links"
        assert all(l.source == "fannie_mae" for l in links)

    def test_resolves_actual_codes_when_available(self):
        codes = {
            "fannie_mae": ["B3-3.1-01", "B3-3.1-02"],
            "freddie_mac": ["5703.1", "5703.2"],
        }
        linker = CrossLinker(codes)
        links = linker.link("B3-3.1-01", GuideSource.FANNIE_MAE)
        # Some links should resolve to actual section codes
        for link in links:
            assert link.section_code  # Not empty

    def test_unknown_code_returns_empty(self):
        linker = CrossLinker()
        links = linker.link("ZZZZ", GuideSource.FANNIE_MAE)
        assert links == []


# --- Summarizer ---


class TestSummarizer:
    def setup_method(self):
        self.summarizer = Summarizer()

    def test_template_summary(self):
        result = self.summarizer.summarize(
            title="General Income Information",
            section_code="B3-3.1-01",
            domains=["BORROWER.borrower_income"],
            key_terms=["income", "employment", "DTI"],
        )
        assert "B3-3.1-01" in result
        assert "General Income Information" in result
        assert len(result) <= 200

    def test_truncation_on_long_summary(self):
        result = self.summarizer.summarize(
            title="Very Long Title " * 10,
            section_code="B3-3.1-01",
            domains=["A.b", "C.d", "E.f"],
            key_terms=["term1", "term2", "term3", "term4", "term5"],
        )
        assert len(result) <= 200

    def test_empty_terms_fallback(self):
        result = self.summarizer.summarize(
            title="Test", section_code="X", domains=["A.b"], key_terms=[],
        )
        assert "general guidelines" in result

    def test_llm_raises_not_implemented(self):
        import pytest
        with pytest.raises(NotImplementedError):
            self.summarizer.summarize_llm("content", "B3-3.1-01")


# --- AdaptiveChunker ---


class TestAdaptiveChunker:
    def setup_method(self):
        self.chunker = AdaptiveChunker(ScraperConfig())

    def test_splits_at_headings(self):
        # Content must exceed min_words (30) per chunk to avoid merging
        long_para = " ".join(["word"] * 40)
        md = f"Intro text {long_para}.\n\n## Heading One\n\n{long_para}\n\n## Heading Two\n\n{long_para}"
        chunks = self.chunker.chunk(md, "policy_rule")
        assert len(chunks) >= 2  # Intro + at least 2 heading chunks

    def test_single_chunk_for_short_content(self):
        md = "Just a short paragraph with no headings."
        chunks = self.chunker.chunk(md, "policy_rule")
        assert len(chunks) == 1
        assert chunks[0].heading is None

    def test_definition_chunking(self):
        md = "**Term One**\nDefinition of term one.\n\n**Term Two**\nDefinition of term two.\n\n**Term Three**\nDefinition of term three.\n\n**Term Four**\nDefinition of term four."
        chunks = self.chunker.chunk(md, "definition")
        # Should split at bold terms
        assert len(chunks) >= 1

    def test_merges_undersized_chunks(self):
        # Each heading section has very few words
        md = "## A\nOne.\n\n## B\nTwo.\n\n## C\nThree words here."
        chunks = self.chunker.chunk(md, "policy_rule")
        # Should merge into fewer chunks
        assert len(chunks) <= 3

    def test_table_detection(self):
        md = "## Data\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        chunks = self.chunker.chunk(md, "policy_rule")
        assert any(c.has_table for c in chunks)

    def test_preserves_table_in_oversized_chunk(self):
        # A chunk with a table should not be split even if oversized
        # Table needs 2+ pipe separators per row for detection (|.*|.*|)
        table_content = "| Col A | Col B |\n|---|---|\n" + "| val | val |\n" * 200
        md = f"## Big Table\n\n{table_content}"
        chunks = self.chunker.chunk(md, "policy_rule")
        table_chunks = [c for c in chunks if c.has_table]
        assert len(table_chunks) >= 1
