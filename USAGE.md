# GSE Guide Scraper - Complete Usage Guide

A tool for scraping, parsing, enriching, and structuring Fannie Mae and Freddie Mac mortgage lending guidelines into RAG-ready chunks with rich metadata.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Commands](#commands)
   - [discover](#discover---find-all-section-urls)
   - [scrape](#scrape---download-guide-sections)
   - [status](#status---check-scraping-progress)
   - [enrich](#enrich---build-rag-ready-chunks)
4. [Output Structure](#output-structure)
5. [Enrichment Pipeline](#enrichment-pipeline)
6. [LLM Enrichment](#llm-enrichment)
7. [Configuration Reference](#configuration-reference)
8. [Typical Workflows](#typical-workflows)
9. [Architecture](#architecture)

---

## Installation

```bash
# Clone and install core dependencies
git clone <repo-url>
cd FreddyAndFannieMae
pip install -e .

# Install dev dependencies (pytest, coverage)
pip install -e ".[dev]"

# Install LLM support (Anthropic Claude / OpenAI)
pip install -e ".[llm]"

# Install everything
pip install -e ".[dev,llm]"

# Install Playwright browser (required for Freddie Mac scraping)
playwright install chromium
```

**Requirements:** Python 3.10+

---

## Quick Start

```bash
# 1. See what's available
gse-guides discover fannie-mae

# 2. Scrape Fannie Mae (takes ~2 minutes)
gse-guides scrape fannie-mae

# 3. Scrape Freddie Mac (takes ~1 hour)
gse-guides scrape freddie-mac

# 4. Enrich everything into RAG-ready chunks
gse-guides enrich

# 5. (Optional) Add LLM-powered enrichment
gse-guides enrich --llm --provider anthropic
```

After running steps 1-4, you'll have:
- `output/` - Raw scraped markdown files with YAML frontmatter
- `enriched/chunks/` - Enriched chunk text files with metadata headers
- `enriched/index.json` - Searchable index of all chunks
- `enriched/ontology.json` - Knowledge graph with entity relationships

---

## Commands

### `discover` - Find all section URLs

Parses the sitemap for a GSE source and lists every section URL without downloading anything. Useful for scoping the work before scraping.

```bash
gse-guides discover fannie-mae
gse-guides discover freddie-mac
```

**Arguments:**

| Argument | Values | Description |
|----------|--------|-------------|
| `source` | `fannie-mae`, `freddie-mac` | Which guide to discover |

**Options:**

| Option | Description |
|--------|-------------|
| `--verbose, -v` | Show debug logging |

**Output example:**
```
Discovered 423 sections:

Code                 Last Modified   URL
--------------------------------------------------------------------------------
A1-1-01              2026-03-04      https://selling-guide.fanniemae.com/sel/...
A1-1-02              2026-03-04      https://selling-guide.fanniemae.com/sel/...
...
```

**What it does:**
- Fetches the sitemap XML for the chosen source
- Extracts all section URLs (filters for guide content, ignores bulletins/forms)
- Displays each section code, last modified date, and full URL
- Makes no changes to disk

---

### `scrape` - Download guide sections

Fetches the HTML content of each guide section, parses it into structured data, and writes markdown files with YAML frontmatter.

```bash
# Scrape one source
gse-guides scrape fannie-mae
gse-guides scrape freddie-mac

# Scrape both sources
gse-guides scrape all

# Scrape a single section (useful for testing)
gse-guides scrape fannie-mae --section B3-3.1-01
gse-guides scrape freddie-mac --section 5703.1
```

**Arguments:**

| Argument | Values | Description |
|----------|--------|-------------|
| `source` | `fannie-mae`, `freddie-mac`, `all` | Which guide(s) to scrape |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--section CODE` | string | - | Scrape only this section code |
| `--output PATH` | path | `output/` | Directory for scraped markdown files |
| `--delay SECONDS` | float | 1.0 (Fannie), 3.0 (Freddie) | Override request delay between pages |
| `--no-resume` | flag | - | Ignore existing files, re-scrape everything |
| `--max-sections N` | int | unlimited | Limit number of sections (for testing) |
| `--workers, -w N` | int | 8 (Fannie), 1 (Freddie) | Number of parallel download threads |
| `--verbose, -v` | flag | - | Show debug logging |

**How each source is scraped:**

| Source | Method | Sections | Default Workers | Typical Time |
|--------|--------|----------|----------------|--------------|
| Fannie Mae | HTTP requests + BeautifulSoup | ~423 | 8 | ~2 minutes |
| Freddie Mac | Playwright headless Chromium | ~897 | 1 | ~1 hour |

Freddie Mac's guide is a JavaScript single-page application (Oracle RightNow framework) that requires a real browser to render content. Playwright automates a headless Chromium instance to load each page, wait for the SPA to render, then extract the HTML.

**Resilience features:**
- **Resume**: Skips already-scraped sections (disable with `--no-resume`)
- **Retry with backoff**: Retries on HTTP 429/500/502/503 with exponential backoff
- **Circuit breaker**: Pauses 60 seconds after 5 consecutive failures
- **Adaptive rate limiting**: Automatically slows down if rate-limited, speeds up after successes
- **Content quality gate**: Retries sections that produce fewer than 50 words
- **Atomic writes**: Manifest saved via write-then-rename to prevent corruption on crash

**Output example:**
```
============================================================
Scraping: fannie_mae
============================================================

Results:
  Discovered:        423
  Scraped:           423
  Skipped:           0
  Quality warnings:  2
  Failed:            0
```

---

### `status` - Check scraping progress

Shows how many sections have been discovered, scraped, skipped, and failed for each source. Reads from the manifest files in the output directory.

```bash
gse-guides status
gse-guides status --output /path/to/output
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output PATH` | path | `output/` | Output directory containing manifests |

**Output example:**
```
========================================
Source: fannie_mae
========================================
  Discovered: 423
  Scraped:    423
  Skipped:    0
  Failed:     0
  Started:    2026-04-01T10:30:00
  Updated:    2026-04-01T10:32:15
  Files:      423
```

---

### `enrich` - Build RAG-ready chunks

The main enrichment command. Reads scraped markdown files, runs a multi-step analysis pipeline, and produces enriched chunk files with metadata suitable for embedding and retrieval-augmented generation.

```bash
# Enrich all sources
gse-guides enrich

# Enrich one source
gse-guides enrich --source fannie-mae

# Only re-process changed files
gse-guides enrich --incremental

# Show detailed statistics
gse-guides enrich --stats

# Custom input/output directories
gse-guides enrich --output ./my-scrape --enriched ./my-enriched
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output PATH` | path | `output/` | Directory containing scraped markdown files |
| `--enriched PATH` | path | `enriched/` | Directory for enriched output |
| `--source` | choice | all | `fannie-mae` or `freddie-mac` (default: both) |
| `--incremental` | flag | - | Skip files unchanged since last run |
| `--stats` | flag | - | Print domain and content-type distributions |
| `--verbose, -v` | flag | - | Show debug logging |

**LLM options** (see [LLM Enrichment](#llm-enrichment) for details):

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--llm` | flag | - | Enable LLM-powered enrichment (Phase 2) |
| `--provider` | choice | `anthropic` | `anthropic` or `openai` |
| `--llm-model` | string | provider default | Override model (e.g. `claude-sonnet-4-20250514`) |
| `--llm-max-chunks N` | int | unlimited | Limit chunks sent to LLM (cost control) |
| `--llm-dry-run` | flag | - | Estimate LLM cost without making API calls |

**Output example:**
```
Enrichment Complete:
  Sections processed: 1320
  Chunks produced:    2248
  Avg chunk words:    302
  Cross-source links: 1847
```

With `--stats`:
```
  Domain Distribution:
    BORROWER.borrower_income                 245
    PROPERTY.property_appraisal              198
    UNDERWRITING.credit_analysis             187
    ...

  Content Type Distribution:
    policy_rule               1456
    procedure                  312
    definition                 245
    eligibility_matrix         142
    reference                   93
```

---

## Output Structure

### Scraped Output (`output/`)

```
output/
  fannie_mae/
    part_a/
      a1-1-01_lender-approval.md
      a1-1-02_representations-and-warranties.md
      ...
    part_b/
      b3-3.1-01_general-income-information.md
      ...
    part_c/ ...
    part_d/ ...
    part_e/ ...
    manifest.json              # Scrape state for resume
  freddie_mac/
    chapter_1101/
      1101.1_overview.md
      ...
    chapter_5703/
      5703.1_income-documentation.md
      ...
    manifest.json
```

Each `.md` file has YAML frontmatter:

```yaml
---
source: fannie_mae
section_code: B3-3.1-01
title: General Income Information
url: https://selling-guide.fanniemae.com/sel/b3-3.1-01/...
part: B
part_name: Origination Through Closing
chapter: B3-3
chapter_name: Income Assessment
effective_date: "2026-03-04"
word_count: 1847
table_count: 1
subsections:
  - Stable and Predictable Income
  - Continuance of Income
  - DU Documentation Requirements
cross_references: [B3-3.1-02, B3-3.2-01, B5-7-02]
scraped_at: "2026-04-01T12:34:56"
---

# B3-3.1-01: General Income Information

[Full markdown content of the section...]
```

### Enriched Output (`enriched/`)

```
enriched/
  chunks/
    fannie_mae__B3-3.1-01__intro.txt
    fannie_mae__B3-3.1-01__stable-and-predictable-income.txt
    fannie_mae__B3-3.1-01__continuance-of-income.txt
    ...
  index.json                   # Full metadata index for all chunks
  ontology.json                # Knowledge graph (edges, entity index)
  state.json                   # Incremental processing state
  .llm_cache/                  # LLM result cache (if --llm used)
```

Each chunk `.txt` file has a metadata header:

```
Source: fannie_mae
Section: B3-3.1-01 - General Income Information
Subsection: Stable and Predictable Income
Domains: BORROWER.borrower_income, UNDERWRITING.income_analysis
MISMO: LoanPurposeType(Purchase, Refinance)
Key Terms: income, employment, DTI, stable income
Entities: income_sources=SelfEmployment,W2Employment; occupancy_types=PrimaryResidence
Requirement: type=eligibility, severity=must_comply
Constraints: LTV<=80%
Cross-Source: freddie_mac/5703.1
Content Type: policy_rule
Summary: B3-3.1-01 (General Income Information) covers borrower income. Key topics: ...
---

[Chunk content in markdown...]
```

### Index File (`enriched/index.json`)

A JSON file with metadata for every chunk, enabling programmatic search:

```json
{
  "version": "1.0",
  "total_chunks": 2248,
  "domain_distribution": { "BORROWER.borrower_income": 245, ... },
  "content_type_distribution": { "policy_rule": 1456, ... },
  "chunks": [
    {
      "chunk_id": "fannie_mae/B3-3.1-01/intro",
      "source": "fannie_mae",
      "section_code": "B3-3.1-01",
      "title": "General Income Information",
      "heading": null,
      "domains": ["BORROWER.borrower_income"],
      "mismo_tags": { "LoanPurposeType": ["Purchase"] },
      "key_terms": ["income", "DTI", "employment"],
      "content_type": "policy_rule",
      "summary": "B3-3.1-01 covers ...",
      "word_count": 302,
      "has_table": false,
      "entities": { "income_sources": ["SelfEmployment"] },
      "requirement": { "type": "eligibility", "severity": "must_comply" },
      "numeric_constraints": [
        { "metric": "LTV", "operator": "<=", "value": "80", "unit": "%" }
      ]
    }
  ]
}
```

### Ontology File (`enriched/ontology.json`)

A knowledge graph representing relationships between entities, sections, and constraints:

```json
{
  "version": "1.0",
  "edges": [
    { "type": "APPLIES_TO", "source": "fannie_mae/B3-3.1-01/intro", "target": "income_sources.SelfEmployment" },
    { "type": "IMPLIES", "source": "property_types.Condo", "target": "project_types.ProjectReview" },
    { "type": "CONSTRAINS", "source": "occupancy_types.Investment", "target": "LTV<=80%" },
    { "type": "EQUIVALENT", "source": "fannie_mae/B3-3.1-01", "target": "freddie_mac/5703.1" },
    { "type": "CONDITIONAL", "source": "fannie_mae/B4-2.2-01/intro", "target": "B4-2.2-01" }
  ],
  "sections_by_entity": {
    "income_sources.SelfEmployment": ["fannie_mae/B3-3.5-01/intro", ...],
    "property_types.Condo": ["fannie_mae/B4-2.2-01/intro", ...]
  },
  "entity_types": { ... },
  "numeric_constraints": [ ... ],
  "stats": { "total_edges": 8690, "total_entity_values": 91 }
}
```

**Edge types:**

| Edge Type | Meaning | Example |
|-----------|---------|---------|
| `APPLIES_TO` | Chunk discusses this entity | chunk -> `property_types.Condo` |
| `IMPLIES` | Domain knowledge implication | `Condo` -> `ProjectReview` required |
| `CONSTRAINS` | Entity scopes a numeric limit | `Investment` -> `LTV<=80%` |
| `EQUIVALENT` | Same topic across GSEs | Fannie B3-3.1-01 <-> Freddie 5703.1 |
| `CONDITIONAL` | "If X, see section Y" pattern | "If condo, see B4-2.2-01" |

---

## Enrichment Pipeline

The enrichment pipeline transforms raw scraped markdown into structured, metadata-rich chunks through these steps:

### Phase 1: Rule-Based Enrichment (always runs)

| Step | Module | What It Does |
|------|--------|--------------|
| 1 | `content_classifier` | Classifies each section as `policy_rule`, `definition`, `procedure`, `eligibility_matrix`, or `reference` based on section codes, titles, and content patterns |
| 2 | `domain_tagger` | Tags with MISMO-aligned domains like `BORROWER.borrower_income`, `PROPERTY.property_appraisal`, `UNDERWRITING.credit_analysis` using section code patterns and keyword fallback |
| 3 | `mismo_extractor` | Extracts MISMO enumeration values (e.g., `LoanPurposeType: [Purchase, Refinance]`, `PropertyType: [Condominium]`) via regex patterns |
| 4 | `cross_linker` | Maps equivalent sections between Fannie Mae and Freddie Mac (e.g., B3-3.1-01 <-> 5703.1) using a static mapping table |
| 5 | `adaptive_chunker` | Splits sections at H2/H3/H4 heading boundaries. Preserves tables intact. Merges undersized chunks (<30 words). Limits chunks to ~800 words (1500 for tables) |
| 6 | `term_extractor` | Identifies 163 domain-specific mortgage terms (LTV, DTI, CLTV, amortization, etc.) in each chunk |
| 7 | `entity_extractor` | Extracts typed entities across 13 categories (91 values total) via compiled regex patterns. Categories include income sources, property types, transaction types, occupancy types, loan types, credit events, and more |
| 8 | `entity_extractor` | Extracts numeric constraints (LTV <= 80%, credit score >= 620, etc.) from 8 regex templates covering LTV, CLTV, HCLTV, DTI, credit score, reserves, and housing expense ratio |
| 9 | `entity_extractor` | Detects conditional cross-references ("if property is a condo, see Section B4-2.2-01") |
| 10 | `content_classifier` | Classifies requirement severity (`must_comply`, `should_comply`, `best_practice`, `info_only`) and requirement type (`eligibility`, `documentation`, `calculation`, `guideline`) |
| 11 | `summarizer` | Generates template-based summary for the first chunk of each section |
| 12 | `relationship_builder` | Builds the ontology knowledge graph with 5 edge types, reverse entity index, and aggregated constraints |

### Phase 2: LLM Enrichment (optional, `--llm` flag)

When enabled, an LLM analyzes each chunk and produces enhanced metadata stored in separate `llm_` prefixed fields:

| Enhancement | What It Adds |
|-------------|-------------|
| `llm_summary` | Natural-language summary describing what the section *requires*, not just what it discusses |
| `llm_entities` | Entities the regex patterns missed (e.g., paraphrased or implied entities) |
| `llm_constraints` | Numeric thresholds extracted from complex tables and prose that regex can't parse |
| `llm_relationships` | Implicit cross-section dependencies and conditional requirements |

LLM results never overwrite rule-based results - they're stored alongside with clear provenance.

---

## LLM Enrichment

The optional LLM enrichment pass uses an AI model to enhance what the rule-based pipeline already extracted.

### Setup

```bash
# Install LLM dependencies
pip install -e ".[llm]"

# Set your API key (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

### Usage

```bash
# Estimate cost before running (no API calls)
gse-guides enrich --llm --llm-dry-run

# Run LLM enrichment with Anthropic Claude (default, cheapest)
gse-guides enrich --llm

# Use OpenAI instead
gse-guides enrich --llm --provider openai

# Use a specific model
gse-guides enrich --llm --llm-model claude-sonnet-4-20250514

# Process only 10 chunks (for testing)
gse-guides enrich --llm --llm-max-chunks 10

# Combine options
gse-guides enrich --llm --provider anthropic --llm-max-chunks 50 --verbose
```

### Cost Estimates

| Model | Input Cost | Output Cost | Est. Total (2,248 chunks) |
|-------|-----------|-------------|--------------------------|
| Claude Haiku (default) | $0.25/MTok | $1.25/MTok | ~$3-5 |
| Claude Sonnet | $3/MTok | $15/MTok | ~$30-50 |
| GPT-4o-mini (default) | $0.15/MTok | $0.60/MTok | ~$2-4 |
| GPT-4o | $2.50/MTok | $10/MTok | ~$25-40 |

### Cost Controls

| Control | How to Use |
|---------|-----------|
| **Dry run** | `--llm-dry-run` estimates cost without calling the API |
| **Chunk limit** | `--llm-max-chunks 50` processes at most 50 chunks |
| **Running cost log** | Cost logged to console every 100 chunks |
| **Caching** | Re-runs skip unchanged chunks automatically |
| **Cheapest default** | Haiku/4o-mini selected by default, override with `--llm-model` |

### Caching

LLM results are cached based on a SHA-256 hash of (chunk content + model + prompt version). This means:

- **Re-running** `--llm` on unchanged content is free (100% cache hits)
- **Changing the model** (`--llm-model`) invalidates the cache for all chunks
- **Changed content** (after re-scraping) automatically invalidates affected chunks
- Cache stored in `enriched/.llm_cache/`

---

## Configuration Reference

All configuration lives in `ScraperConfig` (defined in `src/gse_guides/config.py`). Settings are controlled via CLI options; the table below shows all fields with their defaults.

### Output Paths

| Field | Default | Description |
|-------|---------|-------------|
| `output_dir` | `output/` | Directory for scraped markdown files |
| `enriched_dir` | `enriched/` | Directory for enriched chunks, index, and ontology |

### Rate Limiting

| Field | Default | Description |
|-------|---------|-------------|
| `fannie_request_delay_seconds` | `1.0` | Seconds between Fannie Mae requests |
| `freddie_request_delay_seconds` | `3.0` | Seconds between Freddie Mac requests |
| `max_retries` | `3` | Max retry attempts per section (range: 0-10) |
| `retry_backoff_factor` | `2.0` | Exponential backoff multiplier |
| `request_timeout_seconds` | `30` | HTTP request timeout |
| `adaptive_rate_limit` | `True` | Auto-adjust delay based on server responses |
| `max_rate_limit_delay` | `30.0` | Maximum delay when rate-limited |

### Playwright (Freddie Mac)

| Field | Default | Description |
|-------|---------|-------------|
| `playwright_headless` | `True` | Run browser in headless mode |
| `playwright_page_load_timeout_ms` | `30000` | Max wait for page to load |
| `playwright_content_wait_selector` | `.rn_Answer` | CSS selector to wait for |

### Chunking

| Field | Default | Description |
|-------|---------|-------------|
| `enrich_chunk_min_words` | `30` | Merge chunks smaller than this |
| `enrich_chunk_max_words` | `800` | Target max chunk size |
| `enrich_table_max_words` | `1500` | Max size for table-containing chunks |

### Concurrency

| Field | Default | Description |
|-------|---------|-------------|
| `max_workers` | `1` | Number of parallel threads |
| `fannie_default_workers` | `8` | Default workers for Fannie Mae |
| `freddie_default_workers` | `1` | Default workers for Freddie Mac (Playwright limit) |

### Resilience

| Field | Default | Description |
|-------|---------|-------------|
| `quality_min_words` | `50` | Retry sections producing fewer words |
| `circuit_breaker_threshold` | `5` | Consecutive failures before cooldown |
| `circuit_breaker_cooldown_seconds` | `60.0` | Pause duration after circuit break |
| `manifest_save_interval` | `25` | Save manifest every N sections |

### LLM Enrichment

| Field | Default | Description |
|-------|---------|-------------|
| `llm_provider` | `anthropic` | LLM provider (`anthropic` or `openai`) |
| `llm_model` | `""` | Model override (empty = provider default) |
| `llm_batch_size` | `10` | Chunks per processing batch |
| `llm_max_chunks` | `None` | Max chunks to process (None = all) |
| `llm_cache_enabled` | `True` | Cache LLM results to disk |
| `llm_dry_run` | `False` | Estimate cost without API calls |
| `llm_prompt_version` | `1.0` | Bump to invalidate all caches |
| `llm_max_retries` | `3` | Retry on transient API errors |
| `llm_timeout_seconds` | `60` | Per-request timeout |

---

## Typical Workflows

### First-time full scrape and enrichment

```bash
# 1. Scrape both sources
gse-guides scrape all

# 2. Check results
gse-guides status

# 3. Enrich with full statistics
gse-guides enrich --stats
```

### Update after guide changes

```bash
# Re-scrape (skips unchanged sections automatically)
gse-guides scrape all

# Re-enrich only changed files
gse-guides enrich --incremental
```

### Test with a small sample

```bash
# Scrape just 10 sections from Fannie Mae
gse-guides scrape fannie-mae --max-sections 10

# Enrich them
gse-guides enrich --source fannie-mae

# Try LLM on 5 chunks
gse-guides enrich --llm --llm-max-chunks 5 --source fannie-mae
```

### Scrape a single section for debugging

```bash
# Fannie Mae section
gse-guides scrape fannie-mae --section B3-3.1-01 --verbose

# Freddie Mac section
gse-guides scrape freddie-mac --section 5703.1 --verbose
```

### Cost-conscious LLM enrichment

```bash
# Check cost estimate first
gse-guides enrich --llm --llm-dry-run

# Run on a sample to verify quality
gse-guides enrich --llm --llm-max-chunks 20

# Full run with cheapest model (default)
gse-guides enrich --llm

# Re-run is free (cached)
gse-guides enrich --llm
```

---

## Architecture

```
                    DISCOVERY                  SCRAPING                    PARSING
                 +----------------+       +----------------+       +----------------+
  Sitemap XML    |  discovery.py  |       |  scraper.py    |       |  parser.py     |
  ------------->  |               | ----> |                | ----> |                |
                 | SectionURL[]   | HTTP/ | Raw HTML       | BS4/  | GuideSection   |
                 +----------------+ Play- +----------------+ DOM   +-------+--------+
                                   wright                                  |
                                                                           v
                    WRITING                    ENRICHMENT
                 +----------------+       +----------------+
                 |  writer.py     |       |  pipeline.py   |
                 |                | <---- |                | <----- GuideSection[]
                 |  output/*.md   |       |  10-step rule  |
                 +----------------+       |  pipeline      |
                                          +-------+--------+
                                                  |
                         +------------------------+--------------------+
                         |                        |                    |
                    +---------+            +------------+       +----------+
                    | chunks/ |            | index.json |       | ontology |
                    | *.txt   |            |            |       | .json    |
                    +---------+            +------------+       +----------+
                         |
                         v  (optional)
                 +------------------+
                 |  LLM Enrichment  |
                 |  (--llm flag)    |
                 |                  |
                 | llm_provider.py  |  <--- Anthropic / OpenAI API
                 | llm_enricher.py  |
                 | llm_cache.py     |
                 +------------------+
```

### Source Files

```
src/gse_guides/
  __init__.py                    # slugify utility
  __main__.py                    # Entry point
  cli.py                         # 4 CLI commands: discover, scrape, status, enrich
  config.py                      # ScraperConfig dataclass (50+ fields)
  models.py                      # All data models (15 dataclasses, 2 enums)
  base_scraper.py                # Abstract base with retry/rate-limit/circuit-breaker
  markdown_converter.py          # HTML -> Markdown
  chunker.py                     # Semantic chunking (scrape phase)
  writer.py                      # Markdown file writer

  fannie_mae/
    discovery.py                 # Sitemap parsing (~423 sections)
    parser.py                    # HTML -> GuideSection (Drupal CMS)
    scraper.py                   # requests-based, 8 parallel workers

  freddie_mac/
    discovery.py                 # Sitemap parsing (~897 sections)
    parser.py                    # SPA DOM -> GuideSection
    scraper.py                   # Playwright-based, single-threaded

  enrichment/
    pipeline.py                  # 12-step orchestrator
    taxonomy.py                  # Domain maps, entity types (91 values), MISMO patterns
    domain_tagger.py             # Section -> domain tags
    content_classifier.py        # Content type + severity classification
    adaptive_chunker.py          # Heading-aware splitting with table preservation
    mismo_extractor.py           # MISMO enumeration extraction
    term_extractor.py            # 163 mortgage term patterns
    entity_extractor.py          # Typed entity + constraint + conditional ref extraction
    cross_linker.py              # Fannie <-> Freddie section mapping
    summarizer.py                # Template-based + LLM summary generation
    relationship_builder.py      # Ontology graph (5 edge types, 8,690+ edges)
    writer.py                    # Chunk files + index.json + ontology.json
    llm_provider.py              # Abstract provider + Anthropic/OpenAI implementations
    llm_enricher.py              # LLM orchestrator with prompts, batching, cost tracking
    llm_cache.py                 # Content-hash cache for LLM results
```

### Tests

```bash
# Run all tests (566 tests, ~17 seconds)
pytest

# Run with coverage
pytest --cov=gse_guides --cov-report=html

# Run a specific test file
pytest tests/test_llm_enricher.py -v
```
