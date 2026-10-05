"use client";

import Link from "next/link";
import { useState } from "react";

import type { SearchResult } from "@/lib/api";
import { fmtScore, fmtYears, splitHighlightedSnippet } from "@/lib/format";
import { Chip } from "@/components/ui";

function Snippet({ text }: { text: string }) {
  const parts = splitHighlightedSnippet(text);
  return (
    <p className="text-xs leading-relaxed text-slate-600">
      {parts.map((part, index) =>
        part.match ? (
          <mark key={index} className="rounded bg-amber-100 px-0.5 text-amber-900">
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </p>
  );
}

export function SearchResultCard({
  result,
  showRank = true,
}: {
  result: SearchResult;
  showRank?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const { components, why } = result;

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm transition hover:border-violet-200">
      <div className="flex items-start gap-4 px-5 py-4">
        {showRank ? (
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-600 text-sm font-bold text-white">
            {result.rank}
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <Link
              href={`/candidates/${result.id}`}
              className="text-sm font-semibold text-slate-900 hover:text-violet-700"
            >
              {result.full_name}
            </Link>
            <span className="font-mono text-xs text-slate-400" title="relative score (fusion + rerank)">
              {fmtScore(result.score)}
            </span>
          </div>
          <p className="mt-0.5 truncate text-sm text-slate-600">{result.headline ?? "—"}</p>
          <p className="mt-1 text-xs text-slate-500">
            {[
              result.location,
              result.industry,
              result.seniority ? `${result.seniority} level` : null,
              fmtYears(result.years_experience),
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {result.skills.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {result.skills.slice(0, 8).map((skill) => {
                const matched =
                  why.matched_skills.some((item) => item.skill === skill) ||
                  why.related_skills.some((item) => item.skill === skill);
                return (
                  <Chip key={skill} tone={matched ? "violet" : "slate"}>
                    {skill}
                  </Chip>
                );
              })}
            </div>
          ) : null}
          {why.signals_matched.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {why.signals_matched.map((signal) => (
                <Chip key={signal} tone="green" title="soft signal from the query">
                  ✓ {signal}
                </Chip>
              ))}
            </div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="shrink-0 rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          {open ? "Hide why" : "Why this result?"}
        </button>
      </div>

      {open ? (
        <div className="grid gap-4 border-t border-slate-100 bg-slate-50/60 px-5 py-4 text-xs md:grid-cols-2">
          <div className="space-y-3">
            <div>
              <p className="font-semibold text-slate-700">Score breakdown</p>
              <table className="mt-1.5 w-full">
                <tbody className="divide-y divide-slate-100">
                  {components.lexical ? (
                    <tr>
                      <td className="py-1 pr-2 text-slate-500">Lexical (FTS/BM25)</td>
                      <td className="py-1 font-mono text-slate-700">
                        rank {components.lexical.rank} · score {fmtScore(components.lexical.score)}
                      </td>
                    </tr>
                  ) : (
                    <tr>
                      <td className="py-1 pr-2 text-slate-500">Lexical (FTS/BM25)</td>
                      <td className="py-1 text-slate-400">no lexical hit</td>
                    </tr>
                  )}
                  <tr>
                    <td className="py-1 pr-2 text-slate-500">Vector (embeddings)</td>
                    <td className="py-1 font-mono text-slate-700">
                      {components.vector
                        ? `rank ${components.vector.rank} · cosine ${fmtScore(components.vector.similarity)}`
                        : "no vector hit"}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-1 pr-2 text-slate-500">Fusion (RRF)</td>
                    <td className="py-1 font-mono text-slate-700">
                      {fmtScore(components.fusion.score)} (normalized{" "}
                      {fmtScore(components.fusion.normalized)})
                    </td>
                  </tr>
                  {components.rerank ? (
                    <tr>
                      <td className="py-1 pr-2 text-slate-500">Rerank</td>
                      <td className="py-1 font-mono text-slate-700">
                        {fmtScore(components.rerank.score)}
                        {components.rerank.components.geo_factor
                          ? ` · geo ×${components.rerank.components.geo_factor.toFixed(2)}`
                          : ""}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            {components.rerank?.notes && components.rerank.notes.length > 0 ? (
              <div>
                <p className="font-semibold text-slate-700">Reranker notes</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate-600">
                  {components.rerank.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            {why.matched_skills.length > 0 ? (
              <div>
                <p className="font-semibold text-slate-700">Matched skills (with evidence)</p>
                <ul className="mt-1 space-y-1">
                  {why.matched_skills.map((item) => (
                    <li key={item.skill} className="text-slate-600">
                      <span className="font-medium text-violet-700">{item.skill}</span>
                      {item.evidence ? <> — “{item.evidence}”</> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {why.related_skills.length > 0 ? (
              <div>
                <p className="font-semibold text-slate-700">Related skills found</p>
                <ul className="mt-1 space-y-1">
                  {why.related_skills.map((item) => (
                    <li key={item.skill} className="text-slate-600">
                      <span className="font-medium text-sky-700">{item.skill}</span>
                      {item.evidence ? <> — “{item.evidence}”</> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {why.text_terms_matched.length > 0 ? (
              <div>
                <p className="font-semibold text-slate-700">Query terms matched</p>
                <p className="mt-1 font-mono text-slate-600">
                  {why.text_terms_matched.join(", ")}
                </p>
              </div>
            ) : null}
            {why.snippet ? (
              <div>
                <p className="font-semibold text-slate-700">Source snippet</p>
                <div className="mt-1 rounded-md border border-slate-200 bg-white px-3 py-2">
                  <Snippet text={why.snippet} />
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
