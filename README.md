# SUIPLUS

基于 S-UI（Sing-Box 面板）增强版：**可开关 Cloudflare DDNS、一键申请/绑定证书、按公网 IP 地区自动种子默认入站（HY2/TUIC/AnyTLS/SS/VLESS Reality）、订阅多地址（域名+IP）**。

> 仅供个人学习与交流，请勿用于非法用途。

## 一键安装（Linux）

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh)
```

指定版本（需已发布 Release）：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.3
```

安装后管理菜单：

```bash
s-ui
```

## 默认信息

| 项 | 默认 |
|---|---|
| 面板 | `http(s)://IP:2095/app/` |
| 订阅 | `http(s)://IP:2096/sub/` |
| 账号 | **admin / admin**（安装结束会醒目打印） |

## 增强功能（相对原版 S-UI）

详见 [docs/FEATURES.md](docs/FEATURES.md)。

- 设置页：Cloudflare DDNS（可开关）
- 设置页：一键申请证书并自动写入证书路径
- 安装/初始化：按公网 IP 识别地区，自动创建默认入站模板（参考台湾-TUD 五协议）
- 订阅：默认域名 + 公网 IP 多地址

## 发布二进制

本仓库 GitHub Actions（`.github/workflows/release.yml`）可构建并上传 Release。  
有 Release 后，一键安装脚本会从本仓库下载对应架构的 `s-ui-linux-*.tar.gz`。

手动触发：Actions → 发布 SUIPLUS → 填写 tag（如 `v1.6.3`）。

## 从源码构建

```bash
git clone https://github.com/wusenyu168/SUIPLUS.git
cd SUIPLUS/frontend && npm install && npm run build && cd ..
# 将 frontend/dist 放入 web/html 后：
go build -o sui main.go
```

## 目录说明

| 路径 | 说明 |
|---|---|
| `install.sh` | 一键安装入口 |
| `s-ui.sh` | 面板管理菜单 |
| `cf-ddns-ref/` | Cloudflare DDNS 参考实现（将集成进设置） |
| `docs/FEATURES.md` | 功能规格 |

## License

与上游 S-UI 一致，见 [LICENSE](LICENSE)。
