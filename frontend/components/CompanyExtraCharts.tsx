// Shows pay movement, level comparisons, and the filing sources behind a selected cohort.
import type { CompanyDistribution, CompanyFilters } from "@/lib/api";

const money = (value: number) => "$" + Math.round(value).toLocaleString();
const shortMoney = (value: number) => `$${Math.round(value / 1_000)}k`;
const count = (value: number) => value.toLocaleString();

export function WageTrend({ months }: { months: CompanyDistribution["monthlyFilings"] }) {
  const values = months.filter((row) => row.p50 !== null).map((row) => row.p50 as number);
  const axisMin = values.length ? Math.max(0, Math.floor(Math.min(...values) / 25_000) * 25_000 - 25_000) : 0;
  const axisMax = values.length ? Math.ceil(Math.max(...values) / 25_000) * 25_000 + 25_000 : 50_000;
  const x = (index: number) => months.length === 1 ? 340 : 60 + index * 560 / (months.length - 1);
  const y = (value: number) => 170 - (value - axisMin) / (axisMax - axisMin) * 120;

  return (
    <section aria-labelledby="wage-trend" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="wage-trend" className="text-xl font-normal">Median wage floor over time</h2>
      <p className="mt-1 text-sm text-neutral-500">Monthly medians in the selected cohort · gaps mark months with fewer than five filings</p>
      {values.length === 0 ? (
        <p className="mt-5 text-sm text-neutral-500">No month has enough filings to show a wage trend. Broaden your filters.</p>
      ) : (
        <div className="mt-4 overflow-x-auto pb-2">
          <svg viewBox="0 0 640 215" className="min-w-[640px] w-full" role="img" aria-label="Monthly median reported wage floors">
            {[50, 110, 170].map((tick, index) => (
              <g key={tick}>
                <line x1="60" x2="620" y1={tick} y2={tick} stroke="#ddc0d4" strokeWidth="1" />
                <text x="48" y={tick + 4} textAnchor="end" fill="#6d5268" fontSize="11">
                  {shortMoney(axisMax - index * (axisMax - axisMin) / 2)}
                </text>
              </g>
            ))}
            {months.slice(1).map((row, index) => {
              const previous = months[index];
              return row.p50 !== null && previous.p50 !== null ? (
                <line key={row.month} x1={x(index)} y1={y(previous.p50)} x2={x(index + 1)} y2={y(row.p50)} stroke="#a21e5c" strokeWidth="2.5" />
              ) : null;
            })}
            {months.map((row, index) => (
              <g key={row.month}>
                {row.p50 !== null && (
                  <>
                    <circle cx={x(index)} cy={y(row.p50)} r="5" fill="#a21e5c" stroke="#faf7fa" strokeWidth="2" />
                    <text x={x(index)} y={y(row.p50) - 12} textAnchor="middle" fill="#572747" fontSize="11">{shortMoney(row.p50)}</text>
                  </>
                )}
                <text x={x(index)} y="200" textAnchor="middle" fill="#6d5268" fontSize="11">{row.month.slice(2)}</text>
              </g>
            ))}
          </svg>
          <ol className="sr-only">
            {months.map((row) => <li key={row.month}>{row.month}: {count(row.count)} filings; median wage floor {row.p50 === null ? "not shown" : money(row.p50)}</li>)}
          </ol>
          {months.length > 5 && <p className="mt-1 text-right text-xs text-neutral-500 sm:hidden">Scroll to see more months →</p>}
        </div>
      )}
    </section>
  );
}

export function LevelMedians({ levels, filters }: { levels: CompanyDistribution["levelMedians"]; filters: CompanyFilters }) {
  const scale = Math.max(50_000, Math.ceil(Math.max(0, ...levels.map((row) => row.median)) / 50_000) * 50_000);

  return (
    <section aria-labelledby="level-medians" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="level-medians" className="text-xl font-normal">Pay by inferred level</h2>
      <p className="mt-1 text-sm text-neutral-500">Compare known levels for the chosen role, state, and period · at least five filings per level</p>
      {!filters.role && <p className="mt-2 text-xs text-neutral-600">Choose a role to compare levels within one job family.</p>}
      {levels.length === 0 ? (
        <p className="mt-5 text-sm text-neutral-500">No known level has five filings for this comparison.</p>
      ) : (
        <>
          <div className="mt-5 flex justify-between text-xs tabular-nums text-neutral-500" aria-hidden="true"><span>$0</span><span>{money(scale)}</span></div>
          <ol className="mt-2 space-y-4">
            {levels.map((row) => (
              <li key={row.level}>
                <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium">{row.level} <span className="font-normal text-neutral-500">· n = {count(row.count)}</span></span>
                  <span className="tabular-nums">{money(row.median)}</span>
                </div>
                <div className="relative h-3" aria-hidden="true">
                  <div className="absolute top-1.5 h-px w-full bg-neutral-200" />
                  <div className={`absolute top-0 h-3 w-3 -translate-x-1/2 rounded-full ${filters.level && row.level !== filters.level ? "bg-neutral-300" : "bg-signal"}`}
                    style={{ left: `${row.median / scale * 100}%` }} />
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

export function CaseTypeMix({ caseTypes }: { caseTypes: CompanyDistribution["caseTypeTotals"] }) {
  const total = caseTypes.reduce((sum, row) => sum + row.count, 0);
  const lca = caseTypes.find((row) => row.caseType === "LCA")?.count ?? 0;
  const perm = caseTypes.find((row) => row.caseType === "PERM")?.count ?? 0;

  return (
    <section aria-labelledby="case-type-mix" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="case-type-mix" className="text-xl font-normal">Filing source mix</h2>
      <p className="mt-1 text-sm text-neutral-500">How much of this cohort comes from H-1B LCAs versus PERM certifications</p>
      {total === 0 ? (
        <p className="mt-5 text-sm text-neutral-500">No filings match this selection.</p>
      ) : (
        <>
          <div className="mt-6 flex h-5 overflow-hidden rounded-full bg-neutral-100" role="img" aria-label={`${count(lca)} LCA filings and ${count(perm)} PERM filings`}>
            <div className="bg-signal" style={{ width: `${lca / total * 100}%` }} />
            <div className="bg-neutral-400" style={{ width: `${perm / total * 100}%` }} />
          </div>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            <div><dt className="flex items-center gap-2 text-sm text-neutral-600"><span className="h-2.5 w-2.5 rounded-sm bg-signal" />H-1B LCA</dt><dd className="mt-1 text-lg font-semibold tabular-nums">{count(lca)} <span className="text-sm font-normal text-neutral-500">({(lca / total * 100).toFixed(1)}%)</span></dd></div>
            <div><dt className="flex items-center gap-2 text-sm text-neutral-600"><span className="h-2.5 w-2.5 rounded-sm bg-neutral-400" />PERM</dt><dd className="mt-1 text-lg font-semibold tabular-nums">{count(perm)} <span className="text-sm font-normal text-neutral-500">({(perm / total * 100).toFixed(1)}%)</span></dd></div>
          </dl>
          <p className="mt-5 text-xs text-neutral-500">Filings are government case records, not a count of unique employees.</p>
        </>
      )}
    </section>
  );
}
