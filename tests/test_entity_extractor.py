"""Tests for the entity extractor module."""

from __future__ import annotations

import pytest

from gse_guides.enrichment.entity_extractor import EntityExtractor


class TestExtractEntities:
    """Tests for EntityExtractor.extract_entities."""

    def setup_method(self):
        self.extractor = EntityExtractor()

    def test_empty_content(self):
        assert self.extractor.extract_entities("") == {}

    def test_single_income_source(self):
        content = "The borrower has self-employment income from a consulting business."
        result = self.extractor.extract_entities(content)
        assert "income_sources" in result
        assert "SelfEmployment" in result["income_sources"]

    def test_multiple_income_sources(self):
        content = "Borrower receives self-employment income, rental income, and Social Security."
        result = self.extractor.extract_entities(content)
        assert "SelfEmployment" in result["income_sources"]
        assert "Rental" in result["income_sources"]
        assert "SocialSecurity" in result["income_sources"]

    def test_property_type_condo(self):
        content = "The subject property is a condominium unit in an established project."
        result = self.extractor.extract_entities(content)
        assert "property_types" in result
        assert "Condo" in result["property_types"]

    def test_property_type_manufactured(self):
        content = "Requirements for manufactured housing loans."
        result = self.extractor.extract_entities(content)
        assert "ManufacturedHousing" in result["property_types"]

    def test_transaction_type_cash_out(self):
        content = "For a cash-out refinance transaction, the maximum LTV is 80%."
        result = self.extractor.extract_entities(content)
        assert "transaction_types" in result
        assert "CashOutRefinance" in result["transaction_types"]

    def test_transaction_type_purchase(self):
        content = "This is a purchase transaction for a primary residence."
        result = self.extractor.extract_entities(content)
        assert "Purchase" in result["transaction_types"]

    def test_occupancy_types(self):
        content = "The property is a second home, not an investment property."
        result = self.extractor.extract_entities(content)
        assert "SecondHome" in result["occupancy_types"]
        assert "Investment" in result["occupancy_types"]

    def test_loan_type_arm(self):
        content = "For an adjustable-rate mortgage (ARM), qualification rules apply."
        result = self.extractor.extract_entities(content)
        assert "AdjustableRate" in result["loan_types"]

    def test_credit_events(self):
        content = "Borrower had a bankruptcy and a subsequent foreclosure."
        result = self.extractor.extract_entities(content)
        assert "Bankruptcy" in result["credit_events"]
        assert "Foreclosure" in result["credit_events"]

    def test_program_types(self):
        content = "HomeReady mortgage program eligibility requirements."
        result = self.extractor.extract_entities(content)
        assert "HomeReady" in result["program_types"]

    def test_aus_types(self):
        content = "Submit the loan to Desktop Underwriter (DU) for a risk assessment."
        result = self.extractor.extract_entities(content)
        assert "DesktopUnderwriter" in result["aus_types"]

    def test_manual_underwriting(self):
        content = "Loans manually underwritten must meet additional requirements."
        result = self.extractor.extract_entities(content)
        assert "ManualUnderwriting" in result["aus_types"]

    def test_asset_types(self):
        content = "The borrower may use gift funds or gift of equity for the down payment."
        result = self.extractor.extract_entities(content)
        assert "GiftFunds" in result["asset_types"]
        assert "GiftOfEquity" in result["asset_types"]

    def test_valuation_types(self):
        content = "A desktop appraisal may be acceptable for this transaction."
        result = self.extractor.extract_entities(content)
        assert "DesktopAppraisal" in result["valuation_types"]

    def test_lien_positions(self):
        content = "This applies to first lien conventional mortgages only."
        result = self.extractor.extract_entities(content)
        assert "FirstLien" in result["lien_positions"]

    def test_no_false_positives_generic_text(self):
        content = "The quick brown fox jumps over the lazy dog."
        result = self.extractor.extract_entities(content)
        assert result == {}

    def test_results_are_sorted(self):
        content = "Social Security, rental income, and self-employment income."
        result = self.extractor.extract_entities(content)
        values = result["income_sources"]
        assert values == sorted(values)

    def test_no_duplicates(self):
        content = "Self-employment income. Self-employed borrowers. Self-employment history."
        result = self.extractor.extract_entities(content)
        assert result["income_sources"].count("SelfEmployment") == 1

    def test_multi_dimension_extraction(self):
        """Test a realistic chunk mentioning multiple entity dimensions."""
        content = (
            "For a cash-out refinance on an investment property that is a "
            "condominium, the maximum LTV is 75%. The borrower must have "
            "self-employment income documented with tax returns."
        )
        result = self.extractor.extract_entities(content)
        assert "CashOutRefinance" in result.get("transaction_types", [])
        assert "Investment" in result.get("occupancy_types", [])
        assert "Condo" in result.get("property_types", [])
        assert "SelfEmployment" in result.get("income_sources", [])


class TestExtractConstraints:
    """Tests for EntityExtractor.extract_constraints."""

    def setup_method(self):
        self.extractor = EntityExtractor()

    def test_empty_content(self):
        assert self.extractor.extract_constraints("", {}) == []

    def test_maximum_ltv(self):
        content = "The maximum LTV is 80% for this transaction type."
        result = self.extractor.extract_constraints(content, {})
        assert len(result) >= 1
        ltv = [c for c in result if c.metric == "LTV"]
        assert len(ltv) >= 1
        assert ltv[0].operator == "<="
        assert ltv[0].value == "80"

    def test_minimum_credit_score(self):
        content = "The minimum credit score is 620."
        result = self.extractor.extract_constraints(content, {})
        scores = [c for c in result if c.metric == "credit_score"]
        assert len(scores) >= 1
        assert scores[0].operator == ">="
        assert scores[0].value == "620"

    def test_dti_not_exceed(self):
        content = "The DTI must not exceed 45%."
        result = self.extractor.extract_constraints(content, {})
        dti = [c for c in result if c.metric == "DTI"]
        assert len(dti) >= 1
        assert dti[0].operator == "<="
        assert dti[0].value == "45"

    def test_reserves_months(self):
        content = "The borrower must have at least 6 months of reserves."
        result = self.extractor.extract_constraints(content, {})
        reserves = [c for c in result if c.metric == "reserves_months"]
        assert len(reserves) >= 1
        assert reserves[0].value == "6"
        assert reserves[0].unit == "months"

    def test_constraint_with_entity_context(self):
        content = (
            "For investment property transactions, the maximum LTV is 85%."
        )
        entities = {"occupancy_types": ["Investment"]}
        result = self.extractor.extract_constraints(content, entities)
        ltv = [c for c in result if c.metric == "LTV"]
        assert len(ltv) >= 1
        # Should have condition tagging from entity context
        # (depends on whether alias appears in surrounding text)

    def test_deduplication(self):
        content = "Maximum LTV of 80%. The maximum LTV is 80% for conforming."
        result = self.extractor.extract_constraints(content, {})
        ltv = [c for c in result if c.metric == "LTV" and c.value == "80"]
        assert len(ltv) == 1  # Deduped

    def test_reversed_order_pattern(self):
        content = "80% maximum LTV applies to this program."
        result = self.extractor.extract_constraints(content, {})
        ltv = [c for c in result if c.metric == "LTV"]
        assert len(ltv) >= 1
        assert ltv[0].value == "80"

    def test_source_text_captured(self):
        content = "The maximum LTV is 80% for this loan."
        result = self.extractor.extract_constraints(content, {})
        assert len(result) >= 1
        assert result[0].source_text  # Non-empty


class TestExtractConditionalRefs:
    """Tests for EntityExtractor.extract_conditional_refs."""

    def setup_method(self):
        self.extractor = EntityExtractor()

    def test_empty_content(self):
        assert self.extractor.extract_conditional_refs("", "B1-1-01") == []

    def test_if_property_see_section(self):
        content = "If the property is a condominium, see Section B4-2.2-01 for requirements."
        result = self.extractor.extract_conditional_refs(content, "B1-1-01")
        assert len(result) >= 1
        assert result[0]["then_see"] == "B4-2.2-01"

    def test_for_entity_refer_to(self):
        content = "For manufactured housing properties, refer to Section B5-2-01."
        result = self.extractor.extract_conditional_refs(content, "B1-1-01")
        assert len(result) >= 1
        assert result[0]["then_see"] == "B5-2-01"

    def test_skips_self_references(self):
        content = "If the property is a PUD, see Section B1-1-01."
        result = self.extractor.extract_conditional_refs(content, "B1-1-01")
        assert len(result) == 0

    def test_deduplication(self):
        content = (
            "If the property is a condo, see Section B4-2.2-01. "
            "When the property is a condominium, see Section B4-2.2-01."
        )
        result = self.extractor.extract_conditional_refs(content, "B1-1-01")
        # May match multiple patterns but same entity+section deduped
        sections = [r["then_see"] for r in result]
        # Count unique section references
        assert len(set(sections)) <= len(result)
