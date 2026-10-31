"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

// Routes a typed company name to /company/[slug]. Slugify is intentionally simple.
export default function SearchBar() {
  const router = useRouter();
  const [q, setQ] = useState("");

  function go(e: React.FormEvent) {
    e.preventDefault();
    const slug = q.trim().toLowerCase().replace(/\s+/g, "-");
    if (slug) router.push(`/company/${slug}`);
  }

  return (
    <form onSubmit={go} className="flex w-full max-w-2xl flex-col gap-2 sm:flex-row">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search any of 50 companies — e.g. Anthropic"
        className="w-full rounded-md border border-neutral-300 px-4 py-3 text-base outline-none focus:border-neutral-900"
      />
      <button
        type="submit"
        className="rounded-md bg-signal px-5 py-3 text-base font-medium text-white hover:bg-neutral-700"
      >
        Search
      </button>
    </form>
  );
}
