#!/bin/bash
# SUIPLUS 一键安装（基于 S-UI）
# bash <(curl -Ls https://raw.githubusercontent.com/lindanbo1688-ctrl/SUIPLUS/main/install.sh)

red='\033[0;31m'
green='\033[0;32m'
yellow='\033[0;33m'
plain='\033[0m'

REPO="${SUIPLUS_REPO:-lindanbo1688-ctrl/SUIPLUS}"
FALLBACK_REPO="${SUIPLUS_FALLBACK_REPO:-admin8800/s-ui}"

[[ $EUID -ne 0 ]] && echo -e "${red}致命错误：${plain}请使用 root 权限运行此脚本\n" && exit 1

if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    release=$ID
elif [[ -f /usr/lib/os-release ]]; then
    # shellcheck disable=SC1091
    source /usr/lib/os-release
    release=$ID
else
    echo "检测系统失败" >&2
    exit 1
fi
echo "当前系统：$release | 仓库：$REPO"

arch() {
    case "$(uname -m)" in
    x86_64 | x64 | amd64) echo 'amd64' ;;
    i*86 | x86) echo '386' ;;
    armv8* | arm64 | aarch64) echo 'arm64' ;;
    armv7* | arm) echo 'armv7' ;;
    armv6*) echo 'armv6' ;;
    armv5*) echo 'armv5' ;;
    s390x) echo 's390x' ;;
    *) echo -e "${red}不支持的 CPU 架构${plain}" && exit 1 ;;
    esac
}
echo "架构：$(arch)"

install_base() {
    # apt 源失效时不要整段失败（旧 Debian / 坏 mirror 常见）
    case "${release}" in
    centos | almalinux | rocky | oracle)
        yum install -y -q wget curl tar tzdata ca-certificates || true
        ;;
    fedora)
        dnf install -y -q wget curl tar tzdata ca-certificates || true
        ;;
    arch | manjaro)
        pacman -Sy --noconfirm wget curl tar tzdata ca-certificates || true
        ;;
    *)
        apt-get update -y || echo -e "${yellow}apt update 失败（源可能失效），继续尝试安装依赖…${plain}"
        apt-get install -y -q wget curl tar tzdata ca-certificates || \
            apt-get install -y wget curl tar ca-certificates || true
        ;;
    esac
    command -v curl >/dev/null || { echo -e "${red}缺少 curl${plain}"; exit 1; }
    command -v tar >/dev/null || { echo -e "${red}缺少 tar${plain}"; exit 1; }
}

install_suiplus_helpers() {
    mkdir -p /usr/local/s-ui/scripts
    # Prefer files shipped in release tarball; else pull from GitHub raw
    if [[ -f /usr/local/s-ui/scripts/suiplus_seed.py ]]; then
        :
    else
        curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/scripts/suiplus_seed.py" \
            -o /usr/local/s-ui/scripts/suiplus_seed.py 2>/dev/null || true
        curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/scripts/suiplus_cf_ddns.py" \
            -o /usr/local/s-ui/scripts/suiplus_cf_ddns.py 2>/dev/null || true
        curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/scripts/suiplus_issue_cert.sh" \
            -o /usr/local/s-ui/scripts/suiplus_issue_cert.sh 2>/dev/null || true
    fi
    chmod +x /usr/local/s-ui/scripts/*.py /usr/local/s-ui/scripts/*.sh 2>/dev/null || true

    curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/scripts/suiplus-cf-ddns.service" \
        -o /etc/systemd/system/suiplus-cf-ddns.service 2>/dev/null || true
    curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/scripts/suiplus-cf-ddns.timer" \
        -o /etc/systemd/system/suiplus-cf-ddns.timer 2>/dev/null || true
    if [[ -f /etc/systemd/system/suiplus-cf-ddns.timer ]]; then
        systemctl daemon-reload
        systemctl enable --now suiplus-cf-ddns.timer 2>/dev/null || true
    fi
}

config_after_install() {
    echo -e "${yellow}正在迁移...${plain}"
    /usr/local/s-ui/sui migrate 2>/dev/null || true

    # Start once so InitDB creates admin/admin if DB is new
    systemctl daemon-reload 2>/dev/null || true
    systemctl start s-ui 2>/dev/null || /usr/local/s-ui/sui run >/dev/null 2>&1 &
    sleep 2
    systemctl stop s-ui 2>/dev/null || true
    pkill -f '/usr/local/s-ui/sui' 2>/dev/null || true
    sleep 1

    local had_db=0
    [[ -f "/usr/local/s-ui/db/s-ui.db" ]] && had_db=1

    # Default credentials: always admin / admin on fresh install print
    echo -e "###############################################"
    echo -e "${green}面板默认账号${plain}"
    echo -e "${green}用户名：admin${plain}"
    echo -e "${green}密码：admin${plain}"
    echo -e "###############################################"
    /usr/local/s-ui/sui admin -username admin -password admin 2>/dev/null || true

    install_suiplus_helpers

    # Fresh DB or empty inbounds → seed 5 TUD nodes + Addrs
    # SUIPLUS_FORCE_SEED=1 强制重建入站
    if [[ -f /usr/local/s-ui/scripts/suiplus_seed.py ]]; then
        if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
            local py=python3
            command -v python3 >/dev/null 2>&1 || py=python
            command -v openssl >/dev/null 2>&1 || apt-get install -y -q openssl >/dev/null 2>&1 || true
            local seed_args=(--db /usr/local/s-ui/db/s-ui.db --domain "${SUIPLUS_DOMAIN:-node.douyin.uk}")
            [[ "${SUIPLUS_FORCE_SEED:-0}" == "1" ]] && seed_args+=(--force)
            SUIPLUS_DOMAIN="${SUIPLUS_DOMAIN:-node.douyin.uk}" \
                $py /usr/local/s-ui/scripts/suiplus_seed.py "${seed_args[@]}" \
                || echo -e "${yellow}种子入站执行失败（可稍后手动运行 scripts/suiplus_seed.py）${plain}"
        else
            echo -e "${yellow}未找到 python3，跳过默认入站种子${plain}"
        fi
    fi

    if [[ "$had_db" -eq 1 ]]; then
        echo -e "${yellow}若库中已有入站则不会覆盖；强制重建可运行：${plain}"
        echo -e "  python3 /usr/local/s-ui/scripts/suiplus_seed.py --force"
    fi

    echo -e "${yellow}证书一键申请：bash /usr/local/s-ui/scripts/suiplus_issue_cert.sh${plain}"
    echo -e "${yellow}DDNS：设置页填写 CF Token 并打开 cfDdnsEnable，或改 settings 后由 timer 同步${plain}"
}

prepare_services() {
    if [[ -f "/etc/systemd/system/sing-box.service" ]]; then
        systemctl stop sing-box 2>/dev/null || true
        rm -f /usr/local/s-ui/bin/sing-box /usr/local/s-ui/bin/runSingbox.sh /usr/local/s-ui/bin/signal
    fi
    systemctl daemon-reload
}

resolve_download() {
    # stdout: "version|url"
    local arch_name="$1"
    local want_ver="${2:-}"
    local ver url

    if [[ -n "$want_ver" ]]; then
        [[ "$want_ver" != v* ]] && want_ver="v${want_ver}"
        url="https://github.com/${REPO}/releases/download/${want_ver}/s-ui-linux-${arch_name}.tar.gz"
        if curl -fsI --connect-timeout 5 "$url" >/dev/null 2>&1; then
            echo "${want_ver}|${url}"
            return 0
        fi
        echo -e "${yellow}${REPO} 无 ${want_ver}，尝试回退仓库…${plain}" >&2
        url="https://github.com/${FALLBACK_REPO}/releases/download/${want_ver}/s-ui-linux-${arch_name}.tar.gz"
        echo "${want_ver}|${url}"
        return 0
    fi

    ver=$(curl -Ls "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name":' | head -n1 | sed -E 's/.*"([^"]+)".*/\1/')
    if [[ -n "$ver" ]]; then
        url="https://github.com/${REPO}/releases/download/${ver}/s-ui-linux-${arch_name}.tar.gz"
        echo "${ver}|${url}"
        return 0
    fi

    echo -e "${yellow}${REPO} 尚无 Release，临时使用上游 ${FALLBACK_REPO} 二进制（面板可先装上）${plain}" >&2
    ver=$(curl -Ls "https://api.github.com/repos/${FALLBACK_REPO}/releases/latest" | grep '"tag_name":' | head -n1 | sed -E 's/.*"([^"]+)".*/\1/')
    if [[ -z "$ver" ]]; then
        echo -e "${red}无法获取任何 Release 版本${plain}" >&2
        return 1
    fi
    url="https://github.com/${FALLBACK_REPO}/releases/download/${ver}/s-ui-linux-${arch_name}.tar.gz"
    echo "${ver}|${url}"
}

install_suiplus() {
    cd /tmp/ || exit 1
    local arch_name info ver url
    arch_name=$(arch)

    info=$(resolve_download "$arch_name" "${1:-}") || exit 1
    ver="${info%%|*}"
    url="${info#*|}"

    echo -e "下载：${url}"
    if ! wget -N --no-check-certificate -O "/tmp/s-ui-linux-${arch_name}.tar.gz" "${url}"; then
        echo -e "${red}下载失败${plain}"
        exit 1
    fi

    if [[ -e /usr/local/s-ui/ ]]; then
        systemctl stop s-ui 2>/dev/null || true
    fi

    tar zxvf "s-ui-linux-${arch_name}.tar.gz"
    rm -f "s-ui-linux-${arch_name}.tar.gz"

    chmod +x s-ui/sui s-ui/s-ui.sh
    cp s-ui/s-ui.sh /usr/bin/s-ui
    # 菜单升级源指向 SUIPLUS
    sed -i "s|admin8800/s-ui|${REPO}|g" /usr/bin/s-ui s-ui/s-ui.sh 2>/dev/null || true
    sed -i "s|lindanbo1688-ctrl/SUIPLUS|${REPO}|g" /usr/bin/s-ui s-ui/s-ui.sh 2>/dev/null || true

    # 用仓库最新 install/管理脚本覆盖（若可拉取）
    curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/s-ui.sh" -o /usr/bin/s-ui 2>/dev/null && chmod +x /usr/bin/s-ui || true

    cp -rf s-ui /usr/local/
    cp -f s-ui/*.service /etc/systemd/system/ 2>/dev/null || true
    # ship helper scripts if present in tarball layout
    mkdir -p /usr/local/s-ui/scripts
    if [[ -d /tmp/s-ui/scripts ]]; then
        cp -f /tmp/s-ui/scripts/* /usr/local/s-ui/scripts/ 2>/dev/null || true
    fi
    rm -rf s-ui

    config_after_install
    prepare_services
    systemctl enable s-ui --now

    echo -e "${green}SUIPLUS 安装完成（包版本标签：${ver}）${plain}"
    echo -e "###############################################"
    echo -e "${green}用户名：admin${plain}"
    echo -e "${green}密码：admin${plain}"
    echo -e "###############################################"
    /usr/local/s-ui/sui uri 2>/dev/null || true
    echo ""
    s-ui help 2>/dev/null || true
}

echo -e "${green}SUIPLUS 安装脚本${plain}"
install_base
install_suiplus "${1:-}"
