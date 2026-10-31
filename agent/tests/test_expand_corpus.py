"""Verify deterministic corpus expansion without replacing existing filings."""
from pathlib import Path

import pytest

from src.core.tiger_client import QueryResult
from src.ingestion import expand_corpus


def _row(case: str, title: str = "Engineer", *, wage: float = 100_000) -> dict:
    return {
        "case_number": case, "case_type": "LCA", "employer_normalized": "Google",
        "job_title_raw": title, "role_family": "Other", "level_normalized": "Unknown",
        "normalization_confidence": 0.0, "wage_low_usd": wage,
    }


def test_selects_lowest_hashes_from_all_historical_files_and_keeps_first_duplicate(monkeypatch):
    files = {
        "Q1.xlsx": [_row("A", wage=100_000), _row("B")],
        "Q2.xlsx": [_row("A", wage=200_000), _row("C"), _row("D")],
    }

    def parse(path, case_type):
        assert case_type == "LCA"
        return files[path.name]

    monkeypatch.setattr(expand_corpus.dol_flag, "parse_filtered", parse)
    paths = [Path(name) for name in files]
    expected = sorted(("A", "B", "C", "D"), key=lambda case: expand_corpus._rank((case, "LCA")))[:3]

    first = expand_corpus._select_rows(set(), 3, paths)
    files["Q1.xlsx"].reverse()
    files["Q2.xlsx"].reverse()
    second = expand_corpus._select_rows(set(), 3, paths)

    assert {row["case_number"] for row in first} == set(expected)
    assert first == second
    all_rows = expand_corpus._select_rows(set(), 4, paths)
    assert next(row for row in all_rows if row["case_number"] == "A")["wage_low_usd"] == 100_000


def test_expansion_preserves_existing_rows_and_second_run_is_noop(monkeypatch, tmp_path):
    original = ("OLD", "PERM", "Google", "Engineer", "SWE", "L4", 0.9)
    unrelated = ("OTHER", "PERM", "Other Company", "Engineer", "Other", "Unknown", 0.0)
    stored = {(original[0], original[1]): original, (unrelated[0], unrelated[1]): unrelated}
    parsed = {
        expand_corpus.FY2026_FILE: [_row("RECENT", "Engineer"), _row("NEW", "Designer")],
        **{name: [_row(f"H{quarter}", "Engineer")]
           for quarter, name in enumerate(expand_corpus.FY2025_FILES, 1)},
    }
    normalized_pairs = []
    inserted_keys = []

    def fake_query(sql):
        assert "FROM filings" in sql
        return QueryResult(list(stored.values()), [])

    def parse(path, case_type):
        assert case_type == "LCA"
        return parsed[path.name]

    def normalize(rows):
        normalized_pairs.extend((row["employer_normalized"], row["job_title_raw"]) for row in rows)
        return [{**row, "role_family": "Design", "level_normalized": "L3",
                 "normalization_confidence": 0.8} for row in rows]

    def insert(rows):
        for row in rows:
            key = (row["case_number"], row["case_type"])
            assert key not in stored
            inserted_keys.append(key)
            stored[key] = (key[0], key[1], row["employer_normalized"], row["job_title_raw"],
                           row["role_family"], row["level_normalized"], row["normalization_confidence"])
        return len(rows)

    monkeypatch.setattr(expand_corpus, "query", fake_query)
    monkeypatch.setattr(expand_corpus.dol_flag, "download", lambda name: tmp_path / name)
    monkeypatch.setattr(expand_corpus, "download_xlsx", lambda url, dest: dest)
    monkeypatch.setattr(expand_corpus.dol_flag, "parse_filtered", parse)
    monkeypatch.setattr(expand_corpus, "normalize_rows", normalize)
    monkeypatch.setattr(expand_corpus.dol_flag, "insert_filings", insert)

    first = expand_corpus.expand_corpus(target=5, batch_size=2)
    second = expand_corpus.expand_corpus(target=5, batch_size=2)

    assert first == {"existing": 1, "inserted": 4, "total": 5}
    assert second == {"existing": 5, "inserted": 0, "total": 5}
    assert stored[("OLD", "PERM")] == original
    assert stored[("OTHER", "PERM")] == unrelated
    assert normalized_pairs == [("Google", "Designer")]
    assert len(inserted_keys) == len(set(inserted_keys)) == 4
    assert all(stored[key][4:7] == ("SWE", "L4", 0.9)
               for key in inserted_keys if stored[key][3] == "Engineer")


def test_insufficient_sources_fail_before_normalization_or_inserts(monkeypatch, tmp_path):
    monkeypatch.setattr(expand_corpus, "query", lambda sql: QueryResult([], []))
    monkeypatch.setattr(expand_corpus.dol_flag, "download", lambda name: tmp_path / name)
    monkeypatch.setattr(expand_corpus, "download_xlsx", lambda url, dest: dest)
    monkeypatch.setattr(expand_corpus.dol_flag, "parse_filtered", lambda path, case_type: [_row("ONLY")])
    monkeypatch.setattr(expand_corpus, "normalize_rows", lambda rows: pytest.fail("normalized too soon"))
    monkeypatch.setattr(expand_corpus.dol_flag, "insert_filings", lambda rows: pytest.fail("inserted too soon"))

    with pytest.raises(ValueError, match="no rows inserted"):
        expand_corpus.expand_corpus(target=6)
