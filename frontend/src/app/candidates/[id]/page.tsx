"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { getCandidate, type CandidateDetail } from "@/lib/api";
import { Card, CardHeader, Chip, EmptyState, ErrorBox, Spinner } from "@/components/ui";
import { fmtDate, fmtYears } from "@/lib/format";

export default function CandidatePage() {
  const params = useParams<{ id: string }>();
  const candidateId = Number(params.id);
  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getCandidate(candidateId);
        if (!active) return;
        setCandidate(data);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Could not load candidate");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [candidateId]);

  if (loading) return <Spinner label="Loading profile…" />;
  if (error) return <ErrorBox message={error} />;
  if (!candidate) return <EmptyState title="Candidate not found" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/" className="text-sm text-violet-700 hover:underline">
          ← Back to search
        </Link>
        {candidate.source === "ingested" ? <Chip tone="amber">ingested (demo)</Chip> : <Chip tone="slate">seeded</Chip>}
      </div>

      <Card>
        <div className="px-5 py-5">
          <h1 className="text-xl font-bold tracking-tight text-slate-900">{candidate.full_name}</h1>
          <p className="mt-0.5 text-sm text-slate-600">{candidate.headline ?? "—"}</p>
          <p className="mt-1 text-xs text-slate-500">
            {[
              candidate.location,
              candidate.industry,
              candidate.seniority ? `${candidate.seniority} level` : null,
              fmtYears(candidate.years_experience),
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {candidate.summary ? (
            <p className="mt-3 text-sm leading-relaxed text-slate-700">{candidate.summary}</p>
          ) : null}
          {candidate.embedding ? (
            <p className="mt-3 text-xs text-slate-400">
              Embedded with <span className="font-mono">{candidate.embedding.model}</span> (
              {candidate.embedding.dims} dims) · {fmtDate(candidate.embedding.embedded_at)}
            </p>
          ) : null}
        </div>
      </Card>

      <Card>
        <CardHeader
          title={`Skills (${candidate.skills.length})`}
          subtitle="Every skill carries its source evidence — the same quotes the “Why this result?” panel shows."
        />
        <ul className="divide-y divide-slate-100">
          {candidate.skills.map((skill) => (
            <li key={`${skill.name}-${skill.evidence ?? ""}`} className="flex items-start gap-3 px-5 py-3">
              <div className="min-w-0">
                <p className="text-sm text-slate-800">
                  <span className="font-medium">{skill.name}</span>
                  {skill.canonical && skill.canonical !== skill.name.toLowerCase() ? (
                    <span className="ml-2 text-xs text-slate-400">→ {skill.canonical}</span>
                  ) : null}
                  {skill.category ? (
                    <span className="ml-2 text-xs text-violet-500">{skill.category}</span>
                  ) : null}
                </p>
                {skill.evidence ? (
                  <p className="mt-0.5 text-xs text-slate-500">“{skill.evidence}”</p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardHeader title="Experience" />
        <ul className="divide-y divide-slate-100">
          {candidate.experiences.map((experience, index) => (
            <li key={index} className="flex items-baseline justify-between gap-4 px-5 py-3">
              <div>
                <p className="text-sm font-medium text-slate-800">{experience.title}</p>
                {experience.normalized_title ? (
                  <p className="text-xs text-slate-400">normalized: {experience.normalized_title}</p>
                ) : null}
              </div>
              <p className="shrink-0 text-xs text-slate-500">
                {experience.start_date?.slice(0, 4) ?? "?"} –{" "}
                {experience.is_current ? "present" : experience.end_date?.slice(0, 4) ?? "?"}
              </p>
            </li>
          ))}
        </ul>
      </Card>

      {candidate.educations.length > 0 ? (
        <Card>
          <CardHeader title="Education" />
          <ul className="divide-y divide-slate-100">
            {candidate.educations.map((education, index) => (
              <li key={index} className="px-5 py-3 text-sm text-slate-700">
                {education.degree} — {education.institution}
                {education.year ? ` (${education.year})` : ""}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}
