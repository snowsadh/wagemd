"""Company brief generation (OpenAI), called by the Investigator.

Gathers a company's DOL distribution (by role/level), location breakdown, recent WARN
context, and real case numbers from TimescaleDB, then has OpenAI render a structured,
agent-friendly company brief.
"""
from __future__ import annotations

import datetime as dt

from ..core.config import settings
from ..core.openai_client import get_openai
from ..core.tiger_client import query
from ..tools.queries import FLAG_URL, warn_context

BRIEF_PROMPT = """Generate a public, agent-discoverable salary brief for {company}.

Data provided (JSON):
{data}

Output structured markdown with these sections:
1. TL;DR — 3 sentences, key percentiles for the top role
2. Source and scope — sample size, employer-reported offered wages, and the selected DOL sample
3. Role breakdown table (p50, p75, p90, sample size per role+level)
4. Location breakdown
5. Recent context (if WARN data is not loaded, say that rather than claiming no layoffs)
6. Citations — original DOL case numbers as examples; percentiles use the full matched cohort,
   not only those examples. Cases are verifiable in DOL FLAG disclosures ({flag_url})
7. Last updated timestamp: {today}

Tone: factual, citable, agent-friendly. No marketing language. Every claim backed by the data."""


def gather_company_data(company: str) -> dict:
    roles = query(
        "SELECT role_family, level_normalized, count(*), "
        "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wage_low_usd)), "
        "round(percentile_cont(0.75) WITHIN GROUP (ORDER BY wage_low_usd)), "
        "round(percentile_cont(0.9) WITHIN GROUP (ORDER BY wage_low_usd)) "
        "FROM filings WHERE employer_normalized=%(c)s AND level_normalized!='Unknown' "
        "AND wage_low_usd>0 GROUP BY role_family, level_normalized HAVING count(*)>=2 "
        "ORDER BY count(*) DESC LIMIT 25",
        {"c": company},
    ).result_rows
    locs = query(
        "SELECT worksite_state, count(*), "
        "round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wage_low_usd)) FROM filings "
        "WHERE employer_normalized=%(c)s AND wage_low_usd>0 GROUP BY worksite_state "
        "ORDER BY 2 DESC LIMIT 6",
        {"c": company},
    ).result_rows
    total = query(
        "SELECT count(*) FROM filings WHERE employer_normalized=%(c)s AND wage_low_usd>0", {"c": company}
    ).result_rows[0][0]
    cites = [
        r[0] for r in query(
            "SELECT case_number FROM filings WHERE employer_normalized=%(c)s AND wage_low_usd>0 "
            "ORDER BY wage_low_usd DESC LIMIT 8", {"c": company}
        ).result_rows
    ]
    return {
        "company": company,
        "sample_size": total,
        "role_breakdown": [
            {"role_family": r[0], "level": r[1], "sample_size": r[2],
             "p50": int(r[3]), "p75": int(r[4]), "p90": int(r[5])}
            for r in roles
        ],
        "location_breakdown": [
            {"state": r[0], "sample_size": r[1], "median_usd": int(r[2])} for r in locs
        ],
        "warn": warn_context(company),
        "citations": cites,
    }


def generate_brief(company: str) -> dict:
    """Return {markdown, citations, sample_size, data} for a company brief."""
    import json

    data = gather_company_data(company)
    if data["sample_size"] == 0:
        return {"markdown": f"# {company}\nNo DOL filings on record.", "citations": [], "sample_size": 0, "data": data}
    ai = get_openai()
    prompt = BRIEF_PROMPT.format(
        company=company, data=json.dumps(data, indent=2),
        flag_url=FLAG_URL, today=dt.date.today(),
    )
    resp = ai.generate(
        model=settings.openai_model, contents=[ai.user_content(prompt)]
    )
    md = ai.text_of(resp).strip()
    if not md:
        raise ValueError(f"OpenAI returned an empty brief for {company}")
    return {"markdown": md, "citations": data["citations"], "sample_size": data["sample_size"], "data": data}
