# Company Level Taxonomy — Methodology and Notes

## What this is
A hand-curated mapping from each company's internal level strings (as they appear in DOL PERM/LCA filings or company career pages) to WAGE.md's canonical L1–L7 scale.

## Files in this folder
- `company_levels.csv` — direct ClickHouse import format matching the SPEC schema
- `company_levels.json` — structured version with metadata, rationale, and confidence ratings per company
- `LEVELS_NOTES.md` — this file

## How to load into ClickHouse

```bash
clickhouse-client --query "INSERT INTO company_levels FORMAT CSVWithNames" < company_levels.csv
```

Or via the Python ingestion script Claude Code builds, using clickhouse_driver or clickhouse-connect.

## The WAGE canonical level scale

This is intentionally NOT Google's scale. WAGE canonical is what the negotiation reports and percentile lookups use.

| Canonical | Meaning | YOE range | Maps roughly to |
|-----------|---------|-----------|----------------|
| L1 | Junior / new grad | 0-1 | — (rarely used; most "new grad" rows are L2) |
| L2 | Entry IC | 1-2 | Google L3, Meta E3, Amazon SDE I |
| L3 | Mid IC | 2-5 | Google L4, Meta E4, Amazon SDE II |
| L4 | Senior IC | 5-8 | Google L5, Meta E5, Stripe L3, Amazon Senior SDE |
| L5 | Staff IC | 8-12 | Google L6, Meta E6, Stripe L4, Amazon Principal (debatable) |
| L6 | Senior Staff | 10+ | Google L7, Meta E7, Stripe L5 |
| L7 | Principal / Director+ | 12+ | Google L8+, Meta E8+, anything higher capped here |

## Confidence ratings per company

| Company | Confidence | Why |
|---------|-----------|-----|
| Google | Very High | Widely documented, public ladders |
| Meta | Very High | Widely documented, public ladders |
| Amazon | Very High | Standard reference |
| Apple | High | ICT system documented, but Apple opaque about ICT5/6 distinction |
| Microsoft | High | Numeric levels well-known, but "Principal" interpretation varies |
| Stripe | High | Public career ladder posts very detailed |
| Databricks | High | levels.fyi data robust |
| Netflix | High | Levels introduced 2022, well-documented |
| OpenAI | Medium-High | Multiple recruiter quotes confirm FAANG-minus-1 mapping |
| Anthropic | **Medium** | No public docs, extrapolated from compensation trackers |

## Critical gotchas to handle in code

### 1. "Member of Technical Staff" appears at multiple levels
Both Anthropic and OpenAI use this title for *everyone*. When a DOL filing shows just "Member of Technical Staff" with no other level info, the normalization agent must make a best guess. I've defaulted to canonical L5 (Staff-equivalent) for both, but Claude Code should also feed wage data into the decision — if salary is sub-$250K it's probably an earlier level; if $600K+ it's L6+.

### 2. Microsoft "Principal" ≠ FAANG Principal
At Microsoft, "Principal Software Engineer" (level 65) is Staff-equivalent, NOT Senior Staff. This is a frequent normalization error. The mapping table reflects this but Claude Code's title normalization prompt needs to know it explicitly.

### 3. Stripe titles are flat
L1, L2, L3 ALL externally titled "Software Engineer". L4 and L5 externally titled "Staff Software Engineer". When a DOL filing shows Stripe + "Software Engineer", the wage band is the only signal for true level.

### 4. Meta titles are even flatter
Meta titles all E-levels as "Software Engineer". The wage range is the only differentiator.

### 5. Netflix pre-2022 data
All pre-2022 filings will show "Senior Software Engineer" regardless of true internal level (because Netflix had only one level publicly). If you ingest historical DOL data going back 4+ years, expect Netflix data to be noisy.

### 6. Amazon L7 Principal is HIGH
Don't blindly map Amazon Principal SDE to FAANG Staff. Amazon L7 has scope closer to Google L7 / Senior Staff (= WAGE L6), not Google L6 Staff (= WAGE L5). I've reflected this in the mapping.

### 7. PM and Design ladders typically skip junior levels
At most companies, PM ladders start at L4/E4 (Google PM L4 = Associate PM). There's no PM L3 at Google. Don't expect PM/Design rows for L1-L2.

## What's NOT in this table

- **Forward Deployed Engineer at Palantir** — not in our top 10. Worth adding separately if FDE is a key demo angle.
- **ML Research vs Engineering split at OpenAI/Anthropic** — research scientists often have different comp bands. Currently treated as same ladder. Could split into ML role family later.
- **Manager ladder** — only IC ladder included. M-level rows (M3, M4, D1) intentionally excluded since WAGE is IC-focused.
- **International levels** — US-based DOL filings, US-based ladders only. Don't apply this taxonomy to India/Ireland/UK filings without adjustment.

## Next steps for the Investigator agent

When the Investigator detects a salary distribution shift at a company, it should:
1. Check `company_levels` table for that company's mapping
2. Use the `canonical_level` field to compare against peer companies at the same canonical level
3. NOT compare Google L5 vs Stripe L5 directly (those are different things) — compare Google L5 (canonical L4) vs Stripe L3 (canonical L4)
4. If canonical_level is missing for a filing, flag for human review (anomaly with reason "unknown_level")

## Verification recommendation

Before recording the demo video, manually spot-check 3 specific assertions:
1. Pick a real DOL case number for Anthropic. Verify it has a salary that's plausibly in the T-level range you mapped.
2. Pick a real Google DOL case showing "Senior Software Engineer". Verify wage range matches expected L4 (canonical) band — likely $200-300K.
3. Pick a Stripe DOL case showing "Software Engineer". Verify wage range — if it's $250K+ it's likely Stripe L3 (canonical L4).

If any of these fail, the underlying assumption is broken and the demo needs adjustment.
