from pathlib import Path
import subprocess

import pytest

from leetcode_local_cli import browser
from leetcode_local_cli.auth import DevToolsBrowserInfo


def test_find_chrome_executable_uses_known_windows_installation(tmp_path: Path) -> None:
    program_files = tmp_path / "Program Files"
    executable = program_files / "Google" / "Chrome" / "Application" / "chrome.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()

    result = browser.find_chrome_executable(
        environment={"PROGRAMFILES": str(program_files)},
        home=tmp_path,
        platform="win32",
        os_name="nt",
    )

    assert result == executable


def test_find_edge_executable_uses_known_windows_installation(tmp_path: Path) -> None:
    program_files = tmp_path / "Program Files (x86)"
    executable = program_files / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()

    result = browser.find_edge_executable(
        environment={"PROGRAMFILES(X86)": str(program_files)},
        home=tmp_path,
        platform="win32",
        os_name="nt",
    )

    assert result == executable


@pytest.mark.parametrize(
    ("finder", "browser_name"),
    [
        (browser.find_chrome_executable, "Chrome"),
        (browser.find_edge_executable, "Microsoft Edge"),
    ],
)
def test_find_browser_executable_reports_missing_browser(
    finder,
    browser_name,
    tmp_path: Path,
) -> None:
    with pytest.raises(browser.BrowserError, match=browser_name):
        finder(
            environment={},
            home=tmp_path,
            platform="win32",
            os_name="nt",
        )


@pytest.mark.parametrize(
    ("kind", "executable_name", "debug_url"),
    [
        (
            browser.BrowserKind.CHROME,
            "chrome.exe",
            "chrome://inspect/#remote-debugging",
        ),
        (
            browser.BrowserKind.EDGE,
            "msedge.exe",
            "edge://inspect/#remote-debugging",
        ),
    ],
)
def test_open_browser_authorization_pages_does_not_claim_process_ownership(
    kind,
    executable_name,
    debug_url,
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / executable_name
    executable.touch()
    received = []
    monkeypatch.setattr(
        browser.subprocess,
        "Popen",
        lambda command, **kwargs: received.append((command, kwargs)) or object(),
    )

    assert browser.open_browser_authorization_pages(kind, executable=executable) is None

    command, options = received[0]
    assert command == [
        str(executable),
        "--new-window",
        debug_url,
        "https://leetcode.cn/",
    ]
    assert options == {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }


@pytest.mark.parametrize(
    "kind",
    [browser.BrowserKind.CHROME, browser.BrowserKind.EDGE],
)
def test_read_browser_devtools_endpoint_accepts_valid_file(
    kind,
    tmp_path: Path,
) -> None:
    port_file = tmp_path / "User Data" / "DevToolsActivePort"
    port_file.parent.mkdir(parents=True)
    port_file.write_text("53127\n/devtools/browser/example\n", encoding="utf-8")

    endpoint = browser.read_browser_devtools_endpoint(kind, port_file=port_file)

    assert endpoint == browser.BrowserDevToolsEndpoint(
        port=53127,
        debugger_url="ws://127.0.0.1:53127/devtools/browser/example",
    )


@pytest.mark.parametrize(
    "kind",
    [browser.BrowserKind.CHROME, browser.BrowserKind.EDGE],
)
def test_read_browser_devtools_endpoint_reports_missing_authorization(
    kind,
    tmp_path: Path,
) -> None:
    port_file = tmp_path / "User Data" / "DevToolsActivePort"
    port_file.parent.mkdir(parents=True)

    with pytest.raises(browser.BrowserAuthorizationPending, match="尚未授权"):
        browser.read_browser_devtools_endpoint(kind, port_file=port_file)


@pytest.mark.parametrize(
    "content",
    [
        "not-a-port\n/devtools/browser/example\n",
        "9222\nnot-a-browser-path\n",
        "9222\n",
        "9222\n/devtools/browser/example?redirect=evil\n",
        "9222\n/devtools/browser/example bad\n",
    ],
)
def test_read_browser_devtools_endpoint_rejects_invalid_content(
    content,
    tmp_path: Path,
) -> None:
    port_file = tmp_path / "User Data" / "DevToolsActivePort"
    port_file.parent.mkdir(parents=True)
    port_file.write_text(content, encoding="utf-8")

    with pytest.raises(browser.BrowserError, match="无效"):
        browser.read_browser_devtools_endpoint(
            browser.BrowserKind.CHROME,
            port_file=port_file,
        )


def test_read_browser_devtools_endpoint_rejects_directory_target(
    tmp_path: Path,
) -> None:
    port_file = tmp_path / "User Data" / "DevToolsActivePort"
    port_file.mkdir(parents=True)

    with pytest.raises(browser.BrowserError, match="目录"):
        browser.read_browser_devtools_endpoint(
            browser.BrowserKind.EDGE,
            port_file=port_file,
        )


@pytest.mark.parametrize(
    ("kind", "reported_browser"),
    [
        (browser.BrowserKind.CHROME, "Chrome/140.0"),
        (browser.BrowserKind.EDGE, "Edg/140.0"),
    ],
)
def test_validate_devtools_browser_accepts_requested_identity(
    kind,
    reported_browser,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        browser,
        "get_devtools_browser_info",
        lambda port: DevToolsBrowserInfo(
            browser=reported_browser,
            debugger_url=f"ws://127.0.0.1:{port}/devtools/browser/example",
        ),
    )

    assert browser.validate_devtools_browser(9222, kind) is None


def test_validate_devtools_browser_rejects_wrong_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        browser,
        "get_devtools_browser_info",
        lambda port: DevToolsBrowserInfo(
            browser="Chrome/140.0",
            debugger_url=f"ws://127.0.0.1:{port}/devtools/browser/example",
        ),
    )

    with pytest.raises(browser.BrowserError, match="不是 Microsoft Edge"):
        browser.validate_devtools_browser(9222, browser.BrowserKind.EDGE)
