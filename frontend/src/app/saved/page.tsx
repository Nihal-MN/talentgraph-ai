"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { deleteSaved, listSaved, type SavedSearch } from "@/lib/api";
import { Button, Card, EmptyState, ErrorBox, Spinner } from "@/components/ui";
import { fmtDate } from "@/lib/format";

export default function SavedPage() {
  const router = useRouter();
  const [items, setItems] = useState<SavedSearch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await listSaved();
        if (!active) return;
        setItems(data);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Could not load saved searches");
      }
    })();
    return () => {
      active = false;
    };
  }, [refreshKey]);

  const reopen = (item: SavedSearch) => {
    const query = item.query as {
      raw?: string;
      strategy?: string;
      rerank?: boolean;
      filters?: Record<string, unknown>;
    };
    const params = new URLSearchParams();
    params.set("raw", query.raw ?? "");
    params.set("strategy", query.strategy ?? "hybrid");
    params.set("rerank", String(query.rerank ?? true));
    if (query.filters && Object.keys(query.filters).length) {
      params.set("filters", JSON.stringify(query.filters));
    }
    router.push(`/?${params.toString()}`);
  };

  const remove = async (item: SavedSearch) => {
    if (!window.confirm(`Delete “${item.name}”?`)) return;
    setBusyId(item.id);
    try {
      await deleteSaved(item.id);
      setRefreshKey((key) => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Saved searches</h1>
        <p className="mt-1 text-sm text-slate-500">
          Reopen any saved search to re-run it against the current pool — with its strategy, rerank
          setting and hard filters intact.
        </p>
      </header>

      {error ? <ErrorBox message={error} /> : null}
      {items === null ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState
          title="No saved searches yet"
          hint="Run a search and press “Save search”, or save a rediscovery run."
        />
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const query = item.query as { raw?: string; strategy?: string };
            return (
              <Card key={item.id}>
                <div className="flex items-start justify-between gap-4 px-5 py-4">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-800">{item.name}</p>
                    <p className="mt-0.5 truncate text-sm text-slate-600">“{query.raw}”</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {query.strategy ?? "hybrid"} · run {item.run_count}× · last{" "}
                      {fmtDate(item.last_run_at)}
                      {item.description ? ` · ${item.description}` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button variant="secondary" onClick={() => reopen(item)}>
                      Reopen
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => remove(item)}
                      disabled={busyId === item.id}
                    >
                      {busyId === item.id ? "…" : "Delete"}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
