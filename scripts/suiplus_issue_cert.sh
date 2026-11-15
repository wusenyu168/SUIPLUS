#!/bin/bash
# One-click ACME cert for panel domain (must already be set in settings.webDomain).
set -euo pipefail
DB="${SUI_DB:-/usr/local/s-ui/db/s-ui.db}"
CERT_DIR="${SUIPLUS_CERT_DIR:-/usr/local/s-ui/cert}"
mkdir -p "$CERT_DIR"

get_setting() {
  sqlite3 "$DB" "SELECT value FROM settings WHERE key='$1' LIMIT 1;" 2>/dev/null || true
}

DOMAIN="$(get_setting webDomain)"
DOMAIN="$(echo -n "$DOMAIN" | tr -d '\r\n ')"
TOKEN="$(get_setting cfDdnsToken)"
TOKEN="${CF_API_TOKEN:-$TOKEN}"
ZONE="$(get_setting cfDdnsZone)"
ZONE="$(echo -n "$ZONE" | tr -d '\r\n ')"

if [[ -z "$DOMAIN" ]]; then
  echo "[suiplus-cert] webDomain 为空：请先在面板「设置→域名」手动绑定本机域名后再申请证书" >&2
  exit 1
fi

CERT_FILE="${CERT_DIR}/${DOMAIN}.crt"
KEY_FILE="${CERT_DIR}/${DOMAIN}.key"

echo "[suiplus-cert] domain=${DOMAIN}"

if [[ -n "$TOKEN" ]]; then
  export CF_Token="$TOKEN"
  if [[ ! -x /root/.acme.sh/acme.sh ]]; then
    email_zone="${ZONE:-$DOMAIN}"
    curl -fsSL https://get.acme.sh | sh -s email="admin@${email_zone}" || true
  fi
  /root/.acme.sh/acme.sh --set-default-ca --server letsencrypt || true
  /root/.acme.sh/acme.sh --issue --dns dns_cf -d "$DOMAIN" --force || exit 1
  /root/.acme.sh/acme.sh --install-cert -d "$DOMAIN" \
    --fullchain-file "$CERT_FILE" \
    --key-file "$KEY_FILE" || exit 1
else
  echo "[suiplus-cert] 无 CF Token；尝试 HTTP-01（需 80 端口开放）" >&2
  if ! command -v certbot >/dev/null 2>&1; then
    apt-get update -y >/dev/null 2>&1 || true
    apt-get install -y -q certbot >/dev/null 2>&1 || true
  fi
  certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos \
    --register-unsafely-without-email --preferred-challenges http || exit 1
  LIVE="/etc/letsencrypt/live/${DOMAIN}"
  cp -f "${LIVE}/fullchain.pem" "$CERT_FILE"
  cp -f "${LIVE}/privkey.pem" "$KEY_FILE"
fi

chmod 600 "$KEY_FILE" 2>/dev/null || true
chmod 644 "$CERT_FILE" 2>/dev/null || true

for kv in "webCertFile|${CERT_FILE}" "webKeyFile|${KEY_FILE}" "subCertFile|${CERT_FILE}" "subKeyFile|${KEY_FILE}"; do
  k="${kv%%|*}"; v="${kv#*|}"
  n=$(sqlite3 "$DB" "SELECT COUNT(*) FROM settings WHERE key='$k';")
  if [[ "$n" == "0" ]]; then
    sqlite3 "$DB" "INSERT INTO settings(key,value) VALUES('$k','$v');"
  else
    sqlite3 "$DB" "UPDATE settings SET value='$v' WHERE key='$k';"
  fi
done

echo "[suiplus-cert] bound webCertFile=${CERT_FILE}"
echo "[suiplus-cert] restart panel to apply HTTPS: systemctl restart s-ui"
