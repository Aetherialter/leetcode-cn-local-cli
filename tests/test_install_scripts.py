import os
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHELL_INSTALLER = PROJECT_ROOT / "scripts" / "install.sh"
POWERSHELL_INSTALLER = PROJECT_ROOT / "scripts" / "install.ps1"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _write_fake_uv(path: Path) -> None:
    _write_executable(
        path,
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_UV_LOG"
case "$*" in
    "tool install --force "*) exit 0 ;;
    "tool update-shell") exit 0 ;;
    "tool dir --bin") printf '%s\\n' "$FAKE_TOOL_BIN" ;;
    *) exit 2 ;;
esac
""",
    )


def _write_fake_lc(path: Path) -> None:
    _write_executable(
        path,
        """#!/bin/sh
[ "$1" = "--version" ] || exit 2
printf '%s\\n' 'leetcode-local-cli 9.9.9'
""",
    )


def _installer_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "bin"
    tool_bin = tmp_path / "tool-bin"
    fake_bin.mkdir()
    tool_bin.mkdir()
    log_file = tmp_path / "uv.log"
    _write_fake_lc(tool_bin / "lc")

    environment = os.environ.copy()
    environment.update(
        {
            "LEETCODE_LOCAL_CLI_INSTALL_SPEC": str(tmp_path / "leetcode_local_cli.whl"),
            "FAKE_TOOL_BIN": str(tool_bin),
            "FAKE_UV_LOG": str(log_file),
            "HOME": str(tmp_path / "home"),
            "PATH": f"{fake_bin}:/usr/bin:/bin",
        }
    )
    return environment, fake_bin, log_file


def test_shell_installer_has_valid_syntax() -> None:
    result = subprocess.run(
        ["sh", "-n", str(SHELL_INSTALLER)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_shell_installer_uses_existing_uv_and_verifies_lc(tmp_path) -> None:
    environment, fake_bin, log_file = _installer_environment(tmp_path)
    _write_fake_uv(fake_bin / "uv")

    result = subprocess.run(
        [str(SHELL_INSTALLER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = log_file.read_text(encoding="utf-8").splitlines()
    assert calls == [
        f"tool install --force {tmp_path / 'leetcode_local_cli.whl'}",
        "tool update-shell",
        "tool dir --bin",
    ]
    assert "安装成功：leetcode-local-cli 9.9.9" in result.stdout


def test_shell_installer_bootstraps_uv_when_missing(tmp_path) -> None:
    environment, fake_bin, log_file = _installer_environment(tmp_path)
    fake_uv_template = tmp_path / "fake-uv"
    fake_uv_installer = tmp_path / "fake-install-uv.sh"
    _write_fake_uv(fake_uv_template)
    _write_executable(
        fake_uv_installer,
        """#!/bin/sh
mkdir -p "$HOME/.local/bin"
cp "$FAKE_UV_TEMPLATE" "$HOME/.local/bin/uv"
chmod +x "$HOME/.local/bin/uv"
""",
    )
    _write_executable(
        fake_bin / "curl",
        """#!/bin/sh
output=''
while [ "$#" -gt 0 ]; do
    if [ "$1" = '-o' ]; then
        shift
        output=$1
    fi
    shift
done
[ -n "$output" ] || exit 2
cp "$FAKE_UV_INSTALLER" "$output"
""",
    )
    environment.update(
        {
            "FAKE_UV_INSTALLER": str(fake_uv_installer),
            "FAKE_UV_TEMPLATE": str(fake_uv_template),
        }
    )

    result = subprocess.run(
        [str(SHELL_INSTALLER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "home" / ".local" / "bin" / "uv").is_file()
    assert "未检测到 uv" in result.stdout
    assert "tool install --force" in log_file.read_text(encoding="utf-8")


def test_shell_installer_rejects_non_https_uv_installer(tmp_path) -> None:
    environment, _, _ = _installer_environment(tmp_path)
    environment["LEETCODE_LOCAL_CLI_UV_INSTALL_URL"] = "http://example.com/install.sh"

    result = subprocess.run(
        [str(SHELL_INSTALLER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 1
    assert "必须使用 HTTPS" in result.stderr


def test_shell_installer_rejects_non_https_package_source(tmp_path) -> None:
    environment, fake_bin, _ = _installer_environment(tmp_path)
    _write_fake_uv(fake_bin / "uv")
    environment["LEETCODE_LOCAL_CLI_INSTALL_SPEC"] = (
        "http://example.com/leetcode-local-cli.whl"
    )

    result = subprocess.run(
        [str(SHELL_INSTALLER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 1
    assert "必须使用 HTTPS" in result.stderr


def test_shell_installer_rejects_non_https_url_inside_package_spec(tmp_path) -> None:
    environment, fake_bin, _ = _installer_environment(tmp_path)
    _write_fake_uv(fake_bin / "uv")
    environment["LEETCODE_LOCAL_CLI_INSTALL_SPEC"] = (
        "leetcode-local-cli @ git+http://example.com/leetcode-local-cli.git"
    )

    result = subprocess.run(
        [str(SHELL_INSTALLER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 1
    assert "必须使用 HTTPS" in result.stderr


def test_shell_installer_propagates_uv_install_failure(tmp_path) -> None:
    environment, fake_bin, _ = _installer_environment(tmp_path)
    _write_executable(
        fake_bin / "uv",
        """#!/bin/sh
if [ "$*" = "tool install --force $LEETCODE_LOCAL_CLI_INSTALL_SPEC" ]; then
    exit 17
fi
exit 2
""",
    )

    result = subprocess.run(
        [str(SHELL_INSTALLER)],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 17
    assert "安装成功" not in result.stdout


def test_powershell_installer_declares_same_install_contract() -> None:
    content = POWERSHELL_INSTALLER.read_text(encoding="utf-8")

    assert "https://astral.sh/uv/install.ps1" in content
    assert "LEETCODE_LOCAL_CLI_INSTALL_SPEC" in content
    assert "tool install --force" in content
    assert "tool update-shell" in content
    assert "--version" in content
    assert 'IndexOf("http://"' in content
