# WAGE.md — Technical Specification

## What we're building

WAGE.md is an autonomous multi-agent system that ingests US Department of 
Labor PERM and H1B LCA salary disclosures (verified by federal filing), 
normalizes them across companies and role taxonomies, autonomously investigates 
anomalies, and publishes a public agent-discoverable salary index to cited.md.

The pitch: Glassdoor is rumor, Levels.fyi is crowdsourced, but the DOL has the 
real numbers — every H1B sponsor must legally disclose actual salaries by job 
title. WAGE.md is the substrate that every future career, recruiting, and 
negotiation AI will query.

## Context

- 8-hour hackathon at Datadog NYC ("Agentic Engineering Hack")
- Solo build with Claude Code as force multiplier
- Submission: video demo + GitHub repo by 4:30 PM
- Live demo only for finalists (plan v2 if selected)
- Sponsors whose tools we use: Nimble, ClickHouse, Senso, Datadog (Lapdog), 
  Google (Gemini)
- Optional monetization: x402 (fake button is fine for video)

## Judging criteria (each 20%)

1. **Autonomy** — agent acts on real-time data without manual intervention
2. **Idea** — solves meaningful problem with real-world value
3. **Technical Implementation** — quality of build
4. **Tool Use** — effectively uses 3+ sponsor tools
5. **Presentation (Demo)** — 3-minute demo quality

## Core architectural principle

This is **agentic, not a pipeline.** The system contains three distinct agents, 
each implementing an observe → decide → act → observe loop using Gemini function 
calling. Agents are NOT cron jobs. They select tools based on observed state.

If at any point you find yourself writing a fixed sequence of steps, stop and 
ask: should this be an agent decision instead?

---

## The three agents

### Agent 1: Ingestion Scout
**Goal:** Maintain freshness of the salary corpus.

**Loop:**
- Observe source freshness across DOL, WARN portals, career pages
- Decide which source to poll next based on staleness, change probability, 
  rate-limit budget
- Act: poll the chosen source via Nimble, fetch new filings
- Observe results: did data arrive? did normalization downstream succeed? 
  any anomalies?
- Decide: re-poll, escalate to Investigator, or continue rotation

**Tools available to Scout:**
- `check_source_freshness(source: str) -> dict` — returns last_polled, 
  expected_change_rate, rate_limit_remaining
- `fetch_source(source: str, since_date: str) -> dict` — pulls new filings 
  via Nimble
- `validate_filings(filings: list) -> dict` — sanity checks, returns issues
- `commit_to_clickhouse(filings: list) -> int` — inserts, returns row count
- `flag_anomaly(description: str, severity: str) -> None` — passes to Investigator
- `done() -> None` — exits the loop

### Agent 2: Investigator
**Goal:** When anomalies appear, investigate and decide whether to republish.

**Loop:**
- Observe: new anomaly flag (data shift, WARN filing, new company)
- Decide: is this signal significant? Action: republish brief, publish anomaly 
  note, or dismiss?
- Act: query data, fetch context, regenerate briefs, publish via Senso
- Observe: did publish succeed? are claims defensible?
- Decide: investigation complete or follow-up needed?

**Tools available to Investigator:**
- `query_salary_distribution(company, role_family, level, location) -> dict`
- `query_warn_filings(company, since_date) -> list`
- `compute_distribution_shift(company, role, level, window_days) -> dict`
- `fetch_filing_details(case_number) -> dict`
- `regenerate_company_brief(company) -> str` (markdown content)
- `publish_to_senso(company, content, citations) -> str` (returns URL)
- `publish_anomaly_note(title, body, citations) -> str`
- `done(summary) -> None`

### Agent 3: Negotiation Counselor
**Goal:** Given a user offer, produce strongest defensible negotiation report.

**Loop:**
- Observe: user offer (company, role, level, location, base, YOE)
- Decide: what data do I need to be confident?
- Act: tool calls — percentiles, peer comps, WARN context, specific filings
- Observe: do results give confident recommendation, or do I need more evidence?
- Decide: ship report or fetch more (broader role family? different location? 
  longer time window?)
- Act: generate final report with full citation chain
- Observe: are all citations resolvable?
- Decide: done

**Tools available to Counselor:**
- `query_salary_distribution(company, role_family, level, location)`
- `query_peer_companies(company, role_family) -> list[str]`
- `query_warn_context(company, timeframe_days) -> list`
- `fetch_filing_details(case_number)`
- `query_role_distribution_broadened(company, role_family, level_range, 
   location_state) -> dict` (for thin samples)
- `generate_report(structured_findings) -> str`
- `done(report) -> None`

### Generic agent loop (build this first)

```python
def run_agent(goal: str, tools: list, system_prompt: str, max_iterations: int = 5) -> dict:
    """
    Generic agent loop. Used by Scout, Investigator, Counselor.
    - Uses Gemini native function calling
    - Instruments every tool call with Lapdog spans
    - Logs structured agent traces for demo visibility
    - Returns final result or raises AgentLoopExhausted
    """
    messages = [{"role": "system", "content": system_prompt + f"\n\nGoal: {goal}"}]
    
    for iteration in range(max_iterations):
        # Lapdog span: agent.iteration with attributes (goal, iteration_n)
        response = gemini_call(messages, tools=tools)
        
        if response.is_final():
            return {"status": "ok", "result": response.content, "iterations": iteration + 1}
        
        for tool_call in response.tool_calls:
            # Lapdog span: tool.{tool_name} with args and result as attributes
            result = execute_tool(tool_call.name, tool_call.args)
            messages.append({"role": "assistant", "tool_call": tool_call})
            messages.append({"role": "tool", "name": tool_call.name, "result": result})
    
    raise AgentLoopExhausted(goal)
```

---

## Tech stack

- **Language:** Python 3.11+ (agent backend), TypeScript (frontend)
- **Agent backend:** FastAPI server with the three agents + REST endpoints
- **Analytical store:** ClickHouse Cloud (free tier, fastest setup)
- **Frontend:** Next.js 14 App Router + Tailwind + Server Components
- **Scraping:** Nimble Python SDK
- **LLM:** Gemini 2.5 Pro (normalization), Gemini 2.5 Flash (reports, agent loops)
- **Publishing:** Senso API (with GitHub Pages fallback if Senso doesn't fit)
- **Observability:** Lapdog (datadog-lapdog) for LLM trace capture
- **Monetization:** x402 stub (mock button + screenshot for video)

---

## Data sources

### DOL FLAG Disclosure Data
- **Quarterly downloads:** https://flag.dol.gov/case-data
- **File format:** `PERM_Disclosure_Data_FY{year}_Q{quarter}.csv` and 
  `LCA_Disclosure_Data_FY{year}_Q{quarter}.xlsx`
- **Strategy:** Download last 4 quarters worth of files, parse with pandas, 
  ingest to ClickHouse via Nimble
- **Key fields:** `EMPLOYER_NAME`, `JOB_TITLE`, `SOC_CODE`, `SOC_TITLE`, 
  `WAGE_RATE_OF_PAY_FROM`, `WAGE_RATE_OF_PAY_TO`, `WAGE_UNIT_OF_PAY`, 
  `WORKSITE_CITY`, `WORKSITE_STATE`, `CASE_NUMBER`, `DECISION_DATE`

### State WARN Act Portals
- **California (priority):** https://edd.ca.gov/jobs_and_training/Layoff_Services_WARN.htm
- **Washington:** https://esd.wa.gov/about-employees/WARN
- **New York:** https://dol.ny.gov/warn-notices
- If time-constrained, ship CA only and stub WA/NY.

### Company Career Pages (level taxonomy)
Hand-curate URLs for these 10 companies for internal level mappings:
1. Anthropic
2. OpenAI
3. Stripe
4. Google
5. Meta
6. Amazon
7. Microsoft
8. Apple
9. Databricks
10. Netflix

### Senso API
- **Pre-flight task:** Verify Senso API publishes structured content to cited.md 
  with citations preserved. See docs.senso.ai.
- **Fallback:** If Senso behaves differently than expected, publish to a public 
  GitHub Pages site under our control as `cited.md` files in a public repo. 
  Senso prize wording explicitly allows "cited.md (or another public destination)."

### Lapdog
- Install: `brew install datadog/lapdog/lapdog`
- Launch agent: `lapdog python agent.py`
- Dashboard: https://lapdog.datadoghq.com (reads from localhost:8126)

### Gemini
- Get API key from Google AI Studio
- 2.5 Pro for normalization (better classification)
- 2.5 Flash for agent loops and report generation (faster, cheaper)

---

## ClickHouse schema

```sql
-- Core filings table
CREATE TABLE filings (
    case_number String,
    case_type Enum('PERM' = 1, 'LCA' = 2),
    decision_date Date,
    employer_name_raw String,
    employer_normalized String,
    job_title_raw String,
    soc_code String,
    soc_title String,
    role_family Enum('SWE' = 1, 'PM' = 2, 'Design' = 3, 'FDE' = 4, 
                     'ML' = 5, 'Data' = 6, 'Other' = 7),
    level_normalized Enum('L1' = 1, 'L2' = 2, 'L3' = 3, 'L4' = 4, 
                          'L5' = 5, 'L6' = 6, 'L7' = 7, 'Unknown' = 99),
    normalization_confidence Float32,
    wage_low_usd Float64,
    wage_high_usd Float64,
    wage_unit String,
    worksite_city String,
    worksite_state String,
    ingested_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(decision_date)
ORDER BY (employer_normalized, role_family, level_normalized, decision_date);

-- Aggregating materialized view for percentile lookups
CREATE MATERIALIZED VIEW salary_distributions
ENGINE = AggregatingMergeTree()
PARTITION BY year
ORDER BY (employer_normalized, role_family, level_normalized, worksite_state, year)
AS SELECT
    employer_normalized,
    role_family,
    level_normalized,
    worksite_state,
    toYear(decision_date) AS year,
    quantileState(0.5)(wage_low_usd) AS p50,
    quantileState(0.75)(wage_low_usd) AS p75,
    quantileState(0.9)(wage_low_usd) AS p90,
    count() AS sample_size
FROM filings
WHERE level_normalized != 'Unknown'
GROUP BY employer_normalized, role_family, level_normalized, worksite_state, year;

-- WARN Act layoffs
CREATE TABLE warn_filings (
    filing_id String,
    employer_normalized String,
    state String,
    notice_date Date,
    effective_date Date,
    employees_affected UInt32,
    raw_data String,
    ingested_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (employer_normalized, notice_date);

-- Company-specific level taxonomy (seeded by hand for top 10)
CREATE TABLE company_levels (
    employer_normalized String,
    internal_level String,
    canonical_level Enum('L1' = 1, 'L2' = 2, 'L3' = 3, 'L4' = 4, 
                         'L5' = 5, 'L6' = 6, 'L7' = 7),
    role_family String,
    source_url String,
    notes String
) ENGINE = MergeTree()
ORDER BY (employer_normalized, internal_level);

-- Published page registry
CREATE TABLE published_pages (
    employer_normalized String,
    page_url String,
    last_published DateTime,
    sample_size UInt32,
    version UInt32
) ENGINE = ReplacingMergeTree(version)
ORDER BY (employer_normalized);

-- Anomaly log (for Investigator agent)
CREATE TABLE anomalies (
    anomaly_id String,
    detected_at DateTime,
    severity Enum('low' = 1, 'medium' = 2, 'high' = 3),
    description String,
    company String,
    investigation_status Enum('open' = 1, 'investigating' = 2, 
                              'resolved' = 3, 'dismissed' = 4),
    investigation_notes String
) ENGINE = MergeTree()
ORDER BY (detected_at, severity);
```

---

## Gemini prompts

### Title normalization (system prompt, Gemini 2.5 Pro)

```
You normalize US Department of Labor job filing titles to a canonical taxonomy.

Taxonomy:
- role_family: SWE, PM, Design, FDE, ML, Data, Other
  * SWE = Software Engineer (frontend, backend, full-stack, infra, platform)
  * PM = Product Manager
  * Design = Product Designer, UX, UI
  * FDE = Forward Deployed Engineer, Solutions Engineer, Customer Engineer
  * ML = Machine Learning Engineer, ML Scientist, Research Engineer
  * Data = Data Scientist, Data Engineer, Analytics Engineer
  * Other = everything else

- level: L1-L7 (and Unknown)
  * L1-L2 = Junior/Entry (1-2 YOE expected)
  * L3 = Mid IC (3-5 YOE)
  * L4 = Senior IC (5-8 YOE)
  * L5 = Staff IC or first-level manager (8-12 YOE)
  * L6 = Senior Staff / Senior Manager
  * L7 = Principal / Director and above

Company-specific knowledge:
- Anthropic "Member of Technical Staff" (no suffix) ≈ L5-L6 equivalent
- OpenAI "Member of Technical Staff" ≈ L5
- Google: Software Engineer II=L3, III=L4, Senior=L5, Staff=L6, Senior Staff=L7
- Meta: E3=L3, E4=L4, E5=L5 (Senior), E6=L6 (Staff), E7=L7 (Principal)
- Stripe: L1=L2, L2=L3, L3=L4, L4=L5 (Staff), L5=L6
- Amazon: SDE I=L3, SDE II=L4, SDE III=L5 (Senior), Principal=L6

If you cannot confidently determine the level, return "Unknown" with 
confidence < 0.5. Never guess.

Output JSON only:
{
  "role_family": "SWE|PM|Design|FDE|ML|Data|Other",
  "level": "L1|L2|L3|L4|L5|L6|L7|Unknown",
  "confidence": 0.0-1.0,
  "reasoning": "1-sentence rationale"
}
```

### Ingestion Scout system prompt

```
You are the Ingestion Scout for WAGE.md. Your goal is to maintain a fresh, 
clean salary corpus.

You manage three source families:
- DOL FLAG quarterly disclosures (changes ~4 times/year)
- State WARN Act portals (CA, WA, NY) (change weekly-ish)
- Company career pages (change rarely)

On each iteration, you observe source freshness and decide which source to 
poll next. Prioritize sources where new data is likely. Respect rate limits. 
After polling, validate the data. If anomalies appear (huge salary outliers, 
missing companies, new companies), flag them via flag_anomaly().

Call done() when all sources are reasonably fresh and no anomalies pending. 
Don't loop pointlessly.

Your tools are listed; use them by calling. Think before each tool call about 
WHY this tool is the right choice now.
```

### Investigator system prompt

```
You are the Investigator for WAGE.md. You handle anomaly flags from the Scout 
and from automated data checks. Your goal: decide whether each anomaly is real 
and meaningful, and if so, regenerate and republish the affected company brief.

When you receive an anomaly:
1. Query the underlying data to understand what changed
2. Compare to historical norms (recent WARN activity, distribution shifts)
3. Decide: is this real (publish), suspicious (need more data), or noise (dismiss)?
4. If real: regenerate the brief with the new context, publish via Senso
5. Optionally publish a standalone anomaly note for major events 
   (e.g., layoffs > 1000 people)

Be conservative. Don't republish for noise. Don't publish anomaly notes for 
trivial shifts. The published index must remain credible.

Call done() with a summary of what you decided and why.
```

### Negotiation Counselor system prompt

```
You are the Negotiation Counselor for WAGE.md. A user has provided their job 
offer. Your goal: produce the strongest defensible negotiation report.

Strategy:
1. Look up the salary distribution for their exact (company, role, level, location)
2. If sample size < 10, broaden — adjacent levels, statewide instead of city
3. Check WARN context — recent layoffs at this company affect leverage
4. Pull peer companies for comparison
5. Cite specific DOL case numbers in the report
6. Recommend a specific dollar ask with rationale

Every number in your final report must trace to a DOL case number or 
WARN filing. No invented data. If data is thin, say so honestly.

Call done(report) with the final markdown report.
```

### Company brief generation prompt (Gemini 2.5 Flash, called by Investigator)

```
Generate a public, agent-discoverable salary brief for {company}.

Data provided:
- {sample_size} verified DOL filings (last 12 months)
- Breakdown by role: {role_breakdown}
- Breakdown by location: {location_breakdown}
- Recent WARN activity: {warn_summary}

Output structured markdown with these sections:
1. TL;DR — 3 sentences, key percentiles for top role
2. Verified by — sample size + source statement
3. Role breakdown table (p50, p75, p90, sample size per role+level)
4. Location breakdown
5. Recent context (WARN if any, trend direction)
6. Citations — list of DOL case numbers used (linked to DOL FLAG)
7. Last updated timestamp

Tone: factual, citable, agent-friendly. No marketing language. Every claim 
backed by a citation.
```

---

## Senso publishing flow

1. Investigator generates structured markdown content per company
2. Sends to Senso ingest API with citation metadata preserved
3. Senso publishes to a permanent cited.md URL  
4. URL stored in `published_pages` ClickHouse table
5. Frontend deep-links to published pages

**Pre-flight verification (FIRST 30 MINUTES OF HACKATHON):**
- Test minimal Senso ingest + publish call
- Confirm citations preserved
- Confirm URL is publicly accessible and resolves
- If any step fails, switch immediately to GitHub Pages fallback

**GitHub Pages fallback:**
- Create public repo `wage-md-index`
- Each company brief written as `/companies/{company}.md`
- GitHub Pages serves these as `https://yourusername.github.io/wage-md-index/companies/anthropic.md`
- This is "another public destination" per Senso prize wording

---

## Lapdog instrumentation

Required spans (use Lapdog Python auto-instrumentation + manual spans):

- `agent.scout.iteration` (attributes: iteration_n, sources_checked)
- `agent.investigator.iteration` (attributes: anomaly_id, action_taken)
- `agent.counselor.iteration` (attributes: company, queries_made)
- `tool.{tool_name}` for every tool call (attributes: args summary, latency, 
  success/fail)
- `gemini.call` (attributes: model, prompt_tokens, completion_tokens, cost)
- `clickhouse.query` (attributes: query_kind, rows_returned, latency_ms)
- `nimble.fetch` (attributes: source, status_code, bytes)
- `senso.publish` (attributes: company, page_url, success)

Name spans deliberately. The Lapdog trace tree is the visible proof of agency 
in the demo.

---

## Next.js frontend (minimal)

Five pages:

- `/` — hero with prominent search bar, "search any of 50 companies"
- `/company/[slug]` — server-rendered, queries ClickHouse, shows percentile 
  table + link to cited.md page
- `/negotiate` — form for user to enter their offer; calls Counselor agent; 
  displays returned report
- `/about` — methodology + why this beats Levels.fyi
- `/index` — list of all published cited.md pages

Server components query ClickHouse directly via a small FastAPI middleware. 
Keep CSS clean and minimal — use Tailwind defaults. No animations.

---

## Project structure

```
wage-md/
├── README.md
├── SPEC.md                  # this file
├── CLAUDE.md                # living project context
├── PROGRESS.md              # append-only progress log
├── DECISIONS.md             # architectural decision log
├── Makefile                 # one-command operations
├── .env.example
├── .gitignore
├── docker-compose.yml       # local ClickHouse if needed
├── agent/
│   ├── README.md
│   ├── pyproject.toml
│   ├── src/
│   │   ├── core/
│   │   │   ├── agent_loop.py     # generic run_agent()
│   │   │   ├── gemini_client.py
│   │   │   ├── clickhouse_client.py
│   │   │   ├── lapdog_setup.py
│   │   │   └── nimble_client.py
│   │   ├── agents/
│   │   │   ├── scout.py          # Ingestion Scout
│   │   │   ├── investigator.py   # Investigator
│   │   │   └── counselor.py      # Negotiation Counselor
│   │   ├── tools/
│   │   │   ├── scout_tools.py
│   │   │   ├── investigator_tools.py
│   │   │   └── counselor_tools.py
│   │   ├── ingestion/
│   │   │   ├── dol_flag.py
│   │   │   ├── warn_ca.py
│   │   │   ├── warn_wa.py
│   │   │   ├── warn_ny.py
│   │   │   └── career_pages.py
│   │   ├── normalization/
│   │   │   └── title_normalizer.py
│   │   ├── publishing/
│   │   │   ├── senso_client.py
│   │   │   ├── github_pages_fallback.py
│   │   │   └── brief_generator.py
│   │   └── api/
│   │       └── server.py         # FastAPI exposing agent endpoints
│   └── tests/
├── frontend/
│   ├── README.md
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx              # /
│   │   ├── company/[slug]/page.tsx
│   │   ├── negotiate/page.tsx
│   │   ├── about/page.tsx
│   │   └── index/page.tsx
│   ├── components/
│   └── lib/
└── data-samples/                 # small sample files for testing without 
                                  # live API calls
```

---

## Build plan (hour-by-hour)

### Hour 0 (9:30-10:00) — Pre-flight (THIS MUST HAPPEN BEFORE ANYTHING)
- Verify Senso API: minimal ingest + publish + retrieve test
- Install Lapdog, verify dashboard loads
- Spin up ClickHouse Cloud free tier
- Confirm Gemini API key works
- Confirm Nimble credentials work
- If Senso fails: switch to GitHub Pages fallback now, don't waste time later

### Hour 0.5-1 — Skeleton
- Create all directories + README files
- Initialize git, first commit `v0.0-skeleton`
- Write `.env.example`, set up `.env.local`
- Create Makefile stubs
- Set up Python and Next.js scaffolding

### Hour 1-2 — Core infrastructure
- ClickHouse schema (all tables + materialized view)
- `core/agent_loop.py` — generic `run_agent()` with Gemini function calling 
  and Lapdog tracing
- `core/clickhouse_client.py`
- `core/gemini_client.py`
- `core/nimble_client.py`
- Test the generic agent loop with a trivial echo agent

### Hour 2-3.5 — Ingestion (Scout agent + tools)
- DOL FLAG downloader + parser
- WARN CA scraper (most important; ship WA/NY if time)
- Scout agent + tools
- Start ingestion running in background — this populates ClickHouse

### Hour 3.5-4 — LUNCH (eat, check ingestion progress)

### Hour 4-5 — Normalization + Investigator
- Title normalization via Gemini (batch over ingested filings)
- Hand-seed `company_levels` table for top 10
- Investigator agent + tools
- Test Investigator on a synthetic anomaly

### Hour 5-6 — Counselor + frontend skeleton  
- Counselor agent + tools
- FastAPI server exposing all three agents
- Next.js pages: /, /company/[slug], /negotiate
- Wire frontend to FastAPI

### Hour 6-7 — Publishing + polish
- Senso publishing pipeline (or GitHub Pages fallback)
- Investigator generates and publishes briefs for top 10 companies
- Lapdog span polish (name everything well)
- Verify cited.md URLs resolve publicly

### Hour 7-7.5 — End-to-end demo test
- Full demo flow on Anthropic test case
- Verify Lapdog dashboard shows clean trace trees
- Take screenshots for the video

### 4:30 PM — Submission deadline
- Push to GitHub, tag `v1.0-submission`
- Final SPEC.md and CLAUDE.md update
- README has setup + run instructions

### Hour 7.5+ — Video recording (5:00-7:00 PM available)
- Write script (use the one in VIDEO_SCRIPT.md)
- Record screen captures
- Edit, caption, export 1080p
- Upload unlisted YouTube, submit link

---

## Cut points (in order of what to drop if time-constrained)

1. WARN scraping for WA + NY (keep CA only)
2. Career page scraping (use only hand-seeded company_levels)
3. Reduce to 5 companies instead of 10 for published briefs
4. Investigator agent becomes simpler (stub the regenerate-brief flow)
5. /about and /index pages on frontend (just have / and /company/[slug] and 
   /negotiate)

If at hour 5 the ingestion + Counselor are working but Investigator isn't, 
**ship without Investigator** — Counselor + Scout alone still demonstrates 
agency. Pitch it as "two agents, with Investigator on the roadmap."

---

## Documentation conventions

### CLAUDE.md — the living context file
Update at minimum every 90 minutes. Contains:
- 1-paragraph project summary
- Current state of each layer (✅ done / 🚧 in progress / ⏳ planned)
- Critical conventions (naming, file structure)
- Known issues / gotchas
- Next planned task

### PROGRESS.md — append-only log
Each entry: timestamp + what completed + what next.

### DECISIONS.md — architectural decisions
Each entry: decision + rationale + alternatives considered. Helps future 
Claude Code sessions understand WHY things are this way.

### Git conventions
- Branch per feature: `feat/dol-ingestion`, `feat/investigator-agent`
- Commit format: `[layer] action — detail` 
  - examples: `[ingestion] add DOL FLAG quarterly downloader`, 
    `[agent] implement Investigator anomaly handling`
- Tag milestones: `v0.1-ingestion`, `v0.2-normalization`, `v0.3-agents`, 
  `v0.4-publishing`, `v1.0-submission`

### `make` commands to have working
- `make setup` — install dependencies, init env
- `make ingest` — run Scout agent once
- `make normalize` — run normalization batch
- `make publish` — run Investigator to regenerate + publish all briefs
- `make frontend` — start Next.js dev server
- `make api` — start FastAPI server
- `make demo` — boot everything for video recording
- `make test-senso` — pre-flight Senso check
- `make test-lapdog` — verify Lapdog dashboard works

---

## Video demo script (3 minutes)

### 0:00-0:15 — Hook
> "Glassdoor is rumor. Levels-dot-fyi is crowdsourced. But the US Department 
> of Labor has the real numbers — every company sponsoring an H1B is legally 
> required to publish their actual salaries by job title. Two and a half 
> million filings. Almost nobody reads them. I built three agents that do."

### 0:15-0:35 — The problem  
Split-screen visual: Levels.fyi vs DOL FLAG portal raw data.
> "Levels has 18 self-reported entries for senior engineers at Anthropic. 
> The DOL has 127 verified ones. Workers leave tens of thousands on the table 
> every negotiation because they trust the wrong data."

### 0:35-1:05 — The agents
Lapdog dashboard showing live agent traces.
> "WAGE.md is three agents — not a pipeline. The Scout autonomously decides 
> which sources to poll. The Investigator detects anomalies and decides 
> whether to republish. The Counselor decides what evidence to gather for 
> each negotiation. They all use Gemini function calling, observe state, 
> select tools, and act. Here's the trace tree."

### 1:05-1:45 — Counselor demo
> "Watch this. Anthropic. Software Engineer L5. San Francisco. Base $215K." 
> (Type into UI.) "The Counselor decides: query the percentile distribution. 
> Sample is only 8 filings — too thin. Broaden to L4-L6. Pull peer companies. 
> Check WARN context. Now it has enough." (Lapdog shows the branching tool 
> calls.) "Final report: your offer sits in the 18th percentile. Recommended 
> ask: $275K. Citing these three specific DOL case numbers." (Click case 
> number, opens real DOL filing.)

### 1:45-2:30 — The Investigator and the publishing layer
> "But here's the real difference. While I was talking, the Investigator 
> detected a WARN Act filing at Meta — 2,400 layoffs in California. It 
> queried Meta's recent DOL filings, noticed the median L5 PM salary had 
> shifted 6%, decided this anomaly warranted attention, and republished 
> Meta's salary brief with layoff context. On its own." (Open the published 
> cited.md page.) "Every claim cited to a DOL case ID. Public. Agent-discoverable."

### 2:30-3:00 — The close
> "Built solo in 8 hours with Claude Code. Five sponsor tools, every one 
> doing real work. Nimble pulls from sources designed to resist scraping. 
> ClickHouse handles 2.5M filings with sub-100ms percentile queries. Gemini 
> drives three autonomous agents. Senso publishes the public index. Lapdog 
> audits every decision. The data was always public. Until today, nobody 
> made it agent-discoverable. That's WAGE.md."

End card: GitHub URL + cited.md index URL + "built with Nimble, ClickHouse, 
Senso, Lapdog, Gemini"

---

## Demo failure modes and mitigations

| Failure | Mitigation |
|---|---|
| Senso API doesn't work | GitHub Pages fallback ready by hour 1 |
| Title normalization is slow | Pre-run for top 10 companies, cache results |
| Lapdog dashboard chaotic | Spend 30 min naming spans well at hour 6 |
| Agent loops forever | max_iterations=5 hard limit, log clearly |
| Live data fails during recording | All demo data pre-cached in ClickHouse |
| Video too long | Pre-write captions, cut ruthlessly in edit |

---

## Risk: what NOT to spend time on

- Perfect CSS / animations on frontend
- Custom auth / accounts
- Real payment integration (mock x402 button)
- Comprehensive WARN coverage (CA only is fine)
- Title normalization perfection (70% is enough for demo)
- More than 10 companies in published index
- Multi-LLM ensemble or fancy prompt engineering

---

## What "done" means

By 4:30 PM:
- [ ] GitHub repo public, all code committed
- [ ] README has setup instructions a stranger could follow
- [ ] At least 5 companies have published briefs on cited.md (or fallback)
- [ ] Counselor agent works end-to-end for at least one demo case
- [ ] Lapdog dashboard shows clean trace trees
- [ ] CLAUDE.md and PROGRESS.md up to date
- [ ] SPEC.md hasn't drifted from reality (or DECISIONS.md notes the drift)
- [ ] `make demo` boots everything

By video submission time:
- [ ] 3-minute video recorded and edited
- [ ] Captions added
- [ ] Uploaded to YouTube unlisted
- [ ] Submitted to hackathon platform

---

## End of SPEC.md
