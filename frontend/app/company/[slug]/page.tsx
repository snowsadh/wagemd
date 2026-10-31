// Server component — fetches the percentile distribution from the FastAPI middleware.
import Link from "next/link";
import CompanyCharts from "@/components/CompanyCharts";
import ChartFilters from "@/components/ChartFilters";
import { getCompany, type CompanyFilters } from "@/lib/api";

export const dynamic = "force-dynamic"; // rendered per-request (depends on the live API)

const fmt = (n: number) => "$" + n.toLocaleString();
const fmtDate = (date: string) =>
  new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC",
  });

type SearchParams = Record<string, string | string[] | undefined>;
const one = (value: string | string[] | undefined) => typeof value === "string" ? value : "";

function selectedFilters(searchParams: SearchParams): CompanyFilters {
  const role = one(searchParams.role);
  const level = one(searchParams.level);
  const state = one(searchParams.state).toUpperCase();
  const period = one(searchParams.period);
  return {
    role: ["SWE", "PM", "Design", "FDE", "ML", "Data", "Other"].includes(role) ? role : "",
    level: ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "Unknown"].includes(level) ? level : "",
    state: /^[A-Z]{2}$/.test(state) ? state : "",
    period: period === "FY2025" || period === "FY2026" ? period : "all",
  };
}

export default async function CompanyPage({ params, searchParams = {} }: { params: { slug: string }; searchParams?: SearchParams }) {
  const filters = selectedFilters(searchParams);
  let data;
  try {
    data = await getCompany(params.slug, filters);
  } catch {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-normal tracking-tight">
          {params.slug.replace(/-/g, " ")}
        </h1>
        <p className="text-neutral-500">Could not reach the API. Is it running on :8000?</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight">{data.company}</h1>
        <p className="text-neutral-600">
          {data.total_filings.toLocaleString()} certified DOL filings in this index (PERM + full-time H-1B LCA).
          {" "}Wage figures use the annualized lower end of employer-reported offers.
        </p>
      </div>

      <ChartFilters key={`${filters.role}-${filters.level}-${filters.state}-${filters.period}`}
        slug={params.slug} states={data.stateOptions} selected={filters} />

      <section aria-label="Selected filing summary" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">Selected evidence</p>
        <div className="mt-3 grid gap-5 sm:grid-cols-3">
          <div><p className="text-sm text-neutral-500">Matching filings</p><p className="text-2xl font-semibold tabular-nums">{data.matchedFilings.count.toLocaleString()}</p></div>
          <div><p className="text-sm text-neutral-500">Median reported wage floor</p><p className="text-2xl font-semibold tabular-nums">{data.matchedFilings.p50 == null ? "—" : fmt(data.matchedFilings.p50)}</p></div>
          <div><p className="text-sm text-neutral-500">Middle half of wage floors</p><p className="text-lg font-semibold tabular-nums">{data.matchedFilings.p25 == null || data.matchedFilings.p75 == null ? "—" : `${fmt(data.matchedFilings.p25)}–${fmt(data.matchedFilings.p75)}`}</p></div>
        </div>
        {data.matchedFilings.firstDecision && data.matchedFilings.lastDecision && (
          <p className="mt-3 text-xs text-neutral-500">DOL decision dates: {fmtDate(data.matchedFilings.firstDecision)}–{fmtDate(data.matchedFilings.lastDecision)}</p>
        )}
        {data.matchedFilings.count > 0 && data.matchedFilings.count < 5 && (
          <p className="mt-3 text-sm text-neutral-600">Fewer than five filings match. Wages are hidden because this sample is too small.</p>
        )}
        {data.matchedFilings.count === 0 && (
          <p className="mt-3 text-sm text-neutral-600">No filings match these filters. Try a broader role, level, state, or period.</p>
        )}
      </section>

      <CompanyCharts
        rows={data.rows}
        roleTotals={data.roleTotals}
        locations={data.locations}
        monthlyFilings={data.monthlyFilings}
        filters={filters}
      />

      <h2 className="text-xl font-normal">Detailed wage data</h2>
      {data.rows.length === 0 ? (
        <p className="text-neutral-500">No role and level group has at least five filings for this selection.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-neutral-300 text-left text-neutral-500">
                <th className="py-2">Role</th>
                <th className="py-2">Level</th>
                <th className="py-2">p25</th>
                <th className="py-2">p50</th>
                <th className="py-2">p75</th>
                <th className="py-2">p90</th>
                <th className="py-2">n</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={i} className="border-b border-neutral-100">
                  <td className="py-2 font-medium">{r.role_family}</td>
                  <td className="py-2">{r.level}</td>
                  <td className="py-2">{fmt(r.p25)}</td>
                  <td className="py-2">{fmt(r.p50)}</td>
                  <td className="py-2">{fmt(r.p75)}</td>
                  <td className="py-2">{fmt(r.p90)}</td>
                  <td className="py-2 text-neutral-500">{r.sample_size}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.briefUrl ? (
        <Link href={data.briefUrl} className="text-sm text-signal underline">
          Read the company brief →
        </Link>
      ) : (
        <p className="text-sm text-neutral-400">No generated brief yet.</p>
      )}
    </div>
  );
}
