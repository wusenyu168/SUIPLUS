# SUIPLUS 1.6.12 — 完整源码包说明（必读）

相对 1.6.11：排版对齐演示稿。

- 设置：Tab 与保存/重启同一行；附加功能栅格分区（开关 / 字段 / 按钮分行）；时刻「时:分」成对下拉
- 入站等实体卡片：加宽、等高、长文本省略、底部操作居中
- **功能不减**（Argo/DDNS/证书/拨号/定时/立即重拨及各页增删改均保留）

## 发布与一键更新

1. push main + tag **`v1.6.12`**（与 `config/version` 一致）
2. Actions「发布 SUIPLUS」成功，Releases 有 `s-ui-linux-*.tar.gz`
3. 原机：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.12
```

**一句话：源码在 Git；一键安装吃 Release；版本必须对齐（1.6.12 / v1.6.12）。**
