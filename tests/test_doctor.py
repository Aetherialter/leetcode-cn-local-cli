import json

import pytest

from aether_lc.doctor import DoctorCheck, DoctorReport, DoctorStatus, diagnose_session


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
