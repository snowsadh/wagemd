"""Seed the company_levels table from the hand-curated company_levels.csv at the repo root.

The CSV maps each company's internal level strings (as they appear in DOL filings / careers
pages) to WAGE.md canonical L1-L7. Slugs (e.g. 'anthropic') are mapped to canonical display
names ('Anthropic') so the table joins cleanly against filings.
"""
from __future__ import annotations

import csv

from ..core.tiger_client import query, transaction
from ..core.config import settings
from .companies import TARGET_COMPANIES

VALID_LEVELS = {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}
COLUMNS = ["employer_normalized", "internal_level", "canonical_level", "role_family", "source_url", "notes"]


def seed() -> dict:
    csv_path = settings.repo_root / "company_levels.csv"
    if not csv_path.exists():
        return {"status": "skipped", "reason": f"{csv_path} not found"}
    slug_to_canon = {c.lower(): c for c in TARGET_COMPANIES}
    rows = []
    with csv_path.open() as f:
        for r in csv.DictReader(f):
            lvl = r["canonical_level"].strip()
            if lvl not in VALID_LEVELS:
                continue
            emp = slug_to_canon.get(r["employer_normalized"].strip().lower(),
                                    r["employer_normalized"].strip().title())
            rows.append([emp, r["internal_level"].strip(), lvl, r["role_family"].strip(),
                         r.get("source_url", "").strip(), r.get("notes", "").strip()])
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM company_levels")
            if rows:
                cur.executemany(
                    "INSERT INTO company_levels (" + ", ".join(COLUMNS) + ") VALUES ("
                    + ", ".join(f"%({c})s" for c in COLUMNS) + ")",
                    [dict(zip(COLUMNS, row)) for row in rows],
                )
    n = len(rows)
    return {"status": "ok", "seeded": n,
            "companies": [r[0] for r in query(
                "SELECT DISTINCT employer_normalized FROM company_levels").result_rows]}


if __name__ == "__main__":
    print(seed())
