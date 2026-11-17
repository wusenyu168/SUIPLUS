#!/usr/bin/env bash
# Map local dials to panel public IPv4:webPort -> 127.0.0.1:webPort (hairpin).
set -euo pipefail

DB="${SUI_DB:-/usr/local/s-ui/db/s-ui.db}"
PORT="$(python3 - <<'PY'
import sqlite3
db=sqlite3.connect("/usr/local/s-ui/db/s-ui.db")
print(next((v for k,v in db.execute("select key,value from settings") if k=="webPort"), "2095"))
PY
)"
DOMAIN="$(python3 - <<'PY'
import sqlite3
db=sqlite3.connect("/usr/local/s-ui/db/s-ui.db")
print(next((v for k,v in db.execute("select key,value from settings") if k=="webDomain"), ""))
PY
)"

IPS=()
if [[ -n "$DOMAIN" ]]; then
  while read -r ip; do
    [[ -n "$ip" ]] && IPS+=("$ip")
  done < <(python3 - <<PY
import socket
d="$DOMAIN".strip()
if not d:
    raise SystemExit
try:
    for fam,_,_,_,sa in socket.getaddrinfo(d, None, socket.AF_INET):
        print(sa[0])
except Exception:
    pass
PY
)
fi

while read -r ip; do
  [[ -n "$ip" ]] && IPS+=("$ip")
done < <(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' || true)

DEST="127.0.0.1:${PORT}"
declare -A SEEN=()
for ip in "${IPS[@]}"; do
  [[ -n "${SEEN[$ip]:-}" ]] && continue
  SEEN[$ip]=1
  case "$ip" in
    127.*|10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[0-1].*) continue ;;
  esac
  if ! iptables -t nat -C OUTPUT -d "${ip}/32" -p tcp --dport "$PORT" -j DNAT --to-destination "$DEST" 2>/dev/null; then
    iptables -t nat -I OUTPUT -d "${ip}/32" -p tcp --dport "$PORT" -j DNAT --to-destination "$DEST"
    echo "hairpin added ${ip}:${PORT} -> ${DEST}"
  else
    echo "hairpin ok ${ip}:${PORT}"
  fi
done
