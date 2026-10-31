// Lists company briefs stored in Tiger Data (server component).
import Link from "next/link";
import { listPublished } from "@/lib/api";

export const dynamic = "force-dynamic"; // rendered per-request (depends on the live API)

export default async function IndexPage() {
  let pages: Awaited<ReturnType<typeof listPublished>>["pages"] = [];
  try {
    pages = (await listPublished()).pages;
  } catch {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-normal tracking-tight">Salary index</h1>
        <p className="text-neutral-500">Could not reach the API.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-normal tracking-tight">Salary index</h1>
      <p className="text-neutral-600">
        Company salary briefs built from DOL filings and stored in Tiger Data.
      </p>
      {pages.length === 0 ? (
        <p className="text-sm text-neutral-400">No briefs generated yet.</p>
      ) : (
        <ul className="flex flex-col gap-2 text-sm">
          {pages.map((p, i) => (
            <li key={i} className="flex items-center justify-between border-b border-neutral-100 py-2">
              <Link href={p.url} className="font-medium text-signal underline">
                {p.company}
              </Link>
              <span className="text-neutral-400">
                {p.sample_size} filings · {p.last_published?.slice(0, 10)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
