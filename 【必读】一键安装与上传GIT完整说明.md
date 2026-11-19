# SUIPLUS 1.6.11 — 完整源码包说明（必读）

相对 1.6.10：全面板 UI 视觉优化（深色侧栏、顶栏、登录、首页磁贴、设置页卡片分区）；附加功能「时 / 分」下拉（内部仍存 `HH:MM`）。**功能不减**。

## 发布与一键更新

1. push main + tag **`v1.6.11`**（与 `config/version` 一致）
2. Actions「发布 SUIPLUS」成功，Releases 有 `s-ui-linux-*.tar.gz`
3. 原机：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.11
```

**一句话：源码在 Git；一键安装吃 Release；版本必须对齐（1.6.11 / v1.6.11）。**
