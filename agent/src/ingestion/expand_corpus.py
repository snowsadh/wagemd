"""Expand the existing Tiger Data corpus to a fixed size from official DOL LCA workbooks."""
from __future__ import annotations

import argparse
import hashlib
import heapq
from pathlib import Path

from ..core.tiger_client import query
from ..normalization.companies import TARGET_COMPANIES
from ..normalization.title_normalizer import normalize_rows
from . import dol_flag
from .download import download_xlsx

FY2026_FILE = "LCA_Disclosure_Data_FY2026_Q3.xlsx"
FY2025_FILES = [f"LCA_Disclosure_Data_FY2025_Q{quarter}.xlsx" for quarter in range(1, 5)]
FY2025_URL = "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/"


def _rank(key: tuple[str, str]) -> int:
    return int.from_bytes(hashlib.sha256(f"{key[0]}\0{key[1]}".encode()).digest(), "big")


def _select_rows(existing: set[tuple[str, str]], needed: int, paths: list[Path]) -> list[dict]:
    """Keep the lowest stable hash ranks, preserving the first source's duplicate case."""
    selected: dict[tuple[str, str], dict] = {}
    heap: list[tuple[int, tuple[str, str]]] = []
    for path in paths:
        rows = dol_flag.parse_filtered(path, "LCA")
        print(f"{path.name}: {len(rows)} eligible filings")
        for row in rows:
            key = (row["case_number"], row["case_type"])
            if not key[0] or key in existing or key in selected:
                continue
            item = (-_rank(key), key)
            if len(heap) < needed:
                heapq.heappush(heap, item)
                selected[key] = row
            elif item > heap[0]:
                _, removed = heapq.heapreplace(heap, item)
                del selected[removed]
                selected[key] = row
    if len(selected) < needed:
        raise ValueError(f"only {len(selected)} new eligible filings found; need {needed}; no rows inserted")
    return [selected[key] for key in sorted(selected)]


def expand_corpus(*, target: int = 80_000, batch_size: int = 1_000) -> dict:
    if target < 1 or batch_size < 1:
        raise ValueError("target and batch_size must be positive")

    stored = query(
        "SELECT case_number, case_type, employer_normalized, job_title_raw, "
        "role_family, level_normalized, normalization_confidence "
        "FROM filings ORDER BY case_number, case_type"
    ).result_rows
    existing = {(row[0], row[1]) for row in stored}
    target_existing = sum(row[2] in TARGET_COMPANIES for row in stored)
    if target_existing >= target:
        return {"existing": target_existing, "inserted": 0, "total": target_existing}

    known = {}
    for _, _, employer, title, role, level, confidence in stored:
        pair = (employer, title)
        if pair not in known or confidence > known[pair][2]:
            known[pair] = (role, level, confidence)

    recent_path = dol_flag.download(FY2026_FILE)
    recent = {}
    for row in dol_flag.parse_filtered(recent_path, "LCA"):
        key = (row["case_number"], row["case_type"])
        if key[0] and key not in existing:
            recent.setdefault(key, row)
    needed = target - target_existing
    print(f"{recent_path.name}: {len(recent)} new eligible filings")
    if len(recent) >= needed:
        rows = [recent[key] for key in sorted(recent, key=lambda key: (_rank(key), key))[:needed]]
    else:
        paths = [download_xlsx(FY2025_URL + name, dol_flag.DATA_CACHE / name)
                 for name in FY2025_FILES]
        rows = list(recent.values()) + _select_rows(existing | recent.keys(), needed - len(recent), paths)
    rows.sort(key=lambda row: (row["case_number"], row["case_type"]))

    unseen = {}
    for row in rows:
        pair = (row["employer_normalized"], row["job_title_raw"])
        if pair not in known:
            unseen.setdefault(pair, row)
    if unseen:
        print(f"Normalizing {len(unseen)} unseen employer/title pairs")
        for row in normalize_rows(list(unseen.values())):
            known[(row["employer_normalized"], row["job_title_raw"])] = (
                row["role_family"], row["level_normalized"], row["normalization_confidence"]
            )
    for row in rows:
        row["role_family"], row["level_normalized"], row["normalization_confidence"] = (
            known[(row["employer_normalized"], row["job_title_raw"])]
        )

    inserted = 0
    for start in range(0, len(rows), batch_size):
        inserted += dol_flag.insert_filings(rows[start : start + batch_size])
    if inserted != len(rows):
        raise RuntimeError(f"inserted {inserted} rows, expected {len(rows)}; check concurrent writers")
    return {"existing": target_existing, "inserted": inserted, "total": target_existing + inserted}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grow existing Tiger Data filings from DOL LCA sources")
    parser.add_argument("--target", type=int, default=80_000)
    parser.add_argument("--batch-size", type=int, default=1_000)
    args = parser.parse_args()
    print(expand_corpus(target=args.target, batch_size=args.batch_size))
