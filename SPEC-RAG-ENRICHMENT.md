# RAG Enrichment & MISMO Metadata Spec

## 1. Problem

We have ~1,320 scraped markdown files (423 Fannie Mae + 897 Freddie Mac) with YAML frontmatter. The content is clean but needs enrichment before it's optimal for RAG retrieval. Current gaps:

- **No domain taxonomy** - sections aren't tagged by mortgage concept (LTV, DTI, income types, property types, etc.)
- **No MISMO alignment** - the industry-standard data model isn't mapped to guide content
- **Chunk sizing is basic** - section-level chunks only; some are 5,000 words, some are 16 words
- **Cross-source linking** - Fannie Mae B2-1.2-01 (LTV Ratios) and Freddie Mac 4201.x (LTV requirements) cover the same topic but aren't linked
- **No semantic enrichment** - no summaries, no key-term extraction, no regulatory intent tagging

## 2. MISMO Metadata Layer

### 2.1 What Is MISMO

[MISMO](https://www.mismo.org/) (Mortgage Industry Standards Maintenance Organization) maintains the Reference Model (v3.6.2 as of Oct 2025) - an XML schema defining ~3,000+ data points, containers, and enumerations covering the entire mortgage lifecycle. The [ULDD](https://singlefamily.fanniemae.com/delivering/uniform-mortgage-data-program/uniform-loan-delivery-dataset) (Uniform Loan Delivery Dataset) is the GSE-specific subset both Fannie and Freddie require for loan delivery.

### 2.2 MISMO Domain Taxonomy

Rather than mapping to every MISMO data point (which requires the paid reference model), we create a **domain taxonomy** aligned with MISMO's top-level containers and the actual guide structure:

```yaml
mortgage_domains:
  # MISMO top-level containers mapped to guide topics
  LOAN:
    - loan_purpose          # Purchase, Refinance, Cash-Out Refi
    - loan_type             # Conventional, FHA, VA, USDA
    - loan_amortization     # Fixed, ARM, Balloon
    - loan_limits           # Conforming, High-Balance, Super Conforming
    - loan_term             # 15yr, 20yr, 30yr

  BORROWER:
    - borrower_eligibility  # Citizenship, age, number of properties
    - borrower_income       # Employment, self-employment, other sources
    - borrower_assets       # Depository, non-depository, gifts, grants
    - borrower_credit       # Credit scores, credit history, derogatory events
    - borrower_liabilities  # DTI, monthly obligations, housing expense

  PROPERTY:
    - property_type         # SFR, Condo, Co-op, PUD, Manufactured
    - property_eligibility  # Occupancy, legal requirements, environmental
    - property_valuation    # Appraisals, desktop, hybrid, value acceptance
    - property_insurance    # Hazard, flood, title, MI

  UNDERWRITING:
    - manual_underwriting   # Risk assessment, compensating factors
    - du_automated          # DU findings, recommendations, validation
    - project_standards     # Condo/PUD/Co-op project review
    - special_programs      # HomeReady, High-LTV Refi, NACLI, HomeStyle

  CLOSING:
    - legal_documents       # Notes, security instruments, riders
    - title_requirements    # Title insurance, exceptions
    - closing_process       # Signatures, POA, eMortgages

  DELIVERY:
    - execution_options     # Whole loan, MBS, best efforts, mandatory
    - loan_delivery         # Data requirements, document delivery
    - mbs_securitization    # Pooling, guaranty fees, trading
    - servicing             # Transfer, concurrent, marketplace

  QUALITY_CONTROL:
    - lender_qc             # Prefunding, post-closing, reverification
    - gse_qc                # Fannie/Freddie reviews, remedies framework
    - representations       # Warranties, repurchase, enforcement relief

  COMPLIANCE:
    - regulatory            # Federal/state laws, responsible lending
    - fraud_prevention      # Detection, reporting
    - data_integrity        # Quality, confidentiality
```

### 2.3 MISMO Enumeration Tags

Key enumerations from MISMO that map directly to guide content:

```yaml
enumerations:
  LoanPurposeType:
    - Purchase
    - NoCashOutRefinance      # "Limited Cash-Out Refinance" in Fannie terms
    - CashOutRefinance

  PropertyUsageType:          # OccupancyType in guides
    - PrimaryResidence
    - SecondHome
    - Investor

  MortgageType:
    - Conventional
    - FHA
    - VA
    - USDARuralDevelopment

  PropertyType:
    - Detached
    - Attached
    - Condominium
    - Cooperative
    - ManufacturedHousing
    - PUD

  AmortizationType:
    - Fixed
    - AdjustableRate
    - GraduatedPaymentMortgage

  LienPriorityType:
    - FirstLien
    - SecondLien

  DocumentationType:
    - Full
    - Alternative
    - StreamlinedRefinance
```

## 3. Content Enrichment Pipeline

### 3.1 Architecture

```
scraped markdown files (output/)
        │
        ▼
  ┌─────────────┐
  │  Enrichment  │  Python pipeline (new module)
  │   Pipeline   │
  └─────┬───────┘
        │
        ├── 1. Domain Tagging (rule-based + keyword matching)
        ├── 2. MISMO Mapping (section code → domain taxonomy)
        ├── 3. Cross-Source Linking (Fannie ↔ Freddie topic alignment)
        ├── 4. Key Term Extraction (regex + domain glossary)
        ├── 5. Smart Re-chunking (adaptive by content type)
        └── 6. Summary Generation (optional, LLM-powered)
                │
                ▼
        enriched/ directory
        ├── fannie_mae/
        │   └── *.md  (enhanced frontmatter + chunk markers)
        ├── freddie_mac/
        │   └── *.md
        ├── chunks/
        │   └── *.txt  (one file per chunk, ready for embedding)
        └── index.json  (master index for RAG pipeline)
```

### 3.2 Enhanced Frontmatter Schema

```yaml
---
# Existing fields
source: fannie_mae
section_code: B2-1.2-01
title: Loan-to-Value (LTV) Ratios
url: https://...
# ... (all existing fields preserved)

# NEW: Domain taxonomy tags
domains:
  - LOAN.loan_purpose
  - UNDERWRITING.manual_underwriting
mismo_enumerations:
  - LoanPurposeType: [Purchase, NoCashOutRefinance, CashOutRefinance]
  - PropertyUsageType: [PrimaryResidence, SecondHome, Investor]

# NEW: Cross-source links
cross_source_links:
  - source: freddie_mac
    section_code: "4201.4"
    topic: LTV ratio requirements
    relationship: equivalent  # equivalent | related | supersedes

# NEW: Key terms extracted from content
key_terms:
  - LTV
  - CLTV
  - HCLTV
  - appraised value
  - sales price
  - loan-level price adjustment

# NEW: Content classification
content_type: policy_rule       # policy_rule | definition | procedure | eligibility_matrix | example | reference
regulatory_context: null        # e.g., "TILA", "RESPA", "Dodd-Frank" when applicable

# NEW: RAG metadata
summary: "Defines how LTV ratios are calculated for purchase and refinance transactions, including rounding rules and DU handling."
embedding_model: null           # Populated when embeddings generated
chunk_count: 3
---
```

### 3.3 Step Details

#### Step 1: Domain Tagging (Rule-Based)

Map each section to one or more domain taxonomy tags using:
- **Section code prefix** - deterministic mapping (e.g., B3-3.x → `BORROWER.borrower_income`)
- **Keyword matching** - scan content for domain-specific terms
- **Title matching** - section titles often directly name the domain

```python
# Deterministic mapping from Fannie Mae section code prefixes
FANNIE_DOMAIN_MAP = {
    "A1": ["COMPLIANCE.regulatory"],           # Seller/Servicer approval
    "A2": ["QUALITY_CONTROL.representations"], # Contractual obligations
    "A3": ["COMPLIANCE.regulatory"],           # Getting started
    "A4": ["COMPLIANCE.regulatory"],           # Maintaining eligibility
    "B1": ["UNDERWRITING.manual_underwriting"],# Application package
    "B2-1": ["LOAN.loan_purpose", "LOAN.loan_amortization", "LOAN.loan_limits"],
    "B2-2": ["BORROWER.borrower_eligibility"],
    "B2-3": ["PROPERTY.property_eligibility"],
    "B3-1": ["UNDERWRITING.manual_underwriting"],
    "B3-2": ["UNDERWRITING.du_automated"],
    "B3-3": ["BORROWER.borrower_income"],
    "B3-4": ["BORROWER.borrower_assets"],
    "B3-5": ["BORROWER.borrower_credit"],
    "B3-6": ["BORROWER.borrower_liabilities"],
    "B4-1": ["PROPERTY.property_valuation"],
    "B4-2": ["UNDERWRITING.project_standards"],
    "B5":   ["UNDERWRITING.special_programs"],
    "B6":   ["LOAN.loan_type"],                # Government programs
    "B7":   ["PROPERTY.property_insurance"],
    "B8":   ["CLOSING.legal_documents"],
    "C1":   ["DELIVERY.execution_options"],
    "C2":   ["DELIVERY.loan_delivery"],
    "C3":   ["DELIVERY.mbs_securitization"],
    "D1":   ["QUALITY_CONTROL.lender_qc"],
    "D2":   ["QUALITY_CONTROL.gse_qc"],
    "E":    ["reference"],
}

# Freddie Mac chapter ranges
FREDDIE_DOMAIN_MAP = {
    (1101, 1199): ["COMPLIANCE.regulatory"],
    (1201, 1299): ["COMPLIANCE.regulatory"],
    (1301, 1399): ["COMPLIANCE.regulatory"],
    (2101, 2199): ["QUALITY_CONTROL.representations"],
    (2301, 2399): ["BORROWER.borrower_eligibility"],
    (2401, 2499): ["PROPERTY.property_eligibility"],
    (2501, 2599): ["PROPERTY.property_eligibility"],
    (3101, 3199): ["BORROWER.borrower_income"],
    (3201, 3299): ["BORROWER.borrower_assets"],
    (3301, 3399): ["BORROWER.borrower_credit"],
    (3401, 3499): ["BORROWER.borrower_liabilities"],
    (4101, 4199): ["PROPERTY.property_valuation"],
    (4201, 4299): ["LOAN.loan_purpose"],
    (4301, 4399): ["UNDERWRITING.special_programs"],
    (4501, 4599): ["UNDERWRITING.project_standards"],
    (4601, 4699): ["CLOSING.legal_documents"],
    (5101, 5199): ["DELIVERY.loan_delivery"],
    (5201, 5299): ["DELIVERY.mbs_securitization"],
    (5601, 5699): ["DELIVERY.servicing"],
    (5701, 5799): ["DELIVERY.servicing"],
    (6101, 6199): ["QUALITY_CONTROL.lender_qc"],
}
```

#### Step 2: MISMO Enumeration Extraction

Scan content for MISMO-aligned enumeration values:

```python
MISMO_KEYWORD_PATTERNS = {
    "LoanPurposeType": {
        "Purchase": r"\bpurchase\s+transaction",
        "NoCashOutRefinance": r"\blimited\s+cash[- ]out\s+refinanc",
        "CashOutRefinance": r"\bcash[- ]out\s+refinanc",
    },
    "PropertyUsageType": {
        "PrimaryResidence": r"\bprimary\s+residence|principal\s+residence|owner[- ]occupied",
        "SecondHome": r"\bsecond\s+home",
        "Investor": r"\binvestment\s+propert",
    },
    "PropertyType": {
        "Condominium": r"\bcondo(?:minium)?",
        "Cooperative": r"\bco[- ]?op(?:erative)?",
        "ManufacturedHousing": r"\bmanufactured\s+hous",
        "PUD": r"\bPUD|planned\s+unit\s+development",
    },
    # ... more patterns
}
```

#### Step 3: Cross-Source Linking

Build a topic alignment map between Fannie Mae and Freddie Mac sections:

```python
# Known equivalences (curated, can be expanded)
CROSS_SOURCE_MAP = [
    # (fannie_section_pattern, freddie_chapter_range, topic)
    ("B2-1.2",  (4201, 4201), "LTV ratio requirements"),
    ("B2-1.3",  (4201, 4201), "Loan purpose / transaction type"),
    ("B2-2",    (2301, 2399), "Borrower eligibility"),
    ("B3-3",    (3101, 3199), "Income assessment"),
    ("B3-4",    (3201, 3299), "Asset assessment"),
    ("B3-5",    (3301, 3399), "Credit assessment"),
    ("B3-6",    (3401, 3499), "Liability / DTI assessment"),
    ("B4-1",    (4101, 4199), "Property valuation / appraisal"),
    ("B7",      (4801, 4899), "Insurance requirements"),
    # ... extend as needed
]
```

#### Step 4: Key Term Extraction

Extract domain-specific terms using a curated glossary + regex:

```python
MORTGAGE_TERMS = [
    # Ratios
    "LTV", "CLTV", "HCLTV", "DTI",
    # Income
    "W-2", "1040", "Schedule C", "Schedule E", "K-1", "VOE",
    # Credit
    "FICO", "credit score", "derogatory", "bankruptcy", "foreclosure",
    "short sale", "deed-in-lieu",
    # Property
    "appraisal", "comparable sale", "desktop appraisal", "hybrid appraisal",
    "value acceptance",
    # Programs
    "HomeReady", "HomeStyle", "High LTV", "DU", "Desktop Underwriter",
    # Regulatory
    "TRID", "TILA", "RESPA", "ATR/QM", "Dodd-Frank", "ECOA",
    # ... ~200 total terms
]
```

#### Step 5: Smart Re-Chunking

Adaptive chunking strategy based on content analysis:

```python
class AdaptiveChunker:
    """
    Chunk strategy varies by content type:

    - policy_rule (most sections): chunk at H2/H3 headings, 200-800 words
    - eligibility_matrix (tables): keep table + surrounding context intact
    - definition (glossary): one chunk per term
    - procedure (step-by-step): keep numbered lists intact
    - reference (E-sections): single chunk per section
    """

    # Target chunk sizes by content type
    CHUNK_TARGETS = {
        "policy_rule": (200, 800),     # min, max words
        "eligibility_matrix": (100, 1500),  # wider range to keep tables whole
        "definition": (20, 200),
        "procedure": (150, 600),
        "reference": (50, 2000),
    }
```

#### Step 6: Summary Generation (Optional, LLM-Powered)

For sections over 500 words, generate a 1-2 sentence summary for the frontmatter. This improves retrieval because the summary acts as a dense semantic anchor.

Two approaches:
- **Offline batch** - run through an LLM API (Claude or GPT) to generate summaries
- **Template-based** - use the section title + first paragraph + key terms to construct a summary without an LLM

Recommend starting with template-based (zero cost, deterministic) and optionally upgrading to LLM-generated later.

## 4. Output: RAG-Ready Chunks

### 4.1 Chunk File Format (for embedding)

```
enriched/chunks/fannie_mae__B2-1.2-01__ltv-ratios.txt
```

Contents:
```
Source: Fannie Mae Selling Guide
Section: B2-1.2-01 - Loan-to-Value (LTV) Ratios
Domains: LOAN.loan_purpose, UNDERWRITING.manual_underwriting
MISMO: LoanPurposeType(Purchase, NoCashOutRefinance, CashOutRefinance)
Key Terms: LTV, CLTV, HCLTV, appraised value, sales price
Freddie Mac Equivalent: Section 4201.4

---

[chunk content in markdown]
```

The metadata header gives the embedding model rich context for semantic similarity. When a user asks "What are the LTV requirements for a cash-out refinance?", the embedding of this chunk will match on:
- "LTV" in key terms
- "CashOutRefinance" in MISMO tags
- "Loan-to-Value" in the title
- The actual policy content

### 4.2 Master Index (`enriched/index.json`)

```json
{
  "version": "1.0",
  "generated_at": "2026-04-01T...",
  "sources": {
    "fannie_mae": { "sections": 423, "chunks": 1200 },
    "freddie_mac": { "sections": 897, "chunks": 2400 }
  },
  "total_chunks": 3600,
  "domain_distribution": {
    "BORROWER.borrower_income": 89,
    "PROPERTY.property_valuation": 67,
    "..."
  },
  "chunks": [
    {
      "chunk_id": "fannie_mae/B2-1.2-01/ltv-calculation",
      "file": "chunks/fannie_mae__B2-1.2-01__ltv-calculation.txt",
      "source": "fannie_mae",
      "section_code": "B2-1.2-01",
      "title": "LTV Ratio Calculation",
      "domains": ["LOAN.loan_purpose"],
      "mismo_tags": ["LoanPurposeType"],
      "key_terms": ["LTV", "appraised value"],
      "word_count": 342,
      "content_type": "policy_rule",
      "cross_source": ["freddie_mac/4201.4"]
    }
  ]
}
```

## 5. Implementation Plan

### New module: `src/gse_guides/enrichment/`

```
src/gse_guides/enrichment/
    __init__.py
    taxonomy.py          # Domain taxonomy definitions + MISMO enumerations
    domain_tagger.py     # Rule-based domain tagging
    mismo_extractor.py   # MISMO enumeration extraction from content
    cross_linker.py      # Cross-source topic alignment
    term_extractor.py    # Key mortgage term extraction
    adaptive_chunker.py  # Content-type-aware chunking
    summarizer.py        # Template-based summary generation
    pipeline.py          # Orchestrator: runs all steps in sequence
    writer.py            # Writes enriched files + chunk files + index
```

### CLI additions:

```bash
gse-guides enrich                          # Run full enrichment pipeline
gse-guides enrich --step domain-tag        # Run only domain tagging
gse-guides enrich --step chunk             # Run only re-chunking
gse-guides enrich --source fannie-mae      # Only enrich one source
gse-guides enrich --stats                  # Show enrichment statistics
```

### Dependencies to add:

None required for the rule-based pipeline. If LLM summaries are added later:
- `anthropic` or `openai` for summary generation
- `chromadb` or `faiss-cpu` for vector store (future phase)

## 6. Estimated Scope

| Module | Lines | Purpose |
|--------|-------|---------|
| `taxonomy.py` | ~150 | All domain/enum/term definitions |
| `domain_tagger.py` | ~100 | Section-to-domain mapping |
| `mismo_extractor.py` | ~80 | Regex-based enum extraction |
| `cross_linker.py` | ~80 | Cross-source alignment |
| `term_extractor.py` | ~60 | Key term scanning |
| `adaptive_chunker.py` | ~200 | Content-type-aware chunking |
| `summarizer.py` | ~60 | Template-based summaries |
| `pipeline.py` | ~120 | Orchestration + CLI |
| `writer.py` | ~100 | Output file generation |
| **Total** | **~950** | |

## 7. Open Questions

1. **MISMO depth** - Should we attempt to map individual data points (e.g., "LoanToValueRatioPercent") or stay at the container level? Full data point mapping requires access to the MISMO Logical Data Dictionary (paid/member resource).

2. **LLM summaries** - Worth the cost/complexity now, or start with template-based and iterate?

3. **Embedding model choice** - When we get to embeddings:
   - `text-embedding-3-small` (OpenAI, 1536 dim, cheapest)
   - `text-embedding-3-large` (OpenAI, 3072 dim, best quality)
   - `voyage-finance-2` (Voyage AI, domain-specialized for finance, 12-30% better on financial docs)
   - Local: `BAAI/bge-large-en-v1.5` (free, 1024 dim, good quality)

4. **Vector store** - ChromaDB (simplest), FAISS (fastest local), Pinecone/Weaviate (hosted)?

5. **Cross-source granularity** - Should we link at section level only, or also at subsection/chunk level?
