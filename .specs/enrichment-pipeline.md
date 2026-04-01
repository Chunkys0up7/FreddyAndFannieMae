# Change Spec: RAG Enrichment Pipeline with MISMO Metadata

## 1. Summary

**What:** Add an enrichment pipeline that reads scraped GSE guide markdown files and produces RAG-ready chunk text files with MISMO-aligned domain tags, cross-source links, key terms, adaptive sub-heading chunking, and metadata headers suitable for OpenAI embeddings.

**Why:** The scraped markdown is clean but lacks the semantic metadata and fine-grained chunking needed for high-precision RAG retrieval. A user asking "What are the LTV requirements for a cash-out refinance on a second home?" needs the pipeline to match against domain tags (`LOAN.loan_purpose`), MISMO enums (`CashOutRefinance`, `SecondHome`), and granular chunks — not entire 3,000-word sections.

**Size estimate:** Large

## 2. Project Context

- **Project aim:** Build a searchable knowledge base over Fannie Mae and Freddie Mac lending guidelines for RAG-powered Q&A.
- **Current state:** Scraping pipeline complete. ~1,320 markdown files in `output/` with YAML frontmatter (source, section_code, title, hierarchy, word_count, cross_references, related_announcements). Existing `SemanticChunker` creates section-level and heading-level chunks, but only during the scrape phase and only writes `<!-- chunk -->` markers into the markdown files. No standalone chunk files. No domain taxonomy.
- **Desired state:** An `enriched/` directory containing:
  - One `.txt` file per chunk with a metadata header + markdown content (ready for OpenAI `text-embedding-3-small` ingestion)
  - A master `index.json` mapping every chunk with its metadata
  - Enhanced metadata on each chunk: domain tags, MISMO enumerations, key terms, cross-source links, content type classification, and a template-based summary
- **Success criteria:**
  1. `gse-guides enrich` runs on the full `output/` directory and produces `enriched/chunks/*.txt` + `enriched/index.json`
  2. Every chunk file has a well-formed metadata header parseable as YAML
  3. Every section is tagged with at least one domain from the taxonomy
  4. Cross-source links connect at least the 10 major topic areas (income, credit, assets, property, LTV, etc.)
  5. Chunk granularity is at the lowest heading level (H2/H3/H4) with table-aware boundaries
  6. `gse-guides enrich --stats` reports domain distribution, chunk count, and avg chunk size
  7. A placeholder `summarizer.py` defines the LLM interface but does not call any external API

## 3. Blast Radius Analysis

- **Files created (new `enrichment/` subpackage):**
  - `src/gse_guides/enrichment/__init__.py`
  - `src/gse_guides/enrichment/taxonomy.py` — domain taxonomy, MISMO enums, mortgage terms
  - `src/gse_guides/enrichment/domain_tagger.py` — section code → domain mapping + keyword scan
  - `src/gse_guides/enrichment/mismo_extractor.py` — regex-based MISMO enum extraction from content
  - `src/gse_guides/enrichment/cross_linker.py` — Fannie ↔ Freddie topic alignment
  - `src/gse_guides/enrichment/term_extractor.py` — key mortgage term scanning
  - `src/gse_guides/enrichment/content_classifier.py` — classify section as policy_rule / definition / procedure / eligibility_matrix / reference
  - `src/gse_guides/enrichment/adaptive_chunker.py` — content-type-aware chunking at lowest heading level
  - `src/gse_guides/enrichment/summarizer.py` — template-based summary + LLM interface placeholder
  - `src/gse_guides/enrichment/pipeline.py` — orchestrator: reads markdown, runs all steps, writes output
  - `src/gse_guides/enrichment/writer.py` — writes chunk .txt files + index.json

- **Files modified:**
  - `src/gse_guides/models.py` — add `EnrichedChunk` and `EnrichmentResult` dataclasses
  - `src/gse_guides/config.py` — add enrichment config fields
  - `src/gse_guides/cli.py` — add `enrich` command
  - `pyproject.toml` — no new dependencies needed (all stdlib + pyyaml already present)

- **Interfaces affected:** None of the existing scraper interfaces change. The enrichment pipeline reads the output files as input; it does not modify the scraping pipeline.

- **Downstream dependents:** None yet. The chunk .txt files are the interface to a future embedding pipeline.

- **Side effects:** Creates the `enriched/` directory tree on disk.

## 4. Design

### Approach

The enrichment pipeline is a **read-only post-processor** over the scraped markdown. It does not re-scrape or modify the `output/` files. The pipeline:

1. Reads each `.md` file from `output/{source}/`, parses the YAML frontmatter and markdown body
2. Applies enrichment steps in sequence (tagging, extraction, linking, chunking)
3. Writes one `.txt` file per chunk to `enriched/chunks/`
4. Writes a master index to `enriched/index.json`

### Key decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MISMO depth | Container/enumeration level (free) | Full data-point mapping requires paid MISMO membership; container-level gives 90% of the retrieval benefit |
| Chunking granularity | Lowest heading level (H2/H3/H4) with table-aware boundaries | User asked for "lowest possible level"; heading-based splits preserve semantic coherence while maximizing granularity |
| Chunk file format | Plain text with YAML-like metadata header | OpenAI embeddings accept plain text; the metadata header gets embedded alongside content, improving semantic matching |
| LLM summaries | Template-based now, interface for LLM later | User confirmed LLM will be called but not in this environment |
| Cross-source linking | Subsection/chunk level where possible | User asked for lowest possible level; we link at topic level and propagate to chunks |
| Domain tagging | Deterministic (section code mapping) + keyword boost | Rule-based is fast, deterministic, and auditable; no model dependency |

### Alternatives considered

- **Embedding during enrichment** — Rejected. User wants OpenAI embeddings but not in this env. The pipeline produces the text files; embedding is a separate step.
- **Single enriched .md file (modify frontmatter in-place)** — Rejected. Enrichment should not mutate scraper output. Separate `enriched/` dir keeps concerns clean.
- **JSON chunks instead of .txt** — Rejected. OpenAI embeddings want plain text input. Metadata in the text header is simpler than JSON parsing.

### Constraints & assumptions

- Input: `output/` directory with `.md` files produced by the scraper, each with YAML frontmatter
- The scraper may still be running for Freddie Mac; enrichment should work on whatever files exist
- No network calls. No external API calls. Pure local file processing.
- Python 3.10+, same dependency set as the scraper (no new packages)

## 5. Task Breakdown

```
Task 1: Add enrichment dataclasses to models.py
  Context: The enrichment pipeline needs data containers for enriched chunks and
           pipeline results. These go in the shared models module alongside existing
           scraper models.
  Action:  Add EnrichedChunk dataclass (chunk_id, source, section_code, title,
           domains, mismo_tags, key_terms, content_type, summary, cross_source_links,
           word_count, content) and EnrichmentResult dataclass (total_sections,
           total_chunks, domain_distribution, errors).
  Verify:  Import the new classes from gse_guides.models without error.
  Depends: none

Task 2: Add enrichment config fields to config.py
  Context: The enrichment pipeline needs its own config (enriched output dir, chunk
           size targets per content type, whether to enable LLM summaries).
  Action:  Add to ScraperConfig: enriched_dir (Path, default "enriched"),
           chunk_min_words (int, 30), chunk_max_words (int, 800),
           enable_llm_summaries (bool, False).
  Verify:  ScraperConfig() instantiates with new defaults.
  Depends: none

Task 3: Create taxonomy.py with all definitions
  Context: This is the foundation — the domain taxonomy, MISMO enumeration patterns,
           mortgage term glossary, section-code-to-domain mappings, and cross-source
           alignment map. Every other enrichment module reads from this.
  Action:  Create src/gse_guides/enrichment/taxonomy.py with:
           - DOMAIN_TAXONOMY dict (8 top-level domains, ~30 sub-domains)
           - FANNIE_DOMAIN_MAP dict (section code prefix → domain list)
           - FREDDIE_DOMAIN_MAP dict (chapter range → domain list)
           - MISMO_PATTERNS dict (enum name → {value: regex pattern})
           - MORTGAGE_TERMS list (~150 terms)
           - CROSS_SOURCE_MAP list of (fannie_pattern, freddie_range, topic, relationship)
           - CONTENT_TYPE_SIGNALS dict (content_type → keyword patterns)
  Verify:  Import taxonomy.py; assert len(MORTGAGE_TERMS) > 100;
           assert all Fannie Mae part codes (A-E) have mappings.
  Depends: none

Task 4: Create domain_tagger.py
  Context: Tags each section with one or more domains from the taxonomy. Uses the
           deterministic section-code mapping as primary, keyword scanning as secondary.
  Action:  Create DomainTagger class with:
           - tag(section_code, source, content) -> list[str] method
           - _match_by_code() for deterministic prefix matching
           - _match_by_keywords() for content scanning against DOMAIN_TAXONOMY keywords
  Verify:  DomainTagger().tag("B3-3.1-02", FANNIE_MAE, "") returns ["BORROWER.borrower_income"];
           DomainTagger().tag("4201.4", FREDDIE_MAC, "") returns ["LOAN.loan_purpose"].
  Depends: Task 3

Task 5: Create mismo_extractor.py
  Context: Scans chunk content for MISMO enumeration values using regex. Extracts
           which enum values are discussed in a given piece of text.
  Action:  Create MismoExtractor class with:
           - extract(content) -> dict[str, list[str]] method
           Returns e.g. {"LoanPurposeType": ["Purchase", "CashOutRefinance"]}.
  Verify:  extract("cash-out refinance on a primary residence") returns
           {"LoanPurposeType": ["CashOutRefinance"], "PropertyUsageType": ["PrimaryResidence"]}.
  Depends: Task 3

Task 6: Create term_extractor.py
  Context: Scans content for domain-specific mortgage terms from the glossary.
           Terms in the metadata header improve embedding recall.
  Action:  Create TermExtractor class with:
           - extract(content) -> list[str] method
           Uses case-insensitive matching against MORTGAGE_TERMS. Deduplicates.
  Verify:  extract("The LTV ratio must not exceed 80% for this FICO range") returns
           list containing "LTV" and "FICO".
  Depends: Task 3

Task 7: Create content_classifier.py
  Context: Classifies each section into a content type (policy_rule, definition,
           procedure, eligibility_matrix, reference). This determines chunking strategy.
  Action:  Create ContentClassifier class with:
           - classify(section_code, title, content, has_tables, source) -> str method
           Uses CONTENT_TYPE_SIGNALS from taxonomy + heuristics:
           - E-3 sections → "definition"
           - Sections with tables + "eligib" in title → "eligibility_matrix"
           - Sections with numbered steps → "procedure"
           - E-1, E-2 → "reference"
           - Default → "policy_rule"
  Verify:  classify("E-3-02", ...) → "definition";
           classify("B2-1.2-01", "LTV Ratios", content_with_tables) → "eligibility_matrix".
  Depends: Task 3

Task 8: Create cross_linker.py
  Context: Connects equivalent/related sections across Fannie Mae and Freddie Mac.
           Links propagate to chunks so RAG can retrieve both sources for a topic.
  Action:  Create CrossLinker class with:
           - link(section_code, source) -> list[dict] method
           Each dict: {"source": str, "section_code": str, "topic": str, "relationship": str}
           Uses CROSS_SOURCE_MAP from taxonomy.
  Verify:  link("B3-3.1-02", FANNIE_MAE) returns list containing freddie_mac income sections.
  Depends: Task 3

Task 9: Create adaptive_chunker.py
  Context: The core chunking engine. Splits markdown content at the lowest heading
           level (H2/H3/H4) while keeping tables intact. Chunk size targets vary by
           content type. This REPLACES the existing SemanticChunker for enrichment
           purposes (the scraper chunker is untouched).
  Action:  Create AdaptiveChunker class with:
           - chunk(content_markdown, content_type, section_code, source) -> list[dict]
           Each dict: {"heading": str|None, "content": str, "word_count": int, "has_table": bool}
           Algorithm:
           1. Split at H2/H3/H4 heading boundaries (regex on markdown)
           2. For each split, check if it contains a table block
           3. If chunk > max_words AND no table: split at paragraph boundaries
           4. If chunk < min_words: merge with previous chunk
           5. For "definition" type: split at bold term patterns
           6. Intro text before first heading becomes its own chunk
  Verify:  Given markdown with 3 H2 headings, returns 4 chunks (intro + 3 heading chunks).
           Given markdown with a table spanning 1500 words, table stays in one chunk.
  Depends: Task 2

Task 10: Create summarizer.py
  Context: Generates a 1-2 sentence summary per section. Template-based for now,
           with a clearly defined interface for LLM integration later.
  Action:  Create Summarizer class with:
           - summarize(title, section_code, domains, key_terms, first_paragraph) -> str
           Template approach: "{title} covers {domains_readable}. Key topics include
           {top_3_terms}."
           - summarize_llm(content, section_code) -> str  [NOT IMPLEMENTED — raises
             NotImplementedError with message about configuring LLM provider]
  Verify:  summarize("LTV Ratios", "B2-1.2-01", ["LOAN.loan_purpose"], ["LTV", "CLTV"], ...)
           returns a non-empty string under 200 chars.
  Depends: none

Task 11: Create enrichment writer (enrichment/writer.py)
  Context: Writes the enriched chunk .txt files and master index.json. Each chunk
           file has a YAML-like metadata header followed by the chunk content.
  Action:  Create EnrichmentWriter class with:
           - write_chunk(enriched_chunk: EnrichedChunk, output_dir: Path) -> Path
             Writes: enriched/chunks/{source}__{section_code}__{slug}.txt
             Format:
               Source: {source}
               Section: {section_code} - {title}
               Domains: {comma-separated}
               MISMO: {enum(values), ...}
               Key Terms: {comma-separated}
               Cross-Source: {links}
               Content Type: {type}
               Summary: {summary}
               ---
               {chunk content}
           - write_index(chunks: list[EnrichedChunk], output_dir: Path) -> Path
             Writes enriched/index.json with full metadata for every chunk.
  Verify:  Write a chunk, read it back, verify header parses and content preserved.
  Depends: Task 1

Task 12: Create pipeline.py (orchestrator)
  Context: The main orchestrator that reads scraped markdown, runs all enrichment
           steps, and writes output. This is the entry point called by the CLI.
  Action:  Create EnrichmentPipeline class with:
           - __init__(config: ScraperConfig)
           - run(source: str | None = None) -> EnrichmentResult
           Flow:
           1. Glob output/{source}/**/*.md
           2. For each file: parse YAML frontmatter + body
           3. Classify content type
           4. Tag domains
           5. Extract MISMO enums
           6. Extract key terms
           7. Get cross-source links
           8. Generate summary
           9. Run adaptive chunker on the body
           10. For each chunk: create EnrichedChunk with all metadata
           11. Write chunk file
           12. After all files: write index.json
           13. Return EnrichmentResult with stats
  Verify:  Run on 5 test markdown files. Verify chunk files created, index.json valid.
  Depends: Tasks 1-11

Task 13: Add `enrich` command to CLI
  Context: Exposes the enrichment pipeline as a CLI command consistent with existing
           scrape/discover/status commands.
  Action:  Add to cli.py:
           - `enrich` command with options: --output, --source, --stats, --verbose
           - `--stats` flag: runs pipeline then prints domain distribution, chunk count,
             avg chunk size, cross-source link count
  Verify:  `python -m gse_guides enrich --source fannie-mae --stats` runs without error
           and produces output in enriched/ directory.
  Depends: Task 12

Task 14: Integration verification
  Context: Verify all pieces work together end-to-end and the output is suitable
           for OpenAI embedding ingestion.
  Action:  Run `gse-guides enrich` on existing scraped output. Verify:
           - enriched/chunks/ contains .txt files
           - enriched/index.json is valid JSON with expected schema
           - Spot-check 5 chunk files for correct metadata headers
           - Verify domain coverage (every section has >= 1 domain)
           - Verify chunk sizes are within target ranges
           - Verify cross-source links present for major topics
           - Verify no import errors, no crashes, no silent failures
  Verify:  All acceptance criteria from Section 2 pass.
  Depends: Task 13
```

## 6. Risks & Mitigations

- **Risk:** Freddie Mac chapter-to-domain mapping is approximate (based on chapter number ranges, not verified against all 897 sections).
  **Likelihood:** Medium. **Impact:** Low (worst case: a section gets tagged "General" instead of a specific domain).
  **Mitigation:** Keyword-based secondary tagging catches misclassified sections. The mapping can be refined incrementally as we inspect output.

- **Risk:** Adaptive chunking at H4 level may produce very small chunks (<30 words) for some sections.
  **Likelihood:** Medium. **Impact:** Low (small chunks get merged with neighbors).
  **Mitigation:** Merge logic in adaptive_chunker ensures no chunk falls below min_words threshold.

- **Risk:** Cross-source linking map is manually curated and incomplete.
  **Likelihood:** High (we can't cover all 1,320 sections by hand). **Impact:** Low (missing links reduce recall but don't break anything).
  **Mitigation:** Start with 15-20 major topic areas. Log sections that have no cross-source links for future refinement.

- **Risk:** Regex-based MISMO extraction may produce false positives (e.g., "purchase" in a context unrelated to LoanPurposeType).
  **Likelihood:** Medium. **Impact:** Low (extra tags slightly reduce precision but don't break retrieval).
  **Mitigation:** Patterns use multi-word phrases ("purchase transaction", "cash-out refinance") not single words.

## 7. Verification Plan

- **Integration check:** `gse-guides enrich` completes without error on the full scraped dataset. `enriched/index.json` loads as valid JSON. Every chunk file in `enriched/chunks/` has a parseable metadata header.

- **Regression check:** Existing scraper functionality unchanged. `gse-guides scrape fannie-mae --section A2-1-01` still works. `gse-guides status` still works. No modifications to scraper output files.

- **Acceptance criteria:**
  1. `enriched/chunks/` contains >= 2,000 `.txt` files (avg ~2.5 chunks per section across 1,320 sections)
  2. `enriched/index.json` has valid schema with `chunks` array
  3. 100% of sections have at least 1 domain tag
  4. >= 10 cross-source topic areas linked
  5. No chunk exceeds 1,500 words (except tables)
  6. No chunk under 20 words (after merging)
  7. `--stats` flag prints readable statistics
  8. `summarizer.summarize_llm()` raises `NotImplementedError` with clear message
