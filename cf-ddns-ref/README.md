# cf-ddns

台湾 HiNet / 动态公网 IP VPS 专用：**自动查询当前公网 IP，并更新 Cloudflare A 记录**。

适合搭配 S-UI 面板域名（例如 `node.douyin.uk`）：换 IP 后无需手动改 DNS。

## 功能

- 多接口探测公网 IPv4（`ipify` / `icanhazip` / `ip.sb` 等）
- Cloudflare API Token 更新 / 创建 A 记录
- IP 未变化时跳过写入
- `systemd timer` 每 2 分钟检查一次（可改）
- 纯 Python 标准库 + PyYAML，无 Docker 依赖

## 一键运行命令（推荐）

登录 VPS 终端（root），执行：

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/lindanbo1688-ctrl/cf-ddns/main/install.sh)"
```

若系统未预装 `curl`，可用 `wget`：

```bash
bash -c "$(wget -qO- https://raw.githubusercontent.com/lindanbo1688-ctrl/cf-ddns/main/install.sh)"
```

交互流程：

1. 选择几分钟查一次 IP（默认 2 分钟）
2. 粘贴 Cloudflare API Token
3. 填写 Zone / 主机记录（默认 `douyin.uk` + `node`）
4. 自动安装并立刻同步一次

## 手动安装（可选）

```bash
git clone https://github.com/lindanbo1688-ctrl/cf-ddns.git
cd cf-ddns
bash scripts/install.sh
nano /etc/cf-ddns/config.yaml
/opt/cf-ddns/.venv/bin/python -m cf_ddns -c /etc/cf-ddns/config.yaml once --force
```

配置示例：

```yaml
api_token: "你的Cloudflare_API_Token"
zone: "douyin.uk"
record: "node"          # → node.douyin.uk
proxied: false          # 面板/节点建议灰云
interval_seconds: 120
```

```bash
journalctl -u cf-ddns.service -n 50 --no-pager
tail -n 50 /var/log/cf-ddns.log
```

## Cloudflare Token 权限

创建 Token 时建议：

- **DNS**：读取 + 编辑
- **区域**：读取（可选但推荐）
- **区域资源**：特定域名，或所有区域

不要开启橙云代理（`proxied: false`），否则代理协议节点可能异常。

## 常用命令

```bash
# 单次同步
python3 -m cf_ddns -c /etc/cf-ddns/config.yaml once

# 强制更新
python3 -m cf_ddns -c /etc/cf-ddns/config.yaml once --force

# 前台循环（一般用 systemd timer 即可）
python3 -m cf_ddns -c /etc/cf-ddns/config.yaml loop

# 定时器状态
systemctl list-timers | grep cf-ddns
systemctl status cf-ddns.timer
```

## 卸载

```bash
bash scripts/uninstall.sh
```

## 目录结构

```text
cf-ddns/
├── cf_ddns/           # Python 源码
├── scripts/           # install / uninstall
├── systemd/           # service + timer
├── config.example.yaml
└── README.md
```

## 免责声明

仅供个人学习与运维使用，请遵守当地法律法规与 Cloudflare / 服务商条款。请勿把 API Token 提交到 Git。
