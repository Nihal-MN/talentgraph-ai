import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { SearchResult } from "@/lib/api";
import { SearchResultCard } from "./SearchResultCard";

const RESULT: SearchResult = {
  id: 42,
  full_name: "Priya Patel",
  headline: "Senior Backend Software Engineer",
  seniority: "senior",
  years_experience: 7.8,
  location: "Berlin, Germany",
  country: "Germany",
  region: "Europe",
  industry: "Fintech",
  skills: ["python", "kubernetes", "postgresql"],
  rank: 1,
  score: 0.95,
  components: {
    lexical: { rank: 2, score: 1.2345, matched_terms: ["python", "kubernetes"] },
    vector: { rank: 1, similarity: 0.8123 },
    fusion: { score: 0.0321, normalized: 1.0 },
    rerank: {
      score: 0.95,
      components: { fusion: 1, title_family: 1, skill_overlap: 0.66, years_fit: 1, geo_factor: 1.4 },
      notes: ["based in Berlin, as requested (geo boost ×1.40)", "skills matched: python, kubernetes"],
    },
  },
  why: {
    matched_skills: [
      { skill: "python", evidence: "Built production services in Python" },
      { skill: "kubernetes", evidence: "Owned Kubernetes in production" },
    ],
    related_skills: [{ skill: "docker", evidence: "Owned Docker in production" }],
    text_terms_matched: ["python", "kubernetes"],
    snippet: "Senior Backend Software Engineer with depth in [python] and [kubernetes]",
    rerank_notes: [],
    signals_matched: ["experience 7.8 yrs ≥ 5 requested", "based in Berlin, as requested"],
    filters_applied: {},
  },
};

describe("SearchResultCard", () => {
  it("renders the candidate summary compactly", () => {
    render(<SearchResultCard result={RESULT} />);
    expect(screen.getByText("Priya Patel")).toBeInTheDocument();
    expect(screen.getByText("Senior Backend Software Engineer")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // rank badge
    expect(screen.getByText(/Berlin, Germany/)).toBeInTheDocument();
    expect(screen.getByText(/experience 7\.8 yrs ≥ 5 requested/)).toBeInTheDocument();
  });

  it("reveals the explainability panel on demand", async () => {
    const user = userEvent.setup();
    render(<SearchResultCard result={RESULT} />);

    expect(screen.queryByText("Score breakdown")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /why this result/i }));

    expect(screen.getByText("Score breakdown")).toBeInTheDocument();
    expect(screen.getByText(/rank 2 · score 1.2345/)).toBeInTheDocument();
    expect(screen.getByText(/cosine 0.8123/)).toBeInTheDocument();
    expect(screen.getByText(/geo ×1\.40/)).toBeInTheDocument();
    expect(screen.getByText(/Built production services in Python/)).toBeInTheDocument();
    expect(screen.getByText(/geo boost ×1.40/)).toBeInTheDocument();
    expect(screen.getByText("docker")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /hide why/i }));
    expect(screen.queryByText("Score breakdown")).not.toBeInTheDocument();
  });
});
