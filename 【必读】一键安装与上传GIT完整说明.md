# SUIPLUS 1.6.10 — 完整源码包说明（必读）

相对 1.6.9：动态拨号增加**定时自动重拨**（任意 N 天 + 固定 HH:MM）。

## 定时规则

- 满 N 天未成功换 IP → 到设定时刻自动重拨
- 周期内已换过 → 跳过自动
- 手动可随时重拨；成功换 IP 后 **5 分钟**内不可再拨
- 成功后刷新 CF DDNS，不重建 Argo SNI

## 发布与一键更新

1. push main + tag **`v1.6.10`**（与 `config/version` 一致）
2. Actions「发布 SUIPLUS」成功，Releases 有 `s-ui-linux-*.tar.gz`
3. 原机：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.10
```

**一句话：源码在 Git；一键安装吃 Release；版本必须对齐（1.6.10 / v1.6.10）。**
