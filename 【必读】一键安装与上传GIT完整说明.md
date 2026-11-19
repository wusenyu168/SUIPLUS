# SUIPLUS 1.6.9 — 完整源码包说明（必读）

相对 1.6.8：附加功能页改名、Argo 文案精简、移除橙云（强制灰云）、动态拨号（服务商域名+重拨后刷 DDNS）。

## 本版要点

- Tab「域名证书」→「附加功能」；优选开关 →「Argo默认+优选」
- DDNS 固定 `proxied=false`（灰云）
- 动态拨号：关联域名=VPS 服务商域名（非面板域名）；立即重拨后刷新 CF DDNS，不重建 Argo SNI

---

## 最重要的结论

**一键安装吃的是 GitHub Release 二进制，不是你刚 push 的源码。**

1. 上传本包到 GitHub：`https://github.com/wusenyu168/SUIPLUS`
2. 打标签并发布：**`v1.6.9`**（与 `config/version` 一致）
3. Actions「发布 SUIPLUS」全部成功，Releases Latest = **v1.6.9** 且有 `s-ui-linux-amd64.tar.gz`
4. 再执行一键安装或菜单「更新」

### 发布命令示例

```bash
git tag v1.6.9
git push origin v1.6.9
```

### 一键安装 / 更新（原机即可，无需新 VPS）

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh)
```

或指定版本：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.9
```

**一句话：源码在 Git；一键安装吃 Release；版本必须对齐（1.6.9 / v1.6.9）。**
