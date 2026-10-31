"""Tools available to the Investigator agent (OpenAI function calling).

Regenerated brief markdown is cached server-side (keyed by company) so the agent passes only
a company name to the Tiger Data publisher — not the whole document back through the model.
"""
from __future__ import annotations

from ..core.agent_loop import Tool
from ..core.tiger_client import query
from ..publishing import brief_generator, local_briefs
from . import queries

_BRIEF_CACHE: dict[str, dict] = {}


def query_warn_filings(company: str, since_date: str = "2024-01-01") -> dict:
    agg = query(
        "SELECT count(*), sum(employees_affected), max(notice_date)::text FROM warn_filings "
        "WHERE employer_normalized=%(c)s AND notice_date >= %(d)s::date",
        {"c": company, "d": since_date},
    ).result_rows[0]
    sample = query(
        "SELECT notice_date::text, effective_date::text, employees_affected "
        "FROM warn_filings WHERE employer_normalized=%(c)s AND notice_date >= %(d)s::date "
        "ORDER BY employees_affected DESC LIMIT 8",
        {"c": company, "d": since_date},
    ).result_rows
    return {
        "company": company,
        "notice_count": int(agg[0]),
        "total_employees_affected": int(agg[1]) if agg[1] else 0,
        "latest_notice": agg[2],
        "largest_notices": [
            {"notice_date": r[0], "effective_date": r[1], "employees_affected": int(r[2])} for r in sample
        ],
    }


def compute_distribution_shift(company: str, role_family: str = "", level: str = "", window_days: int = 180) -> dict:
    where = ["employer_normalized=%(c)s", "wage_low_usd>0"]
    params: dict = {"c": company, "w": int(window_days)}
    if role_family:
        where.append("role_family=%(rf)s"); params["rf"] = role_family
    if level and level.lower() != "any":
        where.append("level_normalized=%(lv)s"); params["lv"] = level
    base = " AND ".join(where)
    recent = query(
        f"SELECT count(*), round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wage_low_usd)) "
        f"FROM filings WHERE {base} AND decision_date >= CURRENT_DATE - %(w)s::int", params,
    ).result_rows[0]
    prior = query(
        f"SELECT count(*), round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wage_low_usd)) "
        f"FROM filings WHERE {base} AND decision_date < CURRENT_DATE - %(w)s::int "
        f"AND decision_date >= CURRENT_DATE - 2 * %(w)s::int", params,
    ).result_rows[0]
    rn, rm = recent[0], (int(recent[1]) if recent[1] else 0)
    pn, pm = prior[0], (int(prior[1]) if prior[1] else 0)
    shift = round(100 * (rm - pm) / pm, 1) if pm else None
    return {
        "company": company, "role_family": role_family or "any", "level": level or "any",
        "window_days": int(window_days),
        "recent": {"sample_size": rn, "median_usd": rm},
        "prior": {"sample_size": pn, "median_usd": pm},
        "median_shift_pct": shift,
        "confidence": "low" if min(rn, pn) < 10 else "medium",
    }


def regenerate_company_brief(company: str) -> dict:
    brief = brief_generator.generate_brief(company)
    _BRIEF_CACHE[company] = brief
    return {
        "company": company,
        "sample_size": brief["sample_size"],
        "citations": brief["citations"],
        "markdown_preview": brief["markdown"][:500],
        "note": "Full brief cached. Call publish_company_brief(company) to store it in the Index.",
    }


MIN_BRIEF_SAMPLE = 5  # don't publish a company brief we can't stand behind


def publish_company_brief(company: str) -> dict:
    brief = _BRIEF_CACHE.get(company)
    if not brief:
        brief = brief_generator.generate_brief(company)
        _BRIEF_CACHE[company] = brief
    if brief["sample_size"] < MIN_BRIEF_SAMPLE:
        return {"published": False, "company": company, "sample_size": brief["sample_size"],
                "reason": f"only {brief['sample_size']} DOL filings — too few to publish a credible "
                          "company brief"}
    return local_briefs.publish_brief(company, brief["markdown"], brief["sample_size"])


def done(summary: str) -> dict:
    return {"status": "done", "summary": summary}


def get_tools() -> list[Tool]:
    return [
        Tool("query_salary_distribution",
             "DOL wage distribution for a company + role_family + level + location.",
             queries.salary_distribution,
             {"type": "object", "properties": {"company": {"type": "string"}, "role_family": {"type": "string"},
              "level": {"type": "string"}, "location": {"type": "string"}}, "required": ["company"]}),
        Tool("query_warn_filings", "Recent WARN layoff notices for a company since a date (YYYY-MM-DD).",
             query_warn_filings,
             {"type": "object", "properties": {"company": {"type": "string"}, "since_date": {"type": "string"}},
              "required": ["company"]}),
        Tool("compute_distribution_shift",
             "Compare the company's median wage in the recent vs prior window; returns shift %.",
             compute_distribution_shift,
             {"type": "object", "properties": {"company": {"type": "string"}, "role_family": {"type": "string"},
              "level": {"type": "string"}, "window_days": {"type": "integer"}}, "required": ["company"]}),
        Tool("fetch_filing_details", "Look up one DOL filing by case number.", queries.filing_details,
             {"type": "object", "properties": {"case_number": {"type": "string"}}, "required": ["case_number"]}),
        Tool("regenerate_company_brief",
             "Regenerate the company's salary brief from current DOL+WARN data (caches it).",
             regenerate_company_brief,
             {"type": "object", "properties": {"company": {"type": "string"}}, "required": ["company"]}),
        Tool("publish_company_brief", "Store the regenerated company brief in Tiger Data and return its local URL.",
             publish_company_brief,
             {"type": "object", "properties": {"company": {"type": "string"}}, "required": ["company"]}),
        Tool("done", "Finish with a summary of what you decided and why.", done,
             {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
             terminal=True),
    ]
