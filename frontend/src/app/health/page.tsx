"use client";

import { useEffect, useState } from "react";

import { getHealth, type HealthResponse } from "@/lib/api";
import { Button, Card, CardHeader, Chip, ErrorBox, Spinner, Stat } from "@/components/ui";

export default function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getHealth();
        if (!active) return;
        setHealth(data);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Could not reach the API");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refreshKey]);

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">System health</h1>
          <p className="mt-1 text-sm text-slate-500">
            Live status of the retrieval stack: database, vector backend, embedding provider and
            query parser. No secrets are exposed.
          </p>
        </div>
        <Button
          onClick={() => {
            setLoading(true);
            setRefreshKey((key) => key + 1);
          }}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </Button>
      </header>

      {error ? <ErrorBox message={error} /> : null}
      {loading && !health ? (
        <Spinner label="Contacting API…" />
      ) : health ? (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <Stat
              label="Overall"
              value={
                <span className={health.status === "ok" ? "text-emerald-700" : "text-amber-700"}>
                  {health.status}
                </span>
              }
              hint={`${health.app} v${health.version}`}
            />
            <Stat label="Database" value={health.database.dialect ?? "—"} hint={health.database.status} />
            <Stat
              label="Vector backend"
              value={health.retrieval.vector_backend}
              hint={health.database.dialect === "postgresql" ? `pgvector: ${health.retrieval.pgvector_verified ? "verified" : "not verified"}` : "SQLite fallback active"}
            />
            <Stat label="Lexical backend" value={health.retrieval.lexical_backend} />
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Stat
              label="AI mode"
              value={health.ai.mode}
              hint={health.ai.api_key_configured ? "OpenAI key configured" : "keyless demo paths"}
            />
            <Stat
              label="Embeddings"
              value={health.ai.embedding.provider}
              hint={health.ai.embedding.dims ? `${health.ai.embedding.dims} dimensions` : undefined}
            />
            <Stat label="Query parser" value={health.ai.query_parser} hint={health.retrieval.fusion} />
          </div>

          <Card>
            <CardHeader title="Corpus counts" subtitle="What is currently indexed and searchable." />
            <div className="flex flex-wrap gap-2 px-5 py-4">
              {Object.entries(health.counts).map(([key, value]) => (
                <Chip key={key} tone="slate" title={key}>
                  {key.replace(/_/g, " ")}: <span className="ml-1 font-mono">{value}</span>
                </Chip>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Raw response" subtitle="/api/v1/health" />
            <pre className="overflow-x-auto px-5 py-4 text-xs text-slate-600">
              {JSON.stringify(health, null, 2)}
            </pre>
          </Card>
        </>
      ) : null}
    </div>
  );
}
