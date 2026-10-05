"use client";

import { useEffect, useState } from "react";

import {
  getBenchmark,
  recentSearches,
  runBenchmark,
  type BenchmarkResponse,
} from "@/lib/api";
import { Button, Card, CardHeader, EmptyState, ErrorBox, Spinner, Stat } from "@/components/ui";
import { fmtDate } from "@/lib/format";

const METRIC_LABELS: Record<string, string> = {
  precision_at_k: "Precision@K",
  recall_at_k: "Recall@K",
  mrr: "MRR",
  ndcg_at_k: "nDCG@K",
};

const STRATEGY_LABELS: Record<string, string> = {
  lexical: "Lexical only (FTS/BM25)",
  vector: "Vector only (embeddings)",
  hybrid: "Hybrid (RRF fusion)",
  hybrid_rerank: "Hybrid + reranker",
};

function bestByMetric(
  metrics: BenchmarkResponse["metrics"],
  metric: string,
): number {
  return Math.max(...Object.values(metrics).map((row) => row[metric as keyof typeof row] as number));
}

export default function EvaluationPage() {
  const [benchmark, setBenchmark] = useState<BenchmarkResponse | null>(null);
  const [recent, setRecent] = useState<
    { id: number; raw_query: string; strategy: string; result_count: number; latency_ms: number; created_at: string }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [bench, searches] = await Promise.all([getBenchmark(), recentSearches(10)]);
        if (!active) return;
        setBenchmark(bench);
        setRecent(searches);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Could not load evaluation");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const rerun = async () => {
    setRunning(true);
    setError(null);
    try {
      setBenchmark(await runBenchmark(10));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benchmark failed");
    } finally {
      setRunning(false);
    }
  };

  const grouped = benchmark
    ? benchmark.strategies.map((strategy) => ({
        strategy,
        rows: benchmark.per_query.filter((row) => row.strategy === strategy),
      }))
    : [];

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Search evaluation</h1>
          <p className="mt-1 text-sm text-slate-500">
            Actual measured retrieval quality on a 24-query golden set with ground-truth graded
            labels (P@K, R@K, MRR, nDCG) — the same real pipeline, four strategies.
          </p>
        </div>
        <Button onClick={rerun} disabled={running}>
          {running ? "Running benchmark…" : "Re-run benchmark"}
        </Button>
      </header>

      {error ? <ErrorBox message={error} /> : null}
      {loading ? (
        <Spinner label="Loading benchmark…" />
      ) : benchmark ? (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <Stat label="Dataset" value={`${benchmark.dataset_size} profiles`} />
            <Stat label="Golden queries" value={benchmark.query_count} hint={`K = ${benchmark.k}`} />
            <Stat
              label="Run duration"
              value={`${(benchmark.duration_ms / 1000).toFixed(1)} s`}
              hint="all strategies × all queries"
            />
            <Stat
              label="Last run"
              value={benchmark.created_at ? fmtDate(benchmark.created_at) : "—"}
              hint={benchmark.id ? `run #${benchmark.id}` : "computed live"}
            />
          </div>

          <Card>
            <CardHeader
              title="Strategy comparison (mean across the golden set)"
              subtitle="Green cells mark the best value per metric. Hybrid fuses both rankings; the reranker re-scores the fused top."
            />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3">Strategy</th>
                    {Object.entries(METRIC_LABELS).map(([metric, label]) => (
                      <th key={metric} className="px-4 py-3">
                        {label.replace("@K", `@${benchmark.k}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {benchmark.strategies.map((strategy) => (
                    <tr key={strategy}>
                      <td className="px-5 py-3 font-medium text-slate-800">
                        {STRATEGY_LABELS[strategy] ?? strategy}
                      </td>
                      {Object.keys(METRIC_LABELS).map((metric) => {
                        const value = benchmark.metrics[strategy]?.[
                          metric as keyof (typeof benchmark.metrics)[string]
                        ] as number;
                        const best = value === bestByMetric(benchmark.metrics, metric);
                        return (
                          <td
                            key={metric}
                            className={`px-4 py-3 font-mono ${best ? "bg-emerald-50 font-semibold text-emerald-800" : "text-slate-700"}`}
                          >
                            {value.toFixed(4)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="px-5 pb-4 pt-2 text-xs leading-relaxed text-slate-500">
              Reading the numbers: lexical is strong when queries share exact terms; vector catches
              paraphrases and synonym variants (e.g. “k8s” ↔ “Kubernetes”, “postgres” ↔
              “PostgreSQL”) that never co-occur literally; hybrid fusion wins or ties on most
              metrics; the reranker adds the skill/experience/geography layer on top. Labels are
              predicates over synthetic ground truth — this measures retrieval mechanics
              reproducibly, not human relevance judgment (see docs/EVALUATION.md).
            </p>
          </Card>

          <Card>
            <CardHeader
              title="Per-query breakdown"
              subtitle="Top-10 grades per query: 2 = ideal, 1 = acceptable, 0 = irrelevant."
            />
            <div className="divide-y divide-slate-100">
              {grouped.map((group) => (
                <details key={group.strategy} className="group">
                  <summary className="cursor-pointer px-5 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50">
                    {STRATEGY_LABELS[group.strategy] ?? group.strategy}
                  </summary>
                  <div className="overflow-x-auto px-5 pb-4">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left uppercase tracking-wide text-slate-400">
                          <th className="py-2 pr-3">Query</th>
                          <th className="py-2 pr-3">P@K</th>
                          <th className="py-2 pr-3">R@K</th>
                          <th className="py-2 pr-3">MRR</th>
                          <th className="py-2 pr-3">nDCG</th>
                          <th className="py-2 pr-3">Latency</th>
                          <th className="py-2">Top-10 grades</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {group.rows.map((row) => (
                          <tr key={row.query_id}>
                            <td className="max-w-[280px] truncate py-2 pr-3 text-slate-700" title={row.query}>
                              {row.query}
                            </td>
                            <td className="py-2 pr-3 font-mono">{row.metrics.precision_at_k.toFixed(2)}</td>
                            <td className="py-2 pr-3 font-mono">{row.metrics.recall_at_k.toFixed(2)}</td>
                            <td className="py-2 pr-3 font-mono">{row.metrics.mrr.toFixed(2)}</td>
                            <td className="py-2 pr-3 font-mono">{row.metrics.ndcg_at_k.toFixed(2)}</td>
                            <td className="py-2 pr-3 font-mono">{row.latency_ms} ms</td>
                            <td className="py-2 font-mono">
                              {row.top_grades.join(" ")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Recent searches (analytics)"
              subtitle="Every search is logged with strategy, latency and result count."
            />
            {recent.length === 0 ? (
              <div className="px-5 py-4">
                <EmptyState title="No searches logged yet" hint="Run a search to see analytics here." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 text-left uppercase tracking-wide text-slate-400">
                      <th className="px-5 py-2.5">Query</th>
                      <th className="px-3 py-2.5">Strategy</th>
                      <th className="px-3 py-2.5">Results</th>
                      <th className="px-3 py-2.5">Latency</th>
                      <th className="px-3 py-2.5">When</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {recent.map((item) => (
                      <tr key={item.id}>
                        <td className="max-w-[320px] truncate px-5 py-2.5 text-slate-700" title={item.raw_query}>
                          {item.raw_query}
                        </td>
                        <td className="px-3 py-2.5">{item.strategy}</td>
                        <td className="px-3 py-2.5 font-mono">{item.result_count}</td>
                        <td className="px-3 py-2.5 font-mono">{item.latency_ms} ms</td>
                        <td className="px-3 py-2.5">{fmtDate(item.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}
