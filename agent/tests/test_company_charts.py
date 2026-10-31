"""Check company chart filtering, sample thresholds, and fetch-on-miss behavior."""

from fastapi.testclient import TestClient

from src.api import server


def _results(count=20):
    return [
        [("SWE", "L4", 12, 130000, 150000, 180000, 210000)],
        [(20,)],
        [(count, 120000, 150000, 180000, "2026-05-01", "2026-06-30")],
        [("SWE", 12), ("Other", 8)],
        [("CA", 14, 170000), ("WA", 6, 150000)],
        [("2026-05", 8, 140000), ("2026-06", 12, 160000)],
        [("L3", 6, 140000), ("L4", 12, 180000)],
        [("LCA", 16), ("PERM", 4)],
        [("CA",), ("WA",)],
        [("/briefs/Amazon", "2026-10-31")],
    ]


def test_company_chart_payload_default_compatibility(monkeypatch):
    def fake_query_many(statements, parameters=None):
        assert parameters["c"] == "Amazon"
        assert parameters["period"] == "all"
        assert len(statements) == 10
        assert "wage_low_usd>0" not in statements[1]
        return _results()

    monkeypatch.setattr(server, "query_many", fake_query_many)
    payload = TestClient(server.app).get("/company/amazon?fetch=false").json()

    assert payload["total_filings"] == 20
    assert payload["matchedFilings"] == {
        "count": 20, "p25": 120000, "p50": 150000, "p75": 180000,
        "firstDecision": "2026-05-01", "lastDecision": "2026-06-30",
    }
    assert payload["rows"][0] == {
        "role_family": "SWE", "level": "L4", "sample_size": 12,
        "p25": 130000, "p50": 150000, "p75": 180000, "p90": 210000,
    }
    assert payload["roleTotals"] == [
        {"role": "SWE", "count": 12}, {"role": "Other", "count": 8}
    ]
    assert payload["locations"] == [
        {"state": "CA", "count": 14, "median": 170000},
        {"state": "WA", "count": 6, "median": 150000},
    ]
    assert payload["monthlyFilings"] == [
        {"month": "2026-05", "count": 8, "p50": 140000},
        {"month": "2026-06", "count": 12, "p50": 160000},
    ]
    assert payload["levelMedians"] == [
        {"level": "L3", "count": 6, "median": 140000},
        {"level": "L4", "count": 12, "median": 180000},
    ]
    assert payload["caseTypeTotals"] == [
        {"caseType": "LCA", "count": 16}, {"caseType": "PERM", "count": 4},
    ]
    assert sum(row["count"] for row in payload["caseTypeTotals"]) == payload["matchedFilings"]["count"]
    assert payload["stateOptions"] == ["CA", "WA"]
    assert payload["briefUrl"] == "/briefs/Amazon"


def test_company_filters_use_bound_values_and_correct_comparison_cohorts(monkeypatch):
    def fake_query_many(statements, parameters=None):
        assert parameters == {
            "c": "Amazon", "role": "SWE", "level": "L4", "state": "CA",
            "period": "FY2026", "start": "2025-10-01", "end": "2026-10-01",
        }
        (rows, totals, matched, role_totals, locations, monthly,
         level_medians, case_types, states, pub) = statements
        for sql in (rows, matched, monthly, case_types):
            assert "role_family=%(role)s" in sql
            assert "level_normalized=%(level)s" in sql
            assert "worksite_state=%(state)s" in sql
        for sql in (rows, matched, role_totals, locations, monthly, level_medians, case_types):
            assert "decision_date >= %(start)s::date" in sql
            assert "decision_date < %(end)s::date" in sql
            assert "FY2026" not in sql and "Amazon" not in sql
        assert "role_family=%(role)s" not in role_totals
        assert "level_normalized=%(level)s" in role_totals
        assert "worksite_state=%(state)s" in role_totals
        assert " AND worksite_state=%(state)s" not in locations
        assert "role_family=%(role)s" in locations
        assert "role_family=%(role)s" in level_medians
        assert "worksite_state=%(state)s" in level_medians
        assert "level_normalized=%(level)s" not in level_medians
        assert "level_normalized<>'Unknown'" in level_medians
        assert "HAVING count(*)>=5" in level_medians
        assert "GROUP BY level_normalized" in level_medians
        assert "GROUP BY case_type" in case_types
        assert "CASE WHEN count(*)>=5" in monthly
        assert "HAVING count(*)>=5" in rows
        assert matched.count("CASE WHEN count(*)>=5") == 3
        assert "HAVING count(*)>=5" in locations
        assert "worksite_state=%(state)s THEN 0" in locations
        assert "decision_date" not in states
        assert "decision_date" not in totals
        assert "decision_date" not in pub
        return _results()

    monkeypatch.setattr(server, "query_many", fake_query_many)
    response = TestClient(server.app).get(
        "/company/amazon?fetch=false&role=SWE&level=L4&state=CA&period=FY2026"
    )
    assert response.status_code == 200


def test_empty_and_small_matched_cohorts(monkeypatch):
    results = _results()
    results[0] = []
    results[2] = [(0, None, None, None, None, None)]
    results[4:8] = [[], [], [], []]
    monkeypatch.setattr(server, "query_many", lambda statements, parameters: results)
    client = TestClient(server.app)
    payload = client.get("/company/amazon?fetch=false&role=ML").json()
    assert payload["total_filings"] == 20
    assert payload["matchedFilings"] == {
        "count": 0, "p25": None, "p50": None, "p75": None,
        "firstDecision": None, "lastDecision": None,
    }
    assert payload["rows"] == payload["locations"] == []
    assert payload["levelMedians"] == payload["caseTypeTotals"] == []
    assert payload["roleTotals"] == [
        {"role": "SWE", "count": 12}, {"role": "Other", "count": 8}
    ]
    assert payload["monthlyFilings"] == []
    assert payload["stateOptions"] == ["CA", "WA"]

    results[2] = [(4, None, None, None, "2026-05-01", "2026-06-30")]
    small = client.get("/company/amazon?fetch=false&role=ML").json()["matchedFilings"]
    assert small["count"] == 4
    assert small["p25"] is small["p50"] is small["p75"] is None


def test_monthly_wage_median_is_hidden_for_small_month(monkeypatch):
    results = _results()
    results[5] = [("2026-05", 4, None), ("2026-06", 16, 160000)]
    monkeypatch.setattr(server, "query_many", lambda statements, parameters: results)
    payload = TestClient(server.app).get("/company/amazon?fetch=false").json()
    assert payload["monthlyFilings"] == [
        {"month": "2026-05", "count": 4, "p50": None},
        {"month": "2026-06", "count": 16, "p50": 160000},
    ]


def test_filter_validation(monkeypatch):
    monkeypatch.setattr(server, "query_many", lambda *args: (_ for _ in ()).throw(AssertionError()))
    client = TestClient(server.app)
    for parameter in ("role=Engineer", "level=L8", "state=California", "state=ca", "period=2026"):
        assert client.get(f"/company/amazon?fetch=false&{parameter}").status_code == 422


def test_fetch_on_miss_uses_unfiltered_count_and_reuses_filters(monkeypatch):
    calls = []

    def fake_query_many(statements, parameters):
        calls.append(parameters.copy())
        results = _results(count=0 if len(calls) == 1 else 6)
        results[1] = [(0,)] if len(calls) == 1 else [(6,)]
        return results

    def fake_ingest(company):
        assert company == "Amazon"
        return {"company": "Amazon", "ingested": 6}

    monkeypatch.setattr(server, "query_many", fake_query_many)
    monkeypatch.setattr("src.ingestion.on_demand.ingest_company", fake_ingest)
    payload = TestClient(server.app).get("/company/amazon?role=PM&period=FY2025").json()
    assert payload["fetched_on_demand"] == 6
    assert payload["total_filings"] == 6
    assert calls[0] == calls[1]
    assert calls[0]["role"] == "PM"
    assert calls[0]["period"] == "FY2025"
    assert (calls[0]["start"], calls[0]["end"]) == ("2024-10-01", "2025-10-01")


def test_empty_filtered_cohort_does_not_fetch(monkeypatch):
    results = _results()
    results[2] = [(0, None, None, None, None, None)]
    monkeypatch.setattr(server, "query_many", lambda statements, parameters: results)
    monkeypatch.setattr(
        "src.ingestion.on_demand.ingest_company",
        lambda company: (_ for _ in ()).throw(AssertionError("unexpected ingest")),
    )
    assert TestClient(server.app).get("/company/amazon?role=ML").json()["matchedFilings"]["count"] == 0
