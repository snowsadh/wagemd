# DOL FY2026 Q3 samples

These workbooks contain certified cases from the [US Department of Labor FY2026 Q3 disclosure files](https://www.dol.gov/agencies/eta/foreign-labor/performance). The source reporting period ends June 30, 2026. Original case numbers are retained; contact fields are omitted.

| Sample | LCA cases | PERM cases | Files |
| --- | ---: | ---: | --- |
| Expanded | 24,429 | 1,858 | `lca_fy2026_q3_expanded_sample.xlsx`, `perm_fy2026_q3_expanded_sample.xlsx` |
| Compact | 1,500 | 319 | `lca_fy2026_q3_certified_sample.xlsx`, `perm_fy2026_q3_certified_sample.xlsx` |

The extracts use the project's ten target-employer match rules and keep only `Certified` cases with a case number, title, decision date, and positive offered wage. LCA cases are additionally limited to full-time H-1B positions. The expanded sample keeps every eligible PERM case. For LCA, it keeps every eligible case at Anthropic, OpenAI, Stripe, Databricks, and Netflix, and uses deterministic reservoir sampling (seed `20261031`) with caps of 8,000 Amazon, 4,500 Google, and 3,500 each at Meta, Microsoft, and Apple. The compact sample caps each employer at 150 LCA and 50 PERM cases using the same seed.

These are bounded samples, not the full DOL corpus. Percentiles computed from them describe these selected filings. The DOL fields are employer-reported **offered wages**, not a survey of salaries actually paid to every worker.

The importer excludes annualized offers above $2 million as likely source or unit errors. Six rows in the expanded workbooks meet that condition, leaving 26,281 imported sample cases.

From the `wage-md/` directory, reimport into a configured Tiger Data database with OpenAI title normalization:

```bash
cd agent
uv run python - <<'PY'
from pathlib import Path
from src.ingestion.dol_flag import insert_filings, parse_filtered
from src.normalization.title_normalizer import normalize_rows

samples = Path('..') / 'data-samples'
rows = (
    parse_filtered(samples / 'lca_fy2026_q3_expanded_sample.xlsx', 'LCA')
    + parse_filtered(samples / 'perm_fy2026_q3_expanded_sample.xlsx', 'PERM')
)
rows = normalize_rows(rows)
for offset in range(0, len(rows), 1000):
    print(insert_filings(rows[offset:offset + 1000]))
PY
```

The import is idempotent by DOL case number and case type, and requires an OpenAI key for title normalization.
