# DECISIONS.md — architectural decision log

Each entry: decision · rationale · alternatives considered. Helps future sessions
understand WHY things are the way they are.

---

## D1 — Three autonomous agents, not a pipeline
**Decision:** Build Scout, Investigator, and Counselor as observe→decide→act loops over
Gemini function calling, rather than a fixed ETL pipeline with scheduled steps.
**Rationale:** Autonomy is 20% of judging and the core differentiator vs. "just another
chatbot demo." Agents that *select* tools based on observed state produce a Lapdog trace
tree that visibly proves agency.
**Alternatives:** (a) Cron-driven pipeline — simpler but not agentic, fails the core
criterion. (b) Single mega-agent — harder to demo distinct decision-making and muddies the
trace tree. Rejected both.

## D2 — One generic `run_agent()` shared by all three agents
**Decision:** Implement a single `run_agent(goal, tools, system_prompt, max_iterations=5)`
in `core/agent_loop.py`; specialize per agent only via tools + system prompt.
**Rationale:** Shared loop = shared Lapdog instrumentation, one place to enforce the
iteration cap, less code to maintain in an 8-hour build.
**Alternatives:** Three bespoke loops — more duplication, inconsistent tracing. Rejected.

## D3 — `max_iterations=5` hard safety cap
**Decision:** Every agent loop is capped at 5 iterations; exhaustion raises
`AgentLoopExhausted` and is logged clearly.
**Rationale:** Prevents runaway loops/cost during a live-ish demo; bounds latency.
**Alternatives:** Unbounded with cost ceiling — riskier under demo pressure. Rejected.

## D4 — ClickHouse Cloud (free tier) as the analytical store
**Decision:** Use ClickHouse Cloud free tier with a MergeTree `filings` table + an
AggregatingMergeTree materialized view for percentile lookups.
**Rationale:** Fastest setup, sub-100ms percentile queries over millions of rows, and
`quantileState` aggregation fits the percentile use case directly. Sponsor tool (counts
toward Tool Use criterion).
**Alternatives:** Postgres + percentile_cont (slower at scale, not a sponsor tool);
DuckDB local (no managed/public story). Rejected.

## D5 — Gemini 2.5 Pro for normalization, 2.5 Flash for agent loops + reports
**Decision:** Split models by task: Pro for title/level classification accuracy, Flash for
the high-frequency agent loops and report generation.
**Rationale:** Normalization quality drives data trust; loops/reports need speed + cost
efficiency. Matches SPEC.md.
**Alternatives:** Pro everywhere (too slow/expensive for loops); Flash everywhere (weaker
classification). Rejected.

## D6 — Senso primary, GitHub Pages fallback for publishing
**Decision:** Treat Senso as a core dependency for publishing cited.md pages; keep a
GitHub Pages fallback (`/companies/{company}.md` in a public repo) ready by hour 1.
**Rationale:** The published cited.md pages ARE the product. Senso prize wording allows
"cited.md (or another public destination)," so the fallback still satisfies the prize.
De-risks the most demo-critical layer.
**Alternatives:** Frontend-only (no public, agent-discoverable artifact — weakens the
thesis). Rejected.

## D7 — uv to provide Python 3.11+ despite system Python 3.9.6
**Decision:** Target Python 3.11+ in `agent/pyproject.toml` and use `uv` (already installed)
to provision the interpreter and manage the venv.
**Rationale:** System python is 3.9.6; SPEC.md requires 3.11+. uv installs/pins Python
quickly without touching the system interpreter.
**Alternatives:** pyenv (slower setup), downgrade target to 3.9 (loses 3.11 typing/features
and diverges from SPEC). Rejected.

## D8 — Canonical SPEC.md extracted from the kickoff document
**Decision:** The original attachment bundled SPEC.md (Artifact 1) with a kickoff prompt
and a parallel-work guide. Extracted Artifact 1's content into a standalone `SPEC.md` as
the repo's source of truth; the kickoff/parallel-work meta-content was internalized, not
committed.
**Rationale:** SPEC.md should be the clean, canonical spec referenced by code and docs;
meta-instructions about the build session don't belong in the repo. (Filesystem is
case-insensitive, so `spec.md`/`SPEC.md` are the same file — it was renamed in place.)
**Alternatives:** Keep the full bundle as SPEC.md — clutters the source of truth. Rejected.

## D9 — Nimble fetches the Akamai-blocked DOL files as base64
**Decision:** DOL bulk disclosure files (and the OFLC/EDD pages) are Akamai bot-blocked (403)
to direct download. Use Nimble's Web API to fetch them; it returns the .xlsx binary
base64-encoded in `html_content`, which we decode + cache. Same for CA WARN.
**Rationale:** Turns the blocker into a sponsor-tool win ("Nimble pulls from sources designed
to resist scraping" — a real demo talking point). The files are also huge, so we filter to
target companies on parse to keep ClickHouse small and queries fast.
**Alternatives:** Direct download (blocked); third-party mirrors (no case numbers / unofficial).
Rejected.

## D10 — Query filings directly for percentiles; reload after normalization for the MV
**Decision:** The Counselor/Investigator tools compute percentiles with `quantiles()` directly
on the filings table, not the materialized view. Normalization reads filings back, classifies
distinct titles, then TRUNCATEs + reloads with levels so the MV repopulates correctly.
**Rationale:** With only thousands of target rows, direct quantile queries are sub-100ms and
always correct regardless of MV refresh timing. ClickHouse MergeTree is append-only and the MV
only triggers on INSERT, so reload (not mutation) is the clean way to get leveled rows into both.
**Alternatives:** Per-title ALTER UPDATE mutations (heavy, and the MV wouldn't see them). Rejected.

## D11 — One Senso GEO question per company → distinct cited.md URLs
**Decision:** Publish each company's brief under its own GEO question, so each is a separate
cited.md article with its own URL.
**Rationale:** A shared question maps to a single Senso content item, so every brief overwrote
the same URL. Per-company questions give the public index distinct, citable pages.
**Alternatives:** One shared question (collapses all briefs to one page). Rejected.

## D12 — Canonical level scale: SPEC prompt mapping, with the user's curated table seeded
**Decision:** Normalization used the SPEC prompt's embedded company→level knowledge. The user's
hand-curated `company_levels` (CSV/JSON) is seeded into the `company_levels` table as the
authoritative taxonomy reference. The two differ by ~one level for some companies but AGREE on
Anthropic (MTS→L5), the demo's primary company.
**Rationale:** Re-normalizing 1,614 titles to switch scales wasn't worth the time given the demo
beat (Anthropic) is consistent. The curated table is preserved for reference / future re-norm.
**Alternatives:** Re-normalize against the curated scale (costly, marginal). Deferred.

## D13 — In-code tracing via ddtrace → Lapdog's :8126 collector
**Decision:** Lapdog's collector speaks the Datadog trace-agent protocol (/v0.4/traces), so we
emit spans with `ddtrace` (default agent localhost:8126). A no-op + console fallback keeps the
app working if tracing is down.
**Rationale:** Native, zero-config path to the Lapdog dashboard; deliberate span names
(agent.*.iteration, tool.*, gemini.call, clickhouse.query, nimble.fetch, senso.publish) make the
trace tree the visible proof of agency.
**Alternatives:** OpenTelemetry+OTLP (more setup); `lapdog python` auto-instrument only (no manual
span names). Rejected.

## D14 — Per-agent iteration caps of 6–8 (run_agent default stays 5)
**Decision:** Scout/Investigator use max_iterations=8, Counselor 7; run_agent's documented default
remains 5. Exhaustion is caught and returns a partial result instead of crashing the demo.
**Rationale:** Multi-source/multi-tool agents legitimately need more than 5 single-tool turns
(the SPEC's own Counselor demo makes ~5 tool calls). The cap is still a small bounded safety limit.
**Alternatives:** Hard 5 everywhere (cuts agents off mid-flow). Rejected.

## D15 — Post-event Tiger Data reference port
**Decision:** Replace the original ClickHouse analytical store with Tiger Data
(TimescaleDB/PostgreSQL) for the reference copy. Filings remain a keyed PostgreSQL table
so each DOL case has one current record; WARN notices use a time-partitioned hypertable.
Existing percentile reads query filings directly; no continuous aggregate is needed for this port.
**Rationale:** Demonstrate the same application against Tiger Data without changing the
historical hackathon record in D4, SPEC.md, PROGRESS.md, or VIDEO_SCRIPT.md. No query
latency or scale result has been measured for the port. This is not a hackCBS submission.
