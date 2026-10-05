"use client";

import { useState } from "react";

import type { SearchFilters } from "@/lib/api";
import { parseCommaList } from "@/lib/format";
import { Button, Input, Select } from "@/components/ui";

export const SENIORITY_LEVELS = ["junior", "mid", "senior", "lead", "staff", "head"];

export const REGIONS = ["MENA", "Europe", "APAC", "Americas", "Africa"];

export function FiltersPanel({
  filters,
  onChange,
  strategy,
  onStrategyChange,
  rerank,
  onRerankChange,
}: {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
  strategy: string;
  onStrategyChange: (strategy: string) => void;
  rerank: boolean;
  onRerankChange: (rerank: boolean) => void;
}) {
  const [skillsText, setSkillsText] = useState((filters.skills ?? []).join(", "));
  const [citiesText, setCitiesText] = useState((filters.cities ?? []).join(", "));
  const [countriesText, setCountriesText] = useState((filters.countries ?? []).join(", "));

  const apply = () => {
    const next: SearchFilters = {};
    const skills = parseCommaList(skillsText);
    const cities = parseCommaList(citiesText);
    const countries = parseCommaList(countriesText);
    if (skills.length) next.skills = skills;
    if (cities.length) next.cities = cities;
    if (countries.length) next.countries = countries;
    if (filters.min_years != null && filters.min_years !== undefined) next.min_years = filters.min_years;
    if (filters.max_years != null && filters.max_years !== undefined) next.max_years = filters.max_years;
    if (filters.seniority?.length) next.seniority = filters.seniority;
    if (filters.region) next.region = filters.region;
    if (filters.industry) next.industry = filters.industry;
    onChange(next);
  };

  const clear = () => {
    setSkillsText("");
    setCitiesText("");
    setCountriesText("");
    onChange({});
  };

  const toggleSeniority = (level: string) => {
    const current = filters.seniority ?? [];
    const next = current.includes(level)
      ? current.filter((item) => item !== level)
      : [...current, level];
    onChange({ ...filters, seniority: next.length ? next : undefined });
  };

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="grid gap-4 md:grid-cols-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">
            Skills (comma-separated, hard filter)
          </span>
          <Input
            value={skillsText}
            onChange={setSkillsText}
            placeholder="python, kubernetes"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Cities (hard filter)</span>
          <Input value={citiesText} onChange={setCitiesText} placeholder="Dubai, Berlin" />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">
            Countries (hard filter)
          </span>
          <Input
            value={countriesText}
            onChange={setCountriesText}
            placeholder="United Arab Emirates"
          />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Min years</span>
          <Input
            type="number"
            value={filters.min_years?.toString() ?? ""}
            onChange={(value) =>
              onChange({ ...filters, min_years: value === "" ? undefined : Number(value) })
            }
            placeholder="0"
            min={0}
            max={50}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Max years</span>
          <Input
            type="number"
            value={filters.max_years?.toString() ?? ""}
            onChange={(value) =>
              onChange({ ...filters, max_years: value === "" ? undefined : Number(value) })
            }
            placeholder="20"
            min={0}
            max={50}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Region</span>
          <Select
            value={filters.region ?? ""}
            onChange={(value) => onChange({ ...filters, region: value || undefined })}
            options={[
              { value: "", label: "Any region" },
              ...REGIONS.map((region) => ({ value: region, label: region })),
            ]}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Industry</span>
          <Input
            value={filters.industry ?? ""}
            onChange={(value) => onChange({ ...filters, industry: value || undefined })}
            placeholder="Fintech"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium text-slate-600">Seniority (hard filter):</span>
        {SENIORITY_LEVELS.map((level) => {
          const active = filters.seniority?.includes(level) ?? false;
          return (
            <button
              key={level}
              type="button"
              onClick={() => toggleSeniority(level)}
              className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition ${
                active
                  ? "bg-violet-600 text-white"
                  : "border border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {level}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-4 border-t border-slate-100 pt-4">
        <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
          Strategy
          <Select
            value={strategy}
            onChange={onStrategyChange}
            options={[
              { value: "hybrid", label: "Hybrid (RRF)" },
              { value: "lexical", label: "Lexical only" },
              { value: "vector", label: "Vector only" },
            ]}
            className="w-40"
          />
        </label>
        <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
          <input
            type="checkbox"
            checked={rerank}
            onChange={(event) => onRerankChange(event.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-violet-600"
          />
          Rerank (feature reranker + geography)
        </label>
        <div className="ml-auto flex gap-2">
          <Button variant="secondary" onClick={clear}>
            Clear filters
          </Button>
          <Button onClick={apply}>Apply filters</Button>
        </div>
      </div>
      <p className="text-[11px] leading-relaxed text-slate-400">
        Filters here are hard constraints (SQL). Constraints written inside the natural-language
        query — “5+ years”, “in Dubai” — are applied as soft ranking signals and shown in each
        result’s “Why” panel.
      </p>
    </div>
  );
}
