import json
import os
import stat

import pytest

from aether_lc import auth
from aether_lc.auth import SessionFileStatus


def _write_json(path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_inspect_session_file_returns_missing_when_file_does_not_exist(
    tmp_path,
) -> None:
    result = auth.inspect_session_file(tmp_path / "missing-session.json")

    assert result.status is SessionFileStatus.MISSING


def test_inspect_session_file_returns_invalid_json(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    session_file.write_text("{invalid", encoding="utf-8")

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.INVALID_JSON


def test_inspect_session_file_rejects_non_object_root(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    _write_json(session_file, [])

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.INVALID_STRUCTURE


def test_inspect_session_file_rejects_non_object_cookies(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    _write_json(session_file, {"cookies": []})

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.INVALID_STRUCTURE


@pytest.mark.parametrize(
    ("cookies", "expected_missing_names"),
    [
        ({"csrftoken": "csrf-value"}, ("LEETCODE_SESSION",)),
        (
            {"LEETCODE_SESSION": "session-value", "csrftoken": 123},
            ("csrftoken",),
        ),
        (
            {"LEETCODE_SESSION": "", "csrftoken": ""},
            ("LEETCODE_SESSION", "csrftoken"),
        ),
    ],
)
def test_inspect_session_file_reports_missing_or_invalid_cookies(
    tmp_path,
    cookies,
    expected_missing_names,
) -> None:
    session_file = tmp_path / "session.json"
    _write_json(session_file, {"cookies": cookies})

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.MISSING_COOKIES
    assert result.missing_cookie_names == expected_missing_names


def test_inspect_session_file_returns_sanitized_metadata_for_valid_session(
    tmp_path,
) -> None:
    session_file = tmp_path / "session.json"
    _write_json(
        session_file,
        {
            "username": "learner",
            "source": "Chrome",
            "cookies": {
                "LEETCODE_SESSION": "session-value",
                "csrftoken": "csrf-value",
            },
        },
    )

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.VALID
    assert result.username == "learner"
    assert result.source == "Chrome"


def test_inspect_session_file_discards_non_string_metadata(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    _write_json(
        session_file,
        {
            "username": 123,
            "source": ["Chrome"],
            "cookies": {
                "LEETCODE_SESSION": "session-value",
                "csrftoken": "csrf-value",
            },
        },
    )

    result = auth.inspect_session_file(session_file)

    assert result.status is SessionFileStatus.VALID
    assert result.username is None
    assert result.source is None


def test_inspect_session_file_returns_read_error_for_unreadable_path(tmp_path) -> None:
    result = auth.inspect_session_file(tmp_path)

    assert result.status is SessionFileStatus.READ_ERROR


def test_inspection_result_does_not_expose_cookie_values(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    session_value = "private-session-value"
    csrf_value = "private-csrf-value"
    _write_json(
        session_file,
        {
            "cookies": {
                "LEETCODE_SESSION": session_value,
                "csrftoken": csrf_value,
            }
        },
    )

    result = auth.inspect_session_file(session_file)
    result_text = repr(result)

    assert session_value not in result_text
    assert csrf_value not in result_text


def test_load_session_preserves_existing_success_and_failure_contract(
    tmp_path,
    monkeypatch,
) -> None:
    session_file = tmp_path / "session.json"
    monkeypatch.setattr(auth, "SESSION_FILE", session_file)
    session_data = {"cookies": {"LEETCODE_SESSION": "session-value"}}

    _write_json(session_file, session_data)
    assert auth.load_session() == session_data

    session_file.write_text("{invalid", encoding="utf-8")
    assert auth.load_session() is None

    session_file.unlink()
    assert auth.load_session() is None


def test_save_session_writes_atomically_with_private_permissions(tmp_path) -> None:
    session_file = tmp_path / "session.json"
    session_data = {
        "cookies": {
            "LEETCODE_SESSION": "session-value",
            "csrftoken": "csrf-value",
        }
    }

    auth.save_session(session_data, session_file)

    assert json.loads(session_file.read_text(encoding="utf-8")) == session_data
    assert not session_file.with_suffix(".json.tmp").exists()
    if os.name != "nt":
        assert stat.S_IMODE(session_file.stat().st_mode) == 0o600


def test_save_session_cleans_temporary_file_after_serialization_error(
    tmp_path,
) -> None:
    session_file = tmp_path / "session.json"

    with pytest.raises(auth.SessionFileError, match="无法保存 Session 文件"):
        auth.save_session({"invalid": object()}, session_file)

    assert not session_file.exists()
    assert not session_file.with_suffix(".json.tmp").exists()


def test_load_session_raises_clear_error_for_unreadable_path(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(auth, "SESSION_FILE", tmp_path)

    with pytest.raises(auth.SessionFileError, match="无法读取 Session 文件"):
        auth.load_session()


def test_parse_cookie_header_extracts_required_cookies() -> None:
    result = auth.parse_cookie_header(
        "other=value; LEETCODE_SESSION=session=with=equals; csrftoken=csrf"
    )

    assert result == {
        "LEETCODE_SESSION": "session=with=equals",
        "csrftoken": "csrf",
    }


def test_parse_cookie_header_rejects_missing_required_cookie() -> None:
    assert auth.parse_cookie_header("LEETCODE_SESSION=session") is None
