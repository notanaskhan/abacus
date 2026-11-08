"""N-04-T13 (TASK-3265; DEC-2245): notice intake sources.

Row acceptance: "An inbox item, a portal upload and an organizer Q8 upload each create exactly
one intake, and with the flag off they stay where they were with pending_handler." Here: the
registrations and the fail-closed handler; the three sources run end to end in N-04-T15's suite.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from abacus.kernel import _flags
from abacus.modules.notices import intake_sources
from abacus.modules.requests.api import EffectRequest, HandlerUnavailable, answer_effect_handler


def test_notices_owns_route_upload_to_notices_and_two_destinations() -> None:
    import abacus.modules.notices.api
    from abacus.modules.communications import triage_apply

    assert abacus.modules.notices.api is not None
    assert (
        answer_effect_handler("route_upload_to_notices") is intake_sources.route_upload_to_notices
    )
    assert {"notice", "notice_intake"} <= set(triage_apply._DESTINATIONS)  # pyright: ignore[reportPrivateUsage] -- the private helper under test


def test_an_upload_without_a_file_is_unavailable_so_the_engine_records_pending() -> None:
    request = EffectRequest(uuid4(), uuid4(), uuid4(), uuid4(), "r_irs_letter", None, None)
    with pytest.raises(HandlerUnavailable):
        asyncio.run(intake_sources.route_upload_to_notices(request))


def test_no_retired_flag_gates_the_effect() -> None:
    """`notices.workspace` retired (DEC-2602): "notices off" is no longer a state, so the effect
    reads no flag; the only unavailable case is an upload with no evidence version (above)."""
    assert not hasattr(intake_sources, "flag_enabled")
    assert not hasattr(_flags, "NOTICES_WORKSPACE")
