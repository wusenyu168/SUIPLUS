# SUIPLUS 功能规格

## 安装默认（多 VPS 通用）

- 账号：`admin` / `admin`
- 按公网 IP 识别地区，自动创建 5 个入站（HY2/TUIC/AnyTLS/SS/VLESS）
- **不预置任何域名**（`webDomain` / `subDomain` / DDNS Zone 为空）
- 订阅/Addrs：**仅公网 IP**
- `suiplusPreferEnable` 默认关闭
- `cfDdnsEnable` 默认关闭

## 1. 手动绑定域名

在设置「界面 → 域名」填写**本机**域名并保存。每台 VPS 可不同。

## 2. 优选 / 固定隧道（与面板同域）

- 开关：`suiplusPreferEnable`
- 前提：已填写 `webDomain`
- 开启后：Addrs = **面板同域** + 公网 IP；`out_json.server` 优先域名
- 由 `suiplus_sync_addrs.py`（随 DDNS timer）同步

## 3. Cloudflare DDNS

- `cfDdnsEnable` + Token / Zone / 记录名 / 间隔
- 默认空，由操作者按该机域名填写
- 仅 DNS（默认非橙云）

## 4. 一键申请证书并绑定

- 依赖已绑定的 `webDomain`（为空则拒绝）
- 优先 DNS-01（CF Token）；否则 HTTP-01
- 写入 `webCertFile` / `webKeyFile`（及订阅证书路径）

## 5. 持久化

UUID、端口、TLS/Reality、域名、证书路径、DDNS/优选开关均在 SQLite；重启不丢。仅清库或 `--force` 种子才重置入站。
