"""Keep the company chart payload tied to the existing company API."""

from fastapi.testclient import TestClient

from src.api import server


def test_company_chart_payload(monkeypatch):
    def fake_query_many(statements, parameters=None):
        assert parameters == {"c": "Amazon"}
        assert len(statements) == 6
        return [
            [("SWE", "L4", 12, 150000, 180000, 210000)],
            [(20,)],
            [("SWE", 12), ("Other", 8)],
            [("CA", 14, 170000), ("WA", 6, 150000)],
            [("2026-05", 8), ("2026-06", 12)],
            [("/briefs/Amazon", "2026-10-31")],
        ]

    monkeypatch.setattr(server, "query_many", fake_query_many)
    payload = TestClient(server.app).get("/company/amazon?fetch=false").json()

    assert payload["total_filings"] == 20
    assert payload["rows"][0]["p50"] == 150000
    assert payload["roleTotals"] == [
        {"role": "SWE", "count": 12}, {"role": "Other", "count": 8}
    ]
    assert payload["locations"] == [
        {"state": "CA", "count": 14, "median": 170000},
        {"state": "WA", "count": 6, "median": 150000},
    ]
    assert payload["monthlyFilings"] == [
        {"month": "2026-05", "count": 8}, {"month": "2026-06", "count": 12}
    ]
    assert payload["briefUrl"] == "/briefs/Amazon"
