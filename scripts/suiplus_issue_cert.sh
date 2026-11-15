#!/bin/bash
# One-click ACME cert: use webDomain, or derive from cfDdnsRecord + cfDdnsZone.
# On success writes webDomain / webCertFile / webKeyFile (and sub*) into settings.
set -euo pipefail
# s-ui systemd 常不带 HOME，会导致 acme.sh 装到 /.acme.sh
export HOME=/root
export USER=root
DB="${SUI_DB:-/usr/local/s-ui/db/s-ui.db}"
CERT_DIR="${SUIPLUS_CERT_DIR:-/usr/local/s-ui/cert}"
ACME_HOME="${ACME_HOME:-/root/.acme.sh}"
mkdir -p "$CERT_DIR" "$ACME_HOME"

find_acme() {
  for p in "$ACME_HOME/acme.sh" /root/.acme.sh/acme.sh /.acme.sh/acme.sh; do
    if [[ -x "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

ensure_acme() {
  local email_zone="$1"
  local acme
  if acme="$(find_acme)"; then
    echo "$acme"
    return 0
  fi
  echo "[suiplus-cert] installing acme.sh into ${ACME_HOME} ..."
  curl -fsSL https://get.acme.sh | HOME=/root USER=root sh -s email="admin@${email_zone}" || true
  # installer may still drop into /.acme.sh if env ignored — relocate
  if [[ ! -x "$ACME_HOME/acme.sh" && -x /.acme.sh/acme.sh ]]; then
    mkdir -p "$ACME_HOME"
    cp -a /.acme.sh/. "$ACME_HOME/" || true
  fi
  if acme="$(find_acme)"; then
    echo "$acme"
    return 0
  fi
  echo "[suiplus-cert] acme.sh install failed" >&2
  return 1
}

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
  export CF_Email="admin@${ZONE:-$DOMAIN}"
  email_zone="${ZONE:-$DOMAIN}"
  ACME_BIN="$(ensure_acme "$email_zone")" || exit 1
  echo "[suiplus-cert] using acme=$ACME_BIN"
  # #region agent log
  echo "[suiplus-cert] debug HOME=$HOME ACME_BIN=$ACME_BIN" >> /usr/local/s-ui/suiplus-seed-debug.ndjson || true
  # #endregion
  "$ACME_BIN" --set-default-ca --server letsencrypt || true
  "$ACME_BIN" --issue --dns dns_cf -d "$DOMAIN" --force || exit 1
  "$ACME_BIN" --install-cert -d "$DOMAIN" \
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
