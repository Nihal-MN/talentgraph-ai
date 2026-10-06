-- TalentGraph AI — first-boot database setup.
-- The application migration also creates this extension defensively; having
-- it here means a fresh volume is pgvector-ready even outside the app.
CREATE EXTENSION IF NOT EXISTS vector;
