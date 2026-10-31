"""California WARN Act ingestion (priority state).

Source: the CA EDD "Detailed WARN Report" xlsx. Maps to the `warn_filings` schema. CA is the priority state per
SPEC; WA/NY are cut candidates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import pathlib

import openpyxl

from ..core.config import settings
from ..core.tiger_client import insert, query, transaction
from ..normalization.companies import normalize_employer
from .download import download_xlsx

WARN_URL = "https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx"
DATA_CACHE = settings.repo_root / "data-cache"
WARN_COLUMNS = [
    "filing_id", "employer_normalized", "state", "notice_date", "effective_date",
    "employees_affected", "raw_data",
]


def download(*, force: bool = False) -> pathlib.Path:
    return download_xlsx(WARN_URL, DATA_CACHE / "CA_WARN.xlsx", force=force, timeout=120.0)


def _norm(s) -> str:
    return str(s or "").replace("\n", " ").strip().lower()


def _to_date(v) -> dt.date:
    if isinstance(v, (dt.datetime, dt.date)):
        return v.date() if isinstance(v, dt.datetime) else v
    s = str(v)[:10]
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return dt.date(1970, 1, 1)


def _to_int(v) -> int:
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0


def parse(path: pathlib.Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = next((wb[n] for n in wb.sheetnames if "detail" in n.lower()), wb.active)
    rows_iter = ws.iter_rows(values_only=True)
    # find the header row (contains "company" and "effective")
    header = None
    for row in rows_iter:
        cells = [_norm(c) for c in row]
        if "company" in cells and any("effective" in c for c in cells):
            header = cells
            break
    if header is None:
        wb.close()
        raise ValueError("WARN header row not found")

    def col(*names: str) -> int | None:
        for n in names:
            for j, h in enumerate(header):
                if n in h:
                    return j
        return None

    c_company = col("company")
    c_notice = col("notice")
    c_eff = col("effective")
    c_emp = col("employees", "no. of")
    c_county = col("county", "parish")
    c_layoff = col("layoff", "closure")
    c_industry = col("industry")

    out: list[dict] = []
    for row in rows_iter:
        company = row[c_company] if c_company is not None else None
        if not company or _norm(company) in ("", "none", "total", "totals"):
            continue
        notice = _to_date(row[c_notice]) if c_notice is not None else dt.date(1970, 1, 1)
        eff = _to_date(row[c_eff]) if c_eff is not None else dt.date(1970, 1, 1)
        emp = _to_int(row[c_emp]) if c_emp is not None else 0
        raw_bits = {
            "company": str(company),
            "county": str(row[c_county]) if c_county is not None else "",
            "layoff_type": str(row[c_layoff]) if c_layoff is not None else "",
            "industry": str(row[c_industry]) if c_industry is not None else "",
        }
        fid = "CA-" + hashlib.sha1(
            f"{company}|{notice}|{emp}|{raw_bits['county']}".encode()
        ).hexdigest()[:16]
        out.append({
            "filing_id": fid,
            "employer_normalized": normalize_employer(str(company)),
            "state": "CA",
            "notice_date": notice,
            "effective_date": eff,
            "employees_affected": emp,
            "raw_data": __import__("json").dumps(raw_bits),
        })
    wb.close()
    return out


def insert_warn(rows: list[dict]) -> int:
    if not rows:
        return 0
    data = [[r[c] for c in WARN_COLUMNS] for r in rows]
    return insert("warn_filings", data, WARN_COLUMNS)


def fetch_recent(since_date: str | None = None, limit: int | None = None) -> list[dict]:
    """Parse recent WARN notices (for the Scout to stage). Sorted newest first."""
    rows = parse(download())
    rows.sort(key=lambda r: r["notice_date"], reverse=True)
    if since_date:
        cutoff = _to_date(since_date)
        rows = [r for r in rows if r["notice_date"] >= cutoff]
    return rows[:limit] if limit else rows


def ingest(replace: bool = True) -> dict:
    """Ingest the CA WARN report. replace=True does an atomic full refresh so the
    advertised `make seed` path is idempotent — the report is itself a full snapshot."""
    rows = parse(download())
    if replace:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM warn_filings")
                cur.executemany(
                    "INSERT INTO warn_filings (" + ", ".join(WARN_COLUMNS) + ") VALUES ("
                    + ", ".join(f"%({c})s" for c in WARN_COLUMNS) + ") "
                    "ON CONFLICT DO NOTHING",
                    rows,
                )
                n = cur.rowcount
    else:
        n = insert_warn(rows)
    return {"inserted": n, "replaced": replace,
            "distinct_employers": len({r["employer_normalized"] for r in rows})}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="CA WARN ingestion")
    p.add_argument("--ingest", action="store_true")
    p.add_argument("--targets", action="store_true", help="show target-company layoffs")
    a = p.parse_args()
    if a.ingest:
        print(ingest())
    if a.targets:
        from ..normalization.companies import TARGET_COMPANIES
        rows = query(
            "SELECT employer_normalized, sum(employees_affected), count(*), max(notice_date) "
            "FROM warn_filings WHERE employer_normalized = ANY(%(t)s) GROUP BY employer_normalized "
            "ORDER BY 2 DESC",
            {"t": TARGET_COMPANIES},
        ).result_rows
        for r in rows:
            print(f"  {r[0]:<12} total_laid_off={r[1]} notices={r[2]} latest={r[3]}")
    if not (a.ingest or a.targets):
        p.print_help()
