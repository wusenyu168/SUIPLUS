# SUIPLUS 功能规格

## 安装默认（多 VPS 通用）

- 账号：`admin` / `admin`
- 按公网 IP 识别地区，自动创建 5 个入站（HY2/TUIC/AnyTLS/SS/VLESS）
- **不预置任何域名**（`webDomain` / `subDomain` / DDNS Zone 为空）
- 订阅/Addrs：**仅公网 IP**
- `suiplusPreferEnable` 默认关闭
- `cfDdnsEnable` 默认关闭
- `cfDdnsInterval` 默认 **300**（5 分钟）

## 1. 手动绑定域名

在设置「界面 → 域名」填写**本机**域名并保存。每台 VPS 可不同。

## 2. 优选 / Argo（与 DDNS 分离）

- 开关：`suiplusPreferEnable`
- 前提：已填写 `webDomain`
- SNI/Host = Cloudflare Quick Tunnel 临时域；优选1/2 入口为 CF CDN 域名
- **触发：** 保存设置 / 开机 `suiplus-prefer.service` / `suiplus_after_settings.py`
- **不会**随 DDNS timer 重建隧道（避免未重启却换 SNI）
- Argo reuse：cloudflared 仍存活时只保活/补 router，不换新域名

## 3. Cloudflare DDNS

- `cfDdnsEnable` + Token / Zone / 记录名 / **`cfDdnsInterval`（秒，默认 300）**
- Timer 由 `suiplus_apply_ddns_timer.py` 按库内间隔重写（菜单可改）
- oneshot **仅** `cf_ddns.py` + `sync_addrs`（TUD 域名/IP），**不调用** prefer/Argo
- 仅 DNS（默认非橙云）

## 4. 一键申请证书并绑定

- 依赖已绑定的 `webDomain`（为空则拒绝）
- 优先 DNS-01（CF Token）；否则 HTTP-01
- 写入 `webCertFile` / `webKeyFile`（及订阅证书路径）
- 成功后走 `suiplus_after_settings.py`

## 5. 持久化

UUID、端口、TLS/Reality、域名、证书路径、DDNS/优选开关均在 SQLite；重启不丢。仅清库或 `--force` 种子才重置入站。
