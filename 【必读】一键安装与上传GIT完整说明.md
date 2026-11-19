# SUIPLUS 1.6.13 — 完整源码包说明（必读）

相对 1.6.12：

- 动态拨号：`获取 IP`、文字冷却倒计时（5 分钟）、重拨前锁定上次 IP / 待确认
- Argo：`立即重建 Argo`；`Argo异常自动重建` **默认关**（挂了才 FORCE，冷却 30 分钟）
- 重拨不重建 Argo；重建后需重新订阅优选

## 发布与一键更新

1. push main + tag **`v1.6.13`**（与 `config/version` 一致）
2. Actions「发布 SUIPLUS」成功
3. 原机：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.13
```

**一句话：源码在 Git；一键安装吃 Release；版本必须对齐（1.6.13 / v1.6.13）。**
