"""N-04-T16 (TASK-3312; DEC-2311): readiness, the follow-up date and the alert plan, from the row.

"On staging the Whitley response reaches Ready to send only after both signatures and an accepted
confirmation, mark-sent on Sep 17 schedules Nov 16, and no route ever calls an irs.gov host." The
database half lands at the integration pass; the staging clause waits for a staging run.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import sending
from abacus.modules.notices.response_workflow import ALERTS, CP3219A_ALERTS, alert_days
from abacus.modules.notices.sending import follow_up_on, readiness_of

_WHITLEY_PAYMENT = {"required": True, "confirmation_accepted": False}


def test_ac_mark_sent_on_sep_17_schedules_nov_16() -> None:
    assert follow_up_on(date(2026, 9, 17), 60) == date(2026, 11, 16)


def test_ac_ready_only_after_signatures_and_an_accepted_confirmation() -> None:
    assert readiness_of(False, _WHITLEY_PAYMENT, []).blocking == ("envelope", "payment")
    assert readiness_of(True, _WHITLEY_PAYMENT, []).blocking == ("payment",)
    accepted = {"required": True, "confirmation_accepted": True}
    assert readiness_of(False, accepted, []).blocking == ("envelope",)
    assert readiness_of(True, accepted, []).ready


def test_ac_no_payment_needs_no_confirmation() -> None:
    assert readiness_of(True, None, []).ready


def test_ac_a_missing_enclosure_blocks() -> None:
    assert readiness_of(True, None, [{"key": "1099-int"}]).blocking == ("enclosures",)
    assert readiness_of(True, None, [{"key": "1099-int", "included": False}]).ready
    assert readiness_of(True, None, [{"key": "a", "evidence_version_id": "x"}]).ready


def test_ac_r07_a_notice_is_never_ready_unsigned_whatever_else_holds() -> None:
    for payment in (None, {"required": False}, {"required": True, "confirmation_accepted": True}):
        assert not readiness_of(False, payment, []).ready


def test_ac_alert_days_by_notice() -> None:
    assert alert_days("cp2000") == ALERTS == (7, 2)
    assert alert_days("cp3219a") == CP3219A_ALERTS == (30, 14, 7, 2)


def test_ac_no_route_ever_calls_an_irs_host() -> None:
    source = Path(sending.__file__).read_text()
    assert "irs.gov" not in source.lower()
    tree = ast.parse(source)
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert not imports & {"httpx", "requests", "aiohttp", "urllib"}


async def test_ac_an_agency_reply_cites_only_its_own_engagements_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The evidence column has no key: another engagement's version is refused as absent."""
    ctx = SimpleNamespace(tenant=object(), tenant_id=uuid4(), user_id=uuid4())
    found = SimpleNamespace(engagement_id=uuid4())

    async def _notice(*_: object) -> object:
        return found

    async def _view(*_: object) -> object:
        return SimpleNamespace(engagement_id=uuid4())

    monkeypatch.setattr(sending, "notice", _notice)
    monkeypatch.setattr(sending, "version_view", _view)
    with pytest.raises(NotFound):
        await sending.agency_reply(
            cast(AuthContext, ctx),
            uuid4(),
            outcome="resolved",
            closed_on=None,
            note=None,
            evidence_version_id=uuid4(),
        )
