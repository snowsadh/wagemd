"""FastAPI server exposing the three agents + read endpoints for the frontend.

Next.js server components read company distributions and local briefs here, and the
/negotiate page calls the Counselor agent. Agent runs are synchronous (FastAPI runs sync
endpoints in a threadpool) and return a tool-call trace so the UI can show the agent's
decisions.
"""
from __future__ import annotations

import threading
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..agents import counselor, investigator, scout
from ..core.config import settings
from ..core.tiger_client import query, query_many
from ..normalization.companies import TARGET_COMPANIES

app = FastAPI(title="WAGE.md API", version="1.0.0")
# CORS restricted to the configured frontend origin(s), not "*".
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
)

# The agents use process-global staging (scout_tools._STAGED, investigator_tools._BRIEF_CACHE),
# so serialize agent runs to avoid cross-request corruption under the threadpool.
_AGENT_LOCK = threading.Lock()

_SLUG_TO_NAME = {c.lower().replace(" ", "-"): c for c in TARGET_COMPANIES}


def require_admin(x_api_key: str | None = Header(default=None)) -> None:
    """Gate write/agent-trigger endpoints. Disabled (503) unless WAGE_ADMIN_TOKEN is set;
    then requires a matching X-API-Key header."""
    if not settings.admin_token:
        raise HTTPException(status_code=503, detail="Admin endpoints disabled; set WAGE_ADMIN_TOKEN")
    if x_api_key != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


class Offer(BaseModel):
    company: str
    role_family: str
    level: str = ""
    location: str = ""
    base: float = 0
    yoe: int = 0


class AnomalyIn(BaseModel):
    company: str
    severity: str = "high"
    description: str = ""


def _slug_to_company(slug: str) -> str:
    s = slug.strip().lower()
    if s in _SLUG_TO_NAME:
        return _SLUG_TO_NAME[s]
    return slug.replace("-", " ").title()


@app.get("/health")
def health() -> dict:
    n = query("SELECT count(*) FROM filings").result_rows[0][0]
    return {"status": "ok", "service": "wage-md", "filings": n}


@app.get("/companies")
def companies() -> dict:
    rows = query(
        "SELECT employer_normalized, count(*) FROM filings GROUP BY employer_normalized "
        "ORDER BY 2 DESC LIMIT 60"
    ).result_rows
    return {"companies": [{"name": r[0], "slug": r[0].lower().replace(" ", "-"), "filings": r[1]} for r in rows]}


def _company_payload(
    company: str, role: str | None = None, level: str | None = None,
    state: str | None = None, period: str = "all",
) -> dict:
    period_dates = {
        "all": (None, None),
        "FY2025": ("2024-10-01", "2025-10-01"),
        "FY2026": ("2025-10-01", "2026-10-01"),
    }
    start, end = period_dates[period]
    parameters = {"c": company, "role": role, "level": level, "state": state,
                  "period": period, "start": start, "end": end}
    base = " FROM filings WHERE employer_normalized=%(c)s AND wage_low_usd>0"
    period_sql = (" AND (%(period)s='all' OR "
                  "(decision_date >= %(start)s::date AND decision_date < %(end)s::date))")
    role_sql = " AND role_family=%(role)s" if role else ""
    level_sql = " AND level_normalized=%(level)s" if level else ""
    state_sql = " AND worksite_state=%(state)s" if state else ""
    matched = base + period_sql + role_sql + level_sql + state_sql
    (rows, totals, matched_filings, role_totals, locations, monthly_filings,
     level_medians, case_type_totals, states, pub) = query_many([
        ("SELECT role_family, level_normalized, count(*), "
         "round(percentile_cont(0.25) WITHIN GROUP (ORDER BY wage_low_usd)), "
         "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wage_low_usd)), "
         "round(percentile_cont(0.75) WITHIN GROUP (ORDER BY wage_low_usd)), "
         "round(percentile_cont(0.9) WITHIN GROUP (ORDER BY wage_low_usd))"
         + matched + " GROUP BY role_family, level_normalized HAVING count(*)>=5"
         " ORDER BY 5 DESC LIMIT 40"),
        "SELECT count(*) FROM filings WHERE employer_normalized=%(c)s",
        ("SELECT count(*), "
         "CASE WHEN count(*)>=5 THEN round(percentile_cont(0.25) "
         "WITHIN GROUP (ORDER BY wage_low_usd)) END, "
         "CASE WHEN count(*)>=5 THEN round(percentile_cont(0.5) "
         "WITHIN GROUP (ORDER BY wage_low_usd)) END, "
         "CASE WHEN count(*)>=5 THEN round(percentile_cont(0.75) "
         "WITHIN GROUP (ORDER BY wage_low_usd)) END, "
         "min(decision_date)::text, max(decision_date)::text" + matched),
        ("SELECT role_family, count(*)" + base + period_sql + level_sql + state_sql
         + " GROUP BY role_family ORDER BY 2 DESC"),
        ("SELECT worksite_state, count(*), "
         "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wage_low_usd))"
         + base + period_sql + role_sql + level_sql
         + " AND worksite_state<>'' GROUP BY worksite_state HAVING count(*)>=5"
         " ORDER BY CASE WHEN worksite_state=%(state)s THEN 0 ELSE 1 END, 2 DESC LIMIT 6"),
        ("SELECT to_char(date_trunc('month', decision_date), 'YYYY-MM'), count(*), "
         "CASE WHEN count(*)>=5 THEN round(percentile_cont(0.5) "
         "WITHIN GROUP (ORDER BY wage_low_usd)) END"
         + matched + " GROUP BY 1 ORDER BY 1"),
        ("SELECT level_normalized, count(*), "
         "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wage_low_usd))"
         + base + period_sql + role_sql + state_sql
         + " AND level_normalized<>'Unknown'"
         " GROUP BY level_normalized HAVING count(*)>=5 ORDER BY 1"),
        ("SELECT case_type, count(*)" + matched
         + " GROUP BY case_type ORDER BY 1"),
        ("SELECT DISTINCT worksite_state FROM filings WHERE employer_normalized=%(c)s "
         "AND worksite_state<>'' ORDER BY 1"),
        ("SELECT page_url, last_published::text FROM published_pages "
         "WHERE employer_normalized=%(c)s AND markdown<>''"),
    ], parameters)
    count, p25, p50, p75, first_decision, last_decision = matched_filings[0]
    return {
        "company": company,
        "total_filings": totals[0][0],
        "matchedFilings": {
            "count": count, "p25": int(p25) if p25 is not None else None,
            "p50": int(p50) if p50 is not None else None,
            "p75": int(p75) if p75 is not None else None,
            "firstDecision": first_decision, "lastDecision": last_decision,
        },
        "rows": [
            {"role_family": r[0], "level": r[1], "sample_size": r[2],
             "p25": int(r[3]), "p50": int(r[4]), "p75": int(r[5]), "p90": int(r[6])}
            for r in rows
        ],
        "roleTotals": [{"role": r[0], "count": r[1]} for r in role_totals],
        "locations": [
            {"state": r[0], "count": r[1], "median": int(r[2])} for r in locations
        ],
        "monthlyFilings": [
            {"month": r[0], "count": r[1], "p50": int(r[2]) if r[2] is not None else None}
            for r in monthly_filings
        ],
        "levelMedians": [
            {"level": r[0], "count": r[1], "median": int(r[2])}
            for r in level_medians
        ],
        "caseTypeTotals": [
            {"caseType": r[0], "count": r[1]}
            for r in case_type_totals
        ],
        "stateOptions": [r[0] for r in states],
        "briefUrl": pub[0][0] if pub else None,
    }


@app.get("/company/{slug}")
def get_company(
    slug: str, fetch: bool = True,
    role: Literal["SWE", "PM", "Design", "FDE", "ML", "Data", "Other"] | None = None,
    level: Literal["L1", "L2", "L3", "L4", "L5", "L6", "L7", "Unknown"] | None = None,
    state: str | None = Query(default=None, pattern="^[A-Z]{2}$"),
    period: Literal["all", "FY2025", "FY2026"] = "all",
) -> dict:
    company = _slug_to_company(slug)
    payload = _company_payload(company, role, level, state, period)
    if payload["total_filings"] == 0 and fetch:  # fetch-on-miss, then re-query
        from ..ingestion.on_demand import ingest_company

        with _AGENT_LOCK:
            res = ingest_company(company)
        payload = _company_payload(res.get("company", company), role, level, state, period)
        payload["fetched_on_demand"] = res.get("ingested", 0)
    return payload


@app.post("/negotiate")
def negotiate(offer: Offer) -> dict:
    with _AGENT_LOCK:
        return counselor.run(offer.model_dump())


@app.post("/scout/run", dependencies=[Depends(require_admin)])
def run_scout() -> dict:
    with _AGENT_LOCK:
        return scout.run()


@app.post("/investigate", dependencies=[Depends(require_admin)])
def run_investigator(anomaly: AnomalyIn) -> dict:
    with _AGENT_LOCK:
        return investigator.run(anomaly.model_dump())


@app.get("/index")
def list_published() -> dict:
    rows = query(
        "SELECT employer_normalized, page_url, last_published::text, sample_size "
        "FROM published_pages WHERE markdown<>'' ORDER BY last_published DESC"
    ).result_rows
    return {"pages": [{"company": r[0], "url": r[1], "last_published": r[2], "sample_size": r[3]} for r in rows]}


@app.get("/briefs/{company}")
def get_brief(company: str) -> dict:
    rows = query(
        "SELECT employer_normalized, markdown, last_published::text, sample_size "
        "FROM published_pages WHERE employer_normalized=%(c)s AND markdown<>''",
        {"c": company},
    ).result_rows
    if not rows:
        raise HTTPException(status_code=404, detail="Brief not found")
    name, markdown, updated, sample_size = rows[0]
    return {"company": name, "markdown": markdown, "last_published": updated,
            "sample_size": sample_size}
