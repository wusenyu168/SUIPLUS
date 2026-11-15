#!/usr/bin/env bash
# cf-ddns 一键安装（可 curl | bash）
# bash -c "$(curl -fsSL https://raw.githubusercontent.com/lindanbo1688-ctrl/cf-ddns/main/install.sh)"
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

REPO_URL="${REPO_URL:-https://github.com/lindanbo1688-ctrl/cf-ddns.git}"
REPO_RAW="${REPO_RAW:-https://raw.githubusercontent.com/lindanbo1688-ctrl/cf-ddns/main}"
APP_DIR="${APP_DIR:-/opt/cf-ddns}"
CONF_DIR="/etc/cf-ddns"
STATE_DIR="/var/lib/cf-ddns"
WORKDIR="/tmp/cf-ddns-install-$$"

[[ $EUID -ne 0 ]] && echo -e "${RED}请使用 root 运行${NC}" && exit 1

clear_screen() { command -v clear >/dev/null 2>&1 && clear || printf '\n%.0s' {1..5}; }

banner() {
  clear_screen
  echo -e "${CYAN}========================================${NC}"
  echo -e "${CYAN}   Cloudflare DDNS 一键安装 (cf-ddns)  ${NC}"
  echo -e "${CYAN}========================================${NC}"
  echo "自动查询公网 IP，并更新 Cloudflare A 记录"
  echo
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

ensure_deps() {
  echo -e "${GREEN}==> 检查/安装依赖${NC}"
  if need_cmd apt-get; then
    apt-get update -y >/dev/null 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      curl ca-certificates git python3 python3-pip python3-venv rsync >/dev/null 2>&1 || \
      DEBIAN_FRONTEND=noninteractive apt-get install -y \
      curl ca-certificates git python3 python3-venv rsync || true
  elif need_cmd yum; then
    yum install -y curl ca-certificates git python3 python3-pip rsync || true
  fi
  need_cmd python3 || { echo -e "${RED}缺少 python3${NC}"; exit 1; }
}

fetch_source() {
  echo -e "${GREEN}==> 获取源码${NC}"
  rm -rf "${WORKDIR}"
  mkdir -p "${WORKDIR}"
  if need_cmd git; then
    git clone --depth 1 "${REPO_URL}" "${WORKDIR}/repo"
  else
    # 无 git 时用 zip（需要 unzip）
    curl -fsSL -o /tmp/cf-ddns.zip "https://github.com/lindanbo1688-ctrl/cf-ddns/archive/refs/heads/main.zip"
    need_cmd unzip || { apt-get install -y unzip >/dev/null 2>&1 || true; }
    unzip -q /tmp/cf-ddns.zip -d "${WORKDIR}"
    mv "${WORKDIR}"/cf-ddns-main "${WORKDIR}/repo"
  fi
}

ask_config() {
  banner
  echo -e "${YELLOW}【1/4】检查间隔（分钟）${NC}"
  echo "  1) 1 分钟"
  echo "  2) 2 分钟（推荐）"
  echo "  3) 5 分钟"
  echo "  4) 10 分钟"
  echo "  5) 自定义"
  read -rp "请选择 [1-5]，默认 2: " INTERVAL_OPT
  INTERVAL_OPT="${INTERVAL_OPT:-2}"
  case "${INTERVAL_OPT}" in
    1) INTERVAL_MIN=1 ;;
    2) INTERVAL_MIN=2 ;;
    3) INTERVAL_MIN=5 ;;
    4) INTERVAL_MIN=10 ;;
    5)
      read -rp "请输入分钟数（>=1）: " INTERVAL_MIN
      INTERVAL_MIN="${INTERVAL_MIN:-2}"
      ;;
    *) INTERVAL_MIN=2 ;;
  esac
  if ! [[ "${INTERVAL_MIN}" =~ ^[0-9]+$ ]] || [[ "${INTERVAL_MIN}" -lt 1 ]]; then
    echo -e "${YELLOW}无效间隔，改用 2 分钟${NC}"
    INTERVAL_MIN=2
  fi
  INTERVAL_SEC=$((INTERVAL_MIN * 60))

  echo
  echo -e "${YELLOW}【2/4】Cloudflare API Token${NC}"
  echo "在 Cloudflare → 我的个人资料 → API 令牌 创建（DNS 编辑）"
  echo -e "${RED}注意：Token 只保存在本机 /etc/cf-ddns/config.yaml，不会上传 Git${NC}"
  while true; do
    read -rp "请粘贴 Token: " API_TOKEN
    API_TOKEN="$(echo -n "${API_TOKEN}" | tr -d '[:space:]')"
    if [[ -n "${API_TOKEN}" ]]; then
      break
    fi
    echo "Token 不能为空"
  done

  echo
  echo -e "${YELLOW}【3/4】域名 Zone（主域名）${NC}"
  read -rp "Zone（默认 douyin.uk）: " ZONE
  ZONE="${ZONE:-douyin.uk}"

  echo
  echo -e "${YELLOW}【4/4】主机记录${NC}"
  echo "填 node → 解析 node.${ZONE}"
  echo "填 @   → 解析 ${ZONE}"
  read -rp "主机记录（默认 node）: " RECORD
  RECORD="${RECORD:-node}"

  # 若 Zone 误写成 node.xxx.com，自动拆成 zone + record
  if [[ "${ZONE}" == node.* ]]; then
    echo -e "${YELLOW}检测到 Zone 写成了完整域名，自动纠正为主域名${NC}"
    RECORD="node"
    ZONE="${ZONE#node.}"
  fi

  FQDN="${RECORD}.${ZONE}"
  if [[ "${RECORD}" == "@" || "${RECORD}" == "${ZONE}" ]]; then
    FQDN="${ZONE}"
  fi

  echo
  echo -e "${GREEN}即将安装：${NC}"
  echo "  域名:   ${FQDN}"
  echo "  间隔:   每 ${INTERVAL_MIN} 分钟"
  echo "  代理:   仅 DNS（灰云）"
  read -rp "确认开始？[Y/n]: " OK
  OK="${OK:-Y}"
  [[ "${OK}" =~ ^[Yy]$ ]] || { echo "已取消"; exit 0; }
}

write_config() {
  mkdir -p "${CONF_DIR}" "${STATE_DIR}"
  cat > "${CONF_DIR}/config.yaml" <<EOF
api_token: "${API_TOKEN}"
zone: "${ZONE}"
record: "${RECORD}"
proxied: false
ttl: 1
interval_seconds: ${INTERVAL_SEC}
state_file: "${STATE_DIR}/last_ip"
log_file: "/var/log/cf-ddns.log"
EOF
  chmod 600 "${CONF_DIR}/config.yaml"
  echo -e "${GREEN}已写入 ${CONF_DIR}/config.yaml（权限 600）${NC}"
}

write_timer() {
  cat > /etc/systemd/system/cf-ddns.timer <<EOF
[Unit]
Description=Run Cloudflare DDNS every ${INTERVAL_MIN} minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=${INTERVAL_MIN}min
AccuracySec=15s
Persistent=true
Unit=cf-ddns.service

[Install]
WantedBy=timers.target
EOF
}

install_app() {
  echo -e "${GREEN}==> 安装程序到 ${APP_DIR}${NC}"
  mkdir -p "${APP_DIR}"
  rsync -a --delete \
    --exclude '.git' \
    --exclude 'config.yaml' \
    --exclude '__pycache__' \
    --exclude '.venv' \
    "${WORKDIR}/repo/" "${APP_DIR}/"

  python3 -m venv "${APP_DIR}/.venv"
  "${APP_DIR}/.venv/bin/pip" install -U pip setuptools wheel >/dev/null
  "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" >/dev/null
  "${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}" >/dev/null

  install -m 644 "${APP_DIR}/systemd/cf-ddns.service" /etc/systemd/system/cf-ddns.service
  write_timer
  systemctl daemon-reload
  systemctl enable --now cf-ddns.timer
}

run_once() {
  echo -e "${GREEN}==> 立即同步一次 DNS${NC}"
  set +e
  "${APP_DIR}/.venv/bin/python" -m cf_ddns -c "${CONF_DIR}/config.yaml" once --force
  local rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    echo -e "${GREEN}同步成功${NC}"
  else
    echo -e "${RED}同步失败（请检查 Token / 域名 / 网络）${NC}"
    echo "日志: journalctl -u cf-ddns.service -n 50 --no-pager"
    echo "     tail -n 50 /var/log/cf-ddns.log"
  fi
  return 0
}

cleanup() {
  rm -rf "${WORKDIR}" 2>/dev/null || true
}

finish() {
  echo
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN} 安装完成${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo "域名:   ${FQDN}"
  echo "间隔:   每 ${INTERVAL_MIN} 分钟"
  echo "配置:   ${CONF_DIR}/config.yaml"
  echo "日志:   /var/log/cf-ddns.log"
  echo
  echo "常用命令:"
  echo "  立刻同步: ${APP_DIR}/.venv/bin/python -m cf_ddns -c ${CONF_DIR}/config.yaml once --force"
  echo "  看定时器: systemctl list-timers | grep cf-ddns"
  echo "  看日志:   journalctl -u cf-ddns.service -n 50 --no-pager"
  echo "  重装:     bash -c \"\$(curl -fsSL ${REPO_RAW}/install.sh)\""
}

main_menu() {
  banner
  echo "1）安装 / 重装 DDNS"
  echo "2）仅立刻同步一次"
  echo "3）查看状态 / 日志"
  echo "4）卸载"
  echo "5）退出"
  read -rp "请选择 [1-5]，默认 1: " CHOICE
  CHOICE="${CHOICE:-1}"
  case "${CHOICE}" in
    1)
      ensure_deps
      fetch_source
      ask_config
      write_config
      install_app
      run_once
      cleanup
      finish
      ;;
    2)
      [[ -x "${APP_DIR}/.venv/bin/python" ]] || { echo "尚未安装，请先选 1"; exit 1; }
      run_once
      ;;
    3)
      systemctl is-active cf-ddns.timer || true
      systemctl list-timers --all | grep cf-ddns || true
      journalctl -u cf-ddns.service -n 30 --no-pager || true
      tail -n 30 /var/log/cf-ddns.log 2>/dev/null || true
      ;;
    4)
      systemctl disable --now cf-ddns.timer 2>/dev/null || true
      systemctl disable --now cf-ddns.service 2>/dev/null || true
      rm -f /etc/systemd/system/cf-ddns.service /etc/systemd/system/cf-ddns.timer
      systemctl daemon-reload
      rm -rf "${APP_DIR}"
      echo "已卸载程序（保留 ${CONF_DIR}/config.yaml）"
      ;;
    5) exit 0 ;;
    *) echo "无效选项"; exit 1 ;;
  esac
}

trap cleanup EXIT
main_menu
