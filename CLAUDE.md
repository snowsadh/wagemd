# WAGE.md project context

Read the workspace [AGENTS.md](../AGENTS.md) and this project's [README.md](README.md)
before changing code. `SPEC.md`, `DECISIONS.md`, `PROGRESS.md`, and `VIDEO_SCRIPT.md`
are historical planning records; verify their claims against the current code.

WAGE.md is a salary index backed by employer-reported offered wages in US Department of
Labor PERM and H-1B LCA disclosures. The current Tiger Data database holds 26,555
FY2026 Q3 sample filings across ten companies. See [data-samples/README.md](data-samples/README.md)
for source, selection, and limitations.

## Current architecture

- FastAPI and three OpenAI tool-calling agents live under `agent/src/`.
- `agent/src/ingestion/download.py` streams public XLSX files directly from DOL and
  California EDD. `dol_flag.py` and `warn_ca.py` parse them.
- Tiger Data stores filings, WARN notices, anomalies, and generated company briefs.
- The Investigator stores briefs in `published_pages`; `/index` and `/briefs/{company}`
  serve them through the API. The frontend's `/briefs` routes render the local Index.
- `frontend/` is Next.js 14 with the API URL configured by `NEXT_PUBLIC_API_URL`.
- Secrets belong only in the gitignored `.env.local`.

## Useful commands

Run `make help` for targets. `make schema` applies idempotent Tiger Data schema changes;
`make seed` downloads the current FY2026 Q3 DOL files and California WARN report;
`make publish` generates local company briefs; `make demo` starts API and frontend.
Run `uv run pytest` from `agent/` and `npm run build` from `frontend/` after changes.
