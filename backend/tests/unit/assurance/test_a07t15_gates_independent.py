"""A-07-T15 (Q-03-T206, TASK-6129; ADR-078): an independent suite for gate providers G6-G9.

Written from the A-07-T15 row and A-07 F9, not from its tests. Row acceptance: "For a firm on
external mode ENG-02 and AUD-02 render exactly as before, and for an in_app work item the G6-G9
rows read their live blockers from the providers." Covered: the four gates are registered; an
external firm gets the external provider's answer unchanged; an in_app firm gets each gate's live
blockers; compilation and preparation skip G6 and G7 (and only those); a failing provider is
unmet, never met; no work item is unmet.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import gates
from abacus.modules.engagements.api import GateFact
from abacus.modules.engagements.gate_policy import required_gates

Provider = Callable[[TenantContext, uuid.UUID], Awaitable[GateFact]]
TENANT = TenantContext(uuid.uuid4(), "system", "test")
ENGAGEMENT = uuid.uuid4()
EXTERNAL = GateFact(met=False, blockers=("external_record",))


def _providers(monkeypatch: pytest.MonkeyPatch) -> dict[str, Provider]:
    registered: dict[str, Provider] = {}
    monkeypatch.setattr(gates, "register_gate_provider", registered.__setitem__)
    monkeypatch.setattr(gates, "replace_gate_provider", registered.__setitem__)
    monkeypatch.setattr(gates, "register_completion_gates", lambda: None)

    async def external(_t: TenantContext, _e: uuid.UUID) -> GateFact:
        return EXTERNAL

    for name in ("g6", "g7", "g8", "g9"):
        monkeypatch.setattr(gates, name, external)
    gates.register()
    return registered


def _mode(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    async def release_mode(_t: TenantContext) -> str:
        return mode

    monkeypatch.setattr(gates, "release_mode", release_mode)


def _facts(monkeypatch: pytest.MonkeyPatch, facts: dict[str, object] | None) -> None:
    async def read(_t: TenantContext, _e: uuid.UUID) -> dict[str, object] | None:
        return facts

    monkeypatch.setattr(gates, "_in_app_facts", read)

    async def no_eqr(_tenant: object, _engagement: object) -> bool:
        return False  # A-07-T21: no EQR on the ENG-05 team unless a case says so

    monkeypatch.setattr(gates, "_eqr_on_team", no_eqr)


BLANK: dict[str, object] = {
    "engagement_type": "fs_audit",
    "eqr_status": None,
    "eqr_user_id": None,
    "letter_status": None,
    "released": False,
    "archive_status": None,
}


async def test_g6_to_g9_are_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    assert {"G6", "G7", "G8", "G9"} <= set(_providers(monkeypatch))


@pytest.mark.parametrize("gate", ["G6", "G7", "G8", "G9"])
async def test_an_external_firm_gets_exactly_what_it_had(
    monkeypatch: pytest.MonkeyPatch, gate: str
) -> None:
    providers = _providers(monkeypatch)
    _mode(monkeypatch, "external")
    _facts(monkeypatch, {**BLANK, "released": True, "archive_status": "locked"})
    assert await providers[gate](TENANT, ENGAGEMENT) == EXTERNAL


@pytest.mark.parametrize(
    ("gate", "facts", "blockers"),
    [
        ("G6", {"eqr_user_id": uuid.uuid4(), "eqr_status": "in_review"}, ("eqr_not_concurred",)),
        ("G6", {"eqr_user_id": uuid.uuid4(), "eqr_status": "concurred"}, ()),
        ("G6", {}, ()),  # no EQR assigned on ENG-05: not required
        ("G7", {}, ("no_rep_letter",)),
        ("G7", {"letter_status": "date_mismatch"}, ("rep_letter_date_mismatch",)),
        ("G7", {"letter_status": "sent"}, ("rep_letter_not_signed",)),
        ("G7", {"letter_status": "signed"}, ()),
        ("G8", {}, ("not_released",)),
        ("G8", {"released": True}, ()),
        ("G9", {"archive_status": "assembling"}, ("not_locked",)),
        ("G9", {"archive_status": "locked"}, ()),
    ],
)
async def test_an_in_app_firm_reads_live_blockers(
    monkeypatch: pytest.MonkeyPatch, gate: str, facts: dict[str, object], blockers: tuple[str, ...]
) -> None:
    providers = _providers(monkeypatch)
    _mode(monkeypatch, "in_app")
    _facts(monkeypatch, {**BLANK, **facts})
    fact = await providers[gate](TENANT, ENGAGEMENT)
    assert (fact.met, tuple(fact.blockers)) == (not blockers, blockers)


@pytest.mark.parametrize("engagement_type", ["compilation", "preparation"])
@pytest.mark.parametrize(("gate", "skipped"), [("G6", True), ("G7", True), ("G8", False)])
async def test_compilation_and_preparation_skip_g6_and_g7_only(
    monkeypatch: pytest.MonkeyPatch, engagement_type: str, gate: str, skipped: bool
) -> None:
    assert (gate not in required_gates(engagement_type)) is skipped
    providers = _providers(monkeypatch)
    _mode(monkeypatch, "in_app")
    _facts(
        monkeypatch,
        {**BLANK, "engagement_type": engagement_type, "eqr_user_id": uuid.uuid4()},
    )
    fact = await providers[gate](TENANT, ENGAGEMENT)
    assert fact.met is skipped


@pytest.mark.parametrize("gate", ["G6", "G7", "G8", "G9"])
async def test_a_failing_provider_is_unmet(monkeypatch: pytest.MonkeyPatch, gate: str) -> None:
    providers = _providers(monkeypatch)
    _mode(monkeypatch, "in_app")

    async def boom(_t: TenantContext, _e: uuid.UUID) -> dict[str, object]:
        raise RuntimeError("database away")

    monkeypatch.setattr(gates, "_in_app_facts", boom)
    fact = await providers[gate](TENANT, ENGAGEMENT)
    assert fact.met is False and fact.blockers


@pytest.mark.parametrize("gate", ["G6", "G7", "G8", "G9"])
async def test_no_work_item_is_unmet(monkeypatch: pytest.MonkeyPatch, gate: str) -> None:
    providers = _providers(monkeypatch)
    _mode(monkeypatch, "in_app")
    _facts(monkeypatch, None)
    assert (await providers[gate](TENANT, ENGAGEMENT)).met is False
