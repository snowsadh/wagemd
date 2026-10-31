"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

// Routes a typed company name to /company/[slug]. Slugify is intentionally simple.
export default function SearchBar() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [pending, startTransition] = useTransition();

  function go(e: React.FormEvent) {
    e.preventDefault();
    const slug = q.trim().toLowerCase().replace(/\s+/g, "-");
    if (slug && !pending) startTransition(() => router.push(`/company/${slug}`));
  }

  return (
    <form onSubmit={go} className="flex w-full max-w-2xl flex-col gap-2 sm:flex-row">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search a company — e.g. Amazon"
        className="w-full rounded-md border border-neutral-300 px-4 py-3 text-base outline-none focus:border-neutral-900"
      />
      <button
        type="submit"
        disabled={pending}
        aria-busy={pending}
        className="inline-flex min-w-32 items-center justify-center gap-2 rounded-md bg-signal px-5 py-3 text-base font-medium text-white hover:bg-neutral-700 disabled:opacity-70"
      >
        {pending && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden="true" />}
        <span aria-live="polite">{pending ? "Searching…" : "Search"}</span>
      </button>
    </form>
  );
}
