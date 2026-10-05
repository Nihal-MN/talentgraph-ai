# Contributing to TalentGraph AI

Thanks for taking a look! This is a portfolio-scale project, but it is built
to be a *real* codebase: deterministic tests, measured retrieval quality, and
no magic numbers. Contributions, issues and questions are welcome.

## Getting set up

```bash
# full stack (recommended — includes PostgreSQL + pgvector)
docker compose up --build -d
# api on :8300, web on :3400, db on :5434

# or backend-only dev
cd backend
uv sync
uv run python -m app.seed --count 200        # deterministic dataset + benchmark
uv run uvicorn app.main:app --reload --port 8300

# or frontend-only dev (against a running api)
cd frontend && npm ci && npm run dev
```

No API key is needed anywhere — the deterministic demo paths are the default
and the test suite runs entirely offline.

## Before you open a PR

```bash
cd backend
uv run ruff check app tests scripts     # lint
uv run pytest -q                        # full suite, incl. the named evals
uv run pytest tests/evals -q            # just the retrieval eval suite

cd ../frontend
npm run lint && npm run typecheck && npm run test && npm run build
```

All of it green, please — CI runs exactly these on both SQLite and a real
pgvector service, plus Docker builds.

## Project rules (the important ones)

- **Determinism is a feature.** The dataset (seed=42) and the retrieval
  paths must produce identical results run to run. If you touch the
  generator or a scoring path, re-run the benchmark and say what moved in
  the PR.
- **Soft vs hard constraints is settled.** NL-parsed constraints are soft
  ranking signals; only explicit filters are hard (ADR 0003). Don't "fix"
  this by hard-filtering prose.
- **Every ranking change needs an eval or a benchmark delta.** The
  `tests/evals/` suite states product claims; add a numbered eval for a new
  behavior claim, or show metric movement in `docs/EVALUATION.md` terms.
- **No real people data.** Synthetic only. Examples in docs/tests use
  `@example.com`-style contacts and fabricated names.
- **Evidence or it didn't happen.** New ranking signals must surface in the
  "Why this result?" payload with human-readable notes — no unexplainable
  score bumps.
- **No protected characteristics.** Cannot be filters, signals or features —
  see `RESPONSIBLE_AI.md`.

## Commit style

Short imperative subjects (`add: …`, `fix: …`, `docs: …` are fine too), body
explains *why* when it isn't obvious. Keep mechanical churn (formatting) out
of behavior-change commits.
