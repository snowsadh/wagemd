"""Distinguish an empty WARN corpus from a company with no matching notices."""

from types import SimpleNamespace

from src.tools import queries


def test_warn_context_reports_missing_corpus(monkeypatch):
    calls = []

    def fake_query(sql, _params):
        calls.append(sql)
        return SimpleNamespace(result_rows=[(False, 0, None)])

    monkeypatch.setattr(queries, "query", fake_query)
    result = queries.warn_context("Amazon")

    assert result["has_warn_data"] is False
    assert result["notice_count"] == 0
    assert result["recent_notices"] == []
    assert len(calls) == 1
