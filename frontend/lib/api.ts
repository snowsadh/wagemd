// Thin client for the FastAPI middleware. Server components call these directly.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type DistRow = {
  role_family: string;
  level: string;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  sample_size: number;
};

export type CompanyFilters = {
  role: string;
  level: string;
  state: string;
  period: "all" | "FY2025" | "FY2026";
};

export type CompanyDistribution = {
  company: string;
  total_filings: number;
  matchedFilings: {
    count: number;
    p25: number | null;
    p50: number | null;
    p75: number | null;
    firstDecision: string | null;
    lastDecision: string | null;
  };
  stateOptions: string[];
  rows: DistRow[];
  roleTotals: Array<{ role: string; count: number }>;
  locations: Array<{ state: string; median: number; count: number }>;
  monthlyFilings: Array<{ month: string; count: number; p50: number | null }>;
  levelMedians: Array<{ level: string; count: number; median: number }>;
  caseTypeTotals: Array<{ caseType: string; count: number }>;
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

export const getCompany = (slug: string, filters?: Partial<CompanyFilters>) => {
  const params = new URLSearchParams();
  if (filters?.role) params.set("role", filters.role);
  if (filters?.level) params.set("level", filters.level);
  if (filters?.state) params.set("state", filters.state);
  if (filters?.period && filters.period !== "all") params.set("period", filters.period);
  const query = params.toString();
  return getJSON<CompanyDistribution>(`/company/${encodeURIComponent(slug)}${query ? `?${query}` : ""}`);
};

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
