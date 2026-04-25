-- 005: unified users + guardian/ward links + push subscriptions
-- + bind block events to users.
--
-- Replaces the standalone `admins` table. role='admin' grants admin
-- console access; role='user' is a regular signed-up account.
--
--   docker compose exec -T postgres \
--     psql -U $POSTGRES_USER -d $POSTGRES_DB \
--     < postgres/migrations/005_users_dependents.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
  id              BIGSERIAL PRIMARY KEY,
  email           TEXT UNIQUE NOT NULL,
  password_hash   TEXT NOT NULL,                  -- bcrypt
  role            TEXT NOT NULL DEFAULT 'user',   -- user | admin
  invite_code     TEXT UNIQUE NOT NULL,           -- friendly code shared with guardians
  doh_token       TEXT UNIQUE NOT NULL,           -- per-user DoH path component
  display_name    TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_users_invite_code ON users (invite_code);
CREATE INDEX IF NOT EXISTS idx_users_doh_token ON users (doh_token);

-- Migrate any existing admin rows into users.
INSERT INTO users (email, password_hash, role, invite_code, doh_token, created_at, last_login_at)
SELECT
  a.email,
  a.password_hash,
  COALESCE(a.role, 'admin'),
  upper(substring(replace(gen_random_uuid()::text, '-', '') FROM 1 FOR 8)),
  replace(gen_random_uuid()::text, '-', '')
       || replace(gen_random_uuid()::text, '-', ''),
  a.created_at,
  a.last_login_at
FROM admins a
ON CONFLICT (email) DO NOTHING;

-- The old admins table is no longer the source of truth. Rename for safety
-- so we can drop it in a later migration once we confirm nothing reads it.
ALTER TABLE IF EXISTS admins RENAME TO admins_legacy;

CREATE TABLE IF NOT EXISTS guardian_links (
  id            BIGSERIAL PRIMARY KEY,
  guardian_id   BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ward_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status        TEXT NOT NULL DEFAULT 'pending',   -- pending | accepted | rejected | revoked
  invited_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  responded_at  TIMESTAMPTZ,
  CHECK (guardian_id <> ward_id),
  UNIQUE (guardian_id, ward_id)
);
CREATE INDEX IF NOT EXISTS idx_links_ward ON guardian_links (ward_id);
CREATE INDEX IF NOT EXISTS idx_links_guardian ON guardian_links (guardian_id);
CREATE INDEX IF NOT EXISTS idx_links_status ON guardian_links (status);

CREATE TABLE IF NOT EXISTS push_subscriptions (
  id           BIGSERIAL PRIMARY KEY,
  user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  endpoint     TEXT NOT NULL,
  p256dh       TEXT NOT NULL,
  auth         TEXT NOT NULL,
  user_agent   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, endpoint)
);
CREATE INDEX IF NOT EXISTS idx_push_user ON push_subscriptions (user_id);

-- Bind block events to a user when known. Nullable for anonymous traffic.
ALTER TABLE blocked_attempts
  ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_blocked_user ON blocked_attempts (user_id, created_at DESC);
