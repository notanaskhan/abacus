"""Q-03-T067: sealed list cursors (ADR-139, P-36; F-03-T29), from the module's contract.

- A cursor is sealed under the deployment's current payload key and names that key, so it still
  opens after another key is added to the ring; a key removed from the ring no longer opens it.
- The associated data binds a cursor to what it was issued for: other data never opens it.
- Anything that is not a cursor this deployment sealed is `CursorUnreadable`.
- Local runs without a keyring seal with a key made for the process; anywhere else with no
  keyring nothing is sealed (`ServiceUnavailable`).
"""

from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from abacus.kernel.crypto import cursor
from abacus.kernel.errors import ServiceUnavailable

AAD = b"tenant|engagements|q=open"


def _secret(value: str) -> SimpleNamespace:
    return SimpleNamespace(get_secret_value=lambda: value)


def _ring(monkeypatch: pytest.MonkeyPatch, current: str | None, **keys: str) -> None:
    monkeypatch.setattr(
        cursor,
        "settings",
        lambda: SimpleNamespace(
            temporal_payload_keys={kid: _secret(v) for kid, v in keys.items()} or None,
            temporal_payload_current=current,
            environment="production",
        ),
    )


def _local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cursor,
        "settings",
        lambda: SimpleNamespace(
            temporal_payload_keys=None, temporal_payload_current=None, environment="local"
        ),
    )


def test_a_cursor_round_trips_and_names_its_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _ring(monkeypatch, "k1", k1="first-secret")
    token = cursor.seal_cursor(b'{"after": 40}', AAD)
    assert cursor.open_cursor(token, AAD) == b'{"after": 40}'
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    assert raw[0] == 1 and raw[2 : 2 + raw[1]] == b"k1"


def test_a_cursor_survives_a_key_added_and_dies_with_its_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ring(monkeypatch, "k1", k1="first-secret")
    token = cursor.seal_cursor(b"page-2", AAD)
    _ring(monkeypatch, "k2", k1="first-secret", k2="second-secret")
    assert cursor.open_cursor(token, AAD) == b"page-2"
    _ring(monkeypatch, "k2", k2="second-secret")
    with pytest.raises(cursor.CursorUnreadable):
        cursor.open_cursor(token, AAD)


def test_other_associated_data_never_opens_a_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    _ring(monkeypatch, "k1", k1="first-secret")
    token = cursor.seal_cursor(b"page-2", AAD)
    with pytest.raises(cursor.CursorUnreadable):
        cursor.open_cursor(token, b"tenant|engagements|q=closed")


@pytest.mark.parametrize(
    "token",
    [
        "%%%not-base64%%%",
        "",  # nothing
        base64.urlsafe_b64encode(b"\x02\x02k1" + b"\x00" * 40).decode(),  # another version
        base64.urlsafe_b64encode(b"\x01\x02\xff\xfe" + b"\x00" * 40).decode(),  # kid not UTF-8
        base64.urlsafe_b64encode(b"\x01\x02zz" + b"\x00" * 40).decode(),  # unknown key id
        base64.urlsafe_b64encode(b"\x01\x02k1" + b"\x00" * 5).decode(),  # short nonce
    ],
)
def test_anything_but_a_sealed_cursor_is_unreadable(
    monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    _ring(monkeypatch, "k1", k1="first-secret")
    with pytest.raises(cursor.CursorUnreadable):
        cursor.open_cursor(token, AAD)


def test_a_tampered_cursor_is_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    _ring(monkeypatch, "k1", k1="first-secret")
    raw = bytearray(base64.urlsafe_b64decode(cursor.seal_cursor(b"page-2", AAD) + "=="))
    raw[-1] ^= 1
    with pytest.raises(cursor.CursorUnreadable):
        cursor.open_cursor(base64.urlsafe_b64encode(bytes(raw)).decode(), AAD)


def test_a_local_run_without_a_ring_seals_with_the_process_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _local(monkeypatch)
    token = cursor.seal_cursor(b"page-2", AAD)
    assert cursor.open_cursor(token, AAD) == b"page-2"
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    assert raw[2 : 2 + raw[1]] == b"local"


def test_a_ring_whose_current_key_is_missing_is_no_ring(monkeypatch: pytest.MonkeyPatch) -> None:
    _ring(monkeypatch, "k9", k1="first-secret")
    with pytest.raises(ServiceUnavailable):
        cursor.seal_cursor(b"page-2", AAD)


def test_outside_local_with_no_ring_nothing_is_sealed(monkeypatch: pytest.MonkeyPatch) -> None:
    _ring(monkeypatch, None)
    with pytest.raises(ServiceUnavailable):
        cursor.seal_cursor(b"page-2", AAD)
