-- ScamLens schema bootstrap. Runs once on first postgres start.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS blocked_attempts (
  id           BIGSERIAL PRIMARY KEY,
  domain       TEXT NOT NULL,
  reason       TEXT NOT NULL,
  ai_confidence SMALLINT,
  risk_score   SMALLINT,
  verdict      TEXT,
  mimics_brand TEXT,
  country      TEXT,
  client_ip    INET,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_blocked_created_at ON blocked_attempts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_blocked_domain ON blocked_attempts (domain);

CREATE TABLE IF NOT EXISTS domain_verdicts (
  domain       TEXT PRIMARY KEY,
  verdict      TEXT NOT NULL,              -- safe | suspicious | scam
  risk_score   SMALLINT,
  confidence   SMALLINT,
  reasons      JSONB,
  mimics_brand TEXT,
  source       TEXT NOT NULL,              -- blocklist | ai | user_report
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_verdicts_verdict ON domain_verdicts (verdict);
CREATE INDEX IF NOT EXISTS idx_verdicts_updated ON domain_verdicts (updated_at DESC);

CREATE TABLE IF NOT EXISTS user_reports (
  id           BIGSERIAL PRIMARY KEY,
  domain       TEXT NOT NULL,
  note         TEXT,
  reporter_ip  INET,
  status       TEXT NOT NULL DEFAULT 'pending',  -- pending | confirmed | rejected
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reports_status ON user_reports (status);

CREATE TABLE IF NOT EXISTS blocklist_seed (
  domain     TEXT PRIMARY KEY,
  category   TEXT,
  added_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
