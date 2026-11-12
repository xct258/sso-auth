#!/bin/bash
# ============================================================
# 自定义安装脚本（构建时执行一次）
#   - 从当前提交的仓库源码包中取 main.py 和静态登录页
#   - 在镜像内用 Vite 构建 前端/，产物放到 /opt/sso-auth/static/dist
#   - 构建期下载 Node.js，构建完成后删除，不留在运行镜像里
#
# REPO_URL 由 template/Dockerfile 从 CI 传入，固定在当前提交 SHA：
#   https://raw.githubusercontent.com/<owner>/<repo>/<sha>
# 这里解析出 owner/repo 和 ref，再下载同一提交的源码包，避免拿到旧代码。
# ============================================================
set -euo pipefail

target_arch="${TARGETARCH:-}"
if [ -z "$target_arch" ]; then
    case "$(uname -m)" in
        x86_64) target_arch=amd64 ;;
        aarch64 | arm64) target_arch=arm64 ;;
        *) target_arch="$(uname -m)" ;;
    esac
fi
echo "[custom] 目标架构: ${target_arch}"

case "$target_arch" in
    amd64) node_dist="node-v20.19.2-linux-x64" ;;
    arm64) node_dist="node-v20.19.2-linux-arm64" ;;
    *)
        echo "[custom] 不支持的架构: ${target_arch}" >&2
        exit 1
        ;;
esac

repo_url="${REPO_URL:-https://raw.githubusercontent.com/xct258/sso-auth/main}"
repo_url="${repo_url%/}"
repo_path="${repo_url#https://raw.githubusercontent.com/}"
owner_repo="${repo_path%/*}"
ref="${repo_path##*/}"
archive_url="https://github.com/${owner_repo}/archive/${ref}.tar.gz"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "[custom] 下载源码包: ${archive_url}"
curl -fsSL --retry 3 --retry-delay 5 -o "${tmp}/repo.tar.gz" "$archive_url"
mkdir -p "${tmp}/repo"
tar -xzf "${tmp}/repo.tar.gz" -C "${tmp}/repo" --strip-components=1

# ------------------------------------------------------------
# 后端运行文件
# ------------------------------------------------------------
mkdir -p /opt/sso-auth/static
cp "${tmp}/repo/main.py" /opt/sso-auth/
if [ -f "${tmp}/repo/static/login.html" ]; then
    cp "${tmp}/repo/static/login.html" /opt/sso-auth/static/
fi

# ------------------------------------------------------------
# 前端：下载 Node.js，构建 前端/，产物放 /opt/sso-auth/static/dist
# ------------------------------------------------------------
echo "[custom] 下载 Node.js ${node_dist}"
curl -fsSL --retry 3 --retry-delay 5 -o "${tmp}/node.tar.xz" \
    "https://nodejs.org/dist/v20.19.2/${node_dist}.tar.xz"
tar -xf "${tmp}/node.tar.xz" -C "$tmp"
export PATH="${tmp}/${node_dist}/bin:${PATH}"
node --version
npm --version

echo "[custom] 构建前端"
cd "${tmp}/repo/前端"
npm install --registry=https://registry.npmmirror.com --no-audit --no-fund
npm run build
mkdir -p /opt/sso-auth/static/dist
cp -r "${tmp}/repo/static/dist/." /opt/sso-auth/static/dist/
cd /

echo "[custom] 自定义安装完成"
