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

ensure_cron() {
  if command -v crontab >/dev/null 2>&1; then
    return 0
  fi
  echo "[suiplus-cert] installing cron (required by acme.sh renew) ..." >&2
  apt-get update -y >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q cron >/dev/null 2>&1 || true
  systemctl enable --now cron 2>/dev/null || service cron start 2>/dev/null || true
}

ensure_acme() {
  local email_zone="$1"
  local acme
  # IMPORTANT: only the acme path may go to stdout (caller captures it)
  if acme="$(find_acme)"; then
    echo "$acme"
    return 0
  fi
  ensure_cron || true
  echo "[suiplus-cert] installing acme.sh into ${ACME_HOME} ..." >&2
  # --force: allow install even if crontab pre-check still fails
  # installer chatter must not pollute stdout (would break ACME_BIN="$(ensure_acme)")
  curl -fsSL https://get.acme.sh | HOME=/root USER=root sh -s email="admin@${email_zone}" --force >&2 || true
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

# Prefer python3 sqlite (sqlite3 CLI often missing on minimal VPS images)
get_setting() {
  local key="$1"
  python3 - "$DB" "$key" <<'PY' 2>/dev/null || true
import sqlite3,sys
db,key=sys.argv[1],sys.argv[2]
try:
  con=sqlite3.connect(db)
  row=con.execute("SELECT value FROM settings WHERE key=? LIMIT 1",(key,)).fetchone()
  con.close()
  print("" if not row or row[0] is None else row[0], end="")
except Exception:
  pass
PY
}

upsert_setting() {
  local k="$1" v="$2"
  python3 - "$DB" "$k" "$v" <<'PY'
import sqlite3,sys
db,k,v=sys.argv[1],sys.argv[2],sys.argv[3]
con=sqlite3.connect(db)
cur=con.execute("SELECT COUNT(*) FROM settings WHERE key=?",(k,))
n=cur.fetchone()[0]
if n==0:
  con.execute("INSERT INTO settings(key,value) VALUES(?,?)",(k,v))
else:
  con.execute("UPDATE settings SET value=? WHERE key=?",(v,k))
con.commit()
con.close()
PY
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
    # ACME / browsers expect lowercase FQDN
    DOMAIN="$(echo -n "$DOMAIN" | tr 'A-Z' 'a-z')"
    upsert_setting "webDomain" "$DOMAIN"
    upsert_setting "subDomain" "$DOMAIN"
    echo "[suiplus-cert] auto-filled webDomain=${DOMAIN} from DDNS fields"
  fi
else
  DOMAIN="$(echo -n "$DOMAIN" | tr 'A-Z' 'a-z')"
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
  # capture only path line (ignore accidental stdout noise)
  ACME_BIN="$(ensure_acme "$email_zone" | tail -n1 | tr -d '\r')" || exit 1
  ACME_BIN="$(echo -n "$ACME_BIN" | tr -d '\r\n')"
  if [[ ! -x "$ACME_BIN" ]]; then
    echo "[suiplus-cert] acme path invalid: ${ACME_BIN}" >&2
    exit 1
  fi
  echo "[suiplus-cert] using acme=$ACME_BIN"
  "$ACME_BIN" --set-default-ca --server letsencrypt || true
  if ! "$ACME_BIN" --issue --dns dns_cf -d "$DOMAIN" --force; then
    exit 1
  fi
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
