"""G-02-T06 (SPEC-349 AC-9): the request context's device reading is a closed list, the IP is an
address or nothing, and identity's notes land only inside a request."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from abacus.kernel import request_context as rc

CHROME_MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)
EDGE_WIN = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.2792.52"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like "
    "Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)


@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        (CHROME_MAC, ("Chrome", "Chrome · macOS")),
        (EDGE_WIN, ("Edge", "Edge · Windows")),
        (SAFARI_IPHONE, ("Safari", "Safari · iOS")),
        ("curl/8.7.1", ("Other", "Other")),
        ("Robert'); DROP TABLE x;--", ("Other", "Other")),
        (None, (None, None)),
        ("", (None, None)),
    ],
)
def test_device_of_names_a_family_and_a_system_from_a_closed_list(
    agent: str | None, expected: tuple[str | None, str | None]
) -> None:
    assert rc.device_of(agent) == expected


@pytest.mark.parametrize(
    ("host", "expected"),
    [("198.51.100.57", "198.51.100.57"), ("2001:db8::1", "2001:db8::1"), ("testclient", None)],
)
def test_client_ip_is_an_address_or_nothing(host: str, expected: str | None) -> None:
    assert rc.client_ip(host) == expected


def test_notes_land_inside_a_request_and_nowhere_else() -> None:
    rc.note_session(auth_method="support")
    assert rc.current() is None
    at = datetime(2026, 9, 14, 14, 1, tzinfo=UTC)
    session = uuid4()
    with rc.bound(rc.RequestContext(ip="198.51.100.57")):
        rc.note_session(mfa_at=at)
        rc.note_session(session_id=session, auth_method="email_code")
        found = rc.current()
        assert found is not None
        assert (found.ip, found.mfa_at, found.session_id, found.auth_method) == (
            "198.51.100.57",
            at,
            session,
            "email_code",
        )
    assert rc.current() is None


def test_the_cookie_is_kept_only_as_its_sha256() -> None:
    digest = rc.cookie_sha256("opaque-cookie-value")
    assert len(digest) == 64 and "opaque" not in digest
