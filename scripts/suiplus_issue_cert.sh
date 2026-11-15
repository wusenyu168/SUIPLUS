#!/bin/bash
# One-click ACME cert: use webDomain, or derive from cfDdnsRecord + cfDdnsZone.
# On success writes webDomain / webCertFile / webKeyFile (and sub*) into settings.
set -euo pipefail
DB="${SUI_DB:-/usr/local/s-ui/db/s-ui.db}"
CERT_DIR="${SUIPLUS_CERT_DIR:-/usr/local/s-ui/cert}"
mkdir -p "$CERT_DIR"

get_setting() {
  sqlite3 "$DB" "SELECT value FROM settings WHERE key='$1' LIMIT 1;" 2>/dev/null || true
}

upsert_setting() {
  local k="$1" v="$2"
  local n
  n=$(sqlite3 "$DB" "SELECT COUNT(*) FROM settings WHERE key='$k';")
  if [[ "$n" == "0" ]]; then
    sqlite3 "$DB" "INSERT INTO settings(key,value) VALUES('$k','$v');"
  else
    sqlite3 "$DB" "UPDATE settings SET value='$v' WHERE key='$k';"
  fi
}

DOMAIN="$(get_setting webDomain)"
DOMAIN="$(echo -n "$DOMAIN" | tr -d '\r\n ')"
TOKEN="$(get_setting cfDdnsToken)"
TOKEN="${CF_API_TOKEN:-$TOKEN}"
ZONE="$(get_setting cfDdnsZone)"
ZONE="$(echo -n "$ZONE" | tr -d '\r\n ')"
RECORD="$(get_setting cfDdnsRecord)"
RECORD="$(echo -n "$RECORD" | tr -d '\r\n ')"

# Derive panel domain from DDNS fields when webDomain empty
if [[ -z "$DOMAIN" ]]; then
  if [[ -n "$ZONE" ]]; then
    if [[ -z "$RECORD" || "$RECORD" == "@" ]]; then
      DOMAIN="$ZONE"
    elif [[ "$RECORD" == *.* ]]; then
      # already FQDN mistakenly filled as record
      DOMAIN="$RECORD"
    else
      DOMAIN="${RECORD}.${ZONE}"
    fi
    upsert_setting "webDomain" "$DOMAIN"
    upsert_setting "subDomain" "$DOMAIN"
    echo "[suiplus-cert] auto-filled webDomain=${DOMAIN} from DDNS fields"
  fi
fi

if [[ -z "$DOMAIN" ]]; then
  echo "[suiplus-cert] webDomain 为空：请在「界面」填域名，或在 SUIPLUS 填 Zone+记录名后再申请" >&2
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

upsert_setting "webDomain" "$DOMAIN"
upsert_setting "subDomain" "$DOMAIN"
upsert_setting "webCertFile" "$CERT_FILE"
upsert_setting "webKeyFile" "$KEY_FILE"
upsert_setting "subCertFile" "$CERT_FILE"
upsert_setting "subKeyFile" "$KEY_FILE"

echo "[suiplus-cert] bound webDomain=${DOMAIN}"
echo "[suiplus-cert] bound webCertFile=${CERT_FILE}"
echo "[suiplus-cert] bound webKeyFile=${KEY_FILE}"
# machine-readable line for API
echo "SUIPLUS_CERT_RESULT domain=${DOMAIN} cert=${CERT_FILE} key=${KEY_FILE}"
