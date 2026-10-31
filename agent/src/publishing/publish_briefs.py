"""Batch-generate company briefs in Tiger Data for the WAGE.md Index.

Generates each target company's brief from current DOL+WARN data and stores it in published_pages.
Companies below min_sample are skipped (we
don't publish briefs we can't stand behind).
"""
from __future__ import annotations

import argparse

from ..normalization.companies import TARGET_COMPANIES
from . import brief_generator, local_briefs


def publish_briefs(companies: list[str] | None = None, min_sample: int = 10) -> list[dict]:
    if companies is None:  # default: every company in the corpus with enough filings
        from ..core.tiger_client import query

        companies = [
            r[0] for r in query(
                "SELECT employer_normalized, count(*) c FROM filings WHERE wage_low_usd>0 "
                "GROUP BY employer_normalized HAVING count(*) >= %(m)s ORDER BY c DESC", {"m": min_sample},
            ).result_rows
        ] or TARGET_COMPANIES
    results: list[dict] = []
    for c in companies:
        brief = brief_generator.generate_brief(c)
        if brief["sample_size"] < min_sample:
            results.append({"company": c, "skipped": True, "sample_size": brief["sample_size"]})
            print(f"  skip {c}: only {brief['sample_size']} filings")
            continue
        res = local_briefs.publish_brief(c, brief["markdown"], brief["sample_size"])
        results.append(res)
        print(f"  stored {c}: {res['url']}")
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Store company briefs in Tiger Data")
    p.add_argument("--companies", nargs="*", default=None)
    p.add_argument("--min-sample", type=int, default=10)
    a = p.parse_args()
    out = publish_briefs(a.companies, a.min_sample)
    published = [r for r in out if r.get("url")]
    print(f"\nStored {len(published)}/{len(out)} briefs.")
