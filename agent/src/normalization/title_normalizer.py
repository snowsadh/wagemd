"""Title + level normalization via OpenAI.

Batch-classifies raw DOL job titles into the canonical taxonomy (role_family:
SWE/PM/Design/FDE/ML/Data/Other; level: L1-L7/Unknown) with a confidence score, using the
SPEC.md system prompt + company-specific level knowledge. Never guesses: returns Unknown
with confidence < 0.5 when unsure.

We read filings, classify the DISTINCT (employer, title) pairs (dedup keeps model
calls small), then update classifications in one transaction.
Uses the configured OpenAI model; pass --model to override it for a batch.
"""
from __future__ import annotations

import argparse
import json
import math

from ..core.config import settings
from ..core.openai_client import get_openai
from ..core.tiger_client import query, transaction
from ..ingestion.dol_flag import FILINGS_COLUMNS

ROLE_FAMILIES = {"SWE", "PM", "Design", "FDE", "ML", "Data", "Other"}
LEVELS = {"L1", "L2", "L3", "L4", "L5", "L6", "L7", "Unknown"}

SYSTEM_PROMPT = """You normalize US Department of Labor job filing titles to a canonical taxonomy.

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
- Anthropic "Member of Technical Staff" (no suffix) ~ L5-L6 equivalent
- OpenAI "Member of Technical Staff" ~ L5
- Google: Software Engineer II=L3, III=L4, Senior=L5, Staff=L6, Senior Staff=L7
- Meta: E3=L3, E4=L4, E5=L5 (Senior), E6=L6 (Staff), E7=L7 (Principal)
- Stripe: L1=L2, L2=L3, L3=L4, L4=L5 (Staff), L5=L6
- Amazon: SDE I=L3, SDE II=L4, SDE III=L5 (Senior), Principal=L6

If you cannot confidently determine the level, return "Unknown" with confidence < 0.5.
Never guess."""

BATCH_PROMPT = """Classify each of the following {n} job filings into the taxonomy.
Each line is: <index>. employer="..." title="...".

Return ONLY a JSON array of exactly {n} objects, in the same order, each:
{{"idx": <int>, "role_family": "...", "level": "...", "confidence": 0.0-1.0}}

Filings:
{items}"""


def _classify_batch(pairs: list[tuple[str, str]], model: str) -> dict[tuple[str, str], dict]:
    ai = get_openai()
    items = "\n".join(f'{i}. employer="{e}" title="{t}"' for i, (e, t) in enumerate(pairs))
    prompt = BATCH_PROMPT.format(n=len(pairs), items=items)
    resp = ai.generate(
        model=model,
        contents=[ai.user_content(prompt)],
        system_instruction=SYSTEM_PROMPT,
    )
    raw = ai.text_of(resp)
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end < start:
        raise ValueError("OpenAI returned no classification array")
    try:
        arr = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError("OpenAI returned invalid classification JSON") from e
    if not isinstance(arr, list) or len(arr) != len(pairs):
        count = len(arr) if isinstance(arr, list) else "invalid"
        raise ValueError(f"OpenAI returned {count} classifications for {len(pairs)} titles")
    out: dict[tuple[str, str], dict] = {}
    for obj in arr:
        if not isinstance(obj, dict):
            raise ValueError("OpenAI returned an invalid classification object")
        i = obj.get("idx")
        if type(i) is not int or not 0 <= i < len(pairs) or pairs[i] in out:
            raise ValueError(f"OpenAI returned an invalid or duplicate classification index: {i}")
        rf, lv, conf = obj.get("role_family"), obj.get("level"), obj.get("confidence")
        if (not isinstance(rf, str) or rf not in ROLE_FAMILIES
                or not isinstance(lv, str) or lv not in LEVELS):
            raise ValueError(f"OpenAI returned an invalid role or level for title {i}")
        if type(conf) not in (int, float) or not math.isfinite(conf) or not 0 <= conf <= 1:
            raise ValueError(f"OpenAI returned an invalid confidence for title {i}")
        out[pairs[i]] = {"role_family": rf, "level": lv, "confidence": round(conf, 3)}
    return out


def normalize_rows(rows: list[dict], *, model: str | None = None, batch_size: int = 40) -> list[dict]:
    """Classify the distinct titles in `rows` and set role_family/level/confidence in memory.

    Used by on-demand ingestion to level a freshly-fetched company before INSERT,
    without a full corpus reload. A failed or incomplete model batch aborts ingestion.
    """
    model = model or settings.openai_model
    pairs = sorted({(r["employer_normalized"], r["job_title_raw"]) for r in rows})
    mapping: dict[tuple[str, str], dict] = {}
    for i in range(0, len(pairs), batch_size):
        mapping.update(_classify_batch(pairs[i : i + batch_size], model))
    out = []
    for r in rows:
        cls = mapping.get((r["employer_normalized"], r["job_title_raw"]))
        if cls:
            r = {**r, "role_family": cls["role_family"], "level_normalized": cls["level"],
                 "normalization_confidence": cls["confidence"]}
        out.append(r)
    return out


def normalize_and_reload(*, model: str | None = None, batch_size: int = 40) -> dict:
    """Read filings, classify distinct titles, and update existing rows.

    Robustness (per review): (1) we read each row's EXISTING level and keep it when a title
    isn't reclassified, so a transient model failure never silently demotes rows to Unknown;
    (2) if EVERY batch fails we abort without touching the table; (3) updates are
    transactional, and rows inserted during classification remain intact.
    """
    model = model or settings.openai_model
    cols = FILINGS_COLUMNS
    rows = [dict(zip(cols, r)) for r in query(f"SELECT {','.join(cols)} FROM filings").result_rows]
    if not rows:
        return {"status": "no rows"}

    pairs = sorted({(r["employer_normalized"], r["job_title_raw"]) for r in rows})
    mapping: dict[tuple[str, str], dict] = {}
    total_batches = (len(pairs) + batch_size - 1) // batch_size
    failed_batches = 0
    for i in range(0, len(pairs), batch_size):
        chunk = pairs[i : i + batch_size]
        try:
            mapping.update(_classify_batch(chunk, model))
        except Exception as e:  # keep existing levels for this chunk; don't demote
            failed_batches += 1
            print(f"  batch {i // batch_size} failed: {type(e).__name__}: {e}")

    if total_batches and failed_batches == total_batches:
        return {"status": "aborted", "reason": "all classification batches failed; filings untouched",
                "failed_batches": failed_batches}

    reload_rows = []
    for r in rows:
        cls = mapping.get((r["employer_normalized"], r["job_title_raw"]))
        if cls:
            r = {**r, "role_family": cls["role_family"], "level_normalized": cls["level"],
                 "normalization_confidence": cls["confidence"]}
        # else: keep the row's existing role_family/level_normalized/normalization_confidence
        reload_rows.append(r)

    n = _swap_reload(reload_rows)
    classified = sum(1 for r in reload_rows if r["level_normalized"] != "Unknown")
    return {
        "total_rows": n,
        "distinct_titles": len(pairs),
        "failed_batches": failed_batches,
        "rows_with_level": classified,
        "pct_leveled": round(100 * classified / n, 1) if n else 0,
    }


def _swap_reload(reload_rows: list[dict]) -> int:
    """Update classifications atomically without replacing the source filings."""
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE filings SET role_family=%(role_family)s, "
                "level_normalized=%(level_normalized)s, "
                "normalization_confidence=%(normalization_confidence)s "
                "WHERE case_number=%(case_number)s AND case_type=%(case_type)s "
                "AND decision_date=%(decision_date)s "
                "AND employer_normalized=%(employer_normalized)s "
                "AND job_title_raw=%(job_title_raw)s",
                reload_rows,
            )
            if cur.rowcount != len(reload_rows):
                raise RuntimeError(
                    f"updated {cur.rowcount} filings != expected {len(reload_rows)}; aborting reload"
                )
    return len(reload_rows)


def run_batch() -> None:
    print(normalize_and_reload())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Title/level normalization")
    p.add_argument("--model", default=None, help="override configured OpenAI model")
    p.add_argument("--batch-size", type=int, default=40)
    a = p.parse_args()
    print(normalize_and_reload(model=a.model, batch_size=a.batch_size))
