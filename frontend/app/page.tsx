import Link from "next/link";
import SearchBar from "@/components/SearchBar";
import { getCompanies, getHealth, listPublished } from "@/lib/api";

export const dynamic = "force-dynamic"; // live stats at request time

const AGENTS = [
  {
    name: "Scout",
    tagline: "keeps the corpus fresh",
    body: "Decides which official source to poll next — DOL FLAG or state WARN reports — weighing staleness against how likely new data is, then validates and commits it and flags anomalies.",
  },
  {
    name: "Investigator",
    tagline: "decides what to republish",
    body: "When an anomaly appears (a mass layoff, a wage shift), it verifies the event against the data, decides if it's real and material, and only then updates the company's brief in the Index.",
  },
  {
    name: "Counselor",
    tagline: "builds your case",
    body: "Given your offer, it gathers DOL evidence — broadening on thin samples, pulling peers, checking layoffs — until confident, then writes a negotiation report where every number cites a federal case.",
  },
];

const PIPELINE = [
  ["Official sources", "provide DOL filings and California WARN reports"],
  ["Tiger Data", "stores filings and briefs, and computes wage percentiles"],
  ["OpenAI", "normalizes titles, generates briefs, and drives the 3 agents"],
];

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="font-display text-3xl font-normal tracking-tight">{value}</span>
      <span className="text-sm text-neutral-500">{label}</span>
    </div>
  );
}

export default async function Home() {
  let filings = "—";
  let companies = "—";
  let published = "—";
  let statsUnavailable = false;
  try {
    const [h, c, p] = await Promise.all([getHealth(), getCompanies(), listPublished()]);
    filings = h.filings.toLocaleString();
    companies = String(c.companies.length);
    published = String(p.pages.length);
  } catch {
    statsUnavailable = true;
  }

  return (
    <div className="flex flex-col gap-20">
      {/* 1 — Hero */}
      <section className="flex flex-col items-center gap-6 text-center">
        <h1 className="text-4xl font-normal leading-tight tracking-tight sm:text-5xl">
          The government already knows what tech pays.
          <br />
          <span className="text-neutral-500">WAGE.md makes it agent-discoverable.</span>
        </h1>
        <p className="max-w-2xl text-lg text-neutral-600">
          Employers sponsoring an H-1B or green card report offered wages
          by job title to the US Department of Labor. WAGE.md ingests those disclosures, normalizes
          them, and lets three autonomous agents investigate and maintain a cited salary index.
        </p>
        <SearchBar />
        <div className="mt-2 flex flex-wrap justify-center gap-10">
          <Stat value={filings} label="DOL filings ingested" />
          <Stat value={companies} label="companies covered" />
          <Stat value={published} label="company briefs" />
        </div>
        {statsUnavailable && <p className="text-sm text-neutral-500">Live counts unavailable. Check the API on :8000.</p>}
      </section>

      {/* 2 — The problem */}
      <section className="flex flex-col gap-5 border-t border-neutral-200 pt-10">
        <h2 className="text-2xl font-normal tracking-tight">Everyone trusts the wrong data</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-neutral-200 p-4">
            <div className="font-medium">Glassdoor</div>
            <p className="mt-1 text-sm text-neutral-600">Rumor. Self-reported, unverifiable, gameable.</p>
          </div>
          <div className="rounded-lg border border-neutral-200 p-4">
            <div className="font-medium">Levels.fyi</div>
            <p className="mt-1 text-sm text-neutral-600">Crowdsourced. Better, but sparse and still self-reported.</p>
          </div>
          <div className="rounded-lg border border-neutral-900 bg-neutral-900 p-4 text-white">
            <div className="font-medium">DOL filings</div>
            <p className="mt-1 text-sm text-neutral-300">Published by the DOL. Employer-reported offered wages, by title and case number.</p>
          </div>
        </div>
        <p className="max-w-2xl text-neutral-600">
          The catch: the files are enormous, and almost nobody reads them. So workers
          negotiate against rumor and leave real money on the table.
        </p>
      </section>

      {/* 3 — The three agents */}
      <section className="flex flex-col gap-5 border-t border-neutral-200 pt-10">
        <h2 className="text-2xl font-normal tracking-tight">Three agents, not a pipeline</h2>
        <p className="max-w-2xl text-neutral-600">
          Each agent runs an observe → decide → act loop with OpenAI function calling. They choose
          their own tools based on what they see — and every choice is traced.
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          {AGENTS.map((a) => (
            <div key={a.name} className="flex flex-col gap-2 rounded-lg border border-neutral-200 p-5">
              <div className="text-lg font-semibold">{a.name}</div>
              <div className="text-sm font-medium text-neutral-500">{a.tagline}</div>
              <p className="text-sm text-neutral-600">{a.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 4 — How it works */}
      <section className="flex flex-col gap-5 border-t border-neutral-200 pt-10">
        <h2 className="text-2xl font-normal tracking-tight">How it works</h2>
        <ol className="flex flex-col gap-3">
          {PIPELINE.map(([tool, what], i) => (
            <li key={tool} className="flex items-baseline gap-3">
              <span className="text-sm tabular-nums text-neutral-400">{i + 1}</span>
              <span className="w-28 shrink-0 font-medium">{tool}</span>
              <span className="text-neutral-600">{what}</span>
            </li>
          ))}
        </ol>
          <p className="max-w-2xl text-sm text-neutral-500">
          Ask about a company we haven&apos;t loaded and the Counselor fetches it on the fly — it
          resolves the real DOL employer name, pulls the filings, and answers. A self-extending corpus.
        </p>
      </section>

      {/* 5 — Tiger Data */}
      <section className="flex flex-col gap-3 rounded-lg border border-neutral-200 bg-neutral-50 p-6 sm:p-8">
        <h2 className="text-2xl font-normal tracking-tight">Powered by Tiger Data</h2>
        <p className="max-w-3xl text-neutral-600">
          Tiger Data is the backbone of WAGE.md. It holds the filing corpus and published
          company briefs, while PostgreSQL queries calculate wage percentiles directly from
          the source rows. That shared foundation lets you move from a salary figure to the
          underlying DOL cases with the context intact.
        </p>
      </section>

      {/* 6 — See it */}
      <section className="flex flex-col gap-5 border-t border-neutral-200 pt-10">
        <h2 className="text-2xl font-normal tracking-tight">See it</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Link href="/negotiate" className="rounded-lg border border-neutral-200 p-5 hover:border-neutral-900">
            <div className="font-medium">Run the Counselor →</div>
            <p className="mt-1 text-sm text-neutral-600">Enter an offer; watch the agent gather evidence and write a cited report.</p>
          </Link>
          <Link href="/company/anthropic" className="rounded-lg border border-neutral-200 p-5 hover:border-neutral-900">
            <div className="font-medium">Browse a company →</div>
            <p className="mt-1 text-sm text-neutral-600">Percentile tables by role and level, straight from the filings.</p>
          </Link>
          <Link href="/briefs" className="rounded-lg border border-neutral-200 p-5 hover:border-neutral-900">
            <div className="font-medium">The public index →</div>
            <p className="mt-1 text-sm text-neutral-600">Browse generated company briefs backed by DOL cases.</p>
          </Link>
        </div>
      </section>

      {/* 7 — Tools */}
      <section className="flex flex-col gap-3 border-t border-neutral-200 pt-10">
        <p className="text-sm text-neutral-400">Built with</p>
        <div className="flex flex-wrap gap-2">
          {["Tiger Data", "OpenAI", "US DOL", "California EDD"].map((t) => (
            <span key={t} className="rounded-full border border-neutral-300 px-3 py-1 text-sm">{t}</span>
          ))}
        </div>
      </section>
    </div>
  );
}
