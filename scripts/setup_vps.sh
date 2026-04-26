#!/usr/bin/env bash
# ScamLens VPS bootstrap — Ubuntu 22.04 LTS.
#
# Idempotent: safe to re-run. Each step short-circuits if already satisfied.
#
# Expected layout before running:
#   /opt/scamlens/          (git clone of this repo)
#   /opt/scamlens/.env      (filled in from .env.example)
#
# Usage:
#   sudo bash /opt/scamlens/scripts/setup_vps.sh [--skip-certs] [--skip-ufw]

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/scamlens}"
NGINX_CONF_SRC="$APP_DIR/nginx/scamlens.conf"
NGINX_SITE="/etc/nginx/sites-available/scamlens.conf"
NGINX_LINK="/etc/nginx/sites-enabled/scamlens.conf"
SYSTEMD_UNIT_SRC="$APP_DIR/scripts/systemd/scamlens.service"
SYSTEMD_UNIT="/etc/systemd/system/scamlens.service"
CERTBOT_WEBROOT="/var/www/certbot"

SKIP_CERTS=0
SKIP_UFW=0
for arg in "$@"; do
  case "$arg" in
    --skip-certs) SKIP_CERTS=1 ;;
    --skip-ufw)   SKIP_UFW=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

log() { echo -e "\033[1;34m[scamlens]\033[0m $*"; }
err() { echo -e "\033[1;31m[scamlens]\033[0m $*" >&2; }

# --------------------------- preflight ---------------------------------------

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "Run as root: sudo bash $0"
    exit 1
  fi
}

require_ubuntu() {
  if ! grep -q "Ubuntu 22" /etc/os-release; then
    err "Target is Ubuntu 22.04 LTS. Current:"
    cat /etc/os-release | grep PRETTY_NAME || true
    read -rp "Continue anyway? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || exit 1
  fi
}

require_env() {
  if [[ ! -f "$APP_DIR/.env" ]]; then
    err "Missing $APP_DIR/.env. Copy .env.example and fill it in."
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$APP_DIR/.env"
  set +a

  : "${DOMAIN:?DOMAIN not set in .env}"
  : "${DNS_HOSTNAME:?DNS_HOSTNAME not set in .env}"
  : "${BLOCK_PAGE_IP:?BLOCK_PAGE_IP not set in .env}"
  if [[ -z "${LE_EMAIL:-}" && $SKIP_CERTS -eq 0 ]]; then
    err "LE_EMAIL not set in .env (needed for Let's Encrypt). "
    err "Add: LE_EMAIL=admin@yourdomain.com   (or rerun with --skip-certs)"
    exit 1
  fi
}

# --------------------------- packages ----------------------------------------

install_apt_base() {
  log "Installing base packages…"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y \
    ca-certificates curl gnupg lsb-release \
    nginx certbot python3-certbot-nginx \
    ufw gettext-base jq
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker + Compose plugin present."
    return
  fi
  log "Installing Docker Engine + Compose plugin…"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io \
                     docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
}

# --------------------------- port 53 sanity ----------------------------------

ensure_port_53_free() {
  # Ubuntu ships systemd-resolved on 127.0.0.53; that does NOT conflict with
  # Docker binding 0.0.0.0:53. But some setups set DNSStubListener=yes on all
  # interfaces. Detect and fix.
  if ss -lntu | awk '{print $5}' | grep -qE '(^|[^0-9])(0\.0\.0\.0|\*):53($|[^0-9])'; then
    err "Something is already bound to 0.0.0.0:53. Resolve this before continuing:"
    ss -lntup | grep ':53 ' || true
    exit 1
  fi
  log "Port 53 is available for ScamLens."
}

# --------------------------- firewall ----------------------------------------

configure_firewall() {
  if [[ $SKIP_UFW -eq 1 ]]; then
    log "Skipping ufw (--skip-ufw)."
    return
  fi
  log "Configuring ufw…"
  ufw --force reset >/dev/null
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow 22/tcp           comment 'ssh'
  ufw allow 53/tcp           comment 'dns-tcp'
  ufw allow 53/udp           comment 'dns-udp'
  ufw allow 80/tcp           comment 'http'
  ufw allow 443/tcp          comment 'https'
  ufw --force enable
  ufw status verbose
}

# --------------------------- nginx + certs -----------------------------------

render_nginx_conf() {
  mkdir -p "$CERTBOT_WEBROOT"
  log "Rendering nginx config → $NGINX_SITE"
  export DOMAIN DNS_HOSTNAME
  envsubst '${DOMAIN} ${DNS_HOSTNAME}' < "$NGINX_CONF_SRC" > "$NGINX_SITE"
  ln -sf "$NGINX_SITE" "$NGINX_LINK"
  # Disable the distro default if present
  rm -f /etc/nginx/sites-enabled/default
}

obtain_certs() {
  if [[ $SKIP_CERTS -eq 1 ]]; then
    log "Skipping certificate issuance (--skip-certs)."
    return
  fi

  # Certbot needs nginx serving the webroot challenge. Reload with a cert-less
  # scratch config first, then upgrade to the SSL config after issuance.
  log "Preparing HTTP-only nginx for ACME challenge…"
  cat > /etc/nginx/sites-available/scamlens-bootstrap.conf <<EOF
server {
    listen 80 default_server;
    server_name $DOMAIN $DNS_HOSTNAME;
    location /.well-known/acme-challenge/ { root $CERTBOT_WEBROOT; }
    location / { return 200 'ok'; add_header Content-Type text/plain; }
}
EOF
  ln -sf /etc/nginx/sites-available/scamlens-bootstrap.conf \
         /etc/nginx/sites-enabled/scamlens-bootstrap.conf
  rm -f "$NGINX_LINK" # swap out main config during bootstrap
  nginx -t && systemctl reload nginx

  # Main domain: HTTP-01 webroot (no wildcard needed).
  if [[ -d "/etc/letsencrypt/live/$DOMAIN" ]]; then
    log "Cert for $DOMAIN already present."
  else
    log "Requesting cert for $DOMAIN…"
    certbot certonly \
      --webroot -w "$CERTBOT_WEBROOT" \
      --non-interactive --agree-tos \
      --email "$LE_EMAIL" \
      -d "$DOMAIN"
  fi

  # DNS hostname: wildcard via Cloudflare DNS-01 (covers per-user subdomains).
  if [[ -d "/etc/letsencrypt/live/$DNS_HOSTNAME" ]]; then
    log "Cert for $DNS_HOSTNAME (+ wildcard) already present."
  else
    if [[ ! -f /etc/letsencrypt/cloudflare.ini ]]; then
      err "Missing /etc/letsencrypt/cloudflare.ini — create with:"
      err "  dns_cloudflare_api_token = <CF_TOKEN_WITH_DNS_EDIT_FOR_ZONE>"
      err "  chmod 600 /etc/letsencrypt/cloudflare.ini"
      exit 1
    fi
    apt-get install -y python3-certbot-dns-cloudflare
    log "Requesting wildcard cert for $DNS_HOSTNAME + *.${DNS_HOSTNAME}…"
    certbot certonly \
      --dns-cloudflare \
      --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
      --dns-cloudflare-propagation-seconds 30 \
      --non-interactive --agree-tos \
      --email "$LE_EMAIL" \
      -d "$DNS_HOSTNAME" -d "*.${DNS_HOSTNAME}"
  fi

  # Remove bootstrap, enable real config
  rm -f /etc/nginx/sites-enabled/scamlens-bootstrap.conf
  ln -sf "$NGINX_SITE" "$NGINX_LINK"
  nginx -t && systemctl reload nginx

  # Certbot renews twice a day via systemd timer; wire a deploy hook so the
  # renewed cert gets picked up without manual intervention.
  install -d /etc/letsencrypt/renewal-hooks/deploy
  cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
  chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
  log "HTTPS live. Certbot auto-renewal + nginx reload hook installed."
}

# --------------------------- systemd unit ------------------------------------

install_systemd_unit() {
  log "Installing systemd unit → $SYSTEMD_UNIT"
  install -m 0644 "$SYSTEMD_UNIT_SRC" "$SYSTEMD_UNIT"
  systemctl daemon-reload
  systemctl enable scamlens.service
}

# --------------------------- compose up --------------------------------------

bring_stack_up() {
  log "Building + starting Docker Compose stack…"
  cd "$APP_DIR"
  docker compose pull --ignore-pull-failures || true
  docker compose build
  docker compose up -d
  log "Waiting for API health…"
  for i in $(seq 1 30); do
    if curl -fs http://127.0.0.1:8000/health >/dev/null; then
      log "API is healthy."
      break
    fi
    sleep 2
  done
  docker compose ps
}

seed_blocklist() {
  log "Seeding starter blocklist…"
  docker compose exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    < "$APP_DIR/scripts/seed_blocklist.sql" >/dev/null
  local count
  count=$(docker compose exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT count(*) FROM blocklist_seed")
  log "  blocklist_seed rows: $count"
}

# --------------------------- smoke test --------------------------------------

smoke_test() {
  log "Running smoke tests…"
  echo -n "  DNS UDP:  "
  dig @127.0.0.1 example.com +time=3 +tries=1 +short | head -1 || echo "FAIL"
  echo -n "  API:      "
  curl -fs http://127.0.0.1:8000/health && echo ""
  if [[ $SKIP_CERTS -eq 0 ]]; then
    echo -n "  Site:     "
    curl -fsI "https://$DOMAIN/" | head -1 || echo "FAIL"
    echo -n "  DoH:      "
    curl -fsI "https://$DNS_HOSTNAME/health" | head -1 || echo "FAIL"
  fi
}

# --------------------------- main --------------------------------------------

main() {
  require_root
  require_ubuntu
  require_env
  install_apt_base
  install_docker
  ensure_port_53_free
  configure_firewall
  render_nginx_conf
  obtain_certs
  install_systemd_unit
  bring_stack_up
  seed_blocklist
  smoke_test
  log "Done. Point devices at DNS=$BLOCK_PAGE_IP (plain) or https://$DNS_HOSTNAME/dns-query (DoH)."
}

main "$@"
