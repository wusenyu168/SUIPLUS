#!/bin/bash
# SUIPLUS 一键安装（基于 S-UI）
# bash <(curl -Ls https://raw.githubusercontent.com/lindanbo1688-ctrl/SUIPLUS/main/install.sh)

red='\033[0;31m'
green='\033[0;32m'
yellow='\033[0;33m'
plain='\033[0m'

REPO="${SUIPLUS_REPO:-lindanbo1688-ctrl/SUIPLUS}"

[[ $EUID -ne 0 ]] && echo -e "${red}致命错误：${plain}请使用 root 权限运行此脚本\n" && exit 1

if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    release=$ID
elif [[ -f /usr/lib/os-release ]]; then
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
    case "${release}" in
    centos | almalinux | rocky | oracle)
        yum -y update && yum install -y -q wget curl tar tzdata ca-certificates
        ;;
    fedora)
        dnf -y update && dnf install -y -q wget curl tar tzdata ca-certificates
        ;;
    arch | manjaro)
        pacman -Syu --noconfirm wget curl tar tzdata ca-certificates
        ;;
    *)
        apt-get update && apt-get install -y -q wget curl tar tzdata ca-certificates
        ;;
    esac
}

config_after_install() {
    echo -e "${yellow}正在迁移...${plain}"
    /usr/local/s-ui/sui migrate 2>/dev/null || true

    echo -e "${yellow}安装完成。建议修改面板端口/路径/管理员账号${plain}"
    if [[ ! -f "/usr/local/s-ui/db/s-ui.db" ]]; then
        local usernameTemp passwordTemp
        usernameTemp=$(head -c 6 /dev/urandom | base64 | tr -d '/+=' | head -c 8)
        passwordTemp=$(head -c 6 /dev/urandom | base64 | tr -d '/+=' | head -c 8)
        echo -e "###############################################"
        echo -e "${green}用户名：${usernameTemp}${plain}"
        echo -e "${green}密码：${passwordTemp}${plain}"
        echo -e "###############################################"
        /usr/local/s-ui/sui admin -username "${usernameTemp}" -password "${passwordTemp}" 2>/dev/null || true
    fi
}

prepare_services() {
    if [[ -f "/etc/systemd/system/sing-box.service" ]]; then
        systemctl stop sing-box 2>/dev/null || true
        rm -f /usr/local/s-ui/bin/sing-box /usr/local/s-ui/bin/runSingbox.sh /usr/local/s-ui/bin/signal
    fi
    systemctl daemon-reload
}

install_suiplus() {
    cd /tmp/ || exit 1
    local last_version=""
    local arch_name
    arch_name=$(arch)

    if [ $# -eq 0 ] || [ -z "${1:-}" ]; then
        last_version=$(curl -Ls "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
        if [[ -z "$last_version" ]]; then
            echo -e "${yellow}尚未找到 ${REPO} 的 Release，尝试从 main 源码引导说明...${plain}"
            echo -e "${red}请先在 GitHub Actions 发布带二进制的 Release，或稍后重试。${plain}"
            echo -e "仓库：https://github.com/${REPO}"
            echo -e "触发：Actions → 发布 → tag 例如 v1.0.0"
            exit 1
        fi
    else
        last_version=$1
        [[ "${last_version}" != v* ]] && last_version="v${last_version}"
    fi

    echo -e "安装 SUIPLUS ${last_version} ..."
    local url="https://github.com/${REPO}/releases/download/${last_version}/s-ui-linux-${arch_name}.tar.gz"
    wget -N --no-check-certificate -O "/tmp/s-ui-linux-${arch_name}.tar.gz" "${url}"
    if [[ $? -ne 0 ]]; then
        echo -e "${red}下载失败：${url}${plain}"
        exit 1
    fi

    if [[ -e /usr/local/s-ui/ ]]; then
        systemctl stop s-ui 2>/dev/null || true
    fi

    tar zxvf "s-ui-linux-${arch_name}.tar.gz"
    rm -f "s-ui-linux-${arch_name}.tar.gz"

    chmod +x s-ui/sui s-ui/s-ui.sh
    # 管理命令仍用 s-ui，兼容原路径
    cp s-ui/s-ui.sh /usr/bin/s-ui
    # 覆盖菜单内安装源为 SUIPLUS
    sed -i "s|lindanbo1688-ctrl/SUIPLUS|${REPO}|g" /usr/bin/s-ui 2>/dev/null || true
    sed -i "s|lindanbo1688-ctrl/SUIPLUS|${REPO}|g" s-ui/s-ui.sh 2>/dev/null || true

    cp -rf s-ui /usr/local/
    cp -f s-ui/*.service /etc/systemd/system/ 2>/dev/null || true
    rm -rf s-ui

    config_after_install
    prepare_services
    systemctl enable s-ui --now

    echo -e "${green}SUIPLUS ${last_version} 安装完成${plain}"
    /usr/local/s-ui/sui uri 2>/dev/null || true
    echo ""
    s-ui help 2>/dev/null || true
}

echo -e "${green}SUIPLUS 安装脚本${plain}"
install_base
install_suiplus "${1:-}"
