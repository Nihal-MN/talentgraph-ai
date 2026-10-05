"""TalentGraph AI — semantic talent search and candidate rediscovery engine.

Package layout:

- ``app.core``      — settings, error model
- ``app.db``        — engine/session/declarative base
- ``app.models``    — the 13 core domain entities (+ operational tables)
- ``app.services``  — normalization, ingestion, retrieval, fusion, evaluation
- ``app.api``       — versioned REST routes
- ``app.seed``      — deterministic synthetic dataset generator
"""

__version__ = "0.1.0"
