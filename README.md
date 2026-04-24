# ScamLens

AI-powered DNS that blocks scam websites. Point any device at ScamLens as its DNS resolver; known scams are sinkholed to a block page, unknown domains get real-time AI analysis (Claude / Gemini) over a headless browser.

## Architecture

```
        ┌─────────────┐     ┌──────────────┐
client ▶│ DNS server  │◀──▶ │  Redis cache │
        │  :53 / DoH  │     └──────────────┘
        └──────┬──────┘             ▲
               │                    │ verdicts
               ▼                    │
        ┌─────────────┐     ┌──────────────┐
        │ AI scanner  │────▶│  PostgreSQL  │
        │ (Playwright │     └──────┬───────┘
        │   + Claude) │            │ reads
        └─────────────┘     ┌──────▼───────┐
                            │   FastAPI    │
                            │    :8000     │
                            └──────┬───────┘
                                   ▼
                            ┌──────────────┐
                            │  Next.js UI  │
                            │    :3000     │
                            └──────────────┘
```

Nginx fronts everything on 443. Cleartext DNS stays on :53 for desktops/routers; DoH lives at `https://dns.<DOMAIN>/dns-query` for mobile.

## Services

| Service     | Dir            | Port(s)            | Purpose                       |
|-------------|----------------|--------------------|-------------------------------|
| dns_server  | `dns_server/`  | 53 udp/tcp, 8053   | Resolver + DoH endpoint       |
| ai_scanner  | `ai_scanner/`  | —                  | Playwright + Claude worker    |
| api         | `api/`         | 8000               | FastAPI REST                  |
| frontend    | `frontend/`    | 3000               | Next.js marketing + dashboard |
| postgres    | image          | 5432 (internal)    | Logs + verdicts               |
| redis       | image          | 6379 (internal)    | Cache + job queue             |

## Repo layout

```
scamlens/
├── dns_server/       # Python DNS (dnslib) + DoH
├── ai_scanner/       # Playwright + Claude/Gemini worker
├── api/              # FastAPI backend
├── frontend/         # Next.js + Tailwind
├── nginx/            # reverse-proxy config
├── postgres/         # init.sql schema
├── scripts/
│   ├── setup_vps.sh
│   ├── generate_ios_profile.py
│   └── seed_blocklist.py
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start (local dev)

```bash
cp .env.example .env
# edit: ANTHROPIC_API_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD, DOMAIN, BLOCK_PAGE_IP
docker compose up --build
```

Health checks:
- `curl http://localhost:8000/health`
- `dig @127.0.0.1 example.com` (once Phase 2 lands)
- open `http://localhost:3000`

## VPS deploy (Ubuntu 22.04)

```bash
ssh root@your-vps
git clone <repo> /opt/scamlens
cd /opt/scamlens
cp .env.example .env && $EDITOR .env
sudo bash scripts/setup_vps.sh
```

`setup_vps.sh` installs Docker, Nginx, certbot, opens firewall (53/80/443), requests Let's Encrypt certs for both `${DOMAIN}` and `${DNS_HOSTNAME}`, installs a systemd unit that brings Compose up on boot.

## Build phases

| Phase | Scope                                    | Status |
|-------|------------------------------------------|--------|
| 1     | Project structure + Docker scaffold      | ✅     |
| 2     | DNS server + blocklist                   | ✅     |
| 3     | AI scanner (Playwright + Claude)         | ✅     |
| 4     | FastAPI endpoints                        | ✅     |
| 5     | Next.js dashboard + pages                | ✅     |
| 6     | iOS `.mobileconfig` generator            | ✅     |
| 7     | Setup guides (Android/iOS/Desktop/Router)| ✅     |
| 8     | VPS deploy script + systemd              | ✅     |
| 9     | End-to-end testing instructions          | ✅     |

## Testing

See [`TESTING.md`](./TESTING.md) for the full post-deploy test plan:
DNS, DoH, AI scan pipeline, API, frontend, iOS profile install,
resilience + cert renewal.

## License

TBD
