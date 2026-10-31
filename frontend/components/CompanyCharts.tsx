// Shows filing and wage comparisons from a company distribution response.
import type { CompanyDistribution } from "@/lib/api";

type CompanyChartsProps = Pick<
  CompanyDistribution,
  "rows" | "roleTotals" | "locations" | "monthlyFilings"
>;

const money = (value: number) => "$" + Math.round(value).toLocaleString();
const count = (value: number) => value.toLocaleString();

function WageRanges({ rows }: Pick<CompanyChartsProps, "rows">) {
  const topRows = [...rows].sort((a, b) => b.sample_size - a.sample_size).slice(0, 6);
  const scale = Math.max(50_000, Math.ceil(Math.max(...topRows.map((row) => row.p90), 0) / 50_000) * 50_000);

  return (
    <section aria-labelledby="wage-ranges" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="wage-ranges" className="text-xl font-normal">Wage range by role and level</h2>
      <p className="mt-1 text-sm text-neutral-500">Six largest samples · p50 to p90, with p75 marked</p>
      {topRows.length === 0 ? (
        <p className="mt-5 text-sm text-neutral-500">No wage ranges available.</p>
      ) : (
        <>
          <div className="mt-5 flex justify-between text-xs tabular-nums text-neutral-500" aria-hidden="true">
            <span>$0</span><span>{money(scale)}</span>
          </div>
          <ol className="mt-2 space-y-5">
            {topRows.map((row, index) => (
              <li key={`${row.role_family}-${row.level}-${index}`}>
                <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
                  <span className="font-medium">{row.role_family} · {row.level}</span>
                  <span className="text-xs tabular-nums text-neutral-500">n = {count(row.sample_size)}</span>
                </div>
                <div className="relative h-3 rounded-full bg-neutral-100" aria-hidden="true">
                  <div
                    className="absolute top-0 h-full rounded-full bg-signal"
                    style={{ left: `${(row.p50 / scale) * 100}%`, width: `${((row.p90 - row.p50) / scale) * 100}%` }}
                  />
                  <div className="absolute -top-1 h-5 w-0.5 bg-neutral-900" style={{ left: `${(row.p75 / scale) * 100}%` }} />
                </div>
                <p className="mt-1 text-xs tabular-nums text-neutral-600">
                  p50 {money(row.p50)} · p75 {money(row.p75)} · p90 {money(row.p90)}
                </p>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function RoleTotals({ roleTotals }: Pick<CompanyChartsProps, "roleTotals">) {
  const scale = Math.max(1, ...roleTotals.map((row) => row.count));

  return (
    <section aria-labelledby="role-totals" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="role-totals" className="text-xl font-normal">Filings by role</h2>
      <p className="mt-1 text-sm text-neutral-500">Number of DOL filings</p>
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
                  <span className="font-medium">{row.role}</span>
                  <span className="shrink-0 tabular-nums">{count(row.count)}</span>
                </div>
                <div className="h-2.5 rounded-full bg-neutral-100" aria-hidden="true">
                  <div className="h-full rounded-full bg-signal" style={{ width: `${(row.count / scale) * 100}%` }} />
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function StateMedians({ locations }: Pick<CompanyChartsProps, "locations">) {
  const scale = Math.max(50_000, Math.ceil(Math.max(...locations.map((row) => row.median), 0) / 50_000) * 50_000);

  return (
    <section aria-labelledby="state-medians" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="state-medians" className="text-xl font-normal">Median wage by state</h2>
      <p className="mt-1 text-sm text-neutral-500">Top states by filing count · at least five filings per state</p>
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
                  <div className="h-full rounded-full bg-neutral-700" style={{ width: `${(row.median / scale) * 100}%` }} />
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
  const latestMonths = monthlyFilings.slice(-12);
  const scale = Math.max(1, ...latestMonths.map((row) => row.count));

  return (
    <section aria-labelledby="monthly-filings" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <h2 id="monthly-filings" className="text-xl font-normal">Decisions over time</h2>
      <p className="mt-1 text-sm text-neutral-500">Most recent 12 months · cases by DOL decision date</p>
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
                    <span className="absolute left-0 w-full text-xs tabular-nums text-neutral-700" style={{ bottom: `${(row.count / scale) * 80 + 2}%` }}>
                      {count(row.count)}
                    </span>
                  </div>
                  <span className="mt-2 block text-xs text-neutral-600">{row.month}</span>
                  <span className="sr-only">: {count(row.count)} filings</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </section>
  );
}

export default function CompanyCharts(props: CompanyChartsProps) {
  return (
    <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2"><WageRanges rows={props.rows} /></div>
      <RoleTotals roleTotals={props.roleTotals} />
      <StateMedians locations={props.locations} />
      <div className="sm:col-span-2"><MonthlyFilings monthlyFilings={props.monthlyFilings} /></div>
    </div>
  );
}
