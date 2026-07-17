import json
import subprocess

import pytest

from aether_lc.client import ClientErrorKind, ClientResult
from aether_lc.doctor import (
    DoctorCheck,
    DoctorReport,
    DoctorStatus,
    diagnose_remote,
    diagnose_session,
    diagnose_solution,
)
from aether_lc.workspace import ProblemMetadata, build_solution_content


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((), True),
        ((DoctorStatus.PASS,), True),
        ((DoctorStatus.WARNING,), True),
        ((DoctorStatus.PASS, DoctorStatus.WARNING), True),
        ((DoctorStatus.FAIL,), False),
        ((DoctorStatus.WARNING, DoctorStatus.FAIL), False),
    ],
)
def test_doctor_report_is_ok_only_without_failed_checks(statuses, expected) -> None:
    report = DoctorReport(
        checks=tuple(
            DoctorCheck(name="check", status=status, message="message")
            for status in statuses
        )
    )

    assert report.ok is expected


def test_diagnose_session_reports_valid_session_without_exposing_cookies(
    tmp_path,
) -> None:
    session_file = tmp_path / "session.json"
    session_value = "private-session-value"
    csrf_value = "private-csrf-value"
    session_file.write_text(
        json.dumps(
            {
                "username": "learner",
                "source": "Chrome",
                "cookies": {
                    "LEETCODE_SESSION": session_value,
                    "csrftoken": csrf_value,
                },
            }
        ),
        encoding="utf-8",
    )

    result = diagnose_session(session_file)

    assert result.status is DoctorStatus.PASS
    assert result.suggestion is None
    assert "learner" in result.message
    assert "Chrome" in result.message
    assert session_value not in repr(result)
    assert csrf_value not in repr(result)


@pytest.mark.parametrize(
    ("content", "expected_message"),
    [
        ("{invalid", "Session 文件不是有效的 JSON"),
        (json.dumps([]), "Session 文件结构无效"),
    ],
)
def test_diagnose_session_reports_invalid_session_file(
    tmp_path,
    content,
    expected_message,
) -> None:
    session_file = tmp_path / "session.json"
    session_file.write_text(content, encoding="utf-8")

    result = diagnose_session(session_file)

    assert result.status is DoctorStatus.FAIL
    assert result.message == expected_message
    assert result.suggestion is not None
    assert "uv run lc login" in result.suggestion


def test_diagnose_session_reports_missing_file(tmp_path) -> None:
    result = diagnose_session(tmp_path / "missing-session.json")

    assert result.status is DoctorStatus.FAIL
    assert result.message == "未找到 Session 文件"
    assert result.suggestion is not None
    assert "uv run lc login" in result.suggestion


def test_diagnose_session_reports_read_error(tmp_path) -> None:
    result = diagnose_session(tmp_path)

    assert result.status is DoctorStatus.FAIL
    assert result.message == "无法读取 Session 文件"
    assert result.suggestion is not None
    assert "文件权限" in result.suggestion


def test_diagnose_session_reports_missing_cookie_names(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    session_file.write_text(
        json.dumps({"cookies": {"LEETCODE_SESSION": ""}}),
        encoding="utf-8",
    )

    result = diagnose_session(session_file)

    assert result.status is DoctorStatus.FAIL
    assert result.message == "缺少或无效的 Cookie：LEETCODE_SESSION、csrftoken"
    assert result.suggestion is not None
    assert "uv run lc login" in result.suggestion


def test_diagnose_solution_reports_ready_workspace(tmp_path) -> None:
    solution_file = tmp_path / "solution.py"
    metadata = ProblemMetadata("1", "1", "Two Sum", "two-sum")
    solution_file.write_text(
        build_solution_content("class Solution:\n    pass", metadata),
        encoding="utf-8",
    )

    result = diagnose_solution(solution_file)

    assert result.status is DoctorStatus.PASS
    assert "1. Two Sum" in result.message


def test_diagnose_solution_reports_runtime_failure(tmp_path) -> None:
    solution_file = tmp_path / "solution.py"
    metadata = ProblemMetadata("1", "1", "Two Sum", "two-sum")
    content = build_solution_content("class Solution:\n    pass", metadata)
    solution_file.write_text(f"{content}\nraise RuntimeError\n", encoding="utf-8")

    result = diagnose_solution(solution_file)

    assert result.status is DoctorStatus.FAIL
    assert "本地运行失败" in result.message
    assert result.suggestion is not None
    assert "lc test" in result.suggestion


def test_diagnose_solution_runs_valid_file_without_submission_markers(tmp_path) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_text("raise RuntimeError\n", encoding="utf-8")

    result = diagnose_solution(solution_file)

    assert result.status is DoctorStatus.FAIL
    assert "本地运行失败" in result.message


def test_diagnose_solution_reports_runtime_timeout(tmp_path, monkeypatch) -> None:
    solution_file = tmp_path / "solution.py"
    metadata = ProblemMetadata("1", "1", "Two Sum", "two-sum")
    solution_file.write_text(
        build_solution_content("class Solution:\n    pass", metadata),
        encoding="utf-8",
    )

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("python", 10)

    monkeypatch.setattr("aether_lc.doctor.run_solution_file", raise_timeout)

    result = diagnose_solution(solution_file)

    assert result.status is DoctorStatus.FAIL
    assert "运行超时" in result.message


@pytest.mark.parametrize(
    ("content", "expected_status", "expected_text"),
    [
        ("", DoctorStatus.WARNING, "当前为空"),
        ("def broken(:\n", DoctorStatus.FAIL, "语法错误"),
        ("class Solution:\n    pass\n", DoctorStatus.WARNING, "暂不可提交"),
    ],
)
def test_diagnose_solution_maps_workspace_states(
    tmp_path,
    content,
    expected_status,
    expected_text,
) -> None:
    solution_file = tmp_path / "solution.py"
    solution_file.write_text(content, encoding="utf-8")

    result = diagnose_solution(solution_file)

    assert result.status is expected_status
    assert expected_text in result.message


def test_diagnose_solution_reports_missing_and_read_error(tmp_path) -> None:
    missing = diagnose_solution(tmp_path / "missing.py")
    read_error = diagnose_solution(tmp_path)

    assert missing.status is DoctorStatus.WARNING
    assert read_error.status is DoctorStatus.FAIL


@pytest.mark.parametrize(
    ("error_kind", "expected_text"),
    [
        (ClientErrorKind.NETWORK, "无法连接"),
        (ClientErrorKind.HTTP, "HTTP"),
        (ClientErrorKind.INVALID_JSON, "无法解析"),
        (ClientErrorKind.INVALID_RESPONSE, "接口结构异常"),
    ],
)
def test_diagnose_remote_reports_connectivity_failures(
    error_kind,
    expected_text,
) -> None:
    connectivity, authentication = diagnose_remote(ClientResult(error=error_kind))

    assert connectivity.status is DoctorStatus.FAIL
    assert expected_text in connectivity.message
    assert authentication.status is DoctorStatus.WARNING


def test_diagnose_remote_reports_expired_cookie() -> None:
    connectivity, authentication = diagnose_remote(
        ClientResult(data={"isSignedIn": False})
    )

    assert connectivity.status is DoctorStatus.PASS
    assert authentication.status is DoctorStatus.FAIL
    assert authentication.suggestion is not None
    assert "lc login" in authentication.suggestion


def test_diagnose_remote_reports_authenticated_user() -> None:
    connectivity, authentication = diagnose_remote(
        ClientResult(data={"isSignedIn": True, "username": "learner"})
    )

    assert connectivity.status is DoctorStatus.PASS
    assert authentication.status is DoctorStatus.PASS
    assert "learner" in authentication.message
