// Shows filing and wage comparisons from a company distribution response.
import type { CompanyDistribution, CompanyFilters } from "@/lib/api";

type CompanyChartsProps = Pick<
  CompanyDistribution,
  "rows" | "roleTotals" | "locations" | "monthlyFilings"
> & { filters: CompanyFilters };

const money = (value: number) => "$" + Math.round(value).toLocaleString();
const count = (value: number) => value.toLocaleString();
const roleLabel: Record<string, string> = {
  SWE: "Software engineering", ML: "Machine learning", Data: "Data",
  PM: "Product management", Design: "Design", FDE: "Solutions / FDE", Other: "Other titles",
};

function WageRanges({ rows, filters }: Pick<CompanyChartsProps, "rows" | "filters">) {
  const topRows = [...rows].sort((a, b) => {
    if (!filters.level && a.level !== b.level && (a.level === "Unknown" || b.level === "Unknown")) {
      return a.level === "Unknown" ? 1 : -1;
    }
    if (!filters.role && a.role_family !== b.role_family && (a.role_family === "Other" || b.role_family === "Other")) {
      return a.role_family === "Other" ? 1 : -1;
    }
    return b.sample_size - a.sample_size;
  }).slice(0, 6);
  const axisMin = topRows.length ? Math.floor(Math.min(...topRows.map((row) => row.p25)) / 25_000) * 25_000 : 0;
  const axisMax = topRows.length ? Math.max(axisMin + 25_000, Math.ceil(Math.max(...topRows.map((row) => row.p75)) / 25_000) * 25_000) : 25_000;
  const position = (value: number) => ((value - axisMin) / (axisMax - axisMin)) * 100;

  return (
    <section aria-labelledby="wage-ranges" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="wage-ranges" className="text-xl font-normal">Reported wage floors</h2>
      <p className="mt-1 text-sm text-neutral-500">Middle half of reported wage floors (p25–p75) · dark mark is the median</p>
      {topRows.length === 0 ? (
        <p className="mt-5 text-sm text-neutral-500">No role and level group has five filings here. Broaden your filters.</p>
      ) : (
        <>
          <div className="mt-5 flex justify-between text-xs tabular-nums text-neutral-500" aria-hidden="true">
            <span>{money(axisMin)}</span><span>{money(Math.round((axisMin + axisMax) / 2 / 5_000) * 5_000)}</span><span>{money(axisMax)}</span>
          </div>
          <ol className="mt-2 space-y-5">
            {topRows.map((row) => (
              <li key={`${row.role_family}-${row.level}`}>
                <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
                  <span className="font-medium">{roleLabel[row.role_family] ?? row.role_family} · {row.level}</span>
                  <span className="text-xs tabular-nums text-neutral-500">n = {count(row.sample_size)}</span>
                </div>
                <div className="relative h-3 rounded-sm bg-neutral-100" aria-hidden="true">
                  <div className="absolute left-1/2 top-0 h-full w-px bg-neutral-200" />
                  <div
                    className="absolute top-0 h-full min-w-1 rounded-sm bg-signal"
                    style={{ left: `${position(row.p25)}%`, width: `${position(row.p75) - position(row.p25)}%` }}
                  />
                  <div className="absolute -top-1 h-5 w-0.5 bg-neutral-900" style={{ left: `${position(row.p50)}%` }} />
                </div>
                <p className="mt-1 text-xs tabular-nums text-neutral-600">
                  p25 {money(row.p25)} · median {money(row.p50)} · p75 {money(row.p75)}
                </p>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function RoleTotals({ roleTotals, filters }: Pick<CompanyChartsProps, "roleTotals" | "filters">) {
  const scale = Math.max(1, ...roleTotals.map((row) => row.count));
  const total = roleTotals.reduce((sum, row) => sum + row.count, 0);

  return (
    <section aria-labelledby="role-totals" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="role-totals" className="text-xl font-normal">Filings by role</h2>
      <p className="mt-1 text-sm text-neutral-500">Role mix at the chosen level, state, and period · selected role highlighted</p>
      {roleTotals.length === 0 ? (
        <p className="mt-5 text-sm text-neutral-500">No role totals available.</p>
      ) : (
        <>
          <div className="mt-5 flex justify-between text-xs tabular-nums text-neutral-500" aria-hidden="true">
            <span>0</span><span>{count(scale)} filings</span>
          </div>
          <ol className="mt-2 space-y-4">
            {roleTotals.map((row) => (
              <li key={row.role}>
                <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium">{roleLabel[row.role] ?? row.role}</span>
                  <span className="shrink-0 tabular-nums">{count(row.count)} <span className="text-neutral-500">({Math.round((row.count / total) * 100)}%)</span></span>
                </div>
                <div className="h-2.5 rounded-full bg-neutral-100" aria-hidden="true">
                  <div className={`h-full rounded-full ${filters.role && row.role !== filters.role ? "bg-neutral-300" : "bg-signal"}`} style={{ width: `${(row.count / scale) * 100}%` }} />
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function StateMedians({ locations, filters }: Pick<CompanyChartsProps, "locations" | "filters">) {
  const scale = Math.max(50_000, Math.ceil(Math.max(...locations.map((row) => row.median), 0) / 50_000) * 50_000);

  return (
    <section aria-labelledby="state-medians" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="state-medians" className="text-xl font-normal">Median wage floor by state</h2>
      <p className="mt-1 text-sm text-neutral-500">Compare states for the chosen role, level, and period · at least five filings per state</p>
      {(!filters.role || !filters.level) && <p className="mt-2 text-xs text-neutral-600">Choose a role and level for a like-for-like state comparison.</p>}
      {locations.length === 0 ? (
        <p className="mt-5 text-sm text-neutral-500">No state medians available.</p>
      ) : (
        <>
          <div className="mt-5 flex justify-between text-xs tabular-nums text-neutral-500" aria-hidden="true">
            <span>$0</span><span>{money(scale)}</span>
          </div>
          <ol className="mt-2 space-y-4">
            {locations.map((row) => (
              <li key={row.state}>
                <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
                  <span className="font-medium">{row.state} <span className="font-normal text-neutral-500">· n = {count(row.count)}</span></span>
                  <span className="tabular-nums">{money(row.median)}</span>
                </div>
                <div className="h-2.5 rounded-full bg-neutral-100" aria-hidden="true">
                  <div className={`h-full rounded-full ${filters.state && row.state !== filters.state ? "bg-neutral-300" : "bg-signal"}`} style={{ width: `${(row.median / scale) * 100}%` }} />
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function MonthlyFilings({ monthlyFilings }: Pick<CompanyChartsProps, "monthlyFilings">) {
  const latestMonths: CompanyDistribution["monthlyFilings"] = [];
  if (monthlyFilings.length) {
    const byMonth = new Map(monthlyFilings.map((row) => [row.month, row.count]));
    const first = monthlyFilings[0].month;
    const cursor = new Date(`${monthlyFilings[monthlyFilings.length - 1].month}-01T00:00:00Z`);
    for (let i = 0; i < 12 && cursor.toISOString().slice(0, 7) >= first; i++) {
      const month = cursor.toISOString().slice(0, 7);
      latestMonths.unshift({ month, count: byMonth.get(month) ?? 0 });
      cursor.setUTCMonth(cursor.getUTCMonth() - 1);
    }
  }
  const scale = Math.max(1, ...latestMonths.map((row) => row.count));

  return (
    <section aria-labelledby="monthly-filings" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="monthly-filings" className="text-xl font-normal">Decisions over time</h2>
      <p className="mt-1 text-sm text-neutral-500">Up to 12 recent months in the selected cohort · cases by DOL decision date</p>
      {latestMonths.length === 0 ? (
        <p className="mt-5 text-sm text-neutral-500">No monthly filing counts available.</p>
      ) : (
        <div className="mt-5 overflow-x-auto pb-2">
          <div className="flex min-w-max gap-3">
            <div className="relative h-36 w-10 shrink-0 text-right text-xs tabular-nums text-neutral-500" aria-hidden="true">
              <span className="absolute right-0 top-7">{count(scale)}</span>
              <span className="absolute bottom-0 right-0 translate-y-1/2">0</span>
            </div>
            <ol className="flex flex-1 gap-2 border-b border-neutral-300">
              {latestMonths.map((row) => (
                <li key={row.month} className="min-w-[3rem] flex-1 text-center">
                  <div className="relative h-36 border-b border-neutral-300" aria-hidden="true">
                    <div className="absolute bottom-0 left-1/2 w-8 -translate-x-1/2 bg-signal sm:w-10" style={{ height: `${(row.count / scale) * 80}%` }} />
                    {row.count > 0 && <span className="absolute left-0 w-full text-xs tabular-nums text-neutral-700" style={{ bottom: `${(row.count / scale) * 80 + 2}%` }}>
                      {count(row.count)}
                    </span>}
                  </div>
                  <span className="mt-2 block text-xs text-neutral-600">{row.month}</span>
                  <span className="sr-only">: {count(row.count)} filings</span>
                </li>
              ))}
            </ol>
          </div>
          {latestMonths.length > 5 && <p className="mt-2 text-right text-xs text-neutral-500 sm:hidden">Scroll to see more months →</p>}
        </div>
      )}
    </section>
  );
}

export default function CompanyCharts(props: CompanyChartsProps) {
  return (
    <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2"><WageRanges rows={props.rows} filters={props.filters} /></div>
      <RoleTotals roleTotals={props.roleTotals} filters={props.filters} />
      <StateMedians locations={props.locations} filters={props.filters} />
      <div className="sm:col-span-2"><MonthlyFilings monthlyFilings={props.monthlyFilings} /></div>
    </div>
  );
}
