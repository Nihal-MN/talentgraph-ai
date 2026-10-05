"use client";

import { useState } from "react";

import { createSaved, rediscovery as rediscoveryApi, type RediscoveryResponse } from "@/lib/api";
import { SearchResultCard } from "@/components/SearchResultCard";
import { Button, Card, CardHeader, Chip, EmptyState, ErrorBox, Input, Spinner } from "@/components/ui";

const SAMPLE_JD = `Senior Backend Engineer (5+ years) — Logistics Platform

We are hiring a Senior Backend Engineer to build Python/FastAPI services for our Dubai logistics platform. You will own services end to end and work with PostgreSQL, Redis and Docker. Experience with Kubernetes and Kafka is a plus. Fintech or logistics background preferred.`;

export default function RediscoveryPage() {
  const [jdText, setJdText] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RediscoveryResponse | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    setSavedMsg(null);
    try {
      const outcome = await rediscoveryApi({
        jd_text: jdText,
        title: title || undefined,
        company_name: company || undefined,
        limit: 15,
      });
      setResult(outcome);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rediscovery failed");
    } finally {
      setBusy(false);
    }
  };

  const saveAsSearch = async () => {
    if (!result) return;
    try {
      await createSaved({
        name: `JD: ${result.job.title}`,
        description: `Rediscovery run against job #${result.job.id}`,
        query: { raw: result.search.query, strategy: "hybrid", rerank: true, limit: 20, filters: {} },
      });
      setSavedMsg("Saved — reopen it from Saved searches to re-run anytime.");
    } catch (err) {
      setSavedMsg(err instanceof Error ? err.message : "Could not save");
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Talent rediscovery</h1>
        <p className="mt-1 text-sm text-slate-500">
          Paste a job description — TalentGraph parses requirements and searches your existing pool
          for the closest matches, with explicit gaps where nothing convincing exists.
        </p>
      </header>

      <Card>
        <div className="space-y-4 p-5">
          <div className="grid gap-3 md:grid-cols-2">
            <Input value={title} onChange={setTitle} placeholder="Role title (optional)" />
            <Input value={company} onChange={setCompany} placeholder="Company name (optional)" />
          </div>
          <textarea
            value={jdText}
            onChange={(event) => setJdText(event.target.value)}
            rows={9}
            placeholder="Paste the job description here…"
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-100"
          />
          <div className="flex items-center gap-3">
            <Button onClick={run} disabled={busy || jdText.trim().length < 40}>
              {busy ? "Searching the pool…" : "Find matches in the pool"}
            </Button>
            <Button variant="secondary" onClick={() => setJdText(SAMPLE_JD)}>
              Use sample JD
            </Button>
          </div>
        </div>
      </Card>

      {error ? <ErrorBox message={error} /> : null}
      {busy ? <Spinner label="Parsing JD and running hybrid retrieval…" /> : null}

      {result ? (
        <section className="space-y-4">
          <Card>
            <CardHeader
              title={`Job #${result.job.id} — ${result.job.title}`}
              subtitle={result.job.company_name ?? undefined}
              right={
                <Button variant="secondary" onClick={saveAsSearch}>
                  Save as search
                </Button>
              }
            />
            <div className="space-y-3 px-5 py-4">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs font-medium text-slate-500">Parsed requirements:</span>
                {result.parsed_jd.skills.map((skill) => (
                  <Chip key={skill} tone="violet">
                    {skill}
                  </Chip>
                ))}
                {result.parsed_jd.min_years != null ? (
                  <Chip tone="amber">{result.parsed_jd.min_years}+ years</Chip>
                ) : null}
                {result.parsed_jd.seniority ? (
                  <Chip tone="amber">{result.parsed_jd.seniority} level</Chip>
                ) : null}
                {result.parsed_jd.domains.map((domain) => (
                  <Chip key={domain} tone="sky">
                    {domain}
                  </Chip>
                ))}
                {result.parsed_jd.location?.city ? (
                  <Chip tone="sky">{result.parsed_jd.location.city}</Chip>
                ) : null}
              </div>
              <p className="text-xs text-slate-500">
                {result.search.total} candidates scanned · {result.search.took_ms} ms ·{" "}
                {result.search.strategy} retrieval
              </p>
              {result.gaps.length > 0 ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs font-medium text-slate-500">Gaps (no strong match):</span>
                  {result.gaps.map((gap) => (
                    <Chip key={gap} tone="amber">
                      {gap}
                    </Chip>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-emerald-700">
                  No gaps — every parsed requirement appears in the top matches.
                </p>
              )}
              {savedMsg ? <p className="text-xs text-violet-700">{savedMsg}</p> : null}
            </div>
          </Card>

          <h2 className="text-sm font-semibold text-slate-700">Top matches from your pool</h2>
          <div className="space-y-3">
            {result.matches.map((match) => (
              <SearchResultCard key={match.id} result={match} />
            ))}
          </div>
          <p className="text-xs text-slate-400">{result.note}</p>
        </section>
      ) : !busy ? (
        <EmptyState
          title="No JD run yet"
          hint="Paste a job description above (or use the sample) to search the existing pool for rediscovery matches."
        />
      ) : null}
    </div>
  );
}
