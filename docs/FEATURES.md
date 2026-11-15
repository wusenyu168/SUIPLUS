# SUIPLUS 功能规格

## 1. Cloudflare DDNS（设置页，可开关）

- `cfDdnsEnable`：默认关闭
- Token / Zone / 记录名 / 间隔
- 仅 DNS（非橙云），更新面板域名 A 记录
- 关闭后不探测、不改 DNS

## 2. 一键申请证书并绑定

- 使用设置中的「域名」
- ACME（优先 DNS-01 + CF Token）
- 自动写入 `webCertFile` / `webKeyFile`（及同域订阅证书路径）
- 需保存并重启面板使 HTTPS 生效

## 3. 默认入站种子（安装后自动）

按公网 IP 识别地区码（同梭哈 `detect_region_code`），生成：

| Tag 示例 | 协议 | 端口 |
|---|---|---|
| `{地区}-TUD-HY2` | hysteria2 | 443 |
| `{地区}-TUD-TUIC` | tuic | 16122 |
| `{地区}-TUD-AnyTls` | anytls | 45738 |
| `{地区}-TUD-SS` | shadowsocks | 13495 |
| `{地区}-TUD-VLESS` | vless Reality | 443 |

模板参考用户备份库中的台湾-TUD 五入站。

## 4. 订阅多地址（优选简化版）

每个入站 `Addrs`：

1. 面板域名（如 `node.douyin.uk`）
2. 当前公网 IP

CF 线路优选 IP 仅适用于走 Cloudflare 的协议，作为后期可选。

## 5. 持久化

UUID、端口、TLS/Reality、域名、证书路径、DDNS 配置均写入 SQLite；重启不丢。仅清库或强制重装才重置种子。
