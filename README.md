# WAGE.md

Glassdoor is rumor. Levels.fyi is crowdsourced. The US Department of Labor publishes
employer-reported offered wages for H-1B and PERM cases by job title. WAGE.md ingests
those disclosures, normalizes them
across companies and role taxonomies, investigates anomalies, and serves
a citable salary index from Tiger Data.

## This is agentic, not a pipeline

WAGE.md is **three autonomous agents**, each running an observe → decide → act loop via
OpenAI function calling (shared `run_agent()` core, `max_iterations=5`):

| Agent | Goal | Decides |
|---|---|---|
| **Scout** | Keep the corpus fresh | Which source to poll next (staleness × change-probability × rate budget) |
| **Investigator** | Handle anomalies | Whether a data shift / WARN filing / new company warrants republishing |
| **Counselor** | Negotiation reports | What evidence to gather until confident, then ship a cited report |

Each agent returns its tool-call trace with the result so its decisions can be inspected.

## Tech stack

- **Backend:** Python 3.11+ · FastAPI · OpenAI (agent loops, normalization, reports)
- **Store:** Tiger Data (TimescaleDB/PostgreSQL) for filings, WARN notices, and wage queries
- **Briefs:** generated with OpenAI, stored and served from Tiger Data
- **Sources:** public DOL disclosures and California WARN reports
- **Frontend:** Next.js 14 App Router + Tailwind

## Quick start

```bash
cp .env.example .env.local   # set TIGER_DATABASE_URL and OPENAI_API_KEY
make setup                   # install agent + frontend deps
make schema                  # create tables and the WARN hypertable
make seed                    # optional: load DOL/WARN data (requires OpenAI)
make demo                    # start the API and frontend
```

For a smaller dataset, use the [FY2026 Q3 DOL samples](data-samples/README.md).

To expand the certified FY2026 Q3 Tiger Data seed to 80,000 filings for the ten target companies:

```bash
cd agent && uv run python -m src.ingestion.expand_corpus
```

This retains existing filings and adds eligible, certified, full-time H-1B cases from the
official FY2026 Q3 LCA workbook, then a reproducible hash selection from FY2025 Q1–Q4 LCA
workbooks. Downloads are cached in `data-cache/`; rerunning at the target inserts nothing.
New employer/title pairs require `OPENAI_API_KEY` for normalization.

`make schema` creates tables and applies compatible additions without deleting existing data.
It fails on incompatible tables.

## Make targets

| Command | Does |
|---|---|
| `make setup` | Install Python (uv) + Node deps, scaffold env |
| `make schema` | Create Tiger Data tables and the WARN hypertable |
| `make seed` | Load and normalize DOL/WARN data |
| `make ingest` | Run the Scout agent once |
| `make normalize` | Run the title/level normalization batch |
| `make publish` | Generate and store company briefs in Tiger Data |
| `make api` | Start the FastAPI server |
| `make frontend` | Start the Next.js dev server |
| `make demo` | Boot everything for video recording |

