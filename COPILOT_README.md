# GSE Guideline Copilot

Local-first, full-stack copilot for Fannie Mae and Freddie Mac selling/servicing guides.
Ingests guide content, detects new bulletins, and surfaces it through a CopilotKit-powered
React frontend backed by a LangGraph agent.

> This sub-project lives alongside the existing `src/gse_guides/` scraper.
> It is a fresh implementation per `gseguidelinecopilotspecv2.md`.

## Architecture

```
docker compose up
├── gse-chroma     ChromaDB vector store (persisted in volume)
├── gse-pipeline   Python pipeline + REST API (Apify, PDF parse, ingestion)
├── gse-agent      FastAPI + LangGraph + CopilotKit Python SDK
└── gse-frontend   Next.js + CopilotKit (self-hosted runtime)
```

## Prerequisites

- Docker + Docker Compose
- An [Apify](https://console.apify.com) account (free tier works)
- An [Anthropic](https://console.anthropic.com) or [OpenAI](https://platform.openai.com) API key

## Quick Start

```bash
# 1. Configure
cp .env.example .env
# Edit .env: APIFY_TOKEN, ANTHROPIC_API_KEY (or OPENAI_API_KEY)

# 2. Build + start all services
docker compose up -d

# 3. Populate vector store with guide content (first run only)
./scripts/seed.sh

# 4. Open the copilot
open http://localhost:3000
```

## Services & Ports

| Service | Port | Purpose |
|---|---|---|
| `gse-frontend` | 3000 | Next.js dashboard + CopilotKit sidebar |
| `gse-agent` | 8000 | LangGraph agent + CopilotKit endpoint |
| `gse-pipeline` | 8001 | REST API for bulletins/sections/reviews |
| `gse-chroma` | 8500 | ChromaDB HTTP API |

## Pipeline CLI

Run inside the pipeline container:

```bash
docker compose exec gse-pipeline python -m pipeline.main --all
docker compose exec gse-pipeline python -m pipeline.main --fannie
docker compose exec gse-pipeline python -m pipeline.main --freddie
docker compose exec gse-pipeline python -m pipeline.main --bulletins
docker compose exec gse-pipeline python -m pipeline.main --schedule
docker compose exec gse-pipeline python -m pipeline.main --all --dry-run
```

## What Gets Ingested

| Source | Method | Content |
|---|---|---|
| Fannie Mae Selling Guide | Apify Website Content Crawler | ~300 sections from `selling-guide.fanniemae.com` |
| Freddie Mac Guide | Direct PDF download | Full guide PDF, parsed with `pdfplumber` |
| Bulletins (both) | Apify shallow crawl | New bulletin announcements detected by ID diff |

## Configuration

All config flows through `.env` → docker-compose → service env vars. See
`pipeline/pipeline/config.py` for tunable defaults (chunk size, crawl limits, etc.).

## Development

```bash
# Pipeline tests
docker compose exec gse-pipeline pytest

# Agent tests
docker compose exec gse-agent pytest

# Frontend dev mode (outside docker)
cd frontend && npm install && npm run dev
```

## Reset

```bash
./scripts/reset.sh   # Wipes ChromaDB + SQLite, keeps containers
```

## Demo Flow

1. Start services → seed pipeline
2. Open `localhost:3000` → see bulletin feed
3. Select a bulletin → click "What changed?" suggestion → agent renders DiffView
4. Ask "Compare Fannie and Freddie on gift funds" → agent renders ComparisonTable
5. Ask "What are the gift fund requirements?" → agent cites B3-4.3-04
6. Click "Flag for QI review" → action persists, status updates

## Files Not Touched

This copilot scaffold does not modify the existing `src/gse_guides/` scraper, its tests,
or the original `README.md`. They remain functional and are ignored by the new services.
