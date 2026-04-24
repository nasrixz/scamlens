# ScamLens — Testing Plan

End-to-end checklist. Run top-to-bottom after every deploy.

Legend: `💻` run on your laptop · `🖥️` run on the VPS · `📱` run on the phone.

---

## 0. Setup assumptions

- VPS reachable at `$VPS_IP` (= `BLOCK_PAGE_IP`).
- `dig`, `curl`, `jq` installed locally.
- DNS A records propagated:

```bash
💻 dig +short $DOMAIN       # → $VPS_IP
💻 dig +short $DNS_HOSTNAME # → $VPS_IP
```

- Stack running: `🖥️ docker compose ps` — 6 services, all `healthy` / `Up`.

---

## 1. DNS resolver — cleartext

### 1.1 Safe domain forwards to upstream

```bash
💻 dig @$VPS_IP example.com +short
# → 93.184.216.34 (or current Cloudflare answer)  ✅ upstream forwarding works
```

### 1.2 Known blocked domain sinkholed

```bash
💻 dig @$VPS_IP paypa1.com +short
# → $VPS_IP  ✅ blocked by seed list
```

### 1.3 Parent-chain match

```bash
💻 dig @$VPS_IP deep.sub.paypa1.com +short
# → $VPS_IP  ✅ resolver walks parent chain
```

### 1.4 TCP fallback

```bash
💻 dig @$VPS_IP +tcp example.com +short
# → real IP  ✅ TCP listener live
```

### 1.5 Bypass suffix short-circuits

```bash
💻 dig @$VPS_IP 1.1.1.1.in-addr.arpa PTR +short
# → one.one.one.one.  ✅ .arpa queries not filtered
```

### 1.6 AAAA on blocked domain returns empty NOERROR

```bash
💻 dig @$VPS_IP paypa1.com AAAA
# → status: NOERROR, ANSWER: 0, not SERVFAIL  ✅ IPv6 falls through to A
```

---

## 2. DNS-over-HTTPS

### 2.1 DoH endpoint alive

```bash
💻 curl -s https://$DNS_HOSTNAME/health
# → {"status":"ok"}
```

### 2.2 DoH GET (RFC 8484 base64url encoded query)

```bash
💻 Q='q80BAAABAAAAAAAAB2V4YW1wbGUDY29tAAABAAE'   # dns query for example.com A
💻 curl -s -H 'accept: application/dns-message' \
       "https://$DNS_HOSTNAME/dns-query?dns=$Q" --output - | xxd | head
# → binary DNS response, contains answer  ✅
```

### 2.3 DoH POST (mobile clients)

```bash
💻 python3 -c "
import base64, urllib.request, ssl
q = base64.urlsafe_b64decode('q80BAAABAAAAAAAAB2V4YW1wbGUDY29tAAABAAE=')
r = urllib.request.Request(
    'https://$DNS_HOSTNAME/dns-query',
    data=q,
    headers={'Content-Type': 'application/dns-message'},
)
print('bytes:', len(urllib.request.urlopen(r).read()))"
# → bytes: >30  ✅
```

---

## 3. AI scanner end-to-end

### 3.1 Unknown domain gets enqueued

```bash
💻 dig @$VPS_IP brand-new-domain-$(date +%s).com +short   # fast, real answer
🖥️ docker compose exec redis redis-cli -a "$REDIS_PASSWORD" \
      LRANGE scamlens:scan_queue 0 -1
# → shows the domain you just resolved
```

### 3.2 Watch scanner logs

```bash
🖥️ docker compose logs --tail=30 ai_scanner
# Expect: scan_start → scan_done verdict=safe|suspicious|scam
```

### 3.3 Verdict cached

```bash
🖥️ docker compose exec redis redis-cli -a "$REDIS_PASSWORD" \
      GET "verdict:brand-new-domain-<ts>.com"
# → JSON: {"verdict":"safe","risk_score":..., ...}
```

### 3.4 Verdict persisted to Postgres

```bash
🖥️ docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
      -c "SELECT domain,verdict,risk_score,confidence,source,updated_at
          FROM domain_verdicts ORDER BY updated_at DESC LIMIT 5;"
```

### 3.5 Force a scam verdict (sanity check the prompt)

```bash
🖥️ docker compose exec redis redis-cli -a "$REDIS_PASSWORD" \
      LPUSH scamlens:scan_queue "paypal-security-alert.xyz"
# Wait ~30s
🖥️ docker compose exec redis redis-cli -a "$REDIS_PASSWORD" \
      GET "verdict:paypal-security-alert.xyz"
# → verdict should be 'scam' or 'suspicious' with reasoning in JSON
```

---

## 4. API endpoints

```bash
API="https://$DOMAIN/api"

💻 curl -s $API/stats | jq
# total_blocked, blocked_today, unique_domains, top_domains[], daily[7]

💻 curl -s "$API/blocked?page=1&page_size=5&q=paypa" | jq '.items[0]'

💻 curl -s $API/check/paypa1.com | jq
# verdict:"scam", source:"blocklist", cached:true

💻 curl -sX POST $API/report \
      -H 'content-type: application/json' \
      -d '{"domain":"https://fake-bank.xyz/login","note":"test"}' | jq
# {id, domain:"fake-bank.xyz", status:"pending"}

💻 curl -so /tmp/test.mobileconfig -w '%{content_type} %{http_code}\n' \
      $API/setup/ios
# application/x-apple-aspen-config 200

💻 plutil -lint /tmp/test.mobileconfig   # macOS
# OR:
💻 python3 -c "import plistlib; plistlib.load(open('/tmp/test.mobileconfig','rb'))"

💻 curl -s $API/setup/android | jq
💻 curl -s $API/setup/desktop | jq
```

### 4.1 Rate limits

```bash
💻 for i in $(seq 1 35); do
      curl -so /dev/null -w '%{http_code} ' $API/check/example.com
   done
# Expect mostly 200, then 429 after limit (30/hour)
```

---

## 5. Block page

Simulates what a user sees when their browser hits the sinkholed IP.

```bash
💻 curl -s -H "Host: paypa1.com" http://$VPS_IP/ | grep -i "scamlens"
# → block page HTML served; 'paypa1.com' rendered on it

# Same thing in a real browser:
💻 open "http://paypa1.com"    # requires DNS pointed at ScamLens
```

---

## 6. Frontend pages

Visit each and confirm it renders without console errors:

- `https://$DOMAIN/` — homepage, counter shows live number
- `https://$DOMAIN/dashboard` — bar chart, top domains, searchable table
- `https://$DOMAIN/setup` — platform hub
- `https://$DOMAIN/setup/android`
- `https://$DOMAIN/setup/ios` — "Download profile" button + QR visible
- `https://$DOMAIN/setup/windows`
- `https://$DOMAIN/setup/macos`
- `https://$DOMAIN/setup/linux`
- `https://$DOMAIN/setup/router` — vendor table visible
- `https://$DOMAIN/report` — form submits without error
- `https://$DOMAIN/about`

Dashboard smoke: dig a blocked domain, wait 10s, the "Blocked today" counter increments.

---

## 7. iOS / macOS profile install

📱 On iPhone:
1. Open Safari → `https://$DOMAIN/setup/ios` → tap **Download profile**.
2. Settings → General → VPN & Device Management → "ScamLens Protection" → Install.
3. Settings → General → VPN & Device Management → confirm profile present.
4. Open Safari and try `http://paypa1.com` — ScamLens block page appears.
5. Regression: a normal site like `https://apple.com` still loads.

📱 On macOS:
1. Download profile from the same URL (Safari).
2. System Settings → Privacy & Security → Profiles → install.
3. Verify: `dig paypa1.com` → resolves to `$VPS_IP`.

---

## 8. Submit + confirm user report

```bash
# 1. user submits
💻 curl -sX POST $API/report -H 'content-type: application/json' \
       -d '{"domain":"new-scam.example"}' | jq

# 2. operator promotes report → confirmed
🖥️ docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
      -c "UPDATE user_reports SET status='confirmed' WHERE domain='new-scam.example';"

# 3. wait <= 5 minutes for DNS blocklist refresh OR restart to force it:
🖥️ docker compose restart dns_server

# 4. verify blocked
💻 dig @$VPS_IP new-scam.example +short
# → $VPS_IP  ✅
```

---

## 9. Resilience

### 9.1 Container restart

```bash
🖥️ docker compose kill ai_scanner
🖥️ docker compose ps          # scanner shows 'Exited', compose auto-restarts it
🖥️ docker compose logs --tail=5 ai_scanner
```

### 9.2 Postgres outage — DNS hot path keeps working

```bash
🖥️ docker compose stop postgres
💻 dig @$VPS_IP example.com +short    # ✅ still resolves
💻 dig @$VPS_IP paypa1.com +short     # ✅ still blocked (in-memory set)
🖥️ docker compose start postgres
```

### 9.3 Redis outage — falls back to seed set

```bash
🖥️ docker compose stop redis
💻 dig @$VPS_IP paypa1.com +short     # ✅ still blocked (static blocklist)
💻 dig @$VPS_IP example.com +short    # ✅ upstream forwarding still works
🖥️ docker compose start redis
```

### 9.4 Host reboot

```bash
🖥️ reboot
# After boot:
🖥️ systemctl status scamlens.service  # active (exited)
🖥️ docker compose ps                   # everything up
```

### 9.5 Cert renewal dry-run

```bash
🖥️ certbot renew --dry-run
# → "Congratulations, all simulated renewals succeeded"
# Confirms the deploy hook (nginx reload) is wired correctly.
```

---

## 10. Load / perf (optional)

```bash
# dnsperf — install: apt install dnsperf
💻 cat > queries.txt <<EOF
example.com A
cloudflare.com A
google.com A
paypa1.com A
faceb00k-login.com A
EOF
💻 dnsperf -s $VPS_IP -d queries.txt -l 30 -c 50 -Q 2000

# Expected on a 2-vCPU VPS:
#   ~3-6k QPS for cached/blocked answers
#   ~500-1k QPS for upstream-forwarded (bounded by upstream RTT)
# Ensure no 5xx responses on the API during the test:
💻 while true; do curl -so /dev/null -w '%{http_code}\n' \
      https://$DOMAIN/api/stats; sleep 1; done
```

---

## 11. Teardown (optional)

```bash
🖥️ systemctl stop scamlens.service
🖥️ systemctl disable scamlens.service
🖥️ cd /opt/scamlens && docker compose down -v    # -v wipes volumes
🖥️ rm -rf /opt/scamlens
🖥️ rm /etc/nginx/sites-enabled/scamlens.conf \
      /etc/nginx/sites-available/scamlens.conf \
      /etc/systemd/system/scamlens.service
🖥️ certbot delete --cert-name $DOMAIN --non-interactive
🖥️ certbot delete --cert-name $DNS_HOSTNAME --non-interactive
🖥️ systemctl reload nginx
🖥️ ufw disable                                    # only if you enabled it
```

---

## 12. Exit criteria

All of the following must be green before declaring the deploy done:

- [ ] `dig @$VPS_IP paypa1.com` → `$VPS_IP`
- [ ] `dig @$VPS_IP example.com` → real IP
- [ ] `curl https://$DNS_HOSTNAME/dns-query?dns=<q>` → binary DNS response
- [ ] `curl https://$DOMAIN/api/stats` → JSON with 7 daily entries
- [ ] Homepage counter reflects live Postgres row count
- [ ] Scanner logs show at least one `scan_done verdict=...` entry
- [ ] iOS device install test: scam domain blocked, safe site loads
- [ ] `certbot renew --dry-run` passes
- [ ] Host reboot restores the stack via systemd
