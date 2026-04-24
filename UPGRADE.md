# Upgrade — adds whitelist + typosquat + admin

This release adds:

- **Whitelist** (`whitelist` table): exact or parent-domain match → skip all checks & AI scan.
- **Brand anchors** (`brand_domains` table): fuel for typosquat detector.
- **Typosquat detector**: in-process Levenshtein + homoglyph + boundary-aware
  substring. Catches `paypa1.com`, `g00gle.com`, `app1e-support.com`,
  `paypal-secure-login.com`, etc. without hitting the AI.
- **Admin system** (`admins` table + `/api/admin/*`): bcrypt password login,
  JWT cookie session, CRUD for reports / blocklist / whitelist / brands.
- **Admin UI** at `/admin` (login at `/admin/login`).
- **Block page** redesigned — shield icon, brand-mimic callout, risk score,
  clearer CTAs, stats row, guidance list.

## New resolver pipeline

```
  incoming query
        │
        ▼
  bypass suffix (.arpa/.local) ─── yes ──▶ forward upstream
        │ no
        ▼
  whitelist match (parent chain) ── yes ──▶ forward upstream, no scan
        │ no
        ▼
  blocklist match (parent chain) ── yes ──▶ SINKHOLE, log
        │ no
        ▼
  redis cache hit                   ── scam/suspicious ──▶ SINKHOLE
        │ safe → forward
        │ miss
        ▼
  typosquat detector                ── hit ──▶ SINKHOLE with brand mimic
        │ miss
        ▼
  forward upstream + enqueue AI scan (rate-limited, pending marker)
```

Google, Apple, PayPal, banks, major retailers, CDN hosts all whitelisted at
seed time. AI only runs on truly novel, non-brand-adjacent domains — cuts
cost and kills false positives on legit sites.

## Applying on the VPS

```bash
cd /opt/scamlens
git pull

# 1. Add JWT_SECRET to .env
echo "JWT_SECRET=$(openssl rand -hex 48)" | sudo tee -a .env
echo "JWT_TTL_HOURS=12" | sudo tee -a .env

# 2. Apply migration + whitelist seed
sudo docker compose exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  < postgres/migrations/002_whitelist_brands_admins.sql

sudo docker compose exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  < scripts/seed_whitelist.sql

# 3. Rebuild API + DNS with new deps/code + restart all
sudo docker compose build api dns_server frontend
sudo docker compose up -d

# 4. Create first admin
sudo docker compose exec -T api \
  python -m scripts.create_admin you@vendly.my --password "$(openssl rand -hex 16)"
# (save the generated password)

# 5. Confirm
sudo docker compose logs --tail=30 dns_server | grep lists_loaded
# → blocklist=9 whitelist=150+ brands=45+

dig @127.0.0.1 google.com +short      # → real IP (whitelisted, never scanned)
dig @127.0.0.1 paypa1.com +short      # → VPS IP (blocklist)
dig @127.0.0.1 g00gle.com +short      # → VPS IP (typosquat homoglyph)
dig @127.0.0.1 paypal-secure-login.xyz +short   # → VPS IP (typosquat boundary)
```

## Admin UI

- Login: `https://scamlens.vendly.my/admin/login`
- Dashboard: `https://scamlens.vendly.my/admin`

Pending reports page lets you **Confirm → block** (inserts into
`blocklist_seed` within the same transaction as flipping report status) or
**Reject**. Blocklist / Whitelist tabs let you add/remove by domain.

Changes propagate to the DNS server within 5 minutes automatically (refresh
loop pulls from Postgres). Force a sync with
`docker compose restart dns_server` if you need it immediately.

## Keep legit sites legit

If a safe site gets blocked again:

1. Admin → Reports → Confirm *not* scam (or skip if no report).
2. Admin → Whitelist → add the domain.
3. DNS picks it up within 5 min (or restart dns_server).

Whitelist overrides blocklist — adding to whitelist also deletes the entry
from `blocklist_seed` automatically (atomic in the admin API).

## Verdict cost breakdown (typical month)

| Pipeline step        | Per query cost        | Hit rate in real traffic |
|----------------------|-----------------------|--------------------------|
| Bypass suffix        | ~0.01 ms (string cmp) | ~20% (.arpa / .local)    |
| Whitelist lookup     | ~0.02 ms (set)        | ~60% (major sites)       |
| Blocklist lookup     | ~0.02 ms (set)        | ~5%                      |
| Redis cache          | ~0.5 ms (network)     | ~10%                     |
| Typosquat detector   | ~0.1 ms (in-process)  | ~0.5%                    |
| AI scan (Claude/Gemini) | ~3-8s + $0.01-0.03 | ~0.1% — targets novel unknown |

So roughly **1 AI scan per 1000 queries**, down from ~1 per 15 queries
previously.
