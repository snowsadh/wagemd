"use client";

// Keeps company-chart cohorts shareable through the URL.
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { CompanyFilters } from "@/lib/api";
import SelectField from "@/components/ui/SelectField";

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
const ROLE_OPTIONS = [{ value: "all", label: "All roles" }, ...ROLES.map(([value, label]) => ({ value, label, shortLabel: value === "SWE" ? "Software eng." : undefined }))];
const LEVEL_OPTIONS = [{ value: "all", label: "All levels" }, ...LEVELS.map((level) => ({ value: level, label: level }))];
const PERIOD_OPTIONS = [
  { value: "all", label: "All available" },
  { value: "FY2026", label: "FY2026" },
  { value: "FY2025", label: "FY2025" },
];

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
            <SelectField id="chart-role" value={filters.role || "all"}
              onValueChange={(value) => setFilters({ ...filters, role: value === "all" ? "" : value })} options={ROLE_OPTIONS} />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-medium text-neutral-600" htmlFor="chart-level">
            Inferred level
            <SelectField id="chart-level" value={filters.level || "all"}
              onValueChange={(value) => setFilters({ ...filters, level: value === "all" ? "" : value })} options={LEVEL_OPTIONS} />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-medium text-neutral-600" htmlFor="chart-state">
            Worksite state
            <SelectField id="chart-state" value={filters.state || "all"}
              onValueChange={(value) => setFilters({ ...filters, state: value === "all" ? "" : value })}
              options={[
                { value: "all", label: "All states" },
                ...(selected.state && !states.includes(selected.state) ? [{ value: selected.state, label: `${selected.state} (no indexed filings)` }] : []),
                ...states.map((state) => ({ value: state, label: state })),
              ]} />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-medium text-neutral-600" htmlFor="chart-period">
            Decision period
            <SelectField id="chart-period" value={filters.period}
              onValueChange={(value) => setFilters({ ...filters, period: value as CompanyFilters["period"] })} options={PERIOD_OPTIONS} />
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
