## What does this PR change?

<!-- One or two sentences. If it changes ranking behavior, include the benchmark delta. -->

## Checklist

- [ ] `uv run ruff check app tests scripts` passes (backend)
- [ ] `uv run pytest -q` passes (include the named evals)
- [ ] `npm run lint && npm run typecheck && npm run test && npm run build` passes (frontend, if touched)
- [ ] Ranking changes include a benchmark delta or a new numbered eval
- [ ] If the generator/seed changed: I re-ran the benchmark and noted what moved
- [ ] No real candidate data, no secrets, no new hard-filtering of prose constraints (ADR 0003)
- [ ] New scoring signals appear in the "Why this result?" payload with readable notes

## Related issues

<!-- Fixes #… / Relates to #… -->
