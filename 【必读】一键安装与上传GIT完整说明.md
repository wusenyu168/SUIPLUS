# SUIPLUS 1.6.14 — 完整源码包说明（必读）

相对 1.6.13：

- 动态拨号定时 / `LastAt`：**读取面板 `timeLocation`**（默认 `Asia/Shanghai`，与香港同为中国时间）
- 状态区：**72 小时会话倒计时**（changeip 成功即起算，无上次 IP 也可起）+ 5 分钟手动冷却
- pending 时 systemd timer 自动 `--showip` 补拉本次 IP
- 重拨仍不重建 Argo

## 发布与一键更新

1. push main + tag **`v1.6.14`**（与 `config/version` 一致）
2. Actions「发布 SUIPLUS」成功
3. 原机：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.14
```

**一句话：源码在 Git；一键安装吃 Release；版本必须对齐（1.6.14 / v1.6.14）。**
