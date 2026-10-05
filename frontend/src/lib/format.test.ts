import { describe, expect, it } from "vitest";

import { fmtScore, fmtYears, parseCommaList, splitHighlightedSnippet } from "./format";

describe("splitHighlightedSnippet", () => {
  it("splits [matched] markers into parts", () => {
    const parts = splitHighlightedSnippet("Built [python] services in [Berlin]");
    expect(parts).toEqual([
      { text: "Built ", match: false },
      { text: "python", match: true },
      { text: " services in ", match: false },
      { text: "Berlin", match: true },
    ]);
  });

  it("handles text without markers", () => {
    expect(splitHighlightedSnippet("no markers here")).toEqual([
      { text: "no markers here", match: false },
    ]);
  });

  it("handles the SQLite «» style markers left as plain text", () => {
    const parts = splitHighlightedSnippet("used «k8s» in production");
    expect(parts.filter((part) => part.match)).toHaveLength(0);
    expect(parts.map((part) => part.text).join("")).toBe("used «k8s» in production");
  });
});

describe("parseCommaList", () => {
  it("trims and drops empties", () => {
    expect(parseCommaList("python, kubernetes ,, go ")).toEqual([
      "python",
      "kubernetes",
      "go",
    ]);
  });

  it("returns [] for empty input", () => {
    expect(parseCommaList("")).toEqual([]);
  });
});

describe("formatters", () => {
  it("fmtScore keeps 4 decimals and dashes nulls", () => {
    expect(fmtScore(0.12345)).toBe("0.1235");
    expect(fmtScore(null)).toBe("—");
  });

  it("fmtYears renders integers and halves", () => {
    expect(fmtYears(5)).toBe("5 yrs");
    expect(fmtYears(5.5)).toBe("5.5 yrs");
    expect(fmtYears(null)).toBe("—");
  });
});
