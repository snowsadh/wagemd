# WAGE.md — 3-minute demo script

Real numbers from the live build (13,435 DOL filings, 10 companies). Swap in the exact
cited.md URLs from the `/briefs` page when recording.

## Pre-roll setup
- Terminal A: `make api` (FastAPI on :8000). Terminal B: `make frontend` (Next.js on :3000).
- Lapdog running (`lapdog status`); dashboard open at lapdog.datadoghq.com.
- Browser tabs: WAGE.md `/`, the Lapdog dashboard, the published `/briefs`, one cited.md brief.

---

### 0:00–0:15 — Hook
> "Glassdoor is rumor. Levels-dot-fyi is crowdsourced. But the US Department of Labor has the
> real numbers — every company sponsoring an H-1B is legally required to publish actual salaries
> by job title. Millions of filings. Almost nobody reads them. I built three agents that do."

### 0:15–0:35 — The problem
Split screen: Levels.fyi vs the DOL FLAG portal (which is Akamai-blocked to scrapers).
> "These files are bot-blocked and enormous. So WAGE.md pulls them with Nimble, normalizes job
> titles with Gemini, and loads them into ClickHouse — 13,435 verified filings across the ten
> companies, every row tied to a real federal case number."

### 0:35–1:05 — The agents (Lapdog)
Show the Lapdog trace tree.
> "WAGE.md is three agents, not a pipeline. The Scout decides which source to poll. The
> Investigator decides whether an anomaly is worth republishing. The Counselor decides what
> evidence to gather for each negotiation. All Gemini function calling — observe, decide, act.
> Here's the trace tree: agent-dot-iteration, the tool calls it chose, every Gemini and ClickHouse
> call timed."

### 1:05–1:45 — Counselor demo (the main beat)
Type into `/negotiate`: Anthropic · SWE · L5 · San Francisco · base $215,000 · 8 YOE.
> "Watch the Counselor. It looks up Anthropic L5 in San Francisco — only a handful of filings,
> too thin. So it broadens to L4–L6 statewide. Pulls peer companies. Checks WARN context. Now it's
> confident." (Lapdog shows the branching tool calls.)
> "Verdict: your $215K offer is below the 25th percentile. Anthropic's own DOL filings show L5
> engineers at $300K and up. Recommended ask: $300K — citing these specific DOL case numbers."
(Point to the cited case numbers, e.g. I-200-24271-368841.)

### 1:45–2:30 — The Investigator + publishing (the differentiator)
> "But here's the real difference. The Investigator detected WARN Act filings at Amazon — almost
> 7,000 layoffs in California. It cross-checked Amazon's 5,000 salary filings, decided the event
> was real and material, regenerated Amazon's salary brief with layoff context, and published it
> to cited.md. On its own." (Open the published Amazon brief on cited.md.)
> "Every claim cited to a DOL case number. Public. Agent-discoverable. Here's the whole index."
(Open `/briefs`.)

### 2:30–3:00 — The close
> "Built solo in a day with Claude Code. Five sponsor tools, every one doing real work: Nimble
> pulls sources designed to resist scraping. ClickHouse does sub-100ms percentile queries. Gemini
> drives three autonomous agents. Senso publishes the public cited.md index. Lapdog audits every
> decision. The data was always public — until today, nobody made it agent-discoverable. That's
> WAGE.md."

End card: GitHub URL · cited.md index · "built with Nimble · ClickHouse · Senso · Lapdog · Gemini"

---

## Verified claims (only say what we can show)
- 13,435 DOL filings, 10 companies, real case numbers — `GET /companies`, `/company/{slug}`.
- Anthropic SWE L5 median ~$300K; offer $215K below p25 — Counselor report.
- Amazon ~6,975 CA WARN layoffs — `warn_filings`; Investigator republished its brief.
- Live cited.md briefs — `/briefs`.
