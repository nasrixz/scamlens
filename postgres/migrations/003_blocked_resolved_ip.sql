-- Add resolved_ip column so block events record the scam server's real IP
-- (the answer ScamLens would have returned upstream had we not blocked).
--
--   docker compose exec -T postgres \
--     psql -U $POSTGRES_USER -d $POSTGRES_DB \
--     < postgres/migrations/003_blocked_resolved_ip.sql

ALTER TABLE blocked_attempts
  ADD COLUMN IF NOT EXISTS resolved_ip INET;

CREATE INDEX IF NOT EXISTS idx_blocked_resolved_ip
  ON blocked_attempts (resolved_ip)
  WHERE resolved_ip IS NOT NULL;
