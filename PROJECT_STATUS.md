# GSE Guide Scraper — Project Status

**Last updated:** 2026-04-02
**Repository:** https://github.com/Chunkys0up7/FreddyAndFannieMae
**Latest commit:** `6181af0` on `main`

---

## What This Project Does

Scrapes the complete Fannie Mae Selling Guide and Freddie Mac Seller/Servicer Guide — the two authoritative sources for U.S. conforming mortgage underwriting rules — and transforms them into RAG-ready enriched text chunks suitable for embedding and retrieval-augmented generation.

### Pipeline

```
Discovery → Scraping → Chunking → Enrichment → Output
```

1. **Discovery** — Parses XML sitemaps to find all guide section URLs
2. **Scraping** — Fetches HTML (Fannie) or renders SPA via Playwright (Freddie), parses into structured `GuideSection` objects
3. **Chunking** — Splits sections into semantic chunks at heading boundaries (50–2000 words, never mid-table)
4. **Enrichment** — Applies domain tagging, MISMO metadata, content classification, mortgage term extraction, cross-source linking, and summarization
5. **Output** — Writes enriched `.txt` chunks with metadata headers + master `index.json`

---

## Current Scraping Results

| Source | Discovered | Scraped | Quality Warnings | Failed | Files on Disk |
|--------|-----------|---------|-----------------|--------|---------------|
| Fannie Mae | 423 | 422 | 0 | 0 | 423 |
| Freddie Mac | 897 | 882 | 15 | 0 | 919 |
| **Total** | **1,320** | **1,304** | **15** | **0** | **1,342** |

### Enrichment Output

| Metric | Value |
|--------|-------|
| Sections processed | 1,342 |
| Enriched chunks produced | 2,248 |
| Average chunk word count | 410 |
| Cross-source links | 11,120 |
| Output format | `.txt` files with markdown content |

### Domain Distribution (top 10)

| Domain | Chunks |
|--------|--------|
| COMPLIANCE.regulatory | 525 |
| BORROWER.borrower_liabilities | 272 |
| DELIVERY.servicing | 250 |
| BORROWER.borrower_assets | 209 |
| BORROWER.borrower_income | 208 |
| PROPERTY.property_type | 155 |
| PROPERTY.property_eligibility | 151 |
| CLOSING.legal_documents | 150 |
| UNDERWRITING.special_programs | 115 |
| QUALITY_CONTROL.gse_qc | 97 |

### Content Type Distribution

| Type | Chunks |
|------|--------|
| policy_rule | 1,037 |
| procedure | 889 |
| reference | 152 |
| eligibility_matrix | 91 |
| definition | 79 |

---

## Architecture

### Source Layout

```
src/gse_guides/
├── __init__.py              # slugify(), safe_path_component() utilities
├── __main__.py              # python -m gse_guides entry point
├── models.py                # 14 dataclasses (GuideSection, Chunk, EnrichedChunk, etc.)
├── config.py                # ScraperConfig with 30+ validated parameters
├── cli.py                   # Click CLI: scrape, enrich, status, discover commands
├── base_scraper.py          # Abstract base: rate limiting, retries, circuit breaker, resume
├── chunker.py               # SemanticChunker (heading-based splits, min/max bounds)
├── writer.py                # MarkdownWriter (YAML frontmatter + chunk markers)
├── markdown_converter.py    # HTML → markdown (tables, links, nested lists)
│
├── fannie_mae/
│   ├── discovery.py         # Sitemap parsing + TOC fallback
│   ├── parser.py            # HTML → GuideSection (Drupal CMS structure)
│   └── scraper.py           # requests + BeautifulSoup, thread-local sessions
│
├── freddie_mac/
│   ├── discovery.py         # Sitemap parsing for SPA section URLs
│   ├── parser.py            # Playwright-rendered DOM → GuideSection
│   └── scraper.py           # Playwright headless Chromium, single-thread
│
└── enrichment/
    ├── pipeline.py          # Orchestrator: reads scraped → applies enrichment → writes chunks
    ├── taxonomy.py          # Domain taxonomy, MISMO patterns, 160+ mortgage terms, cross-maps
    ├── domain_tagger.py     # Section-code + keyword → domain assignment
    ├── content_classifier.py # policy_rule | procedure | definition | eligibility_matrix | reference
    ├── mismo_extractor.py   # Regex extraction of MISMO enumeration values
    ├── term_extractor.py    # Mortgage term identification (pre-compiled patterns)
    ├── cross_linker.py      # Fannie ↔ Freddie section equivalence mapping
    ├── adaptive_chunker.py  # Heading-aware content splitting with table preservation
    ├── summarizer.py        # Template-based chunk summaries
    └── writer.py            # .txt chunk files + index.json output
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Two scraper implementations** | Fannie Mae is static HTML (requests + BS4), Freddie Mac is a JavaScript SPA requiring Playwright browser rendering |
| **ThreadPoolExecutor for Fannie, single-thread for Freddie** | Playwright's sync API uses greenlets bound to the creating thread — cannot be called from pool threads |
| **Abstract BaseScraper** | Shared retry logic, adaptive rate limiting, circuit breaker, manifest management, resume capability |
| **Rule-based enrichment (no LLM)** | Deterministic, reproducible, fast. Section codes map directly to domains. 160+ regex patterns for terms |
| **MISMO-aligned taxonomy** | Industry-standard mortgage data model. 8 domains, ~30 sub-domains matching MISMO containers |
| **Atomic file writes** | `os.replace()` pattern prevents corrupt manifests/indexes on crash |
| **Content quality gate** | Sections <50 words get retried; if still low, marked QUALITY_WARNING instead of failing |
| **Cross-source linking** | 15 explicit Fannie→Freddie mappings enable side-by-side GSE comparison for RAG queries |

### Resilience Features

- **Adaptive rate limiting** — doubles delay on 429/503, reduces 25% after 3 consecutive 200s, ±15% jitter
- **Exponential backoff** — configurable retries with ±25% jitter on backoff delays
- **Circuit breaker** — aborts after N consecutive failures (default 8), with configurable cooldown
- **Resume capability** — manifest tracks per-section status + content hashes; skips already-scraped sections
- **Path traversal protection** — `safe_path_component()` strips `..`, `/`, `\`, null bytes from all path inputs
- **URL validation** — HTTPS-only, domain-matched URLs in discovery modules

---

## Test Suite

| Metric | Value |
|--------|-------|
| Test files | 17 (16 test files + conftest.py) |
| Total tests | 463 |
| Runtime | ~5 seconds |
| Coverage | ~92% |

### Test File Breakdown

| File | Tests | Coverage Area |
|------|-------|---------------|
| test_config.py | 52 | Config defaults, validation, edge cases, URL scheme checks |
| test_cli.py | 37 | Click CLI commands, options, worker propagation |
| test_fannie_parser.py | 66 | HTML parsing, metadata extraction, subsections, cross-refs |
| test_freddie_parser.py | 56 | SPA DOM parsing, title extraction, content selectors |
| test_fannie_discovery.py | 41 | Sitemap parsing, URL validation, TOC fallback |
| test_freddie_discovery.py | 32 | Section URL discovery from sitemap |
| test_scrapers.py | 37 | Both scraper implementations with mocked HTTP/Playwright |
| test_enrichment_pipeline.py | 38 | Full pipeline orchestration |
| test_enrichment.py | ~40 | Domain tagger, MISMO extractor, term extractor, classifier |
| test_main_writer.py | 34 | MarkdownWriter output, frontmatter, chunk markers |
| test_base_scraper.py | ~30 | Rate limiting, retries, manifest, circuit breaker |
| test_chunker.py | ~15 | Semantic chunking, heading splits, table preservation |
| test_markdown_converter.py | ~10 | HTML→markdown conversion |
| test_models.py | ~10 | Dataclass instantiation and validation |
| test_slugify.py | ~5 | URL-safe slug generation |
| test_writer.py | ~10 | Basic writer output |

All tests use mocking (`unittest.mock`, `responses` library) — no live HTTP calls.

---

## Dependencies

### Runtime
| Package | Version | Purpose |
|---------|---------|---------|
| requests | ~2.31 | Fannie Mae HTTP scraping |
| beautifulsoup4 | ~4.12 | HTML parsing |
| lxml | ≥5.0 | Fast HTML/XML parser backend |
| playwright | ~1.40 | Freddie Mac SPA browser automation |
| markdownify | ≥0.12 | HTML → markdown conversion |
| pyyaml | ~6.0 | YAML frontmatter output |
| click | ~8.1 | CLI framework |
| tqdm | ~4.66 | Progress bars |

### Dev
| Package | Version | Purpose |
|---------|---------|---------|
| pytest | ~7.0 | Test framework |
| pytest-cov | ~4.0 | Coverage reporting |
| responses | ~0.24 | HTTP request mocking |

---

## What Was Built (Chronological)

### Session 1 — Initial Build
- Core scraping infrastructure (BaseScraper, Fannie/Freddie scrapers, discovery, parsers)
- Markdown conversion and writer
- Semantic chunker
- Enrichment pipeline with full taxonomy
- CLI with scrape/enrich/status/discover commands

### Session 2 — Hardening & Quality
- Replaced magic numbers with named constants throughout
- Added `ScraperConfig.__post_init__` validation (10 numeric params + HTTPS URL checks)
- Deduplicated `safe_path_component()` into shared utility
- Added URL validation to both discovery modules (`_is_valid_url()`)
- Made `enrichment/writer.py` use atomic writes (`os.replace()`)
- Fixed `_parse_frontmatter` crash on malformed YAML delimiters
- Fixed `_normalize_whitespace` ordering (strip trailing spaces before collapsing newlines)
- Changed `lxml~=5.0` → `lxml>=5.0` and `markdownify~=0.12` → `markdownify>=0.12` for version compatibility
- Built 17 test files achieving 92% coverage (463 tests)
- Cleaned 1,127 tracked output/enriched/pyc artifacts from git

### Session 3 — Freddie Mac Fix & Full Scrape
- **Fixed Playwright greenlet threading bug** — The root cause was `_create_scrapers()` using `config.max_workers != 1` to detect explicit `--workers`, which treated `-w 1` as "not set" and defaulted Freddie Mac to 4 workers. Playwright's sync API uses greenlets bound to the creating thread, so ThreadPoolExecutor threads can't call it. Fix: changed `freddie_default_workers` to 1 and added explicit `user_set_workers` boolean parameter.
- **Fixed Freddie Mac title extraction** — `<h1>` contained site branding "Seller/Servicer Guide" instead of section title. Added regex filter to skip branding, falls through to `<h2>` which has the actual title. Batch-fixed 746 existing files.
- **Fixed `_should_skip` resume logic** — Discovery returns section code as slug (e.g., `1101.1`), but files were written with title-based slugs (e.g., `introduction-to-the-guide`). Added prefix matching (`section_code + "_"`) to detect existing files regardless of slug.
- **Rebuilt Freddie Mac manifest** from disk files to restore accurate skip counts after corrupted threaded runs.
- Completed Fannie Mae scrape: 422/423 sections in 70 seconds
- Completed Freddie Mac scrape: 882/897 sections (151 remaining after resume) in ~83 minutes
- Ran enrichment pipeline: 1,342 sections → 2,248 chunks

---

## CLI Usage

```bash
# Scrape both sources
python -m gse_guides scrape all

# Scrape one source
python -m gse_guides scrape fannie-mae
python -m gse_guides scrape freddie-mac -w 1

# Scrape a single section
python -m gse_guides scrape fannie-mae --section B3-3.1-01

# Check progress
python -m gse_guides status

# Discover URLs without scraping
python -m gse_guides discover fannie-mae

# Enrich scraped content
python -m gse_guides enrich --stats

# Options
python -m gse_guides scrape all --delay 2.0 --max-sections 10 --no-resume -v
```

---

## Output Structure

```
output/
├── fannie_mae/
│   ├── manifest.json                    # Scrape state tracking
│   ├── B1-1/
│   │   ├── b1-1-01_general-loan-eligibility.md
│   │   └── ...
│   └── B3-3/
│       ├── b3-3.1-01_general-income-information.md
│       └── ...
├── freddie_mac/
│   ├── manifest.json
│   ├── chapter_1101/
│   │   ├── 1101.1_introduction-to-the-guide.md
│   │   └── ...
│   └── chapter_4201/
│       └── ...

enriched/
├── index.json                           # Master index with all chunk metadata
└── chunks/
    ├── fannie_mae__B3-3.1-01__intro.txt
    ├── freddie_mac__4201.1__investment-quality-mortgage.txt
    └── ... (2,248 files)
```

### Scraped File Format (`.md`)
```yaml
---
source: fannie_mae
section_code: B3-3.1-01
title: General Income Information
url: https://selling-guide.fanniemae.com/sel/...
part: B
part_name: Origination Through Closing
chapter: B3
chapter_name: Underwriting Borrowers
effective_date: '2025-12-17'
word_count: 2847
table_count: 3
subsections:
  - Income Documentation Requirements
  - ...
cross_references:
  - B3-3.1-02
  - ...
---
# B3-3.1-01: General Income Information
...markdown content...
```

### Enriched Chunk Format (`.txt`)
```
source: fannie_mae
section_code: B3-3.1-01
title: General Income Information
heading: Income Documentation Requirements
domains: BORROWER.borrower_income
content_type: policy_rule
mismo_tags: DocumentationType=Full
key_terms: VOE, W-2, 1040, DTI
summary: Requirements for documenting borrower income...
cross_source_links: freddie_mac/3101.1 (equivalent)

## Income Documentation Requirements
...markdown content...
```
