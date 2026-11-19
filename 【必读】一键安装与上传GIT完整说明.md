# SUIPLUS 1.6.15 — 完整源码包说明（必读）

相对 1.6.14：

- **上次获取时间**（`pppoeLastAt`）每次成功获取都更新
- **72h 会话锚点**（`pppoeSessionStartTs`）：同 IP 重复获取不重开、不叠加
- **5 分钟按钮灰**：仅 `changeip` 成功后（`pppoeCooldownUntilTs`）；获取 IP 不锁按钮
- 周期天数允许 **0**（不卡 N 天，只按面板时区时刻 + 今日是否已跑）

## 发布与一键更新

1. push main + tag **`v1.6.15`**（与 `config/version` 一致）
2. Actions「发布 SUIPLUS」成功
3. 原机：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.15
```

**一句话：源码在 Git；一键安装吃 Release；版本必须对齐（1.6.15 / v1.6.15）。**
