# SUIPLUS

基于 S-UI（Sing-Box 面板）增强版：**可开关 Cloudflare DDNS、一键申请/绑定证书、按公网 IP 地区自动种子默认入站（HY2/TUIC/AnyTLS/SS/VLESS Reality）、订阅多地址（域名+IP）**。

> 仅供个人学习与交流，请勿用于非法用途。

## 一键安装（Linux）

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh)
```

指定版本（需已发布对应 Release；**一键安装拉的是 Release 包，不是 main 源码即时编译**）：

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wusenyu168/SUIPLUS/main/install.sh) v1.6.16
```

当前源码版本见 `config/version`（应为 `1.6.16`）。发布后 Latest Release 也必须是 `v1.6.16`，否则重装/更新仍会落到旧包。

**1.6.16：** 定时重拨改为周几下拉多选 + 时刻；开关旁显示距下次重拨倒计时。  
**1.6.15：** 会话锚点与「上次获取」拆分（同 IP 不重开 72h）；仅重拨成功锁按钮 5 分钟；周期允许 0 天测定时。  
**1.6.14：** 拨号定时/LastAt 读取面板 `timeLocation`（默认上海）；72h 会话倒计时；pending 时 timer 自动 `--showip`。  
**1.6.13：** 动态拨号「获取 IP」+ 冷却倒计时；Argo 立即重建 + 异常自动重建（默认关）；重拨断网后 IP 可补拉。  
**1.6.12：** 排版对齐演示稿（设置工具栏同行、附加功能栅格、入站等实体卡片加宽/等高/长文本省略/操作居中）。  
**1.6.11：** 全面板 UI 优化（侧栏/顶栏/登录/首页/设置）；附加功能卡片分区 + 时/分下拉；功能不减。  
**1.6.10：** 动态拨号定时（任意 N 天 + HH:MM；满 N 天未换 IP 才自动；手动成功后 5 分钟冷却）。  
**1.6.9：** 附加功能页；Argo 文案精简；移除橙云；动态拨号（服务商域名 + 重拨后刷 DDNS）。  
**1.6.8：** 优选/Argo 与 DDNS 定时器分离；DDNS 间隔菜单生效，默认 300 秒。

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

手动触发：Actions → 发布 SUIPLUS → 填写 tag（如 `v1.6.8`）。  
或推送标签：`git tag v1.6.8 && git push origin v1.6.8`。

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
