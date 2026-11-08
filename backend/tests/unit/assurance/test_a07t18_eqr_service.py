"""A-07-T18 (TASK-6109; A-07 §3.1; SQMS 2): the EQR service's refusals, in order.

Row acceptance: "Concur is refused while any item or EQR note is open, refused for Hannah Leclerc
with 403 eqr_only, and on success records G6 and notifies Margaret Okonkwo." The database half (the
concurrence row, the review status, the notification) runs in the end-pass integration set; here
the order of the checks, with the engagement reads patched.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import eqr_service as eqr
from abacus.modules.identity.api import AuthContext

pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 10, 8, 15, tzinfo=UTC)
EQR_USER, HANNAH, MARGARET = uuid4(), uuid4(), uuid4()
ENGAGEMENT, WORK_ITEM, REVIEW = uuid4(), uuid4(), uuid4()


def _ctx(user: UUID, *, mfa_minutes_ago: float | None = 1, actor: str = "human") -> AuthContext:
    mfa = None if mfa_minutes_ago is None else NOW - timedelta(minutes=mfa_minutes_ago)
    return AuthContext(
        TenantContext(uuid4(), actor, str(user)),  # type: ignore[arg-type]
        user,
        uuid4(),
        None,
        mfa,
    )


@pytest.fixture(autouse=True)
def patched(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    state: dict[str, object] = {"notes": []}

    async def review(tenant: TenantContext, work_item_id: UUID) -> eqr.ReviewRow:
        return eqr.ReviewRow(REVIEW, ENGAGEMENT, work_item_id, EQR_USER, "in_progress", 3)

    async def get_ref(ctx: AuthContext, engagement_id: UUID) -> object:
        return SimpleNamespace(resource=lambda: None)

    async def authorise(ctx: AuthContext, action: str, resource: object) -> None:
        return None

    async def open_notes(tenant: TenantContext, engagement_id: UUID) -> object:
        return state["notes"]

    async def team_of(tenant_id: UUID, engagement_id: UUID) -> object:
        return [(MARGARET, "engagement_partner"), (EQR_USER, "eqr_reviewer")]

    monkeypatch.setattr(eqr, "_review", review)
    monkeypatch.setattr(eqr, "get_ref", get_ref)
    monkeypatch.setattr(eqr, "authorise", authorise)
    monkeypatch.setattr(eqr, "open_notes", open_notes)
    monkeypatch.setattr(eqr, "team_of", team_of)
    monkeypatch.setattr(eqr.clock, "system_now", lambda: NOW)
    return state


async def test_hannah_is_refused_403_eqr_only() -> None:
    with pytest.raises(eqr.EqrOnly):
        await eqr.concur(
            _ctx(HANNAH), WORK_ITEM, not_involved=True, concurrence_date=date(2026, 10, 8)
        )
    assert eqr.EqrOnly.code == "eqr_only"


async def test_an_agent_context_is_refused_even_as_the_eqr() -> None:
    with pytest.raises(eqr.EqrOnly):
        await eqr.concur(
            _ctx(EQR_USER, actor="agent"),
            WORK_ITEM,
            not_involved=True,
            concurrence_date=date(2026, 10, 8),
        )


@pytest.mark.parametrize("minutes", [None, 16])
async def test_concur_needs_a_second_factor_in_the_last_15_minutes(minutes: float | None) -> None:
    with pytest.raises(eqr.MfaRequired):
        await eqr.concur(
            _ctx(EQR_USER, mfa_minutes_ago=minutes),
            WORK_ITEM,
            not_involved=True,
            concurrence_date=date(2026, 10, 8),
        )


async def test_concur_needs_the_not_involved_attestation() -> None:
    with pytest.raises(eqr.ChecklistIncomplete):
        await eqr.concur(
            _ctx(EQR_USER), WORK_ITEM, not_involved=False, concurrence_date=date(2026, 10, 8)
        )


async def test_an_open_eqr_note_on_this_review_refuses_concur(patched: dict[str, object]) -> None:
    patched["notes"] = [(uuid4(), REVIEW)]
    with pytest.raises(eqr.EqrNotesOpen):
        await eqr.concur(
            _ctx(EQR_USER), WORK_ITEM, not_involved=True, concurrence_date=date(2026, 10, 8)
        )


async def test_notes_on_other_targets_do_not_count_as_eqr_notes(
    patched: dict[str, object],
) -> None:
    patched["notes"] = [(uuid4(), uuid4())]
    # Past the note check, the database half runs (no engine here): a configuration error, not a
    # refusal of the EQR's.
    with pytest.raises(Exception) as caught:
        await eqr.concur(
            _ctx(EQR_USER), WORK_ITEM, not_involved=True, concurrence_date=date(2026, 10, 8)
        )
    assert not isinstance(caught.value, eqr.EqrNotesOpen | eqr.EqrOnly | eqr.MfaRequired)


async def test_checklist_and_card_acts_are_the_eqr_s_only() -> None:
    with pytest.raises(eqr.EqrOnly):
        await eqr.update_checklist(_ctx(HANNAH), WORK_ITEM, "materiality", "done", None, 1)
    with pytest.raises(eqr.EqrOnly):
        await eqr.mark_reviewed(_ctx(HANNAH), WORK_ITEM, uuid4(), True)


async def test_a_review_opens_only_for_an_eligible_eqr_with_a_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing(tenant: TenantContext, engagement_id: UUID, user_id: UUID) -> dict[str, str]:
        return {"not_on_team": "pass", "cooling_off": "fail"}

    async def passing(tenant: TenantContext, engagement_id: UUID, user_id: UUID) -> dict[str, str]:
        return {"not_on_team": "pass", "cooling_off": "pass"}

    tenant = TenantContext(uuid4(), "system", "test")
    monkeypatch.setattr(eqr, "eqr_eligibility", failing)
    with pytest.raises(eqr.EqrNotEligible):
        await eqr.open_reviews(tenant, ENGAGEMENT, EQR_USER)
    monkeypatch.setattr(eqr, "eqr_eligibility", passing)
    monkeypatch.setattr(eqr, "_TEMPLATE", [])
    with pytest.raises(eqr.EqrTemplateMissing):
        await eqr.open_reviews(tenant, ENGAGEMENT, EQR_USER)


def test_the_concurrence_event_names_the_partners_and_the_catalogue_notifies_them() -> None:
    from abacus.modules.notifications.api import CATALOGUE

    assert CATALOGUE["eqr.concurred_v2"].kind == "eqr_concurred"
    assert CATALOGUE["eqr.requested"].kind == "eqr_requested"
    assert "partner_user_ids" in eqr.EqrConcurredV2.model_fields
