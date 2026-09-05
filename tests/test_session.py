import json
import os
import stat
from pathlib import Path

import pytest

from leetcode_local_cli.models.session import (
    Credentials,
    Session,
    SessionErrorKind,
    SessionFileError,
)
from leetcode_local_cli.storage import session


def _session() -> Session:
    return Session(
        Credentials("synthetic-session", "synthetic-csrf"), "learner", "Chrome"
    )


@pytest.mark.parametrize(
    ("content", "kind"),
    [
        (b"\xff", SessionErrorKind.INVALID_ENCODING),
        (b"{invalid", SessionErrorKind.INVALID_JSON),
        (b"[]", SessionErrorKind.INVALID_STRUCTURE),
        (b'{"cookies": []}', SessionErrorKind.INVALID_STRUCTURE),
        (b'{"cookies": {}}', SessionErrorKind.MISSING_COOKIES),
        (b'{"site":"other.invalid","cookies":{}}', SessionErrorKind.INVALID_STRUCTURE),
    ],
)
def test_load_classifies_corrupt_content(tmp_path, content, kind) -> None:
    path = tmp_path / "session.json"
    path.write_bytes(content)
    with pytest.raises(SessionFileError) as caught:
        session.load_session(path)
    assert caught.value.kind is kind
    assert path.read_bytes() == content


def test_load_distinguishes_missing_and_directory(tmp_path) -> None:
    for path, kind in (
        (tmp_path / "missing.json", SessionErrorKind.MISSING),
        (tmp_path, SessionErrorKind.READ_ERROR),
    ):
        with pytest.raises(SessionFileError) as caught:
            session.load_session(path)
        assert caught.value.kind is kind


@pytest.mark.parametrize(
    "value", [None, "", 123, "bad\r\nvalue", "bad;cookie", "非ASCII"]
)
def test_credentials_reject_invalid_header_values(value) -> None:
    with pytest.raises(SessionFileError) as caught:
        session.credentials_from_mapping(
            {"LEETCODE_SESSION": value, "csrftoken": "synthetic-csrf"}
        )
    assert caught.value.kind is SessionErrorKind.MISSING_COOKIES
    assert caught.value.missing_cookie_names == ("LEETCODE_SESSION",)
    assert "synthetic-csrf" not in str(caught.value)


def test_session_round_trip_private_permissions_and_one_read(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "state" / "session.json"
    expected = _session()
    session.save_session(expected, path)
    reads = []
    read_text = Path.read_text

    def counted_read(self, *args, **kwargs):
        reads.append(self)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted_read)
    assert session.load_session(path) == expected
    assert reads == [path]
    assert (
        json.loads(path.read_text(encoding="utf-8"))["cookies"]
        == expected.credentials.as_cookies()
    )
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not list(path.parent.glob("*.tmp"))


def test_session_discards_invalid_optional_metadata(tmp_path) -> None:
    path = tmp_path / "session.json"
    path.write_text(
        json.dumps(
            {
                "username": 123,
                "source": [],
                "cookies": _session().credentials.as_cookies(),
            }
        ),
        encoding="utf-8",
    )
    result = session.load_session(path)
    assert result.username is None and result.source is None


def test_credentials_do_not_appear_in_default_representations() -> None:
    value = _session()
    for rendered in (repr(value), repr(value.credentials), str(value)):
        assert "synthetic-session" not in rendered
        assert "synthetic-csrf" not in rendered


def test_save_preserves_existing_session_on_replace_failure(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "session.json"
    path.write_bytes(b"original")

    def fail(*args):
        raise PermissionError("synthetic failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(SessionFileError) as caught:
        session.save_session(_session(), path)
    assert caught.value.kind is SessionErrorKind.WRITE_ERROR
    assert path.read_bytes() == b"original"
    assert not list(tmp_path.glob("*.tmp"))


def test_save_rejects_file_as_state_directory(tmp_path) -> None:
    state = tmp_path / "state"
    state.write_bytes(b"original")
    with pytest.raises(SessionFileError) as caught:
        session.save_session(_session(), state / "session.json")
    assert caught.value.kind is SessionErrorKind.WRITE_ERROR
    assert state.read_bytes() == b"original"


@pytest.mark.parametrize("target_exists", [False, True])
def test_load_and_save_reject_symlinks(tmp_path, target_exists) -> None:
    target = tmp_path / "outside.json"
    if target_exists:
        session.save_session(_session(), target)
    path = tmp_path / "session.json"
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    for operation in (
        lambda: session.load_session(path),
        lambda: session.save_session(_session(), path),
    ):
        with pytest.raises(SessionFileError):
            operation()
    assert path.is_symlink()
    if target_exists:
        assert session.load_session(target) == _session()
