-- Starter blocklist for integration tests.
-- Apply with:
--   docker compose exec -T postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
--     < scripts/seed_blocklist.sql

INSERT INTO blocklist_seed (domain, category) VALUES
  ('paypa1.com',                   'typosquat-paypal'),
  ('faceb00k-login.com',           'phish-facebook'),
  ('app1e-support.com',            'phish-apple'),
  ('secure-chase-verify.com',      'phish-chase'),
  ('amazon-refund-center.com',     'phish-amazon'),
  ('crypto-double-reward.com',     'scam-crypto'),
  ('netflix-billing-update.com',   'phish-netflix'),
  ('micros0ft-security.com',       'phish-microsoft'),
  ('scam-test.scamlens.local',     'test')
ON CONFLICT (domain) DO NOTHING;
