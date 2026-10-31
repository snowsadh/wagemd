"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { postNegotiate, type AgentResult, type Offer } from "@/lib/api";

const DEMO: Offer = {
  company: "Anthropic",
  role_family: "SWE",
  level: "L5",
  location: "San Francisco",
  base: 215000,
  yoe: 8,
};

export default function NegotiatePage() {
  const [offer, setOffer] = useState<Offer>(DEMO);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const set = (k: keyof Offer) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setOffer({ ...offer, [k]: k === "base" || k === "yoe" ? Number(e.target.value) : e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await postNegotiate(offer));
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  const rawReport =
    (result && (typeof result.result === "string" ? result.result : result.result?.report)) || "";
  // strip a wrapping ```markdown ... ``` fence so it renders as markdown, not a code block
  const report = rawReport
    .replace(/^\s*```(?:markdown|md)?\s*\n/i, "")
    .replace(/\n?```\s*$/i, "")
    .trim();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight">Negotiate</h1>
        <p className="text-neutral-600">
          Enter your offer. The Counselor agent autonomously gathers DOL evidence (broadening on
          thin samples) and returns a fully-cited recommendation.
        </p>
      </div>

      <form className="grid max-w-2xl grid-cols-2 gap-3" onSubmit={submit}>
        <input value={offer.company} onChange={set("company")} placeholder="Company" className="rounded-md border border-neutral-300 px-3 py-2" />
        <input value={offer.role_family} onChange={set("role_family")} placeholder="Role (SWE/PM/ML/Data/...)" className="rounded-md border border-neutral-300 px-3 py-2" />
        <input value={offer.level} onChange={set("level")} placeholder="Level (e.g. L5)" className="rounded-md border border-neutral-300 px-3 py-2" />
        <input value={offer.location} onChange={set("location")} placeholder="Location" className="rounded-md border border-neutral-300 px-3 py-2" />
        <input value={offer.base} onChange={set("base")} placeholder="Base ($)" className="rounded-md border border-neutral-300 px-3 py-2" />
        <input value={offer.yoe} onChange={set("yoe")} placeholder="YOE" className="rounded-md border border-neutral-300 px-3 py-2" />
        <button type="submit" disabled={loading} className="col-span-2 rounded-md bg-signal px-4 py-2 font-medium text-white hover:bg-neutral-700 disabled:opacity-50">
          {loading ? "Counselor is gathering evidence…" : "Generate report"}
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="flex flex-col gap-4">
          <div className="rounded-md border border-neutral-200 bg-neutral-50 p-3 text-xs">
            <div className="mb-2 font-medium text-neutral-700">
              Agent trace — {result.iterations} iterations, {result.trace?.length ?? 0} tool calls
            </div>
            <ol className="flex flex-col gap-1">
              {result.trace?.map((t, i) => (
                <li key={i} className="text-neutral-600">
                  <span className="font-mono text-neutral-900">{t.tool}</span>
                  <span className="text-neutral-400"> ({Object.values(t.args || {}).join(", ")})</span>
                </li>
              ))}
            </ol>
          </div>
          <article className="prose prose-sm prose-neutral max-w-none rounded-md border border-neutral-200 p-5 prose-headings:font-normal prose-table:text-xs prose-th:text-left prose-a:text-signal">
            {result.status === "exhausted" ? (
              "Counselor reached its iteration limit. Try again; the trace above shows what it checked."
            ) : report ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
            ) : (
              "No report returned."
            )}
          </article>
        </div>
      )}
    </div>
  );
}
