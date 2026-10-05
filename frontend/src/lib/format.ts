export function fmtScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(4);
}

export function fmtYears(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)} yrs`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export function fmtCount(value: number): string {
  return value.toLocaleString();
}

/** Split a ts_headline snippet with [match] markers into parts for safe rendering. */
export function splitHighlightedSnippet(snippet: string): { text: string; match: boolean }[] {
  const parts: { text: string; match: boolean }[] = [];
  let buffer = "";
  let inMatch = false;
  for (const char of snippet) {
    if (char === "[") {
      if (buffer) parts.push({ text: buffer, match: inMatch });
      buffer = "";
      inMatch = true;
    } else if (char === "]") {
      if (buffer) parts.push({ text: buffer, match: inMatch });
      buffer = "";
      inMatch = false;
    } else {
      buffer += char;
    }
  }
  if (buffer) parts.push({ text: buffer, match: inMatch });
  return parts;
}

export function parseCommaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
