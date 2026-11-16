#!/usr/bin/env bash
# 在 Debian/Ubuntu VPS 上一键安装 cf-ddns（systemd timer）
set -euo pipefail

[[ $EUID -ne 0 ]] && echo "请使用 root 运行" && exit 1

APP_DIR="${APP_DIR:-/opt/cf-ddns}"
CONF_DIR="/etc/cf-ddns"
STATE_DIR="/var/lib/cf-ddns"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> 安装到 ${APP_DIR}"
mkdir -p "${APP_DIR}" "${CONF_DIR}" "${STATE_DIR}"
rsync -a --delete \
  --exclude '.git' \
  --exclude 'config.yaml' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  "${REPO_ROOT}/" "${APP_DIR}/"

if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip python3-venv rsync || true
fi

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install -U pip setuptools wheel
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"
"${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}"

if [[ ! -f "${CONF_DIR}/config.yaml" ]]; then
  cp "${APP_DIR}/config.example.yaml" "${CONF_DIR}/config.yaml"
  echo "已生成 ${CONF_DIR}/config.yaml ，请填入 api_token / zone / record"
fi

install -m 644 "${APP_DIR}/systemd/cf-ddns.service" /etc/systemd/system/cf-ddns.service
install -m 644 "${APP_DIR}/systemd/cf-ddns.timer" /etc/systemd/system/cf-ddns.timer

systemctl daemon-reload
systemctl enable --now cf-ddns.timer
systemctl start cf-ddns.service || true

echo "==> 完成"
echo "配置: ${CONF_DIR}/config.yaml"
echo "手动跑一次: ${APP_DIR}/.venv/bin/python -m cf_ddns -c ${CONF_DIR}/config.yaml once --force"
echo "看日志: journalctl -u cf-ddns.service -n 50 --no-pager ; tail -n 50 /var/log/cf-ddns.log"
echo "Timer: systemctl list-timers | grep cf-ddns"
