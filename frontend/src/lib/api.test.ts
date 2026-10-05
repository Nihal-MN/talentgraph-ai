import { afterEach, describe, expect, it, vi } from "vitest";

import { search } from "./api";

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
  vi.restoreAllMocks();
});

function mockFetchOnce(body: unknown, status = 200) {
  const mock = vi.fn().mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: async () => body,
  });
  global.fetch = mock as unknown as typeof fetch;
  return mock;
}

describe("api client", () => {
  it("POSTs searches to /search with the payload and parses the response", async () => {
    const payload = {
      results: [],
      total: 0,
      took_ms: 7,
      strategy: "hybrid",
      rerank: true,
      query_id: 1,
      parsed: { raw: "python", text_terms: [], skills: ["python"], expansions: [] },
      filters_used: {},
      soft_signals: {},
    };
    const mock = mockFetchOnce(payload);

    const response = await search({ query: "python", strategy: "hybrid", limit: 5 });

    expect(response.total).toBe(0);
    expect(response.query_id).toBe(1);
    const [url, init] = mock.mock.calls[0];
    expect(String(url)).toContain("/search");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toMatchObject({
      query: "python",
      strategy: "hybrid",
      limit: 5,
    });
  });

  it("surfaces structured API errors as Error(message)", async () => {
    mockFetchOnce(
      { error: { code: "validation_error", message: "query is too short" } },
      422,
    );
    await expect(search({ query: "x" })).rejects.toThrow("query is too short");
  });

  it("falls back to HTTP status text for non-JSON errors", async () => {
    const mock = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not json");
      },
    });
    global.fetch = mock as unknown as typeof fetch;
    await expect(search({ query: "python" })).rejects.toThrow("500 Internal Server Error");
  });
});
