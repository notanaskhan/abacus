"""Independent AC tests for A-07-T15, T18, T19 and T23's guard (A-07-T21; ADR-078; TASK-6219).

Written from the A-07-T21 row, SQMS 2 and A-07 F1/F9, not the authors' tests. Row acceptance: "The
suite fails if the EQR can sign L1-L4 or if G6 reads met before a concurrence row exists." Covered:
the I-GATES table for G6-G9 by engagement type and release mode; the EQR signs L5 only and is
denied every mutating workpaper act; concur is the assigned EQR's alone (403 `eqr_only`), never an
agent's; the engagement partner can never open as the EQR; the digest is built from decided cards
only; the A-07 registrations are inert with every flag off; the bring-down never starts for an
external-mode firm or while `COMPLETION_LIVE` is False.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import (
    a07_registrations,
    bring_down,
    completion_dark,
    completion_projector,
    eqr_service,
    gates,
)
from abacus.modules.engagements.api import GateFact
from abacus.modules.engagements.gate_policy import FAMILY, required_gates
from abacus.modules.identity.authz import matrix
from abacus.modules.identity.context import AuthContext

Provider = Callable[[TenantContext, uuid.UUID], Awaitable[GateFact]]
TENANT = TenantContext(uuid.uuid4(), "system", "test")
ENGAGEMENT = uuid.uuid4()
EXTERNAL = GateFact(met=False, blockers=("external_record",))
BLANK: dict[str, object] = {
    "engagement_type": "ebp_audit", "eqr_status": None, "eqr_user_id": None,
    "letter_status": None, "released": False, "archive_status": None,
}  # fmt: skip


def _providers(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    facts: dict[str, object] | None,
    *,
    eqr_on_team: bool = False,
) -> dict[str, Provider]:
    registered: dict[str, Provider] = {}
    monkeypatch.setattr(gates, "register_gate_provider", registered.__setitem__)
    monkeypatch.setattr(gates, "replace_gate_provider", registered.__setitem__)
    monkeypatch.setattr(gates, "register_completion_gates", lambda: None)

    async def external(_t: TenantContext, _e: uuid.UUID) -> GateFact:
        return EXTERNAL

    async def release_mode(_t: TenantContext) -> str:
        return mode

    async def read(_t: TenantContext, _e: uuid.UUID) -> dict[str, object] | None:
        return facts

    async def on_team(_t: TenantContext, _e: uuid.UUID) -> bool:
        return eqr_on_team

    for name in ("g6", "g7", "g8", "g9"):
        monkeypatch.setattr(gates, name, external)
    monkeypatch.setattr(gates, "release_mode", release_mode)
    monkeypatch.setattr(gates, "_in_app_facts", read)
    monkeypatch.setattr(gates, "_eqr_on_team", on_team)
    gates.register()
    return registered


# --- I-GATES: G6-G9 by engagement type and release mode ----------------------------------------

ATTEST = sorted(t for t, family in FAMILY.items() if family == "attest")
COMP_PREP = sorted(t for t, family in FAMILY.items() if family == "compilation_preparation")


@pytest.mark.parametrize("engagement_type", ATTEST + COMP_PREP)
@pytest.mark.parametrize("gate", ["G6", "G7", "G8", "G9"])
async def test_external_mode_keeps_the_external_answer(
    monkeypatch: pytest.MonkeyPatch, engagement_type: str, gate: str
) -> None:
    providers = _providers(monkeypatch, "external", {**BLANK, "engagement_type": engagement_type})
    assert await providers[gate](TENANT, ENGAGEMENT) == EXTERNAL


@pytest.mark.parametrize("engagement_type", ATTEST)
@pytest.mark.parametrize(
    ("gate", "facts", "met"),
    [
        ("G6", {"eqr_user_id": uuid.uuid4(), "eqr_status": "open"}, False),
        ("G6", {"eqr_user_id": uuid.uuid4(), "eqr_status": "concurred"}, True),
        ("G7", {"letter_status": "sent"}, False),
        ("G7", {"letter_status": "signed"}, True),
        ("G8", {"released": False}, False),
        ("G8", {"released": True}, True),
        ("G9", {"archive_status": "assembling"}, False),
        ("G9", {"archive_status": "locked"}, True),
    ],
)
async def test_in_app_attest_reads_each_gate_live(
    monkeypatch: pytest.MonkeyPatch,
    engagement_type: str,
    gate: str,
    facts: dict[str, object],
    met: bool,
) -> None:
    assert gate in required_gates(engagement_type)
    providers = _providers(
        monkeypatch, "in_app", {**BLANK, "engagement_type": engagement_type, **facts}
    )
    assert (await providers[gate](TENANT, ENGAGEMENT)).met is met


@pytest.mark.parametrize("engagement_type", COMP_PREP)
async def test_in_app_compilation_and_preparation_never_require_g6_or_g7(
    monkeypatch: pytest.MonkeyPatch, engagement_type: str
) -> None:
    assert {"G6", "G7"}.isdisjoint(required_gates(engagement_type))
    facts = {**BLANK, "engagement_type": engagement_type, "eqr_user_id": uuid.uuid4()}
    providers = _providers(monkeypatch, "in_app", facts, eqr_on_team=True)
    assert (await providers["G6"](TENANT, ENGAGEMENT)).met
    assert (await providers["G8"](TENANT, ENGAGEMENT)).met is False


async def test_g6_is_unmet_while_an_assigned_eqr_has_no_concurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The EQR is on the ENG-05 team, but the review hasn't opened (no row, so no concurrence):
    G6 must not read met (row acceptance)."""
    providers = _providers(monkeypatch, "in_app", dict(BLANK), eqr_on_team=True)
    fact = await providers["G6"](TENANT, ENGAGEMENT)
    assert fact.met is False and fact.blockers == ("eqr_not_concurred",)


async def test_g6_is_met_only_without_an_eqr_or_with_a_concurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    none = _providers(monkeypatch, "in_app", dict(BLANK), eqr_on_team=False)
    assert (await none["G6"](TENANT, ENGAGEMENT)).met
    concurred = {**BLANK, "eqr_user_id": uuid.uuid4(), "eqr_status": "concurred"}
    done = _providers(monkeypatch, "in_app", concurred, eqr_on_team=True)
    assert (await done["G6"](TENANT, ENGAGEMENT)).met


# --- SQMS 2: the EQR's rules ---------------------------------------------------------------------

LEVELS_1_TO_4 = ("sign_off.prepare", "sign_off.review", "sign_off.manager", "sign_off.partner")


@pytest.mark.parametrize("action", LEVELS_1_TO_4)
def test_the_eqr_can_never_sign_l1_to_l4(action: str) -> None:
    assert matrix.ACTIONS.get(action, {}).get("eqr_reviewer", "deny") == "deny", action


def test_the_eqr_signs_l5_only() -> None:
    assert matrix.ACTIONS["sign_off.eqr"]["eqr_reviewer"] == "allow"


WORKPAPER = ("workpaper.", "test.", "sample", "adjustment.", "field.", "ledger", "evidence.")


def test_the_eqr_is_denied_every_mutating_workpaper_act() -> None:
    allowed = sorted(
        action
        for action, entries in matrix.ACTIONS.items()
        if action.startswith(WORKPAPER)
        and not matrix.RULES[action].reads
        and entries.get("eqr_reviewer", "deny") != "deny"
    )
    assert allowed == ["workpaper.export"]  # a copy out, never a change to the work


def _ctx(user: uuid.UUID, *, kind: str = "human") -> AuthContext:
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


def _review(monkeypatch: pytest.MonkeyPatch, eqr: uuid.UUID) -> None:
    row = eqr_service.ReviewRow(uuid.uuid4(), ENGAGEMENT, uuid.uuid4(), eqr, "open", 1)

    async def review(_t: TenantContext, _w: uuid.UUID) -> eqr_service.ReviewRow:
        return row

    class Ref:
        def resource(self) -> object:
            return object()

    async def ref(_ctx: AuthContext, _e: uuid.UUID) -> Ref:
        return Ref()

    async def allowed(*_: object) -> None:
        return None

    monkeypatch.setattr(eqr_service, "_review", review)
    monkeypatch.setattr(eqr_service, "get_ref", ref)
    monkeypatch.setattr(eqr_service, "authorise", allowed)


async def test_a_non_eqr_concur_is_403(monkeypatch: pytest.MonkeyPatch) -> None:
    eqr = uuid.uuid4()
    _review(monkeypatch, eqr)
    with pytest.raises(eqr_service.EqrOnly):
        await eqr_service.concur(
            _ctx(uuid.uuid4()), uuid.uuid4(), not_involved=True, concurrence_date=date(2026, 10, 5)
        )


async def test_an_agent_never_concurs_even_as_the_eqr_s_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eqr = uuid.uuid4()
    _review(monkeypatch, eqr)
    assert matrix.ACTIONS["eqr.concur"]["agent"] == "deny"
    with pytest.raises(eqr_service.EqrOnly):
        await eqr_service.concur(
            _ctx(eqr, kind="agent"),
            uuid.uuid4(),
            not_involved=True,
            concurrence_date=date(2026, 10, 5),
        )


async def test_the_engagement_partner_never_opens_as_the_eqr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def checks(_t: TenantContext, _e: uuid.UUID, _u: uuid.UUID) -> dict[str, str]:
        return {"not_on_team": "fail", "cooling_off": "pass"}  # the EP is on the team

    monkeypatch.setattr(eqr_service, "eqr_eligibility", checks)
    with pytest.raises(eqr_service.EqrNotEligible):
        await eqr_service.open_reviews(TENANT, ENGAGEMENT, uuid.uuid4())


# --- the digest ----------------------------------------------------------------------------------


def test_the_digest_is_built_from_decided_cards_only() -> None:
    import inspect

    source = inspect.getsource(eqr_service.build_digest)
    assert "decided_cards(" in source
    for other in ("open_cards", "pending", "proposals", "suggestions"):
        assert other not in source
    assert "'decision'" in eqr_service._CARD.text  # pyright: ignore[reportPrivateUsage]


# --- T19 inert, T23 guarded ----------------------------------------------------------------------


def test_every_a07_flag_is_off() -> None:
    assert set(a07_registrations.LIVE.values()) == {False}


@pytest.mark.parametrize("key", [key for key, *_ in a07_registrations.SECTIONS])
async def test_no_a07_rail_row_shows_with_its_flag_off(key: str) -> None:
    provider = a07_registrations._section_provider(key)  # pyright: ignore[reportPrivateUsage]
    assert await provider(TENANT, uuid.uuid4()) is None


async def test_no_a07_index_tag_with_the_flags_off() -> None:
    assert await a07_registrations.report_released_tags(TENANT, [uuid.uuid4()]) == {}
    assert await a07_registrations.archived_tags(TENANT, [uuid.uuid4()]) == {}


@pytest.mark.parametrize(
    ("live", "mode"), [(False, "in_app"), (True, "external"), (False, "external")]
)
async def test_the_bring_down_never_starts_dark_or_external(
    monkeypatch: pytest.MonkeyPatch, live: bool, mode: str
) -> None:
    started: list[object] = []

    async def release_mode(_t: TenantContext) -> str:
        return mode

    async def start(*args: object, **kwargs: object) -> None:
        started.append((args, kwargs))

    monkeypatch.setattr(completion_dark, "COMPLETION_LIVE", live)
    monkeypatch.setattr(completion_projector, "release_mode", release_mode)
    monkeypatch.setattr("abacus.kernel.dispatch.signal_with_start", start)
    scheduled = await bring_down.schedule_bring_down(
        TENANT,
        work_item_id=uuid.uuid4(),
        engagement_id=ENGAGEMENT,
        report_date=date(2026, 10, 9),
        time_zone="America/Chicago",
    )
    assert scheduled is False and started == []


async def test_the_bring_down_starts_live_and_in_app(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[object] = []

    async def release_mode(_t: TenantContext) -> str:
        return "in_app"

    async def start(*args: object, **kwargs: object) -> None:
        started.append(kwargs.get("id"))

    monkeypatch.setattr(completion_dark, "COMPLETION_LIVE", True)
    monkeypatch.setattr(completion_projector, "release_mode", release_mode)
    monkeypatch.setattr("abacus.kernel.dispatch.signal_with_start", start)
    item = uuid.uuid4()
    assert await bring_down.schedule_bring_down(
        TENANT, work_item_id=item, engagement_id=ENGAGEMENT, report_date=date(2026, 10, 9),
        time_zone="America/Chicago",
    )  # fmt: skip
    assert started == [f"{bring_down.BRING_DOWN_ID_PREFIX}{item}"]
