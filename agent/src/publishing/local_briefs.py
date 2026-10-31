"""Store generated company briefs in Tiger Data for the local Index."""
from __future__ import annotations

from urllib.parse import quote

from ..core.tiger_client import transaction


def publish_brief(company: str, markdown: str, sample_size: int) -> dict:
    if not company.strip() or not markdown.strip() or sample_size <= 0:
        raise ValueError("A company, nonempty brief, and positive sample size are required")
    url = f"/briefs/{quote(company, safe='')}"
    with transaction() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO published_pages "
            "(employer_normalized, page_url, last_published, sample_size, version, markdown) "
            "VALUES (%(company)s, %(url)s, now(), %(sample_size)s, 1, %(markdown)s) "
            "ON CONFLICT (employer_normalized) DO UPDATE SET "
            "page_url=EXCLUDED.page_url, last_published=EXCLUDED.last_published, "
            "sample_size=EXCLUDED.sample_size, version=published_pages.version+1, "
            "markdown=EXCLUDED.markdown "
            "RETURNING version",
            {"company": company, "url": url, "sample_size": sample_size, "markdown": markdown},
        )
        version = cur.fetchone()[0]
    return {"company": company, "url": url, "sample_size": sample_size, "version": version}
