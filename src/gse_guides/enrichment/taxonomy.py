"""Domain taxonomy, MISMO enumerations, mortgage terms, and cross-source mappings."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Domain Taxonomy
#    8 top-level domains, ~30 sub-domains aligned with MISMO containers.
# ---------------------------------------------------------------------------

DOMAIN_TAXONOMY: dict[str, list[str]] = {
    "LOAN": [
        "loan_purpose",
        "loan_type",
        "loan_amortization",
        "loan_limits",
        "loan_term",
    ],
    "BORROWER": [
        "borrower_eligibility",
        "borrower_income",
        "borrower_assets",
        "borrower_credit",
        "borrower_liabilities",
    ],
    "PROPERTY": [
        "property_type",
        "property_eligibility",
        "property_valuation",
        "property_insurance",
    ],
    "UNDERWRITING": [
        "manual_underwriting",
        "du_automated",
        "project_standards",
        "special_programs",
    ],
    "CLOSING": [
        "legal_documents",
        "title_requirements",
        "closing_process",
    ],
    "DELIVERY": [
        "execution_options",
        "loan_delivery",
        "mbs_securitization",
        "servicing",
    ],
    "QUALITY_CONTROL": [
        "lender_qc",
        "gse_qc",
        "representations",
    ],
    "COMPLIANCE": [
        "regulatory",
        "fraud_prevention",
        "data_integrity",
    ],
}

# ---------------------------------------------------------------------------
# 2. Fannie Mae section-code prefix → domain mapping
#    Longest-prefix-first matching: "B2-1.2" matches before "B2-1" before "B2".
# ---------------------------------------------------------------------------

FANNIE_DOMAIN_MAP: dict[str, list[str]] = {
    # Part A
    "A1":       ["COMPLIANCE.regulatory"],
    "A2-1":     ["COMPLIANCE.regulatory"],
    "A2-2":     ["QUALITY_CONTROL.representations"],
    "A2-3":     ["QUALITY_CONTROL.representations"],
    "A2-4":     ["COMPLIANCE.data_integrity"],
    "A2-5":     ["COMPLIANCE.regulatory"],
    "A3-1":     ["COMPLIANCE.regulatory"],
    "A3-2":     ["COMPLIANCE.regulatory"],
    "A3-3":     ["DELIVERY.servicing"],
    "A3-4":     ["COMPLIANCE.data_integrity", "COMPLIANCE.fraud_prevention"],
    "A3-5":     ["COMPLIANCE.regulatory"],
    "A4":       ["COMPLIANCE.regulatory"],
    # Part B
    "B1":       ["UNDERWRITING.manual_underwriting"],
    "B2-1.1":   ["PROPERTY.property_eligibility"],
    "B2-1.2":   ["LOAN.loan_purpose", "LOAN.loan_limits"],
    "B2-1.3":   ["LOAN.loan_purpose"],
    "B2-1.4":   ["LOAN.loan_amortization"],
    "B2-1.5":   ["LOAN.loan_limits", "LOAN.loan_term"],
    "B2-2":     ["BORROWER.borrower_eligibility"],
    "B2-3":     ["PROPERTY.property_eligibility", "PROPERTY.property_type"],
    "B3-1":     ["UNDERWRITING.manual_underwriting"],
    "B3-2":     ["UNDERWRITING.du_automated"],
    "B3-3.1":   ["BORROWER.borrower_income"],
    "B3-3.2":   ["BORROWER.borrower_income"],
    "B3-3.3":   ["BORROWER.borrower_income"],
    "B3-3.4":   ["BORROWER.borrower_income"],
    "B3-3.5":   ["BORROWER.borrower_income"],
    "B3-3.6":   ["BORROWER.borrower_income"],
    "B3-3.7":   ["BORROWER.borrower_income"],
    "B3-3.8":   ["BORROWER.borrower_income"],
    "B3-4.1":   ["BORROWER.borrower_assets"],
    "B3-4.2":   ["BORROWER.borrower_assets"],
    "B3-4.3":   ["BORROWER.borrower_assets"],
    "B3-4.4":   ["BORROWER.borrower_assets"],
    "B3-5":     ["BORROWER.borrower_credit"],
    "B3-6":     ["BORROWER.borrower_liabilities"],
    "B4-1":     ["PROPERTY.property_valuation"],
    "B4-2":     ["UNDERWRITING.project_standards"],
    "B5-1":     ["UNDERWRITING.special_programs", "LOAN.loan_limits"],
    "B5-2":     ["UNDERWRITING.special_programs", "PROPERTY.property_type"],
    "B5-3":     ["UNDERWRITING.special_programs"],
    "B5-4":     ["UNDERWRITING.special_programs"],
    "B5-5":     ["UNDERWRITING.special_programs"],
    "B5-6":     ["UNDERWRITING.special_programs"],
    "B5-7":     ["UNDERWRITING.special_programs"],
    "B6":       ["LOAN.loan_type"],
    "B7-1":     ["PROPERTY.property_insurance"],
    "B7-2":     ["CLOSING.title_requirements"],
    "B7-3":     ["PROPERTY.property_insurance"],
    "B7-4":     ["PROPERTY.property_insurance"],
    "B8":       ["CLOSING.legal_documents"],
    # Part C
    "C1":       ["DELIVERY.execution_options"],
    "C2":       ["DELIVERY.loan_delivery"],
    "C3":       ["DELIVERY.mbs_securitization"],
    # Part D
    "D1":       ["QUALITY_CONTROL.lender_qc"],
    "D2":       ["QUALITY_CONTROL.gse_qc"],
    # Part E
    "E-1":      ["COMPLIANCE.regulatory"],
    "E-2":      ["COMPLIANCE.regulatory"],
    "E-3":      ["COMPLIANCE.regulatory"],
}

# ---------------------------------------------------------------------------
# 3. Freddie Mac chapter-range → domain mapping
#    Tuples are (start_chapter, end_chapter) inclusive.
# ---------------------------------------------------------------------------

FREDDIE_DOMAIN_MAP: list[tuple[int, int, list[str]]] = [
    (1101, 1199, ["COMPLIANCE.regulatory"]),
    (1201, 1299, ["COMPLIANCE.regulatory"]),
    (1301, 1399, ["COMPLIANCE.regulatory", "DELIVERY.servicing"]),
    (1401, 1499, ["COMPLIANCE.regulatory"]),
    (1501, 1599, ["COMPLIANCE.regulatory"]),
    (2101, 2199, ["QUALITY_CONTROL.representations"]),
    (2201, 2299, ["BORROWER.borrower_eligibility"]),
    (2301, 2399, ["BORROWER.borrower_eligibility"]),
    (2401, 2499, ["PROPERTY.property_eligibility", "PROPERTY.property_type"]),
    (2501, 2599, ["PROPERTY.property_eligibility"]),
    (3101, 3199, ["BORROWER.borrower_income"]),
    (3201, 3299, ["BORROWER.borrower_assets"]),
    (3301, 3399, ["BORROWER.borrower_credit"]),
    (3401, 3499, ["BORROWER.borrower_liabilities"]),
    (4101, 4199, ["PROPERTY.property_valuation"]),
    (4201, 4299, ["LOAN.loan_purpose", "LOAN.loan_limits"]),
    (4301, 4399, ["UNDERWRITING.special_programs"]),
    (4401, 4499, ["LOAN.loan_amortization"]),
    (4501, 4599, ["UNDERWRITING.project_standards"]),
    (4601, 4699, ["CLOSING.legal_documents"]),
    (4701, 4799, ["CLOSING.title_requirements"]),
    (4801, 4899, ["PROPERTY.property_insurance"]),
    (5101, 5199, ["DELIVERY.loan_delivery"]),
    (5201, 5299, ["DELIVERY.mbs_securitization"]),
    (5301, 5399, ["DELIVERY.execution_options"]),
    (5601, 5699, ["DELIVERY.servicing"]),
    (5701, 5799, ["DELIVERY.servicing"]),
    (6101, 6199, ["QUALITY_CONTROL.lender_qc"]),
    (6201, 6299, ["QUALITY_CONTROL.gse_qc"]),
    (7101, 7199, ["DELIVERY.servicing"]),
    (8101, 8199, ["UNDERWRITING.special_programs"]),
    (9101, 9199, ["COMPLIANCE.regulatory"]),
]

# ---------------------------------------------------------------------------
# 4. MISMO Enumeration Patterns
#    Enum name → {value: regex pattern} for content scanning.
#    Patterns use multi-word phrases to reduce false positives.
# ---------------------------------------------------------------------------

MISMO_PATTERNS: dict[str, dict[str, str]] = {
    "LoanPurposeType": {
        "Purchase": r"\bpurchase\s+transaction",
        "NoCashOutRefinance": r"\blimited\s+cash[- ]?out\s+refinanc",
        "CashOutRefinance": r"\bcash[- ]?out\s+refinanc",
    },
    "PropertyUsageType": {
        "PrimaryResidence": r"\bprimary\s+residence|principal\s+residence|owner[- ]?occupied",
        "SecondHome": r"\bsecond\s+home",
        "Investor": r"\binvestment\s+propert",
    },
    "MortgageType": {
        "Conventional": r"\bconventional\s+mortgage|\bconventional\s+loan",
        "FHA": r"\bFHA[- ]?insured|\bFHA\s+mortgage|\bFHA\s+loan",
        "VA": r"\bVA[- ]?guaranteed|\bVA\s+mortgage|\bVA\s+loan",
        "USDARuralDevelopment": r"\bRD[- ]?guaranteed|\bUSDA|\brural\s+development",
    },
    "PropertyType": {
        "Condominium": r"\bcondo(?:minium)?\b",
        "Cooperative": r"\bco[- ]?op(?:erative)?\b",
        "ManufacturedHousing": r"\bmanufactured\s+hous",
        "PUD": r"\bPUD\b|\bplanned\s+unit\s+development",
        "Detached": r"\bdetached\b.*\b(?:single|one)[- ]?(?:family|unit)",
        "TwoToFourUnit": r"\btwo[- ]?\s*to[- ]?\s*four[- ]?unit|\b[234][- ]?unit",
    },
    "AmortizationType": {
        "Fixed": r"\bfixed[- ]?rate\s+(?:mortgage|loan)",
        "AdjustableRate": r"\badjustable[- ]?rate\s+mortgage|\bARM\b",
    },
    "LienPriorityType": {
        "FirstLien": r"\bfirst\s+(?:lien|mortgage)",
        "SecondLien": r"\bsecond\s+(?:lien|mortgage)|subordinate\s+(?:lien|financing)",
    },
    "DocumentationType": {
        "Full": r"\bfull\s+documentation",
        "Alternative": r"\balternative\s+documentation|\balt[- ]?doc",
    },
}

# ---------------------------------------------------------------------------
# 5. Mortgage Terms Glossary (~160 terms)
#    Used for key-term extraction. Case-insensitive matching.
# ---------------------------------------------------------------------------

MORTGAGE_TERMS: list[str] = [
    # Ratios & Metrics
    "LTV", "CLTV", "HCLTV", "DTI", "FICO",
    # Income Sources
    "W-2", "1040", "Schedule C", "Schedule D", "Schedule E", "Schedule F",
    "K-1", "1099", "VOE", "VOD", "VOR",
    "base income", "bonus income", "commission income", "overtime",
    "self-employment income", "rental income", "alimony", "child support",
    "Social Security", "pension", "retirement income", "disability income",
    "trust income", "boarder income", "capital gains",
    # Assets
    "depository assets", "non-depository assets", "gift funds", "gift of equity",
    "grants", "reserves", "earnest money", "stocks", "bonds", "mutual funds",
    "retirement accounts", "401k", "IRA", "cash value life insurance",
    "virtual currency", "cryptocurrency",
    # Credit
    "credit score", "credit report", "credit history",
    "derogatory credit", "bankruptcy", "foreclosure", "short sale",
    "deed-in-lieu", "charge-off", "collection", "judgment", "tax lien",
    "authorized user", "tradeline", "nontraditional credit",
    # Property & Appraisal
    "appraisal", "appraised value", "comparable sale", "sales comparison",
    "desktop appraisal", "hybrid appraisal", "value acceptance",
    "property inspection", "condition rating", "quality rating",
    "environmental hazard", "flood zone", "flood insurance",
    "manufactured housing", "modular housing", "leasehold",
    # Loan Attributes
    "conforming loan", "high-balance", "jumbo", "super conforming",
    "fixed-rate", "adjustable-rate", "ARM", "interest rate",
    "buydown", "temporary buydown", "permanent buydown",
    "prepayment penalty", "balloon payment",
    "mortgage insurance", "PMI", "MI", "LLPA",
    "loan-level price adjustment",
    # Transaction Types
    "purchase", "refinance", "cash-out refinance",
    "limited cash-out refinance", "rate-and-term refinance",
    # Programs
    "HomeReady", "HomeStyle", "HomeStyle Renovation",
    "High LTV Refinance", "Community Seconds",
    "DU", "Desktop Underwriter", "AUS",
    "HomePath", "NACLI",
    # Parties & Documents
    "borrower", "co-borrower", "guarantor", "co-signer",
    "seller", "servicer", "lender", "investor",
    "note", "security instrument", "deed of trust", "mortgage",
    "title insurance", "hazard insurance", "power of attorney",
    "IRS Form 4506-C", "URLA",
    # Regulatory
    "TRID", "TILA", "RESPA", "ATR", "QM", "qualified mortgage",
    "Dodd-Frank", "ECOA", "Fair Housing", "HMDA", "CRA",
    "ability to repay",
    # Underwriting Concepts
    "compensating factors", "risk assessment", "risk layering",
    "credit risk", "collateral risk",
    "front-end ratio", "back-end ratio", "housing expense ratio",
    "residual income", "disposable income",
    # Closing & Delivery
    "closing disclosure", "settlement", "escrow", "impound",
    "MBS", "mortgage-backed securities", "TBA",
    "pool", "guaranty fee", "servicing fee",
    "whole loan", "best efforts", "mandatory commitment",
]

# ---------------------------------------------------------------------------
# 6. Cross-Source Alignment Map
#    Links Fannie Mae section-code prefixes to Freddie Mac chapter ranges.
# ---------------------------------------------------------------------------

CROSS_SOURCE_MAP: list[dict] = [
    {"fannie_prefix": "B2-1.1", "freddie_range": (2301, 2399), "topic": "Occupancy type requirements", "relationship": "equivalent"},
    {"fannie_prefix": "B2-1.2", "freddie_range": (4201, 4299), "topic": "LTV / CLTV ratio requirements", "relationship": "equivalent"},
    {"fannie_prefix": "B2-1.3", "freddie_range": (4201, 4299), "topic": "Loan purpose / transaction type", "relationship": "related"},
    {"fannie_prefix": "B2-1.4", "freddie_range": (4401, 4499), "topic": "Loan amortization types (Fixed, ARM)", "relationship": "equivalent"},
    {"fannie_prefix": "B2-2",   "freddie_range": (2201, 2399), "topic": "Borrower eligibility requirements", "relationship": "equivalent"},
    {"fannie_prefix": "B2-3",   "freddie_range": (2401, 2599), "topic": "Property eligibility requirements", "relationship": "equivalent"},
    {"fannie_prefix": "B3-1",   "freddie_range": (3101, 3199), "topic": "Manual underwriting / risk assessment", "relationship": "related"},
    {"fannie_prefix": "B3-3",   "freddie_range": (3101, 3199), "topic": "Income assessment and documentation", "relationship": "equivalent"},
    {"fannie_prefix": "B3-4",   "freddie_range": (3201, 3299), "topic": "Asset assessment and verification", "relationship": "equivalent"},
    {"fannie_prefix": "B3-5",   "freddie_range": (3301, 3399), "topic": "Credit assessment and scoring", "relationship": "equivalent"},
    {"fannie_prefix": "B3-6",   "freddie_range": (3401, 3499), "topic": "Liability / DTI assessment", "relationship": "equivalent"},
    {"fannie_prefix": "B4-1",   "freddie_range": (4101, 4199), "topic": "Property valuation / appraisal", "relationship": "equivalent"},
    {"fannie_prefix": "B4-2",   "freddie_range": (4501, 4599), "topic": "Project standards (Condo, PUD, Co-op)", "relationship": "equivalent"},
    {"fannie_prefix": "B7",     "freddie_range": (4801, 4899), "topic": "Insurance requirements", "relationship": "equivalent"},
    {"fannie_prefix": "B8",     "freddie_range": (4601, 4699), "topic": "Legal documents / closing", "relationship": "equivalent"},
    {"fannie_prefix": "D1",     "freddie_range": (6101, 6199), "topic": "Lender quality control", "relationship": "equivalent"},
]

# ---------------------------------------------------------------------------
# 7. Content Type Classification Signals
#    Keyword patterns and heuristics for classifying section content type.
# ---------------------------------------------------------------------------

CONTENT_TYPE_SIGNALS: dict[str, list[str]] = {
    "definition": [
        r"\bglossary\b", r"\bacronym", r"\bdefined\s+terms",
    ],
    "eligibility_matrix": [
        r"\beligib\w+\s+matrix", r"\bmaximum\s+LTV", r"\bminimum\s+credit\s+score",
        r"\beligib\w+\s+requirements?\s+\w+\s+table",
    ],
    "procedure": [
        r"\bstep\s+\d", r"\bprocess\s+for\b", r"\bhow\s+to\b",
        r"\bprocedure\b", r"\bworkflow\b",
    ],
    "reference": [
        r"\bcontact", r"\bform\s+list", r"\bresource",
        r"\bexhibit", r"\bsample\s+language",
    ],
}
