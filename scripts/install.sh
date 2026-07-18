#!/bin/sh

set -eu

UV_INSTALL_URL=${LEETCODE_LOCAL_CLI_UV_INSTALL_URL:-https://astral.sh/uv/install.sh}
INSTALL_SPEC=${LEETCODE_LOCAL_CLI_INSTALL_SPEC:-leetcode-local-cli}
TEMP_DIR=""

case "$INSTALL_SPEC" in
    *http://*)
        printf '%s\n' "[leetcode-local-cli] 错误：包安装地址必须使用 HTTPS：$INSTALL_SPEC" >&2
        exit 1
        ;;
esac

info() {
    printf '%s\n' "[leetcode-local-cli] $*"
}

warn() {
    printf '%s\n' "[leetcode-local-cli] 警告：$*" >&2
}

fail() {
    printf '%s\n' "[leetcode-local-cli] 错误：$*" >&2
    exit 1
}

cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup EXIT HUP INT TERM

find_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return 0
    fi

    for candidate in \
        "${UV_INSTALL_DIR:-}/uv" \
        "${HOME:-}/.local/bin/uv" \
        "${HOME:-}/.cargo/bin/uv"
    do
        if [ "$candidate" != "/uv" ] && [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    return 1
}

UV_PATH=$(find_uv || true)
if [ -z "$UV_PATH" ]; then
    case "$UV_INSTALL_URL" in
        https://*) ;;
        *) fail "uv 安装地址必须使用 HTTPS：$UV_INSTALL_URL" ;;
    esac
    command -v curl >/dev/null 2>&1 || fail "未找到 curl，无法下载 uv 官方安装器"

    TEMP_DIR=$(mktemp -d)
    UV_INSTALLER="$TEMP_DIR/install-uv.sh"
    info "未检测到 uv，正在下载安装官方 uv..."
    curl --proto '=https' --tlsv1.2 -LsSf "$UV_INSTALL_URL" -o "$UV_INSTALLER"
    sh "$UV_INSTALLER"

    UV_PATH=$(find_uv || true)
    [ -n "$UV_PATH" ] || fail "uv 安装完成后仍无法定位可执行文件"
fi

info "使用 uv：$UV_PATH"
info "正在安装：$INSTALL_SPEC"
"$UV_PATH" tool install --force "$INSTALL_SPEC"

if [ "${LEETCODE_LOCAL_CLI_NO_MODIFY_PATH:-0}" != "1" ]; then
    if ! "$UV_PATH" tool update-shell >/dev/null 2>&1; then
        warn "无法自动更新 PATH；请执行 '$UV_PATH tool update-shell'"
    fi
fi

TOOL_BIN_DIR=$("$UV_PATH" tool dir --bin)
LC_PATH="$TOOL_BIN_DIR/lc"
[ -x "$LC_PATH" ] || fail "安装完成，但未找到 lc：$LC_PATH"

INSTALLED_VERSION=$("$LC_PATH" --version)
info "安装成功：$INSTALLED_VERSION"
info "如果当前终端找不到 lc，请重新打开终端或执行：$LC_PATH --help"
