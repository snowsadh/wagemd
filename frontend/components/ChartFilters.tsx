"use client";

// Keeps company-chart cohorts shareable through the URL.
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { CompanyFilters } from "@/lib/api";

const ROLES = [
  ["SWE", "Software engineering"],
  ["ML", "Machine learning"],
  ["Data", "Data"],
  ["PM", "Product management"],
  ["Design", "Design"],
  ["FDE", "Solutions / FDE"],
  ["Other", "Other titles"],
] as const;

const LEVELS = ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "Unknown"] as const;

type Props = {
  slug: string;
  states: string[];
  selected: CompanyFilters;
};

export default function ChartFilters({ slug, states, selected }: Props) {
  const router = useRouter();
  const [filters, setFilters] = useState(selected);
  const [pending, startTransition] = useTransition();
  const hasFilters = Boolean(selected.role || selected.level || selected.state || selected.period !== "all");

  function navigate(next: CompanyFilters) {
    const params = new URLSearchParams();
    if (next.role) params.set("role", next.role);
    if (next.level) params.set("level", next.level);
    if (next.state) params.set("state", next.state);
    if (next.period !== "all") params.set("period", next.period);
    const query = params.toString();
    startTransition(() => router.push(`/company/${encodeURIComponent(slug)}${query ? `?${query}` : ""}`));
  }

  return (
    <section aria-labelledby="chart-filters-title" className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="chart-filters-title" className="text-xl font-normal">Compare your market</h2>
        <span className="text-xs text-neutral-500">Choose the filings closest to your offer</span>
      </div>
      <form onSubmit={(event) => { event.preventDefault(); navigate(filters); }} className="mt-5">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1.5 text-xs font-medium text-neutral-600" htmlFor="chart-role">
            Role
            <select id="chart-role" value={filters.role} onChange={(event) => setFilters({ ...filters, role: event.target.value })}
              className="h-11 w-full rounded-md border border-neutral-300 bg-white px-3 text-sm text-neutral-900">
              <option value="">All roles</option>
              {ROLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-medium text-neutral-600" htmlFor="chart-level">
            Inferred level
            <select id="chart-level" value={filters.level} onChange={(event) => setFilters({ ...filters, level: event.target.value })}
              className="h-11 w-full rounded-md border border-neutral-300 bg-white px-3 text-sm text-neutral-900">
              <option value="">All levels</option>
              {LEVELS.map((level) => <option key={level} value={level}>{level}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-medium text-neutral-600" htmlFor="chart-state">
            Worksite state
            <select id="chart-state" value={filters.state} onChange={(event) => setFilters({ ...filters, state: event.target.value })}
              className="h-11 w-full rounded-md border border-neutral-300 bg-white px-3 text-sm text-neutral-900">
              <option value="">All states</option>
              {selected.state && !states.includes(selected.state) && <option value={selected.state}>{selected.state} (no indexed filings)</option>}
              {states.map((state) => <option key={state} value={state}>{state}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-medium text-neutral-600" htmlFor="chart-period">
            Decision period
            <select id="chart-period" value={filters.period} onChange={(event) => setFilters({ ...filters, period: event.target.value as CompanyFilters["period"] })}
              className="h-11 w-full rounded-md border border-neutral-300 bg-white px-3 text-sm text-neutral-900">
              <option value="all">All available</option>
              <option value="FY2026">FY2026</option>
              <option value="FY2025">FY2025</option>
            </select>
          </label>
        </div>
        <div className="mt-4 flex items-center gap-4">
          <button type="submit" disabled={pending} aria-busy={pending}
            className="inline-flex min-w-32 items-center justify-center gap-2 rounded-md bg-signal px-4 py-2.5 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-70">
            {pending && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden="true" />}
            {pending ? "Updating…" : "Update charts"}
          </button>
          {hasFilters && <button type="button" disabled={pending} onClick={() => navigate({ role: "", level: "", state: "", period: "all" })}
            className="text-sm text-neutral-600 underline hover:text-neutral-900 disabled:opacity-50">Clear filters</button>}
          <span aria-live="polite" className="sr-only">{pending ? "Updating charts" : ""}</span>
        </div>
      </form>
    </section>
  );
}
