-- ScamLens migration 002:
--   * whitelist       official safe domains (skip all checks, no AI scan)
--   * brand_domains   official brand anchors for typosquat detection
--   * admins          operator accounts with password hash
--
-- Apply with:
--   docker compose exec -T postgres \
--     psql -U $POSTGRES_USER -d $POSTGRES_DB < postgres/migrations/002_whitelist_brands_admins.sql

CREATE TABLE IF NOT EXISTS whitelist (
  domain     TEXT PRIMARY KEY,
  reason     TEXT,
  added_by   TEXT,
  added_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS brand_domains (
  domain     TEXT PRIMARY KEY,     -- official domain, e.g. paypal.com
  brand      TEXT NOT NULL,        -- display name, e.g. "PayPal"
  category   TEXT,                 -- bank | tech | social | retail | crypto | gov
  added_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_brand_domains_brand ON brand_domains (brand);

CREATE TABLE IF NOT EXISTS admins (
  id              BIGSERIAL PRIMARY KEY,
  email           TEXT UNIQUE NOT NULL,
  password_hash   TEXT NOT NULL,       -- bcrypt
  role            TEXT NOT NULL DEFAULT 'admin',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at   TIMESTAMPTZ
);
