#!/usr/bin/env bash
# Align with suoha-source: cloudflared quick tunnel + path router → local WS inbounds
# Reuse rules (avoid killing a live SNI):
#   - If cloudflared alive + argo_domain.txt valid → keep tunnel (never mint new hostname)
#   - If only router is down → restart router only
#   - FORCE_ARGO_RESTART=1 → tear down and create a new Quick Tunnel domain
set +e
ARGO_DIR=/usr/local/s-ui/argo
ENTRY_PORT=10079
VLESS_PORT=10080
TROJAN_PORT=10081
VLESS_PATH=/suoha-vless
TROJAN_PATH=/suoha-trojan
mkdir -p "$ARGO_DIR"
cd "$ARGO_DIR"

arch=$(uname -m)
case "$arch" in
  x86_64|amd64) cf_arch=linux-amd64 ;;
  aarch64|arm64) cf_arch=linux-arm64 ;;
  *) cf_arch=linux-amd64 ;;
esac

if [ ! -x "$ARGO_DIR/cloudflared" ]; then
  curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-${cf_arch}" -o "$ARGO_DIR/cloudflared"
  chmod +x "$ARGO_DIR/cloudflared"
fi

cf_alive=0
router_alive=0
argo_saved=""
if [ -f "$ARGO_DIR/argo_domain.txt" ]; then
  argo_saved=$(tr -d ' \n\r' < "$ARGO_DIR/argo_domain.txt")
fi
if [ -f "$ARGO_DIR/cf.pid" ] && kill -0 "$(tr -d ' \n\r' < "$ARGO_DIR/cf.pid" 2>/dev/null)" 2>/dev/null; then
  cf_alive=1
fi
if [ -f "$ARGO_DIR/router.pid" ] && kill -0 "$(tr -d ' \n\r' < "$ARGO_DIR/router.pid" 2>/dev/null)" 2>/dev/null; then
  router_alive=1
fi

write_router() {
cat > "$ARGO_DIR/argo_router.py" <<PY
import asyncio
ENTRY_PORT = ${ENTRY_PORT}
VLESS_PORT = ${VLESS_PORT}
TROJAN_PORT = ${TROJAN_PORT}
VLESS_PATH = "${VLESS_PATH}"
TROJAN_PATH = "${TROJAN_PATH}"

async def relay(reader, writer):
    try:
        while True:
            chunk = await reader.read(32768)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass

async def handle_client(client_reader, client_writer):
    try:
        head = await asyncio.wait_for(client_reader.readuntil(b"\\r\\n\\r\\n"), timeout=10.0)
        first_line = head.split(b"\\r\\n", 1)[0]
        target_port = VLESS_PORT
        if TROJAN_PATH.encode() in first_line:
            target_port = TROJAN_PORT
        upstream_reader, upstream_writer = await asyncio.open_connection("127.0.0.1", target_port)
        upstream_writer.write(head)
        await upstream_writer.drain()
        await asyncio.gather(
            relay(client_reader, upstream_writer),
            relay(upstream_reader, client_writer),
        )
    except Exception:
        try:
            client_writer.close()
        except Exception:
            pass

async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", ENTRY_PORT)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
PY
}

start_router() {
  write_router
  pkill -f "argo_router.py" >/dev/null 2>&1 || true
  sleep 1
  setsid nohup python3 "$ARGO_DIR/argo_router.py" >"$ARGO_DIR/router.log" 2>&1 < /dev/null &
  echo $! > "$ARGO_DIR/router.pid"
  sleep 1
}

# Force: kill tunnel + domain (new SNI)
if [ "${FORCE_ARGO_RESTART:-0}" = "1" ]; then
  echo "ARGO_FORCE_RESTART=1 killing old tunnel/router"
  pkill -f "argo_router.py" >/dev/null 2>&1 || true
  pkill -f "cloudflared tunnel --url" >/dev/null 2>&1 || true
  rm -f "$ARGO_DIR/cf.pid" "$ARGO_DIR/router.pid" "$ARGO_DIR/argo_domain.txt"
  sleep 1
  cf_alive=0
  router_alive=0
  argo_saved=""
fi

# Live tunnel + valid domain: never recreate cloudflared (keeps SNI)
if [ "$cf_alive" = "1" ] && [ -n "$argo_saved" ] && echo "$argo_saved" | grep -q '\.'; then
  if [ "$router_alive" != "1" ]; then
    echo "ARGO_ROUTER_RESTART (keep tunnel $argo_saved)"
    start_router
  fi
  echo "ARGO_OK $argo_saved (reuse)"
  exit 0
fi

# Need a new Quick Tunnel
pkill -f "argo_router.py" >/dev/null 2>&1 || true
pkill -f "cloudflared tunnel --url" >/dev/null 2>&1 || true
sleep 1
start_router

rm -f "$ARGO_DIR/argo_main.log"
: > "$ARGO_DIR/argo_main.log"
setsid nohup "$ARGO_DIR/cloudflared" tunnel --url "http://127.0.0.1:${ENTRY_PORT}" --no-autoupdate --edge-ip-version 4 --protocol http2 --loglevel info >>"$ARGO_DIR/argo_main.log" 2>&1 < /dev/null &
echo $! > "$ARGO_DIR/cf.pid"

argo=""
for i in $(seq 1 55); do
  sleep 1
  argo=$(grep -oE '[a-zA-Z0-9.-]+\.trycloudflare\.com' "$ARGO_DIR/argo_main.log" 2>/dev/null | head -n1)
  [ -n "$argo" ] && break
  if [ "$i" = "22" ] || [ "$i" = "40" ]; then
    kill "$(cat "$ARGO_DIR/cf.pid")" >/dev/null 2>&1 || true
    sleep 1
    : > "$ARGO_DIR/argo_main.log"
    setsid nohup "$ARGO_DIR/cloudflared" tunnel --url "http://127.0.0.1:${ENTRY_PORT}" --no-autoupdate --edge-ip-version 4 --protocol quic --loglevel info >>"$ARGO_DIR/argo_main.log" 2>&1 < /dev/null &
    echo $! > "$ARGO_DIR/cf.pid"
  fi
done

if [ -n "$argo" ]; then
  echo "$argo" > "$ARGO_DIR/argo_domain.txt"
  echo "ARGO_OK $argo"
  exit 0
fi
echo "ARGO_FAIL"
tail -n 40 "$ARGO_DIR/argo_main.log" || true
exit 1
