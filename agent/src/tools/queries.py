"""Shared TimescaleDB query helpers used by the Counselor and Investigator tools.

Percentiles come straight from the filings table (over wage_low_usd), keeping
results current. Every distribution returns
real DOL case numbers as examples so the agents can cite them.
"""
from __future__ import annotations

import re

from ..core.tiger_client import query

FLAG_URL = "https://flag.dol.gov/case-data"


def _loc_clause(location: str | None, params: dict) -> str:
    if not location:
        return ""
    loc = location.strip()
    if len(loc) <= 2 and loc.isalpha():
        params["loc_state"] = loc.upper()
        return " AND worksite_state = %(loc_state)s"
    params["loc_city"] = loc
    return " AND worksite_city ILIKE '%%' || %(loc_city)s || '%%'"


def _examples(where_sql: str, params: dict, limit: int = 5) -> list[dict]:
    rows = query(
        f"SELECT case_number, case_type, job_title_raw, round(wage_low_usd), "
        f"worksite_city, worksite_state, decision_date::text "
        f"FROM filings WHERE {where_sql} ORDER BY wage_low_usd DESC LIMIT {limit}",
        params,
    ).result_rows
    return [
        {"case_number": r[0], "case_type": r[1], "job_title": r[2], "wage_usd": int(r[3]),
         "worksite": f"{r[4]}, {r[5]}", "decision_date": r[6], "source": FLAG_URL}
        for r in rows
    ]


def _distribution(where: list[str], params: dict, label: dict) -> dict:
    where_sql = " AND ".join(where)
    row = query(
        f"SELECT count(*), percentile_cont(ARRAY[0.25,0.5,0.75,0.9]::double precision[]) "
        f"WITHIN GROUP (ORDER BY wage_low_usd), "
        f"round(min(wage_low_usd)), round(max(wage_low_usd)) FROM filings WHERE {where_sql}",
        params,
    ).result_rows[0]
    n, q, lo, hi = row[0], row[1], row[2], row[3]
    out = {**label, "sample_size": n}
    if n:
        out.update(
            p25=int(round(q[0])), p50=int(round(q[1])), p75=int(round(q[2])), p90=int(round(q[3])),
            min=int(lo), max=int(hi), examples=_examples(where_sql, params),
        )
    return out


def salary_distribution(company: str, role_family: str = "", level: str = "", location: str = "") -> dict:
    where = ["employer_normalized = %(c)s", "wage_low_usd > 0"]
    params: dict = {"c": company}
    if role_family:
        where.append("role_family = %(rf)s"); params["rf"] = role_family
    if level:
        where.append("level_normalized = %(lv)s"); params["lv"] = level
    where.append("TRUE" + _loc_clause(location, params))
    return _distribution(
        where, params,
        {"company": company, "role_family": role_family or "any", "level": level or "any",
         "location": location or "any"},
    )


def broadened_distribution(company: str, role_family: str = "", level_range: str = "", location_state: str = "") -> dict:
    where = ["employer_normalized = %(c)s", "wage_low_usd > 0"]
    params: dict = {"c": company}
    if role_family:
        where.append("role_family = %(rf)s"); params["rf"] = role_family
    levels = re.findall(r"L[1-7]", (level_range or "").upper())
    if "-" in level_range and len(levels) == 2:
        levels = [f"L{i}" for i in range(int(levels[0][1]), int(levels[1][1]) + 1)]
    if levels:
        params["lvls"] = levels
        where.append("level_normalized = ANY(%(lvls)s)")
    else:
        where.append("level_normalized != 'Unknown'")
    if location_state:
        params["st"] = location_state.strip().upper()
        where.append("worksite_state = %(st)s")
    return _distribution(
        where, params,
        {"company": company, "role_family": role_family or "any",
         "levels": levels or "all known", "location_state": location_state or "any state"},
    )


def peer_companies(company: str, role_family: str = "") -> list[dict]:
    where = ["level_normalized != 'Unknown'", "wage_low_usd > 0", "employer_normalized != %(c)s"]
    params: dict = {"c": company}
    if role_family:
        where.append("role_family = %(rf)s"); params["rf"] = role_family
    rows = query(
        f"SELECT employer_normalized, count(*), "
        f"round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wage_low_usd)) "
        f"FROM filings WHERE {' AND '.join(where)} GROUP BY employer_normalized "
        f"HAVING count(*) >= 5 ORDER BY 3 DESC LIMIT 8",
        params,
    ).result_rows
    return [{"company": r[0], "sample_size": r[1], "median_wage_usd": int(r[2])} for r in rows]


def warn_context(company: str, timeframe_days: int = 540) -> dict:
    agg = query(
        "SELECT EXISTS(SELECT 1 FROM warn_filings), count(*), "
        "sum(employees_affected) FROM warn_filings "
        "WHERE employer_normalized = %(c)s AND notice_date >= CURRENT_DATE - %(d)s::int",
        {"c": company, "d": int(timeframe_days)},
    ).result_rows[0]
    rows = query(
        "SELECT notice_date::text, effective_date::text, employees_affected "
        "FROM warn_filings WHERE employer_normalized = %(c)s AND notice_date >= CURRENT_DATE - %(d)s::int "
        "ORDER BY employees_affected DESC LIMIT 8",
        {"c": company, "d": int(timeframe_days)},
    ).result_rows if agg[0] else []
    return {
        "company": company,
        "window_days": int(timeframe_days),
        "has_warn_data": bool(agg[0]),
        "notice_count": int(agg[1]),
        "total_employees_affected": int(agg[2]) if agg[2] else 0,
        "recent_notices": [
            {"notice_date": r[0], "effective_date": r[1], "employees_affected": int(r[2])}
            for r in rows
        ],
    }


def filing_details(case_number: str) -> dict:
    rows = query(
        "SELECT case_number, case_type, employer_normalized, job_title_raw, soc_title, "
        "round(wage_low_usd), round(wage_high_usd), worksite_city, worksite_state, "
        "decision_date::text, level_normalized, role_family "
        "FROM filings WHERE case_number = %(cn)s LIMIT 1",
        {"cn": case_number},
    ).result_rows
    if not rows:
        return {"error": "case not found", "case_number": case_number}
    r = rows[0]
    return {
        "case_number": r[0], "case_type": r[1], "employer": r[2], "job_title": r[3],
        "soc_title": r[4], "wage_low_usd": int(r[5]), "wage_high_usd": int(r[6]),
        "worksite": f"{r[7]}, {r[8]}", "decision_date": r[9], "level": r[10],
        "role_family": r[11], "source": FLAG_URL,
    }
