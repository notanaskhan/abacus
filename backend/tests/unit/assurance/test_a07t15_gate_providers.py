"""A-07-T15 (TASK-5119; A-07 F9; DEC-2415): G6 to G9 from `assurance/gates.py`.

Row acceptance: "For a firm on external mode ENG-02 and AUD-02 render exactly as before, and for an
in_app work item the G6-G9 rows read their live blockers from the providers." Facts are faked at
the read; `tests/integration` covers the SQL.
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import gates
from abacus.modules.engagements.api import GateFact

TENANT = cast(TenantContext, object())


def _facts(**over: object) -> dict[str, object]:
    return {
        "engagement_type": "ebp_audit",
        "eqr_user_id": None,
        "eqr_status": None,
        "letter_status": None,
        "released": False,
        "archive_status": None,
    } | over


def _with(monkeypatch: pytest.MonkeyPatch, facts: dict[str, object] | None) -> None:
    async def read(_tenant: object, _engagement: object) -> dict[str, object] | None:
        return facts

    monkeypatch.setattr(gates, "_in_app_facts", read)


async def test_g6_not_required_without_an_assignment(monkeypatch: pytest.MonkeyPatch) -> None:
    _with(monkeypatch, _facts())
    assert (await gates.in_app_g6(TENANT, uuid4())).met


async def test_g6_blocks_until_the_eqr_concurs(monkeypatch: pytest.MonkeyPatch) -> None:
    _with(monkeypatch, _facts(eqr_user_id=uuid4(), eqr_status="in_progress"))
    fact = await gates.in_app_g6(TENANT, uuid4())
    assert (fact.met, fact.blockers) == (False, ("eqr_not_concurred",))


@pytest.mark.parametrize(
    ("status", "blocker"),
    [
        (None, "no_rep_letter"),
        ("approved", "rep_letter_not_signed"),
        ("date_mismatch", "rep_letter_date_mismatch"),
    ],
)
async def test_g7_names_what_blocks(
    monkeypatch: pytest.MonkeyPatch, status: str | None, blocker: str
) -> None:
    _with(monkeypatch, _facts(letter_status=status))
    assert (await gates.in_app_g7(TENANT, uuid4())).blockers == (blocker,)


async def test_g7_met_by_a_signed_letter(monkeypatch: pytest.MonkeyPatch) -> None:
    _with(monkeypatch, _facts(letter_status="signed"))
    assert (await gates.in_app_g7(TENANT, uuid4())).met


@pytest.mark.parametrize("engagement_type", ["compilation", "preparation"])
async def test_compilation_and_preparation_skip_g6_and_g7(
    monkeypatch: pytest.MonkeyPatch, engagement_type: str
) -> None:
    _with(monkeypatch, _facts(engagement_type=engagement_type, eqr_user_id=uuid4()))
    assert (await gates.in_app_g6(TENANT, uuid4())).met
    assert (await gates.in_app_g7(TENANT, uuid4())).met


async def test_g8_and_g9(monkeypatch: pytest.MonkeyPatch) -> None:
    _with(monkeypatch, _facts())
    assert (await gates.in_app_g8(TENANT, uuid4())).blockers == ("not_released",)
    assert (await gates.in_app_g9(TENANT, uuid4())).blockers == ("not_locked",)
    _with(monkeypatch, _facts(released=True, archive_status="locked"))
    assert (await gates.in_app_g8(TENANT, uuid4())).met
    assert (await gates.in_app_g9(TENANT, uuid4())).met


async def test_external_mode_keeps_what_it_had(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mode(_tenant: object) -> str:
        return "external"

    async def in_app(_t: object, _e: object) -> GateFact:
        raise AssertionError("in_app read on an external firm")

    async def external(_t: object, _e: object) -> GateFact:
        return GateFact(met=True)

    monkeypatch.setattr(gates, "release_mode", mode)
    assert (await gates._by_mode(in_app, external)(TENANT, uuid4())).met  # pyright: ignore[reportPrivateUsage]  # the rule itself


async def test_a_failing_provider_is_unmet(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mode(_tenant: object) -> str:
        return "in_app"

    async def broken(_t: object, _e: object) -> GateFact:
        raise RuntimeError("down")

    monkeypatch.setattr(gates, "release_mode", mode)
    fact = await gates._by_mode(broken, broken)(TENANT, uuid4())  # pyright: ignore[reportPrivateUsage]  # the rule itself
    assert (fact.met, fact.blockers) == (False, ("gate_unavailable",))


async def test_c13_rows_wait_only_on_in_app_firms(monkeypatch: pytest.MonkeyPatch) -> None:
    async def mode(_tenant: object) -> str:
        return "external"

    monkeypatch.setattr(gates, "release_mode", mode)
    open_for = gates._open_for("report_release_due")  # pyright: ignore[reportPrivateUsage]  # the rule itself
    assert await open_for(TENANT, None) == []
