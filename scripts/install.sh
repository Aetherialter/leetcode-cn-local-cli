#!/bin/sh

set -eu

INSTALL_SPEC=${LEETCODE_LOCAL_CLI_INSTALL_SPEC:-leetcode-local-cli}
UV_DOCS_URL=https://docs.astral.sh/uv/

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
    fail "未检测到 uv。请先按照 uv 官方文档安装：$UV_DOCS_URL"
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

if [ "${LEETCODE_LOCAL_CLI_NO_INIT:-0}" = "1" ]; then
    info "已跳过工作区配置；稍后可执行：$LC_PATH init"
elif [ -t 1 ] && [ -r /dev/tty ] && [ -w /dev/tty ]; then
    info "开始配置工作区"
    if ! "$LC_PATH" init </dev/tty >/dev/tty 2>/dev/tty; then
        fail "lc 已安装，但工作区配置未完成；请稍后执行：$LC_PATH init"
    fi
else
    info "当前环境不可交互，已跳过工作区配置；请执行：$LC_PATH init"
fi

info "如果当前终端找不到 lc，请重新打开终端或执行：$LC_PATH --help"
