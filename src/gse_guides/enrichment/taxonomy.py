"""Domain taxonomy, MISMO enumerations, mortgage terms, and cross-source mappings."""

from __future__ import annotations

import re

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

# ---------------------------------------------------------------------------
# 8. Entity Type Vocabularies (Task 1)
#    Formal typed entities replacing ad-hoc keyword matching.
#    Each entity type maps to a dict of canonical values, each with:
#      - "patterns": list of regex pattern strings (case-insensitive)
#      - "aliases": list of human-readable display names
#
#    These power structured entity extraction so the knowledge graph
#    can answer intersection queries like "self-employment + cash-out + condo".
# ---------------------------------------------------------------------------

ENTITY_TYPES: dict[str, dict[str, dict]] = {
    # --- Loan Scenario Dimensions ---
    "transaction_types": {
        "Purchase": {
            "patterns": [r"\bpurchase\s+(?:transaction|money\s+mortgage|loan)", r"\bpurchas(?:e|ing)\s+(?:a|the|of)\s+(?:property|home|subject)"],
            "aliases": ["purchase", "purchase transaction"],
        },
        "RateTermRefinance": {
            "patterns": [r"\brate[- ]?(?:and[- ]?)?term\s+refinanc", r"\bno[- ]?cash[- ]?out\s+refinanc"],
            "aliases": ["rate-and-term refinance", "rate/term refinance"],
        },
        "CashOutRefinance": {
            "patterns": [r"\bcash[- ]?out\s+refinanc"],
            "aliases": ["cash-out refinance"],
        },
        "LimitedCashOutRefinance": {
            "patterns": [r"\blimited\s+cash[- ]?out\s+refinanc"],
            "aliases": ["limited cash-out refinance"],
        },
        "Refinance": {
            "patterns": [r"\brefinanc(?:e|ing)\b(?!\s+(?:cash|limited|rate))"],
            "aliases": ["refinance"],
        },
        "ConstructionToPermanent": {
            "patterns": [r"\bconstruction[- ]?to[- ]?perm(?:anent)?"],
            "aliases": ["construction-to-permanent"],
        },
    },
    "occupancy_types": {
        "PrimaryResidence": {
            "patterns": [r"\bprimary\s+residence", r"\bprincipal\s+residence", r"\bowner[- ]?occupied"],
            "aliases": ["primary residence", "principal residence", "owner-occupied"],
        },
        "SecondHome": {
            "patterns": [r"\bsecond\s+home"],
            "aliases": ["second home"],
        },
        "Investment": {
            "patterns": [r"\binvestment\s+propert", r"\bnon[- ]?owner[- ]?occupied"],
            "aliases": ["investment property", "non-owner-occupied"],
        },
    },
    "property_types": {
        "SingleFamily": {
            "patterns": [r"\bsingle[- ]?family\b", r"\b(?:one|1)[- ]?unit\s+(?:dwelling|propert|residen)"],
            "aliases": ["single-family", "1-unit"],
        },
        "Condo": {
            "patterns": [r"\bcondo(?:minium)?\b"],
            "aliases": ["condominium", "condo"],
        },
        "Coop": {
            "patterns": [r"\bco[- ]?op(?:erative)?\b"],
            "aliases": ["cooperative", "co-op"],
        },
        "PUD": {
            "patterns": [r"\bPUD\b", r"\bplanned\s+unit\s+development"],
            "aliases": ["PUD", "planned unit development"],
        },
        "ManufacturedHousing": {
            "patterns": [r"\bmanufactured\s+hous(?:e|ing)", r"\bmanufactured\s+home"],
            "aliases": ["manufactured housing", "manufactured home"],
        },
        "TwoToFourUnit": {
            "patterns": [r"\btwo[- ]?\s*to[- ]?\s*four[- ]?unit", r"\b[234][- ]?unit\s+(?:propert|dwelling|residen)"],
            "aliases": ["2-4 unit", "two-to-four-unit"],
        },
        "Leasehold": {
            "patterns": [r"\bleasehold\b"],
            "aliases": ["leasehold"],
        },
        "MixedUse": {
            "patterns": [r"\bmixed[- ]?use\b"],
            "aliases": ["mixed-use"],
        },
    },
    "loan_types": {
        "FixedRate": {
            "patterns": [r"\bfixed[- ]?rate\s+(?:mortgage|loan)", r"\bFRM\b"],
            "aliases": ["fixed-rate mortgage", "FRM"],
        },
        "AdjustableRate": {
            "patterns": [r"\badjustable[- ]?rate\s+mortgage", r"\bARM\b"],
            "aliases": ["adjustable-rate mortgage", "ARM"],
        },
        "Buydown": {
            "patterns": [r"\bbuydown\b", r"\bbuy[- ]?down\b"],
            "aliases": ["buydown"],
        },
        "InterestOnly": {
            "patterns": [r"\binterest[- ]?only\b"],
            "aliases": ["interest-only"],
        },
        "HighBalance": {
            "patterns": [r"\bhigh[- ]?balance\b", r"\bsuper\s+conforming\b"],
            "aliases": ["high-balance", "super conforming"],
        },
    },
    "lien_positions": {
        "FirstLien": {
            "patterns": [r"\bfirst\s+(?:lien|mortgage)\b"],
            "aliases": ["first lien", "first mortgage"],
        },
        "SecondLien": {
            "patterns": [r"\bsecond\s+(?:lien|mortgage)\b", r"\bsubordinate\s+(?:lien|financing)\b"],
            "aliases": ["second lien", "subordinate lien"],
        },
    },
    "program_types": {
        "HomeReady": {
            "patterns": [r"\bHomeReady\b"],
            "aliases": ["HomeReady"],
        },
        "HomeStyle": {
            "patterns": [r"\bHomeStyle\b(?!\s+Renovation)"],
            "aliases": ["HomeStyle"],
        },
        "HomeStyleRenovation": {
            "patterns": [r"\bHomeStyle\s+Renovation\b"],
            "aliases": ["HomeStyle Renovation"],
        },
        "HighLTVRefi": {
            "patterns": [r"\bhigh[- ]?LTV\s+refi(?:nanc)?", r"\bHigh\s+LTV\s+Refinance\b"],
            "aliases": ["High LTV Refinance"],
        },
        "CommunitySeconds": {
            "patterns": [r"\bCommunity\s+Seconds\b"],
            "aliases": ["Community Seconds"],
        },
        "HomeOne": {
            "patterns": [r"\bHome\s*One\b"],
            "aliases": ["Home One"],
        },
        "HomePossible": {
            "patterns": [r"\bHome\s*Possible\b"],
            "aliases": ["Home Possible"],
        },
        "ChoiceRenovation": {
            "patterns": [r"\bCHOICE\s+Renovation\b"],
            "aliases": ["CHOICE Renovation"],
        },
        "SuperConforming": {
            "patterns": [r"\bsuper\s+conforming\b"],
            "aliases": ["super conforming"],
        },
    },

    # --- Borrower Dimensions ---
    "income_sources": {
        "W2Employment": {
            "patterns": [r"\bW[- ]?2\s+(?:income|employ|wage)", r"\bsalaried\s+(?:employ|income|borrow)"],
            "aliases": ["W-2 employment", "salaried employment"],
        },
        "SelfEmployment": {
            "patterns": [r"\bself[- ]?employ"],
            "aliases": ["self-employment", "self-employed"],
        },
        "Commission": {
            "patterns": [r"\bcommission\s+income", r"\bcommission[- ]?based"],
            "aliases": ["commission income"],
        },
        "Bonus": {
            "patterns": [r"\bbonus\s+income"],
            "aliases": ["bonus income"],
        },
        "Overtime": {
            "patterns": [r"\bovertime\s+(?:income|pay|earn)"],
            "aliases": ["overtime income"],
        },
        "Rental": {
            "patterns": [r"\brental\s+income", r"\brent\s+(?:received|collected|income)"],
            "aliases": ["rental income"],
        },
        "SocialSecurity": {
            "patterns": [r"\bSocial\s+Security\b", r"\bSSA\b", r"\bSSI\b"],
            "aliases": ["Social Security", "SSA"],
        },
        "Pension": {
            "patterns": [r"\bpension\s+(?:income|benefit|payment)"],
            "aliases": ["pension income"],
        },
        "Military": {
            "patterns": [r"\bmilitary\s+(?:income|pay|allowance)", r"\bBAH\b", r"\bBAS\b"],
            "aliases": ["military income", "military pay"],
        },
        "BoarderIncome": {
            "patterns": [r"\bboarder\s+income"],
            "aliases": ["boarder income"],
        },
        "CapitalGains": {
            "patterns": [r"\bcapital\s+gain"],
            "aliases": ["capital gains"],
        },
        "ForeignIncome": {
            "patterns": [r"\bforeign\s+income", r"\bincome\s+earned\s+(?:in\s+a\s+)?foreign"],
            "aliases": ["foreign income"],
        },
        "Alimony": {
            "patterns": [r"\balimony\b", r"\bmaintenance\s+income"],
            "aliases": ["alimony"],
        },
        "ChildSupport": {
            "patterns": [r"\bchild\s+support\b"],
            "aliases": ["child support"],
        },
        "Disability": {
            "patterns": [r"\bdisability\s+(?:income|benefit|payment)"],
            "aliases": ["disability income"],
        },
        "TrustIncome": {
            "patterns": [r"\btrust\s+income"],
            "aliases": ["trust income"],
        },
        "RetirementDistribution": {
            "patterns": [r"\bretirement\s+(?:distribution|income|withdraw)", r"\b401[Kk]\s+(?:distribution|withdraw)", r"\bIRA\s+(?:distribution|withdraw)"],
            "aliases": ["retirement distribution"],
        },
        "InterestDividends": {
            "patterns": [r"\binterest\s+(?:and\s+)?dividend\s+income", r"\bdividend\s+income"],
            "aliases": ["interest and dividend income"],
        },
        "NotesReceivable": {
            "patterns": [r"\bnotes?\s+receivable\s+income"],
            "aliases": ["notes receivable income"],
        },
    },
    "asset_types": {
        "Depository": {
            "patterns": [r"\bdepository\s+(?:asset|account)", r"\bchecking\s+account", r"\bsavings\s+account"],
            "aliases": ["depository assets", "checking", "savings"],
        },
        "NonDepository": {
            "patterns": [r"\bnon[- ]?depository\s+(?:asset|account)"],
            "aliases": ["non-depository assets"],
        },
        "Retirement401k": {
            "patterns": [r"\b401[Kk]\b"],
            "aliases": ["401(k)"],
        },
        "RetirementIRA": {
            "patterns": [r"\bIRA\b"],
            "aliases": ["IRA"],
        },
        "GiftFunds": {
            "patterns": [r"\bgift\s+fund", r"\bgift\s+(?:of\s+)?money", r"\bgift\s+(?:from|letter)"],
            "aliases": ["gift funds"],
        },
        "GiftOfEquity": {
            "patterns": [r"\bgift\s+of\s+equity"],
            "aliases": ["gift of equity"],
        },
        "GrantFunds": {
            "patterns": [r"\bgrant\s+fund", r"\bdown\s+payment\s+assistance"],
            "aliases": ["grant funds", "down payment assistance"],
        },
        "Stocks": {
            "patterns": [r"\bstock(?:s)?\s+(?:portfolio|holding|account)", r"\bequit(?:y|ies)\s+(?:portfolio|holding)"],
            "aliases": ["stocks"],
        },
        "Bonds": {
            "patterns": [r"\bbond(?:s)?\s+(?:portfolio|holding|account)"],
            "aliases": ["bonds"],
        },
        "MutualFunds": {
            "patterns": [r"\bmutual\s+fund"],
            "aliases": ["mutual funds"],
        },
        "CashValueLifeInsurance": {
            "patterns": [r"\bcash\s+value\s+(?:of\s+)?life\s+insurance"],
            "aliases": ["cash value life insurance"],
        },
        "Cryptocurrency": {
            "patterns": [r"\bcryptocurrenc", r"\bvirtual\s+currenc", r"\bdigital\s+(?:asset|currenc)"],
            "aliases": ["cryptocurrency", "virtual currency"],
        },
        "EarnestMoney": {
            "patterns": [r"\bearnest\s+money"],
            "aliases": ["earnest money"],
        },
        "ProceedsFromSale": {
            "patterns": [r"\bproceeds\s+from\s+(?:the\s+)?sale", r"\bnet\s+(?:sale\s+)?proceeds"],
            "aliases": ["proceeds from sale"],
        },
    },
    "credit_events": {
        "Bankruptcy": {
            "patterns": [r"\bbankruptcy\b", r"\bChapter\s+[7](?:\s+bankruptcy)?", r"\bChapter\s+13\b"],
            "aliases": ["bankruptcy"],
        },
        "Foreclosure": {
            "patterns": [r"\bforeclosure\b"],
            "aliases": ["foreclosure"],
        },
        "ShortSale": {
            "patterns": [r"\bshort\s+sale\b", r"\bpre[- ]?foreclosure\s+sale"],
            "aliases": ["short sale"],
        },
        "DeedInLieu": {
            "patterns": [r"\bdeed[- ]?in[- ]?lieu\b"],
            "aliases": ["deed-in-lieu"],
        },
        "ChargeOff": {
            "patterns": [r"\bcharge[- ]?off\b"],
            "aliases": ["charge-off"],
        },
        "Collection": {
            "patterns": [r"\bcollection\s+account", r"\baccount\s+in\s+collection"],
            "aliases": ["collection"],
        },
        "Judgment": {
            "patterns": [r"\bjudgment\b(?!\s+(?:lien|call))"],
            "aliases": ["judgment"],
        },
        "TaxLien": {
            "patterns": [r"\btax\s+lien\b"],
            "aliases": ["tax lien"],
        },
        "LoanModification": {
            "patterns": [r"\bloan\s+modification\b", r"\bmodified\s+(?:mortgage|loan)\b"],
            "aliases": ["loan modification"],
        },
    },

    # --- Property Dimensions ---
    "project_types": {
        "CondoProject": {
            "patterns": [r"\bcondo(?:minium)?\s+project", r"\bproject\s+(?:review|approval|eligibility).*\bcondo"],
            "aliases": ["condo project"],
        },
        "PUDProject": {
            "patterns": [r"\bPUD\s+project"],
            "aliases": ["PUD project"],
        },
        "CoopProject": {
            "patterns": [r"\bco[- ]?op(?:erative)?\s+project"],
            "aliases": ["co-op project"],
        },
        "NewProject": {
            "patterns": [r"\bnew\s+(?:condo(?:minium)?\s+)?project", r"\bnewly\s+(?:built|constructed)\s+project"],
            "aliases": ["new project"],
        },
        "EstablishedProject": {
            "patterns": [r"\bestablished\s+(?:condo(?:minium)?\s+)?project"],
            "aliases": ["established project"],
        },
    },
    "valuation_types": {
        "FullAppraisal": {
            "patterns": [r"\bfull\s+appraisal", r"\b(?:interior|exterior)\s+(?:and\s+(?:interior|exterior)\s+)?inspection\s+appraisal"],
            "aliases": ["full appraisal"],
        },
        "DesktopAppraisal": {
            "patterns": [r"\bdesktop\s+appraisal"],
            "aliases": ["desktop appraisal"],
        },
        "HybridAppraisal": {
            "patterns": [r"\bhybrid\s+appraisal"],
            "aliases": ["hybrid appraisal"],
        },
        "ValueAcceptance": {
            "patterns": [r"\bvalue\s+acceptance", r"\bappraisal\s+waiver"],
            "aliases": ["value acceptance", "appraisal waiver"],
        },
        "PropertyInspection": {
            "patterns": [r"\bproperty\s+inspection\b(?!\s+waiv)"],
            "aliases": ["property inspection"],
        },
    },

    # --- Underwriting Dimensions ---
    "documentation_types": {
        "FullDocumentation": {
            "patterns": [r"\bfull\s+documentation"],
            "aliases": ["full documentation"],
        },
        "AlternativeDocumentation": {
            "patterns": [r"\balternative\s+documentation", r"\balt[- ]?doc\b"],
            "aliases": ["alternative documentation", "alt-doc"],
        },
        "ReducedDocumentation": {
            "patterns": [r"\breduced\s+documentation"],
            "aliases": ["reduced documentation"],
        },
    },
    "aus_types": {
        "DesktopUnderwriter": {
            "patterns": [r"\bDesktop\s+Underwriter\b", r"\bDU\b(?!\s+Refi)"],
            "aliases": ["Desktop Underwriter", "DU"],
        },
        "LoanProductAdvisor": {
            "patterns": [r"\bLoan\s+Product\s+Advisor\b", r"\bLPA\b"],
            "aliases": ["Loan Product Advisor", "LPA"],
        },
        "ManualUnderwriting": {
            "patterns": [r"\bmanual(?:ly)?\s+underwr"],
            "aliases": ["manual underwriting"],
        },
    },
}

# ---------------------------------------------------------------------------
# 9. Implication Rules (Task 2)
#    Static domain knowledge: certain entity values trigger requirements
#    or constraints. These power the knowledge graph's conditional edges.
# ---------------------------------------------------------------------------

IMPLICATION_RULES: list[dict] = [
    # Property type → project review requirements
    {
        "if_entity": "PropertyType.Condo",
        "then_type": "REQUIRES",
        "then_target": "ProjectReview",
        "description": "Condominiums require project review per B4-2.2 / Freddie 4501",
    },
    {
        "if_entity": "PropertyType.Coop",
        "then_type": "REQUIRES",
        "then_target": "ProjectReview",
        "description": "Cooperatives require project review per B4-2.3 / Freddie 4501",
    },
    {
        "if_entity": "PropertyType.PUD",
        "then_type": "REQUIRES",
        "then_target": "ProjectReview",
        "description": "PUDs require project review per B4-2.1 / Freddie 4501",
    },
    {
        "if_entity": "PropertyType.ManufacturedHousing",
        "then_type": "REQUIRES",
        "then_target": "FoundationInspection",
        "description": "Manufactured housing requires foundation compliance inspection",
    },

    # Occupancy type → LTV constraints
    {
        "if_entity": "OccupancyType.Investment",
        "then_type": "CONSTRAINS",
        "then_target": {"metric": "LTV", "op": "<=", "value": "85%"},
        "description": "Investment properties have lower maximum LTV (typically 85% purchase, 75% cash-out)",
    },
    {
        "if_entity": "OccupancyType.SecondHome",
        "then_type": "CONSTRAINS",
        "then_target": {"metric": "LTV", "op": "<=", "value": "90%"},
        "description": "Second homes have lower maximum LTV (typically 90%)",
    },

    # Transaction type → LTV constraints
    {
        "if_entity": "TransactionType.CashOutRefinance",
        "then_type": "CONSTRAINS",
        "then_target": {"metric": "LTV", "op": "<=", "value": "80%"},
        "description": "Cash-out refinances have lower maximum LTV (typically 80%)",
    },

    # Income source → documentation requirements
    {
        "if_entity": "IncomeSource.SelfEmployment",
        "then_type": "REQUIRES",
        "then_target": "TwoYearHistory",
        "description": "Self-employment income requires 2-year history to demonstrate stability",
    },
    {
        "if_entity": "IncomeSource.SelfEmployment",
        "then_type": "REQUIRES",
        "then_target": "TaxReturnAnalysis",
        "description": "Self-employment income requires analysis of personal and business tax returns",
    },
    {
        "if_entity": "IncomeSource.Commission",
        "then_type": "REQUIRES",
        "then_target": "TwoYearHistory",
        "description": "Commission income requires 2-year earning history",
    },
    {
        "if_entity": "IncomeSource.Rental",
        "then_type": "REQUIRES",
        "then_target": "LeaseAgreement",
        "description": "Rental income requires lease agreement or Schedule E documentation",
    },

    # Loan type → qualification requirements
    {
        "if_entity": "LoanType.AdjustableRate",
        "then_type": "REQUIRES",
        "then_target": "QualifyingRate",
        "description": "ARM loans require qualification at the note rate or qualifying rate (whichever is greater)",
    },
    {
        "if_entity": "LoanType.Buydown",
        "then_type": "REQUIRES",
        "then_target": "FullRateQualification",
        "description": "Buydown loans require borrower qualification at the full note rate",
    },
    {
        "if_entity": "LoanType.HighBalance",
        "then_type": "REQUIRES",
        "then_target": "AdditionalLLPAs",
        "description": "High-balance loans are subject to additional loan-level price adjustments",
    },

    # AUS → documentation waivers
    {
        "if_entity": "AUSType.DesktopUnderwriter",
        "then_type": "REQUIRES",
        "then_target": "DUDocumentationLevel",
        "description": "DU may issue documentation waivers; specific doc requirements depend on DU findings",
    },

    # Program → specific requirements
    {
        "if_entity": "ProgramType.HomeReady",
        "then_type": "REQUIRES",
        "then_target": "IncomeLimits",
        "description": "HomeReady has area median income limits for borrower eligibility",
    },
    {
        "if_entity": "ProgramType.HomeReady",
        "then_type": "REQUIRES",
        "then_target": "HomeownershipEducation",
        "description": "HomeReady requires completion of homeownership education course",
    },
    {
        "if_entity": "ProgramType.HomePossible",
        "then_type": "REQUIRES",
        "then_target": "IncomeLimits",
        "description": "Home Possible has area median income limits for borrower eligibility",
    },
    {
        "if_entity": "ProgramType.HomePossible",
        "then_type": "REQUIRES",
        "then_target": "HomeownershipEducation",
        "description": "Home Possible requires homeownership education for first-time homebuyers",
    },

    # Credit events → waiting period requirements
    {
        "if_entity": "CreditEvent.Bankruptcy",
        "then_type": "REQUIRES",
        "then_target": "WaitingPeriod",
        "description": "Bankruptcy requires a waiting period (typically 2-4 years depending on chapter)",
    },
    {
        "if_entity": "CreditEvent.Foreclosure",
        "then_type": "REQUIRES",
        "then_target": "WaitingPeriod",
        "description": "Foreclosure requires a waiting period (typically 7 years, 3 with extenuating circumstances)",
    },
    {
        "if_entity": "CreditEvent.ShortSale",
        "then_type": "REQUIRES",
        "then_target": "WaitingPeriod",
        "description": "Short sale requires a waiting period (typically 4 years, 2 with extenuating circumstances)",
    },
    {
        "if_entity": "CreditEvent.DeedInLieu",
        "then_type": "REQUIRES",
        "then_target": "WaitingPeriod",
        "description": "Deed-in-lieu requires a waiting period (typically 4 years, 2 with extenuating circumstances)",
    },
]

# ---------------------------------------------------------------------------
# 10. Severity Detection Signals (Task 3)
#     Patterns for classifying requirement severity (must/should/best practice).
#     Ordered by strength: must_comply > should_comply > best_practice > info_only.
#     The strongest signal found in content governs classification.
# ---------------------------------------------------------------------------

SEVERITY_SIGNALS: dict[str, list[str]] = {
    "must_comply": [
        r"\bmust\b",
        r"\bis required\b",
        r"\bare required\b",
        r"\bshall\b",
        r"\bwill not purchase\b",
        r"\bwill not securitize\b",
        r"\bineligible\b",
        r"\bprohibited\b",
        r"\bnot permitted\b",
        r"\bnot eligible\b",
        r"\bmandatory\b",
        r"\brequired to\b",
        r"\bmust not\b",
        r"\bshall not\b",
        r"\bwill be rejected\b",
        r"\bwill not accept\b",
        r"\bmust be\b",
        r"\bmust have\b",
        r"\bmust provide\b",
        r"\bmust obtain\b",
        r"\bmust verify\b",
        r"\bmust document\b",
        r"\bmust include\b",
    ],
    "should_comply": [
        r"\bshould\b",
        r"\brecommended\b",
        r"\bexpected to\b",
        r"\bmay consider\b",
        r"\bgenerally\b.*\brequire",
        r"\bnormally\b",
        r"\btypically\s+(?:required|expected|needed)",
        r"\bgenerally\s+(?:required|expected|needed)",
        r"\bshould be\b",
        r"\bshould not\b",
        r"\bshould have\b",
        r"\bshould provide\b",
    ],
    "best_practice": [
        r"\bbest\s+practice\b",
        r"\bencourage[sd]?\b",
        r"\bit\s+is\s+good\s+practice\b",
        r"\badvisable\b",
        r"\bFannie\s+Mae\s+(?:encourages|recommends)\b",
        r"\bFreddie\s+Mac\s+(?:encourages|recommends)\b",
        r"\bprudent\b",
        r"\bsound\s+(?:practice|business)\b",
    ],
    "info_only": [
        r"\bfor\s+information\b",
        r"\boverview\b",
        r"\bintroduction\b",
        r"\bbackground\b",
        r"\bdescription\b",
        r"\bfor\s+reference\b",
        r"\bnote\s+that\b",
        r"\bfor\s+additional\s+information\b",
        r"\bgeneral\s+information\b",
    ],
}

# ---------------------------------------------------------------------------
# 11. Requirement Type Signals (Task 3)
#     Classifies the nature of a requirement (eligibility gate vs
#     documentation rule vs calculation method vs general guideline).
# ---------------------------------------------------------------------------

REQUIREMENT_TYPE_SIGNALS: dict[str, list[str]] = {
    "eligibility": [
        r"\beligib",
        r"\bqualif",
        r"\bmaximum\b",
        r"\bminimum\b",
        r"\blimit[s]?\b",
        r"\bnot eligible\b",
        r"\bineligible\b",
        r"\bpermissible\b",
        r"\bacceptable\b",
        r"\bnot acceptable\b",
        r"\ballow(?:ed|able)\b",
        r"\bnot allow(?:ed|able)\b",
    ],
    "documentation": [
        r"\bdocument(?:ation|ed|ing)?\b",
        r"\bverif(?:y|ied|ication)\b",
        r"\bevidence\b",
        r"\bsubstantiat",
        r"\bprovide\b.*\b(?:copies|records|statements)",
        r"\bobtain\b",
        r"\bretain\b.*\b(?:copies|records|documentation)",
        r"\brecords?\s+(?:must|should|required)",
    ],
    "calculation": [
        r"\bcalculat",
        r"\bcompute\b",
        r"\bformula\b",
        r"\bdetermin[e]?\b.*\b(?:ratio|amount|income|value)",
        r"\badd\b.*\bsubtract",
        r"\bdivide\b.*\bby\b",
        r"\bratio\s+(?:is\s+)?(?:calculated|determined|computed)",
        r"\bmonthly\s+(?:income|payment)\s+(?:is\s+)?(?:calculated|determined)",
    ],
    # "guideline" is the fallback — no patterns needed
}

# ---------------------------------------------------------------------------
# 12. Numeric Constraint Patterns (Task 3)
#     Regex patterns for extracting numeric thresholds from prose.
#     {METRIC} is expanded at compile time with the CONSTRAINT_METRICS list.
# ---------------------------------------------------------------------------

CONSTRAINT_METRICS: list[str] = [
    "LTV", "CLTV", "HCLTV", "DTI",
    "credit score", "FICO",
    "reserves",
    "debt-to-income",
    "housing expense",
    "loan-to-value",
    "combined loan-to-value",
]

# Patterns using named groups for structured extraction.
# Each pattern expects METRIC_RE to be interpolated before compilation.
NUMERIC_CONSTRAINT_PATTERN_TEMPLATES: list[str] = [
    # "maximum LTV of 80%", "maximum allowable LTV ratio of 80%"
    r"maximum\s+(?:allowable\s+)?{METRIC}\s+(?:ratio\s+)?(?:of\s+|is\s+)?(\d+(?:\.\d+)?)\s*%",
    # "minimum credit score of 620"
    r"minimum\s+(?:required\s+)?{METRIC}\s+(?:of\s+|is\s+)?(\d+(?:\.\d+)?)",
    # "LTV must not exceed 80%"
    r"{METRIC}\s+(?:must|cannot|shall)\s+not\s+exceed\s+(\d+(?:\.\d+)?)\s*%",
    # "at least 6 months of reserves"
    r"(?:at\s+least|minimum\s+of)\s+(\d+)\s+months?\s+(?:of\s+)?reserves",
    # "80% LTV" (reversed order in tables/matrices)
    r"(\d+(?:\.\d+)?)\s*%\s+(?:maximum\s+)?{METRIC}",
    # "LTV is limited to 80%"
    r"{METRIC}\s+(?:is\s+)?limited\s+to\s+(\d+(?:\.\d+)?)\s*%",
    # "DTI ratio of 45% or less"
    r"{METRIC}\s+(?:ratio\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*%\s+or\s+less",
    # "not to exceed 80% LTV"
    r"not\s+to\s+exceed\s+(\d+(?:\.\d+)?)\s*%\s+{METRIC}",
]

# Pre-build the metric alternation regex
_METRIC_RE = "|".join(
    re.escape(m) if " " not in m else m.replace(" ", r"\s+")
    for m in CONSTRAINT_METRICS
)

NUMERIC_CONSTRAINT_PATTERNS: list[re.Pattern] = []
for _template in NUMERIC_CONSTRAINT_PATTERN_TEMPLATES:
    _pattern_str = _template.replace("{METRIC}", f"(?:{_METRIC_RE})")
    try:
        NUMERIC_CONSTRAINT_PATTERNS.append(re.compile(_pattern_str, re.IGNORECASE))
    except re.error:
        pass  # Skip malformed patterns gracefully
