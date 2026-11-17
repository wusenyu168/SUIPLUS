# SUIPLUS 1.6.7 — 完整源码包说明（必读）

本包在 **1.6.6** 基础上按审查建议做了清理，版本 **1.6.7**。

## 相对 1.6.6 的清理

- 去掉生产热路径调试写盘（`clashService` / `panel_hairpin` → 不再写 `debug-aad3a0.log`）
- 去掉订阅节点名数字前缀逻辑（`linkToJson` / JSON 外链）
- 删除仓库内 `_probe_*` / `_verify_*` / `_dbg_*` 等临时脚本
- 明确 `ensure_client_flow_empty_for_ws` 为安全 no-op（不误清 Reality flow）

---

## 最重要的结论

**一键安装吃的是 GitHub Release 二进制，不是你刚 push 的源码。**

要保证一键安装不踩坑：

1. 上传本包到你的 GitHub  
2. 把 `install.sh` / `s-ui.sh` 里的 `wusenyu168/SUIPLUS` 改成你的 `用户名/仓库名`  
3. 打标签并发布：**`v1.6.7`**（与 `config/version` 一致）  
4. Actions「发布 SUIPLUS」全部成功，Releases Latest = **v1.6.7** 且有 `s-ui-linux-amd64.tar.gz`  
5. 再执行一键安装或菜单「更新」

缺第 3、4 步 → 仍会装到旧包。

### 发布命令示例

```bash
git tag v1.6.7
git push origin v1.6.7
```

### 一键安装示例（改成你的仓库）

```bash
bash <(curl -Ls https://raw.githubusercontent.com/你的用户名/你的仓库名/main/install.sh)
```

### 已有 VPS

Release 就绪后：`s-ui` → **更新** 即可（不必卸载）。确认日志出现 `s-ui 1.6.7`。

---

## 自检清单

- [ ] `config/version` = `1.6.7`
- [ ] 仓库名已改
- [ ] 已 push
- [ ] tag `v1.6.7` Actions 成功
- [ ] Latest Release = v1.6.7
- [ ] 安装/更新后日志为 `s-ui 1.6.7`

**一句话：源码在 Git；一键安装吃 Release；版本必须对齐（1.6.7 / v1.6.7）。**
