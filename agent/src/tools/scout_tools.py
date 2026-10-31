"""Tools available to the Scout agent (OpenAI function calling).

The Scout observes source freshness and decides which to poll. Fetched filings are staged
in-memory per source (so we don't round-trip bulk data through the model) and committed on
the agent's command. Anomalies are written to the `anomalies` table for the Investigator.
"""
from __future__ import annotations

import datetime as dt
import uuid

from ..core.agent_loop import Tool
from ..core.tiger_client import insert, query
from ..ingestion import warn_ca

SOURCES = {
    "dol_lca": {"change": "quarterly", "interval_days": 90},
    "dol_perm": {"change": "quarterly", "interval_days": 90},
    "warn_ca": {"change": "weekly", "interval_days": 7},
}

_STAGED: dict[str, list[dict]] = {}


def check_source_freshness(source: str) -> dict:
    if source not in SOURCES:
        return {"error": f"unknown source '{source}'. valid: {list(SOURCES)}"}
    meta = SOURCES[source]
    if source == "warn_ca":
        row = query("SELECT max(notice_date), count(*) FROM warn_filings").result_rows[0]
    else:
        ct = "LCA" if source == "dol_lca" else "PERM"
        row = query(
            "SELECT max(decision_date), count(*) FROM filings WHERE case_type=%(c)s", {"c": ct}
        ).result_rows[0]
    last, n = row[0], row[1]
    days_since = (dt.date.today() - last).days if isinstance(last, dt.date) else 9999
    staleness = round(days_since / meta["interval_days"], 2)
    return {
        "source": source,
        "rows_in_store": n,
        "latest_record_date": str(last),
        "days_since_latest": days_since,
        "expected_change_rate": meta["change"],
        "staleness_score": staleness,  # >1 means likely overdue for new data
        "rate_limit_remaining": 100,
    }


def fetch_source(source: str, since_date: str = "") -> dict:
    if source == "warn_ca":
        from ..normalization.companies import TARGET_COMPANIES

        rows = warn_ca.fetch_recent(since_date or None, limit=300)
        _STAGED[source] = rows

        def _fmt(r):
            return {"employer": r["employer_normalized"], "employees": r["employees_affected"],
                    "notice_date": str(r["notice_date"])}

        biggest = max(rows, key=lambda r: r["employees_affected"], default=None)
        targets = [r for r in rows if r["employer_normalized"] in TARGET_COMPANIES]
        biggest_target = max(targets, key=lambda r: r["employees_affected"], default=None)
        return {
            "source": source,
            "fetched": len(rows),
            "biggest_layoff": _fmt(biggest) if biggest else None,
            "biggest_layoff_at_tracked_company": _fmt(biggest_target) if biggest_target else None,
            "note": "Flag layoffs at tracked companies (biggest_layoff_at_tracked_company) — "
                    "those affect salary briefs we publish.",
        }
    if source in ("dol_lca", "dol_perm"):
        return {"source": source, "fetched": 0,
                "note": "DOL quarterly imports run through make seed; no rows staged by Scout"}
    return {"error": f"unknown source '{source}'"}


def validate_filings(source: str) -> dict:
    rows = _STAGED.get(source, [])
    if not rows:
        return {"source": source, "staged": 0, "issues": ["nothing staged; call fetch_source first"]}
    issues = []
    missing_emp = sum(1 for r in rows if not r.get("employer_normalized"))
    zero_emp = sum(1 for r in rows if r.get("employees_affected", 0) <= 0)
    if missing_emp:
        issues.append(f"{missing_emp} rows missing employer")
    if zero_emp:
        issues.append(f"{zero_emp} rows with 0 employees_affected")
    return {"source": source, "staged": len(rows), "issues": issues or ["none"]}


def commit_to_tiger(source: str) -> dict:
    rows = _STAGED.get(source, [])
    if not rows:
        return {"committed": 0, "note": "nothing staged"}
    if source == "warn_ca":
        existing = {r[0] for r in query("SELECT filing_id FROM warn_filings").result_rows}
        new = [r for r in rows if r["filing_id"] not in existing]
        n = warn_ca.insert_warn(new)
        return {"source": source, "new_committed": n, "already_present": len(rows) - n}
    return {"committed": 0, "note": f"{source} is committed at ingestion time"}


def flag_anomaly(description: str, severity: str, company: str = "") -> dict:
    aid = str(uuid.uuid4())
    insert(
        "anomalies",
        [[aid, dt.datetime.now(), severity if severity in ("low", "medium", "high") else "medium",
          description, company, "open", ""]],
        ["anomaly_id", "detected_at", "severity", "description", "company",
         "investigation_status", "investigation_notes"],
    )
    return {"anomaly_id": aid, "status": "flagged_for_investigator", "severity": severity, "company": company}


def done(summary: str = "") -> dict:
    return {"status": "done", "summary": summary}


def get_tools() -> list[Tool]:
    return [
        Tool("check_source_freshness", "Return freshness for a source: one of dol_lca, dol_perm, warn_ca. "
             "Tells you rows_in_store, days_since_latest, expected_change_rate, staleness_score.",
             check_source_freshness,
             {"type": "object", "properties": {"source": {"type": "string"}}, "required": ["source"]}),
        Tool("fetch_source", "Stage recent California WARN notices when source=warn_ca; "
             "DOL quarterly imports run through make seed.", fetch_source,
             {"type": "object", "properties": {"source": {"type": "string"},
              "since_date": {"type": "string", "description": "YYYY-MM-DD, optional"}}, "required": ["source"]}),
        Tool("validate_filings", "Sanity-check the staged filings for a source; returns issues.",
             validate_filings,
             {"type": "object", "properties": {"source": {"type": "string"}}, "required": ["source"]}),
        Tool("commit_to_tiger", "Insert the staged filings for a source into TimescaleDB (deduped).",
             commit_to_tiger,
             {"type": "object", "properties": {"source": {"type": "string"}}, "required": ["source"]}),
        Tool("flag_anomaly", "Flag an anomaly (e.g. a large layoff or data shift) for the Investigator.",
             flag_anomaly,
             {"type": "object", "properties": {"description": {"type": "string"},
              "severity": {"type": "string", "enum": ["low", "medium", "high"]},
              "company": {"type": "string"}}, "required": ["description", "severity"]}),
        Tool("done", "Call when all sources are reasonably fresh and anomalies are flagged.",
             done, {"type": "object", "properties": {"summary": {"type": "string"}}}, terminal=True),
    ]
