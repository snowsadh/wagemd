"""Official workbook downloads must preserve valid cached data on failure."""

from io import BytesIO

import pytest
from openpyxl import Workbook

from src.ingestion import download


def test_download_xlsx_is_validated_and_atomic(monkeypatch, tmp_path):
    workbook = Workbook()
    content = BytesIO()
    workbook.save(content)

    class Response:
        def __init__(self, data, fails=False):
            self.data = data
            self.fails = fails

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def raise_for_status(self):
            if self.fails:
                raise RuntimeError("fetch failed")

        def iter_bytes(self, **_):
            yield self.data

    response = Response(content.getvalue())
    monkeypatch.setattr(download.httpx, "stream", lambda *_args, **_kwargs: response)
    dest = tmp_path / "source.xlsx"
    assert download.download_xlsx("https://example.test/source.xlsx", dest) == dest
    assert dest.read_bytes() == content.getvalue()

    response.fails = True
    assert download.download_xlsx("https://example.test/source.xlsx", dest) == dest
    with pytest.raises(RuntimeError, match="fetch failed"):
        download.download_xlsx("https://example.test/source.xlsx", dest, force=True)
    assert dest.read_bytes() == content.getvalue()
    assert not list(tmp_path.glob("*.part"))
