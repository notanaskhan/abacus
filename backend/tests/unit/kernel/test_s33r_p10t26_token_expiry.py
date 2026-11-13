"""P-10-T26 (DEC-3141): the caller's token expiry reaches the request context, so a stream closes
30 seconds before the token does."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel import request_context


def test_no_request_no_expiry() -> None:
    assert request_context.token_expires_at() is None


def test_identity_notes_the_expiry_and_the_request_reads_it() -> None:
    at = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
    with request_context.bound(request_context.RequestContext()):
        request_context.note_session(token_expires_at=at)
        request_context.note_session(mfa_at=at - timedelta(minutes=1))  # keeps the expiry
        assert request_context.token_expires_at() == at
    assert request_context.token_expires_at() is None


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_the_streams_pass_the_expiry_not_none() -> None:
    from pathlib import Path

    import abacus.modules.agents.run_stream as runs
    import abacus.modules.notifications.realtime as events

    for module in (runs, events):
        source = Path(str(module.__file__)).read_text()
        assert "expires_at=None" not in source
        assert "request_context.token_expires_at()" in source
