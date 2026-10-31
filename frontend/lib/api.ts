// Thin client for the FastAPI middleware. Server components call these directly.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type DistRow = {
  role_family: string;
  level: string;
  p50: number;
  p75: number;
  p90: number;
  sample_size: number;
};

export type CompanyDistribution = {
  company: string;
  total_filings: number;
  rows: DistRow[];
  briefUrl?: string | null;
};

export type Offer = {
  company: string;
  role_family: string;
  level: string;
  location: string;
  base: number;
  yoe: number;
};

export type TraceStep = { tool: string; args: Record<string, unknown>; result: unknown };
export type AgentResult = {
  status: string;
  result?: { report?: string } | string;
  iterations: number;
  trace: TraceStep[];
  agent: string;
};

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const getHealth = () =>
  getJSON<{ status: string; service: string; filings: number }>("/health");

export const getCompanies = () =>
  getJSON<{ companies: Array<{ name: string; slug: string; filings: number }> }>("/companies");

export const getCompany = (slug: string) =>
  getJSON<CompanyDistribution>(`/company/${encodeURIComponent(slug)}`);

export const listPublished = () =>
  getJSON<{ pages: Array<{ company: string; url: string; last_published: string; sample_size: number }> }>(
    "/index",
  );

export const getBrief = (company: string) =>
  getJSON<{ company: string; markdown: string; last_published: string; sample_size: number }>(
    `/briefs/${encodeURIComponent(company)}`,
  );

export const postNegotiate = (offer: Offer) =>
  getJSON<AgentResult>("/negotiate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(offer),
  });
