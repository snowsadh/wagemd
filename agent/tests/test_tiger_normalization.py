"""Keep classification updates atomic when the source rows change mid-run."""

import pytest

from src.normalization import title_normalizer


def test_normalization_aborts_when_not_every_filing_is_updated(monkeypatch):
    class Cursor:
        rowcount = 0
        sql = ""

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def executemany(self, sql, _):
            self.sql = sql

    class Connection:
        rolled_back = False

        def __enter__(self):
            return self

        def __exit__(self, error_type, *_):
            self.rolled_back = error_type is not None

        def cursor(self):
            return cursor

    cursor = Cursor()
    connection = Connection()
    monkeypatch.setattr(title_normalizer, "transaction", lambda: connection)

    with pytest.raises(RuntimeError, match="updated 0 filings != expected 1"):
        title_normalizer._swap_reload([{"case_number": "A"}])

    assert connection.rolled_back
    assert "employer_normalized=%(employer_normalized)s" in cursor.sql
    assert "job_title_raw=%(job_title_raw)s" in cursor.sql
