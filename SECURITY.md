# Security

## Scope

TalentGraph AI is a **local demo application**. It runs on your machine (or a
trusted local network), ships with no authentication by design, and stores
only synthetic data. Running it exposed to the public internet is out of
scope until an auth story and hardening work land (tracked in the roadmap).

## No secrets in the repo

- `.env` is git-ignored; `.env.example` contains placeholders only.
- The app runs fully **without any API key** (deterministic demo embeddings +
  rule-based parsing). `OPENAI_API_KEY` is optional and read from the
  environment, never stored.
- `/api/v1/health` reports whether a key is configured and which mode is
  active — it never echoes any credential.

## Untrusted input

Resume/JD/query text is treated as data. Parsers are deterministic and
non-executing; injected strings cannot become instructions, filters or
evidence (see `RESPONSIBLE_AI.md`; tests in `tests/test_injection.py`).

## Data

- All seeded profiles are fictional (`@example.com`, 555 phone ranges).
- The resume-ingest endpoint is for demo pastes; the UI warns against real
  candidate data.
- SQL is parameterized end-to-end (SQLAlchemy); the one raw-SQL block
  (PostgreSQL FTS ranking) uses bound parameters.

## Reporting

This is a personal portfolio project — open a GitHub issue for security
concerns or email the maintainer via the profile on the repository.
