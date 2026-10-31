"""DOL FLAG quarterly disclosure ingestion.

Downloads LCA (H-1B) and PERM disclosure files from the OFLC site, parses the
.xlsx, maps the columns (LCA and PERM use different names) to the `filings` schema, filters
to the demo's target companies, and inserts into TimescaleDB with real CASE_NUMBERs intact.

Wages are annualized to USD. role_family/level_normalized are inserted as placeholders here
and refined by the OpenAI title normalizer (see normalization/title_normalizer.py).
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
from collections import Counter

import openpyxl

from ..core.config import settings
from ..core.tiger_client import command, insert
from .download import download_xlsx

BASE_URL = "https://www.dol.gov/media"
DATA_CACHE = settings.repo_root / "data-cache"

# Field -> candidate column names across LCA and PERM file layouts.
FIELD_CANDIDATES: dict[str, list[str]] = {
    "case_number": ["CASE_NUMBER"],
    "decision_date": ["DECISION_DATE"],
    "employer": ["EMPLOYER_NAME", "EMP_BUSINESS_NAME"],
    "job_title": ["JOB_TITLE", "JOB_INFO_JOB_TITLE"],
    "soc_code": ["SOC_CODE", "PWD_SOC_CODE", "PW_SOC_CODE"],
    "soc_title": ["SOC_TITLE", "PWD_SOC_TITLE", "PW_SOC_TITLE"],
    "wage_from": ["WAGE_RATE_OF_PAY_FROM", "JOB_OPP_WAGE_FROM", "WAGE_OFFER_FROM_9089"],
    "wage_to": ["WAGE_RATE_OF_PAY_TO", "JOB_OPP_WAGE_TO", "WAGE_OFFER_TO_9089"],
    "wage_unit": ["WAGE_UNIT_OF_PAY", "JOB_OPP_WAGE_PER", "PW_UNIT_OF_PAY_9089"],
    "city": ["WORKSITE_CITY", "PRIMARY_WORKSITE_CITY", "JOB_INFO_WORK_CITY"],
    "state": ["WORKSITE_STATE", "PRIMARY_WORKSITE_STATE", "JOB_INFO_WORK_STATE"],
}

WAGE_UNIT_MULT = {
    "YEAR": 1, "YR": 1, "ANNUAL": 1,
    "HOUR": 2080, "HR": 2080,
    "WEEK": 52, "WEEKLY": 52,
    "BI-WEEKLY": 26, "BIWEEKLY": 26,
    "MONTH": 12, "MONTHLY": 12,
}

# Exclude obvious source/unit errors before they distort small-group percentiles.
MAX_ANNUAL_WAGE_USD = 2_000_000

FILINGS_COLUMNS = [
    "case_number", "case_type", "decision_date", "employer_name_raw", "employer_normalized",
    "job_title_raw", "soc_code", "soc_title", "role_family", "level_normalized",
    "normalization_confidence", "wage_low_usd", "wage_high_usd", "wage_unit",
    "worksite_city", "worksite_state",
]


def download(filename: str, *, force: bool = False) -> pathlib.Path:
    """Download a public DOL disclosure workbook into data-cache/."""
    return download_xlsx(f"{BASE_URL}/{filename}", DATA_CACHE / filename, force=force)


def _resolve_columns(header: list) -> dict[str, int]:
    upper = {str(c).upper(): i for i, c in enumerate(header) if c is not None}
    idx: dict[str, int] = {}
    for field, cands in FIELD_CANDIDATES.items():
        for c in cands:
            if c.upper() in upper:
                idx[field] = upper[c.upper()]
                break
    return idx


def _annualize(val, unit) -> float:
    try:
        x = float(str(val).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return 0.0
    return round(x * WAGE_UNIT_MULT.get(str(unit).upper().strip(), 1), 2)


def _parse_date(v) -> dt.date | None:
    """Parse a decision date; return None (not a sentinel) if missing/unparseable."""
    if isinstance(v, (dt.datetime, dt.date)):
        return v.date() if isinstance(v, dt.datetime) else v
    s = str(v)[:10]
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return dt.date.fromisoformat(s)
        except ValueError:
            return None
    return None


def parse_filtered(
    path: pathlib.Path, case_type: str, *, targets_only: bool = True, limit: int | None = None,
    employer_patterns: list[str] | None = None, canonical: str | None = None,
) -> list[dict]:
    """Parse an .xlsx into filings rows.

    - default: keep the hand-curated target companies (targets_only).
    - employer_patterns set: keep any row whose raw employer contains one of the (uppercased)
      patterns, labeling it `canonical` — used by on-demand fetch-on-miss for arbitrary companies.
    """
    from ..normalization.companies import match_target, normalize_employer

    patterns_up = [p.upper() for p in employer_patterns] if employer_patterns else None

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    header = list(next(it))
    idx = _resolve_columns(header)
    required = ("case_number", "employer", "job_title", "wage_from")
    missing = [f for f in required if f not in idx]
    if missing:
        wb.close()
        raise ValueError(f"missing columns {missing} in {path.name}; header[:8]={header[:8]}")

    if "decision_date" not in idx:
        wb.close()
        raise ValueError(f"required column decision_date missing in {path.name}")

    rows: list[dict] = []
    bad_dates = 0
    for raw in it:
        emp_raw = raw[idx["employer"]]
        if patterns_up is not None:  # on-demand: match arbitrary employer by pattern
            up = str(emp_raw or "").upper()
            if not any(p in up for p in patterns_up):
                continue
            canon = canonical or normalize_employer(emp_raw)
        else:
            canon = match_target(emp_raw)
            if targets_only and canon is None:
                continue
            if canon is None:
                canon = normalize_employer(emp_raw)
        unit = raw[idx["wage_unit"]] if "wage_unit" in idx else "Year"
        wage_from = _annualize(raw[idx["wage_from"]], unit)
        if wage_from <= 0:
            continue
        dval = _parse_date(raw[idx["decision_date"]])
        if dval is None:  # don't poison partitions/freshness with a sentinel date
            bad_dates += 1
            continue
        wage_to = _annualize(raw[idx["wage_to"]], unit) if "wage_to" in idx else wage_from
        if wage_from > MAX_ANNUAL_WAGE_USD or wage_to > MAX_ANNUAL_WAGE_USD:
            continue
        rows.append(
            {
                "case_number": str(raw[idx["case_number"]] or ""),
                "case_type": case_type,
                "decision_date": dval,
                "employer_name_raw": str(emp_raw or ""),
                "employer_normalized": canon,
                "job_title_raw": str(raw[idx["job_title"]] or ""),
                "soc_code": str(raw[idx["soc_code"]] or "") if "soc_code" in idx else "",
                "soc_title": str(raw[idx["soc_title"]] or "") if "soc_title" in idx else "",
                "role_family": "Other",
                "level_normalized": "Unknown",
                "normalization_confidence": 0.0,
                "wage_low_usd": wage_from,
                "wage_high_usd": wage_to or wage_from,
                "wage_unit": str(unit or ""),
                "worksite_city": str(raw[idx["city"]] or "") if "city" in idx else "",
                "worksite_state": str(raw[idx["state"]] or "") if "state" in idx else "",
            }
        )
        if limit and len(rows) >= limit:
            break
    wb.close()
    if bad_dates:
        print(f"  [dol_flag] skipped {bad_dates} rows with unparseable decision_date")
    return rows


def insert_filings(rows: list[dict]) -> int:
    if not rows:
        return 0
    data = [[r[c] for c in FILINGS_COLUMNS] for r in rows]
    return insert("filings", data, FILINGS_COLUMNS)


def reset_filings() -> None:
    command("DELETE FROM filings")


def ingest_file(filename: str, case_type: str, *, targets_only: bool = True, limit: int | None = None) -> dict:
    """Download (if needed), parse, and insert one disclosure file. Returns a summary."""
    path = download(filename)
    rows = parse_filtered(path, case_type, targets_only=targets_only, limit=limit)
    n = insert_filings(rows)
    by_company = Counter(r["employer_normalized"] for r in rows)
    return {"file": filename, "inserted": n, "by_company": dict(by_company.most_common())}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="DOL FLAG ingestion")
    p.add_argument("--file", required=True, help="e.g. LCA_Disclosure_Data_FY2026_Q2.xlsx")
    p.add_argument("--case-type", required=True, choices=["LCA", "PERM"])
    p.add_argument("--all-employers", action="store_true", help="do not filter to target companies")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--reset", action="store_true", help="delete existing filings before insert")
    a = p.parse_args()
    if a.reset:
        reset_filings()
        print("reset filings")
    summary = ingest_file(a.file, a.case_type, targets_only=not a.all_employers, limit=a.limit)
    print(summary)
