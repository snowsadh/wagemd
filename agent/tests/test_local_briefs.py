"""Keep the Tiger Data brief writer and public API contract aligned."""

from fastapi.testclient import TestClient

from src.api import server
from src.core.tiger_client import QueryResult
from src.publishing import local_briefs


def test_publish_brief_stores_markdown_with_local_url(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params):
            self.sql, self.params = sql, params

        def fetchone(self):
            return (2,)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def cursor(self):
            return cursor

    cursor = Cursor()
    monkeypatch.setattr(local_briefs, "transaction", lambda: Connection())

    result = local_briefs.publish_brief("Acme Inc", "# Brief", 12)

    assert result == {"company": "Acme Inc", "url": "/briefs/Acme%20Inc", "sample_size": 12, "version": 2}
    assert cursor.params["markdown"] == "# Brief"
    assert "ON CONFLICT" in cursor.sql


def test_index_brief_and_company_api_share_local_url(monkeypatch):
    url = "/briefs/Acme%20Inc"

    def fake_query(sql, parameters=None):
        if "SELECT employer_normalized, page_url" in sql:
            assert "markdown<>''" in sql
            rows = [("Acme Inc", url, "2026-10-31", 12)]
        elif "SELECT employer_normalized, markdown" in sql:
            assert "markdown<>''" in sql
            rows = [("Acme Inc", "# Brief", "2026-10-31", 12)] if parameters["c"] == "Acme Inc" else []
        elif "SELECT page_url" in sql:
            rows = [(url, "2026-10-31")]
        else:
            rows = []
        return QueryResult(rows, [])

    monkeypatch.setattr(server, "query", fake_query)
    monkeypatch.setattr(server, "query_many", lambda statements, parameters: [
        [], [(12,)], [(0, None, None, None, None, None)], [], [], [], [], [], [],
        [(url, "2026-10-31")]
    ])
    client = TestClient(server.app)

    assert client.get("/index").json()["pages"][0]["url"] == url
    assert client.get(url).json()["markdown"] == "# Brief"
    assert client.get("/company/acme-inc?fetch=false").json()["briefUrl"] == url
    assert client.get("/briefs/Missing").status_code == 404
