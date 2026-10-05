/* Typed API client for the TalentGraph backend. */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8300/api/v1";

export type WhySkill = { skill: string; evidence: string | null };

export type SearchResult = {
  id: number;
  full_name: string;
  headline: string | null;
  seniority: string | null;
  years_experience: number | null;
  location: string | null;
  country: string | null;
  region: string | null;
  industry: string | null;
  skills: string[];
  rank: number;
  score: number;
  components: {
    lexical: { rank: number | null; score: number; matched_terms: string[] } | null;
    vector: { rank: number | null; similarity: number } | null;
    fusion: { score: number; normalized: number };
    rerank: {
      score: number;
      components: Record<string, number>;
      notes: string[];
    } | null;
  };
  why: {
    matched_skills: WhySkill[];
    related_skills: WhySkill[];
    text_terms_matched: string[];
    snippet: string;
    rerank_notes: string[];
    signals_matched: string[];
    filters_applied: Record<string, unknown>;
  };
};

export type ParsedQuery = {
  raw: string;
  text_terms: string[];
  skills: string[];
  expansions: string[];
  min_years: number | null;
  max_years: number | null;
  seniority: string[];
  city: string | null;
  country: string | null;
  region: string | null;
  industry: string | null;
  family: string | null;
  remote: boolean;
  notes: string[];
  parser: string;
};

export type SearchResponse = {
  query_id: number | null;
  parsed: ParsedQuery;
  filters_used: Record<string, unknown>;
  soft_signals: Record<string, unknown>;
  strategy: string;
  rerank: boolean;
  took_ms: number;
  total: number;
  results: SearchResult[];
};

export type SearchFilters = {
  skills?: string[];
  min_years?: number | null;
  max_years?: number | null;
  seniority?: string[];
  cities?: string[];
  countries?: string[];
  region?: string | null;
  industry?: string | null;
};

export type HealthResponse = {
  status: string;
  app: string;
  version: string;
  database: { status: string; dialect: string | null; detail: string | null };
  ai: {
    mode: string;
    embedding: { provider: string; dims: number | null };
    query_parser: string;
    api_key_configured: boolean;
  };
  retrieval: {
    vector_backend: string;
    lexical_backend: string;
    fusion: string;
    pgvector_verified: boolean;
  };
  counts: Record<string, number>;
};

export type CandidateDetail = {
  id: number;
  full_name: string;
  headline: string | null;
  seniority: string | null;
  years_experience: number | null;
  summary: string | null;
  location: string | null;
  industry: string | null;
  source: string;
  skills: { name: string; canonical: string | null; category: string | null; evidence: string | null }[];
  experiences: { title: string; normalized_title: string | null; start_date: string | null; end_date: string | null; is_current: boolean }[];
  educations: { degree: string; institution: string; year: number | null }[];
  embedding: { model: string; dims: number; embedded_at: string } | null;
};

export type SavedSearch = {
  id: number;
  name: string;
  description: string | null;
  query: Record<string, unknown>;
  run_count: number;
  last_run_at: string | null;
};

export type BenchmarkResponse = {
  id?: number;
  benchmark_run_id?: number;
  k: number;
  dataset_size: number;
  query_count: number;
  duration_ms: number;
  created_at?: string;
  strategies: string[];
  metrics: Record<
    string,
    { precision_at_k: number; recall_at_k: number; mrr: number; ndcg_at_k: number }
  >;
  per_query: {
    query_id: string;
    query: string;
    strategy: string;
    top_ids: number[];
    top_grades: number[];
    metrics: Record<string, number>;
    latency_ms: number;
  }[];
};

export type RediscoveryResponse = {
  job: { id: number; title: string; company_name: string | null };
  parsed_jd: {
    skills: string[];
    expansions: string[];
    min_years: number | null;
    seniority: string | null;
    domains: string[];
    location: { city: string | null; country: string | null; region: string | null } | null;
    title: string | null;
  };
  search: { query: string; strategy: string; took_ms: number; total: number };
  matches: SearchResult[];
  gaps: string[];
  note: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body?.error?.message ?? body?.detail ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function search(payload: {
  query: string;
  filters?: SearchFilters;
  strategy?: string;
  limit?: number;
  rerank?: boolean;
}): Promise<SearchResponse> {
  return request<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function listCandidates(limit = 50): Promise<
  { id: number; full_name: string; headline: string | null; location: string | null }[]
> {
  return request(`/candidates?limit=${limit}`);
}

export function getCandidate(id: number): Promise<CandidateDetail> {
  return request<CandidateDetail>(`/candidates/${id}`);
}

export function ingestResume(payload: {
  resume_text: string;
  full_name?: string;
}): Promise<{
  id: number;
  full_name: string;
  headline: string | null;
  seniority: string | null;
  years_experience: number | null;
  location: string | null;
  skills_detected: number;
  note: string;
}> {
  return request("/candidates/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listSaved(): Promise<SavedSearch[]> {
  return request("/saved-searches");
}

export function createSaved(payload: {
  name: string;
  description?: string;
  query: Record<string, unknown>;
}): Promise<{ id: number; name: string }> {
  return request("/saved-searches", { method: "POST", body: JSON.stringify(payload) });
}

export function runSaved(id: number): Promise<{ saved_search: SavedSearch } & SearchResponse> {
  return request(`/saved-searches/${id}/run`, { method: "POST" });
}

export function deleteSaved(id: number): Promise<void> {
  return request(`/saved-searches/${id}`, { method: "DELETE" });
}

export function rediscovery(payload: {
  jd_text: string;
  title?: string;
  company_name?: string;
  limit?: number;
}): Promise<RediscoveryResponse> {
  return request("/rediscovery", { method: "POST", body: JSON.stringify(payload) });
}

export function getBenchmark(): Promise<BenchmarkResponse> {
  return request("/evaluation/benchmark");
}

export function runBenchmark(
  k = 10,
  strategies?: string[],
): Promise<BenchmarkResponse> {
  return request("/evaluation/run", {
    method: "POST",
    body: JSON.stringify({ k, strategies }),
  });
}

export function recentSearches(limit = 20): Promise<
  {
    id: number;
    raw_query: string;
    strategy: string;
    result_count: number;
    latency_ms: number;
    created_at: string;
  }[]
> {
  return request(`/search/recent?limit=${limit}`);
}
