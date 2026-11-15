#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -ne 0 ]] && echo "请使用 root 运行" && exit 1

systemctl disable --now cf-ddns.timer 2>/dev/null || true
systemctl disable --now cf-ddns.service 2>/dev/null || true
rm -f /etc/systemd/system/cf-ddns.service /etc/systemd/system/cf-ddns.timer
systemctl daemon-reload
rm -rf /opt/cf-ddns
echo "已卸载服务与 /opt/cf-ddns（保留 /etc/cf-ddns/config.yaml）"
