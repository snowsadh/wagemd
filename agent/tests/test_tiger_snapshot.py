"""Company chart aggregates must read from one database snapshot."""

from src.core import tiger_client


def test_query_many_uses_one_read_only_repeatable_read_transaction(monkeypatch):
    calls = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, statement, parameters=None):
            calls.append((statement, parameters))

        def fetchall(self):
            return [(len(calls),)]

    class Connection:
        def __enter__(self):
            calls.append(("open", None))
            return self

        def __exit__(self, *_):
            calls.append(("close", None))

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(tiger_client, "transaction", Connection)

    assert tiger_client.query_many(["SELECT 1", "SELECT 2"], {"c": "Amazon"}) == [
        [(3,)], [(4,)]
    ]
    assert calls == [
        ("open", None),
        ("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", None),
        ("SELECT 1", {"c": "Amazon"}),
        ("SELECT 2", {"c": "Amazon"}),
        ("close", None),
    ]
