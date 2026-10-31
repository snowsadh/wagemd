// Server component — fetches the percentile distribution from the FastAPI middleware.
import Link from "next/link";
import CompanyCharts from "@/components/CompanyCharts";
import { getCompany } from "@/lib/api";

export const dynamic = "force-dynamic"; // rendered per-request (depends on the live API)

const fmt = (n: number) => "$" + n.toLocaleString();
const fmtMonth = (month: string) =>
  new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short", year: "numeric", timeZone: "UTC",
  });

export default async function CompanyPage({ params }: { params: { slug: string } }) {
  let data;
  try {
    data = await getCompany(params.slug);
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
          {data.total_filings.toLocaleString()} selected certified DOL filings (PERM + full-time H-1B LCA).
          {data.monthlyFilings.length > 0 && ` Decisions: ${fmtMonth(data.monthlyFilings[0].month)}–${fmtMonth(data.monthlyFilings[data.monthlyFilings.length - 1].month)}.`}
          {" "}Wage charts use the annualized lower end of employer-reported offers; percentiles are computed in Tiger Data.
        </p>
      </div>

      <CompanyCharts
        rows={data.rows}
        roleTotals={data.roleTotals}
        locations={data.locations}
        monthlyFilings={data.monthlyFilings}
      />

      <h2 className="text-xl font-normal">Detailed wage data</h2>
      {data.rows.length === 0 ? (
        <p className="text-neutral-500">No salary rows yet for this company.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-neutral-300 text-left text-neutral-500">
                <th className="py-2">Role</th>
                <th className="py-2">Level</th>
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
