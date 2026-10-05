"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  createSaved,
  ingestResume,
  search as searchApi,
  type SearchFilters,
  type SearchResponse,
} from "@/lib/api";
import { FiltersPanel } from "@/components/FiltersPanel";
import { SearchResultCard } from "@/components/SearchResultCard";
import { Button, Card, Chip, EmptyState, ErrorBox, Input, Spinner } from "@/components/ui";

function ParsedChips({ parsed }: { parsed: SearchResponse["parsed"] }) {
  const chips: { label: string; tone: "slate" | "violet" | "sky" | "amber" }[] = [];
  parsed.skills.forEach((skill) => chips.push({ label: `skill: ${skill}`, tone: "violet" }));
  if (parsed.city) chips.push({ label: `city: ${parsed.city}`, tone: "sky" });
  if (parsed.country) chips.push({ label: `country: ${parsed.country}`, tone: "sky" });
  if (parsed.region) chips.push({ label: `region: ${parsed.region}`, tone: "sky" });
  if (parsed.seniority.length)
    chips.push({ label: `seniority: ${parsed.seniority.join("/")}`, tone: "amber" });
  if (parsed.min_years != null) chips.push({ label: `min years: ${parsed.min_years}`, tone: "amber" });
  if (parsed.family) chips.push({ label: `title: ${parsed.family}`, tone: "amber" });
  if (parsed.industry) chips.push({ label: `industry: ${parsed.industry}`, tone: "amber" });
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs font-medium text-slate-500">Parsed from your query:</span>
      {chips.map((chip) => (
        <Chip key={chip.label} tone={chip.tone}>
          {chip.label}
        </Chip>
      ))}
    </div>
  );
}

function IngestPanel() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ingested, setIngested] = useState<{ id: number; full_name: string; skills_detected: number } | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await ingestResume({
        resume_text: text,
        full_name: name || undefined,
      });
      setIngested(result);
      setText("");
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingestion failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <p className="text-sm font-semibold text-slate-800">Ingest a resume (paste text)</p>
          <p className="mt-0.5 text-xs text-slate-500">
            Parsed deterministically into a structured profile — skills, title, seniority, location,
            experience estimate — then embedded and indexed like the seeded pool.
          </p>
        </div>
        <span className="text-xs text-violet-600">{open ? "Hide" : "Open"}</span>
      </button>
      {open ? (
        <div className="space-y-3 border-t border-slate-100 px-5 py-4">
          <Input value={name} onChange={setName} placeholder="Full name (optional — first line is used otherwise)" />
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={"Paste resume text here…\n\nName\nSenior Data Engineer\n8 years building pipelines with Spark, Airflow and dbt…"}
            rows={7}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-100"
          />
          {error ? <ErrorBox message={error} /> : null}
          {ingested ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              Ingested <Link className="font-semibold underline" href={`/candidates/${ingested.id}`}>{ingested.full_name}</Link>{" "}
              ({ingested.skills_detected} skills detected, id {ingested.id}). Search for them by name or skills.
            </div>
          ) : null}
          <p className="text-[11px] text-slate-400">
            Demo only — do not paste real candidate data. Text is treated as untrusted data: parsed,
            quoted as evidence, never executed.
          </p>
          <Button onClick={submit} disabled={busy || text.trim().length < 30}>
            {busy ? "Ingesting…" : "Ingest resume"}
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

function SearchPage() {
  const searchParams = useSearchParams();
  const initialized = useRef(false);

  const initial = useMemo(() => {
    const raw = searchParams.get("raw") ?? "";
    let filters: SearchFilters = {};
    const filtersParam = searchParams.get("filters");
    if (filtersParam) {
      try {
        filters = JSON.parse(filtersParam) as SearchFilters;
      } catch {
        filters = {};
      }
    }
    return {
      raw,
      filters,
      strategy: searchParams.get("strategy") ?? "hybrid",
      rerank: searchParams.get("rerank") !== "false",
    };
  }, [searchParams]);

  const [query, setQuery] = useState(initial.raw);
  const [filters, setFilters] = useState<SearchFilters>(initial.filters);
  const [strategy, setStrategy] = useState(initial.strategy);
  const [rerank, setRerank] = useState(initial.rerank);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveName, setSaveName] = useState("");
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const run = useCallback(
    async (overrideQuery?: string) => {
      const q = (overrideQuery ?? query).trim();
      if (q.length < 2) return;
      setLoading(true);
      setError(null);
      setSaveMsg(null);
      try {
        const result = await searchApi({
          query: q,
          filters: Object.keys(filters).length ? filters : undefined,
          strategy,
          rerank,
          limit: 20,
        });
        setResponse(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed");
      } finally {
        setLoading(false);
      }
    },
    [query, filters, strategy, rerank],
  );

  useEffect(() => {
    if (!initialized.current && initial.raw) {
      initialized.current = true;
      void run(initial.raw);
    }
  }, [initial.raw, run]);

  const save = async () => {
    if (!response || saveName.trim().length < 2) return;
    try {
      await createSaved({
        name: saveName.trim(),
        query: {
          raw: response.parsed.raw,
          strategy: response.strategy,
          rerank: response.rerank,
          limit: 20,
          filters: response.filters_used,
        },
      });
      setSaveMsg(`Saved “${saveName.trim()}” — reopen it from Saved searches.`);
      setSaveName("");
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "Could not save");
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Talent search</h1>
        <p className="mt-1 text-sm text-slate-500">
          Ask in plain language or add hard filters. Every result explains itself — lexical rank,
          vector similarity, fusion, reranker notes and skill evidence.
        </p>
      </header>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void run();
        }}
        className="flex gap-2"
      >
        <div className="flex-1">
          <Input
            value={query}
            onChange={setQuery}
            placeholder='e.g. "senior python backend engineer in Berlin with kubernetes experience"'
          />
        </div>
        <Button type="submit" disabled={loading || query.trim().length < 2}>
          {loading ? "Searching…" : "Search"}
        </Button>
      </form>

      <FiltersPanel
        filters={filters}
        onChange={setFilters}
        strategy={strategy}
        onStrategyChange={setStrategy}
        rerank={rerank}
        onRerankChange={setRerank}
      />

      {error ? <ErrorBox message={error} /> : null}

      {response ? (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-slate-600">
              <span className="font-semibold text-slate-800">{response.results.length}</span> shown ·{" "}
              <span className="font-semibold text-slate-800">{response.total}</span> retrieved ·{" "}
              {response.took_ms} ms ·{" "}
              <span className="capitalize">{response.strategy}</span>
              {response.rerank ? " + rerank" : ""}
            </div>
            <div className="flex items-center gap-2">
              <Input value={saveName} onChange={setSaveName} placeholder="Name this search…" className="w-48" />
              <Button variant="secondary" onClick={save} disabled={saveName.trim().length < 2}>
                Save search
              </Button>
            </div>
          </div>
          {saveMsg ? <p className="text-xs text-violet-700">{saveMsg}</p> : null}
          <ParsedChips parsed={response.parsed} />
          {Object.keys(response.filters_used).length > 0 ? (
            <p className="text-xs text-slate-500">
              Hard filters applied:{" "}
              <span className="font-mono text-slate-600">
                {JSON.stringify(response.filters_used)}
              </span>
            </p>
          ) : null}
          <div className="space-y-3">
            {response.results.length === 0 ? (
              <EmptyState
                title="No candidates matched"
                hint="Try a broader query or remove hard filters — natural-language constraints are soft by design."
              />
            ) : (
              response.results.map((result) => <SearchResultCard key={result.id} result={result} />)
            )}
          </div>
        </section>
      ) : loading ? (
        <Spinner label="Running retrieval (lexical + vector + fusion)…" />
      ) : (
        <EmptyState
          title="Try the demo queries"
          hint='"senior python backend engineer in Berlin with kubernetes experience" · "technical recruiter in the Gulf" · "data engineer with spark and airflow" · "ml engineer with RAG and vector database experience"'
        />
      )}

      <IngestPanel />
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <SearchPage />
    </Suspense>
  );
}
