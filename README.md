# GSE Guide Scraper

Scrapes, parses, and enriches Fannie Mae and Freddie Mac mortgage lending guidelines into RAG-ready chunks with MISMO-aligned metadata.

## Architecture

```
Sitemap XML ─> Discovery ─> Scraper ─> Parser ─> Markdown Writer ─> output/*.md
                                                                        │
                                                    Enrichment Pipeline ◄┘
                                                         │
                                           Domain Tagger, MISMO Extractor,
                                           Term Extractor, Cross-Linker,
                                           Adaptive Chunker, Summarizer
                                                         │
                                                    enriched/chunks/*.txt
                                                    enriched/index.json
```

| Source | Method | Sections | Speed |
|--------|--------|----------|-------|
| Fannie Mae Selling Guide | `requests` + BeautifulSoup | ~423 | ~2 min (8 workers) |
| Freddie Mac Guide | Playwright (headless Chromium) | ~897 | ~1 hr (4 workers) |

## Setup

```bash
# Install
pip install -e ".[dev]"

# Playwright browser (required for Freddie Mac)
playwright install chromium
```

## Usage

```bash
# Discover sections (no scraping)
gse-guides discover fannie-mae
gse-guides discover freddie-mac

# Scrape all sections
gse-guides scrape fannie-mae
gse-guides scrape freddie-mac
gse-guides scrape all

# Scrape with options
gse-guides scrape freddie-mac --workers 4 --max-sections 50 --verbose
gse-guides scrape fannie-mae --section B3-3.1-01

# Check progress
gse-guides status

# Enrich for RAG
gse-guides enrich
gse-guides enrich --incremental --stats
gse-guides enrich --source fannie-mae
```

## CLI Options

### `scrape`
| Flag | Description |
|------|-------------|
| `--section CODE` | Scrape a single section |
| `--output PATH` | Output directory (default: `output/`) |
| `--delay SECONDS` | Override request delay |
| `--no-resume` | Re-scrape everything |
| `--max-sections N` | Limit sections (for testing) |
| `--workers N` | Parallel workers (default: 8 Fannie, 4 Freddie) |
| `--verbose` | Debug logging |

### `enrich`
| Flag | Description |
|------|-------------|
| `--output PATH` | Scraped output directory |
| `--enriched PATH` | Enriched output directory |
| `--source` | Only enrich one source |
| `--incremental` | Skip unchanged files |
| `--stats` | Print domain/content-type distributions |

## Output Format

### Scraped Markdown (`output/`)
Each section is a `.md` file with YAML frontmatter:
```yaml
---
source: fannie_mae
section_code: B3-3.1-01
title: General Income Information
effective_date: "2026-03-04"
word_count: 1847
table_count: 1
cross_references: [B3-3.1-02, B3-3.2-01]
---
```

### Enriched Chunks (`enriched/`)
Each chunk is a `.txt` file with metadata header:
```
Source: fannie_mae
Section: B3-3.1-01 - General Income Information
Domains: BORROWER.borrower_income
MISMO: LoanPurposeType(Purchase, Refinance)
Key Terms: debt-to-income, employment, income
Content Type: policy_rule
---
```

Plus `enriched/index.json` with full metadata for all chunks.

## Resilience Features

- **Parallel scraping**: ThreadPoolExecutor with per-source worker defaults
- **Adaptive rate limiting**: Backs off on HTTP 429/503, speeds up after consecutive successes
- **Circuit breaker**: Pauses after 5 consecutive failures, aborts if failures continue
- **Content quality gate**: Retries sections producing <50 words
- **Atomic manifest writes**: Write-then-rename prevents corruption on crash
- **Resume**: Skips already-scraped sections based on manifest

## Enrichment Pipeline

| Step | Module | Description |
|------|--------|-------------|
| 1 | `content_classifier` | Classifies as policy_rule, definition, procedure, eligibility_matrix, or reference |
| 2 | `domain_tagger` | Tags with MISMO-aligned domains (BORROWER, PROPERTY, LOAN, etc.) |
| 3 | `mismo_extractor` | Extracts MISMO enumeration values (LoanPurposeType, PropertyType, etc.) |
| 4 | `cross_linker` | Links equivalent sections across Fannie Mae and Freddie Mac |
| 5 | `adaptive_chunker` | Splits at H2/H3/H4 boundaries, preserves tables, merges undersized |
| 6 | `term_extractor` | Extracts 163 domain-specific mortgage terms |
| 7 | `summarizer` | Template-based summary (LLM placeholder available) |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=gse_guides --cov-report=html
```

## Project Structure

```
src/gse_guides/
  __init__.py              # slugify utility
  models.py                # All dataclasses and enums
  config.py                # ScraperConfig
  base_scraper.py          # Abstract base with retry/rate-limit/circuit-breaker
  markdown_converter.py    # HTML -> Markdown
  chunker.py               # Semantic chunking (scrape phase)
  writer.py                # Markdown file writer
  cli.py                   # Click CLI
  fannie_mae/
    discovery.py           # Sitemap parsing
    parser.py              # HTML -> GuideSection
    scraper.py             # requests-based scraper
  freddie_mac/
    discovery.py           # Sitemap parsing
    parser.py              # SPA DOM -> GuideSection
    scraper.py             # Playwright-based scraper
  enrichment/
    pipeline.py            # Orchestrator
    taxonomy.py            # Domain maps, MISMO patterns, terms
    domain_tagger.py       # Section -> domain tags
    mismo_extractor.py     # Content -> MISMO enums
    term_extractor.py      # Content -> mortgage terms
    content_classifier.py  # Section -> content type
    cross_linker.py        # Fannie <-> Freddie linking
    adaptive_chunker.py    # Heading-aware chunking
    summarizer.py          # Template + LLM placeholder
    writer.py              # Chunk files + index.json
```
