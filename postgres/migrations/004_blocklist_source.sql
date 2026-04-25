-- 004: track WHERE an auto-blocked domain came from.
--
-- The DNS resolver and AI scanner already write to blocklist_seed; the new
-- social_scraper service additionally promotes scam URLs found in social
-- posts. Operators need to see the original post link so they can audit
-- and report it.
--
--   docker compose exec -T postgres \
--     psql -U $POSTGRES_USER -d $POSTGRES_DB \
--     < postgres/migrations/004_blocklist_source.sql

ALTER TABLE blocklist_seed
  ADD COLUMN IF NOT EXISTS source_post     TEXT,
  ADD COLUMN IF NOT EXISTS source_platform TEXT;     -- threads | x | facebook | manual

CREATE INDEX IF NOT EXISTS idx_blocklist_source_platform
  ON blocklist_seed (source_platform)
  WHERE source_platform IS NOT NULL;

CREATE TABLE IF NOT EXISTS scrape_runs (
  id              BIGSERIAL PRIMARY KEY,
  platform        TEXT NOT NULL,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at     TIMESTAMPTZ,
  posts_seen      INTEGER NOT NULL DEFAULT 0,
  urls_seen       INTEGER NOT NULL DEFAULT 0,
  domains_new     INTEGER NOT NULL DEFAULT 0,
  domains_blocked INTEGER NOT NULL DEFAULT 0,
  errors          INTEGER NOT NULL DEFAULT 0,
  notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_started_at
  ON scrape_runs (started_at DESC);
