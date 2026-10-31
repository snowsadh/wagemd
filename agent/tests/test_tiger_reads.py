"""Read queries stay outside a transaction while write paths remain transactional."""

from types import SimpleNamespace

from src.core import tiger_client


def test_query_uses_autocommit(monkeypatch):
    class Cursor:
        description = (SimpleNamespace(name="value"),)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params):
            assert sql == "SELECT 1"
            assert params is None
            assert connection.autocommit

        def fetchall(self):
            return [(1,)]

    class Connection:
        autocommit = False

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def cursor(self):
            return Cursor()

    connection = Connection()
    monkeypatch.setattr(tiger_client, "transaction", lambda: connection)

    result = tiger_client.query("SELECT 1")

    assert result.result_rows == [(1,)]
    assert result.column_names == ["value"]
