"""On-demand (fetch-on-miss) ingestion for arbitrary companies.

When a user asks about a company we haven't loaded, an agent calls ingest_company(). We:
  1. ask OpenAI to resolve the user's name to the company's real DOL EMPLOYER_NAME forms
     (e.g. "TCS" -> ["TATA CONSULTANCY", "TCS"]) — DOL filings use legal names, not brands;
  2. scan the cached recent DOL quarters for matching filings;
  3. normalize their titles and append them to TimescaleDB.

This makes the corpus self-extending: any company that has filed PERM/LCA can be pulled in
on first query, without re-ingesting the whole dataset.
"""
from __future__ import annotations

from ..core.config import settings
from ..core.openai_client import get_openai
from ..core.tiger_client import query
from ..normalization.title_normalizer import normalize_rows
from . import dol_flag

# Current public quarter (PERM = green cards, LCA = H-1B). download() caches the full workbooks.
STANDARD_FILES = [
    ("PERM_Disclosure_Data_FY2026_Q3.xlsx", "PERM"),
    ("LCA_Disclosure_Data_FY2026_Q3.xlsx", "LCA"),
]

_RESOLVE_PROMPT = """A user searched WAGE.md for the employer "{name}". US Department of Labor
PERM/LCA filings list employers by their LEGAL name, not brand (e.g. "TCS" appears as
"TATA CONSULTANCY SERVICES"). Return JSON only:
{{"canonical": "<short brand name to display>",
  "match_patterns": ["<UPPERCASE substring that appears in the DOL EMPLOYER_NAME>", ...]}}
Include 1-4 specific patterns (legal name fragments + the brand). Avoid generic words that would
match unrelated firms."""


def resolve_company(user_input: str) -> dict:
    """Resolve a user-typed company to {canonical, patterns} using OpenAI."""
    ai = get_openai()
    d = ai.generate_json(prompt=_RESOLVE_PROMPT.format(name=user_input),
                         model=settings.openai_model)
    if not isinstance(d, dict) or not isinstance(d.get("canonical"), str) or not d["canonical"].strip():
        raise ValueError("OpenAI returned no valid canonical company name")
    if not isinstance(d.get("match_patterns"), list):
        raise ValueError("OpenAI returned no valid employer match patterns")
    patterns = [p.strip().upper() for p in d["match_patterns"] if isinstance(p, str) and len(p.strip()) >= 3]
    if not patterns:
        raise ValueError("OpenAI returned no valid employer match patterns")
    return {"canonical": d["canonical"].strip(), "patterns": patterns}


def _existing_count(canonical: str) -> int:
    return query("SELECT count(*) FROM filings WHERE employer_normalized=%(c)s",
                 {"c": canonical}).result_rows[0][0]


def ingest_company(user_input: str, *, files=None, limit_per_file: int = 800) -> dict:
    """Fetch-on-miss: resolve, scan cached DOL quarters, normalize, append. Idempotent per company."""
    files = files or STANDARD_FILES
    res = resolve_company(user_input)
    canonical, patterns = res["canonical"], res["patterns"]
    existing = _existing_count(canonical)
    if existing > 0:
        return {"company": canonical, "ingested": 0, "already_present": existing, "patterns": patterns}

    rows: list[dict] = []
    for filename, case_type in files:
        try:
            path = dol_flag.download(filename)
        except Exception as e:  # a quarter being unavailable shouldn't abort the rest
            print(f"  on_demand: could not fetch {filename}: {e}")
            continue
        rows += dol_flag.parse_filtered(
            path, case_type, employer_patterns=patterns, canonical=canonical, limit=limit_per_file)

    if not rows:
        return {"company": canonical, "ingested": 0, "patterns": patterns,
                "note": "no DOL filings found for this employer in the cached quarters"}

    rows = normalize_rows(rows)
    n = dol_flag.insert_filings(rows)
    return {"company": canonical, "ingested": n, "patterns": patterns}


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="On-demand company ingestion (fetch-on-miss)")
    p.add_argument("company")
    a = p.parse_args()
    print(json.dumps(ingest_company(a.company), indent=2, default=str))
