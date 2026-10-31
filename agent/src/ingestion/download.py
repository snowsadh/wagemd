"""Download official XLSX sources without leaving partial files in the cache."""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import httpx


def download_xlsx(url: str, dest: Path, *, force: bool = False, timeout: float = 600.0) -> Path:
    if dest.exists() and not force:
        if zipfile.is_zipfile(dest):
            return dest
        raise ValueError(f"Cached file is not an XLSX workbook: {dest}; retry with force=True")

    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, suffix=".part", delete=False) as file:
        temporary = Path(file.name)
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as response:
            response.raise_for_status()
            with temporary.open("wb") as file:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    file.write(chunk)
        if not zipfile.is_zipfile(temporary):
            raise ValueError(f"Source did not return an XLSX workbook: {url}")
        temporary.replace(dest)
    finally:
        temporary.unlink(missing_ok=True)
    return dest
