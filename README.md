# GSE Guide Scraper

Scrapes, parses, and enriches Fannie Mae and Freddie Mac mortgage lending guidelines into RAG-ready chunks with MISMO-aligned metadata, entity extraction, ontology graph, and optional LLM enrichment.

**For complete usage instructions, see [USAGE.md](USAGE.md).**

## Architecture

```
Sitemap XML -> Discovery -> Scraper -> Parser -> Markdown Writer -> output/*.md
                                                                        |
                                                    Enrichment Pipeline <-
                                                         |
                                      Phase 1: Rule-based (12 steps)
                                        Domain Tagger, MISMO Extractor,
                                        Entity Extractor, Relationship Builder,
                                        Adaptive Chunker, Severity Classifier
                                                         |
                                      Phase 2: LLM (optional, --llm flag)
                                        Anthropic Claude / OpenAI
                                        Summaries, entities, constraints
                                                         |
                                                    enriched/chunks/*.txt
                                                    enriched/index.json
                                                    enriched/ontology.json
```

| Source | Method | Sections | Speed |
|--------|--------|----------|-------|
| Fannie Mae Selling Guide | `requests` + BeautifulSoup | ~423 | ~2 min (8 workers) |
| Freddie Mac Guide | Playwright (headless Chromium) | ~897 | ~1 hr (single-threaded) |

## Quick Start

```bash
# Install
pip install -e ".[dev]"
playwright install chromium

# Scrape
gse-guides scrape fannie-mae
gse-guides scrape freddie-mac

# Enrich
gse-guides enrich --stats

# Optional: LLM enrichment
pip install -e ".[llm]"
export ANTHROPIC_API_KEY="sk-ant-..."
gse-guides enrich --llm --llm-dry-run    # estimate cost
gse-guides enrich --llm                   # run it
```

## Commands

| Command | Description |
|---------|-------------|
| `gse-guides discover <source>` | List all section URLs from sitemap (no scraping) |
| `gse-guides scrape <source>` | Download and parse guide sections to markdown |
| `gse-guides status` | Show scraping progress from manifest files |
| `gse-guides enrich` | Build enriched RAG-ready chunks with metadata |

## Enrichment Pipeline

### Phase 1: Rule-Based (always runs, ~54 seconds)

| Step | What It Does |
|------|-------------|
| Content classification | `policy_rule`, `definition`, `procedure`, `eligibility_matrix`, `reference` |
| Domain tagging | MISMO-aligned domains (BORROWER, PROPERTY, LOAN, UNDERWRITING, etc.) |
| MISMO extraction | Enumeration values (LoanPurposeType, PropertyType, etc.) |
| Cross-source linking | Fannie Mae <-> Freddie Mac equivalent section mapping |
| Adaptive chunking | Heading-aware splitting, table preservation, undersized merging |
| Entity extraction | 13 entity types, 91 values (income sources, property types, etc.) |
| Constraint extraction | Numeric thresholds (LTV, CLTV, DTI, credit score, reserves) |
| Severity classification | `must_comply`, `should_comply`, `best_practice`, `info_only` |
| Ontology graph | 5 edge types, 8,690+ edges, reverse entity-to-chunk index |

### Phase 2: LLM Enrichment (optional, `--llm` flag)

| Enhancement | What It Adds |
|-------------|-------------|
| `llm_summary` | Requirement-focused natural-language summaries |
| `llm_entities` | Entities missed by regex (paraphrased, implied) |
| `llm_constraints` | Thresholds from complex tables that regex can't parse |
| `llm_relationships` | Implicit cross-section dependencies |

Cost: ~$3-5 with Claude Haiku for all 2,248 chunks. Cached for free re-runs.

## Output

- `output/` - Scraped markdown with YAML frontmatter (one `.md` per section)
- `enriched/chunks/` - Enriched chunk `.txt` files with metadata headers
- `enriched/index.json` - Searchable metadata index for all chunks
- `enriched/ontology.json` - Knowledge graph with entity relationships

## Development

```bash
pip install -e ".[dev]"
pytest                    # 566 tests, ~17 seconds
pytest --cov=gse_guides   # with coverage
```

## Project Structure

```
src/gse_guides/
  cli.py                         # 4 CLI commands
  config.py                      # ScraperConfig (50+ fields)
  models.py                      # 15 dataclasses, 2 enums
  base_scraper.py                # Retry, rate-limit, circuit-breaker
  fannie_mae/                    # HTTP scraper (requests + BS4)
  freddie_mac/                   # Browser scraper (Playwright)
  enrichment/
    pipeline.py                  # 12-step orchestrator
    taxonomy.py                  # Entity types, domain maps, patterns
    entity_extractor.py          # Typed entity + constraint extraction
    relationship_builder.py      # Ontology graph builder
    content_classifier.py        # Content type + severity
    adaptive_chunker.py          # Heading-aware chunking
    llm_provider.py              # Anthropic / OpenAI abstraction
    llm_enricher.py              # LLM orchestrator with caching
    llm_cache.py                 # Content-hash cache
    ...                          # 7 more enrichment modules
```
