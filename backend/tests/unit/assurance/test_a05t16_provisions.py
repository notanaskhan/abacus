"""A-05-T16 (TASK-3022; A-05 §3 F2; DEC-2069): the EBP-02 provisions service's rules.

Row acceptance: "Sign off answers 409 provisions_unverified until all 20 ticks exist, and EBP-03
reads the entry rule from the verified provision, never from the draft." Here: the count the
sign-off guard reports, that only a current tick on an existing value verifies, that downstream
readers get verified values only, that the guard is registered on EBP-02's kind, that review turns
an owner's block into 409 `sign_off_blocked`, and that a guard that fails blocks.
"""

from __future__ import annotations

import uuid

import pytest

import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers
from abacus.kernel.db import TenantContext
from abacus.modules.assurance import ebp_provisions
from abacus.modules.assurance.compute.ebp.provisions import provisions_for
from abacus.modules.review.api import FieldState
from abacus.modules.review.sign_offs import SignOffBlocked
from abacus.modules.workpapers import guards

ROWS = provisions_for(amendment_in_force=True)
ENTRY = next(p for p in ROWS if p.key == "entry_dates")


def _state(value: str | None, levels: frozenset[int] = frozenset()) -> FieldState:
    return FieldState(None if value is None else {"t": "text", "v": value}, (), levels, ())


def _all(levels: frozenset[int]) -> dict[str, FieldState]:
    states: dict[str, FieldState] = {}
    for p in ROWS:
        states[p.value_cell] = _state(f"value {p.key}", levels)
        states[p.reference_cell] = _state("AA §2.02")
    return states


def test_ac_twenty_rows_with_the_amendment_eighteen_without() -> None:
    assert len(ROWS) == 20
    assert len(provisions_for(amendment_in_force=False)) == 18


def test_ac_nothing_ticked_leaves_all_twenty_unverified() -> None:
    assert ebp_provisions.unverified_of(ROWS, _all(frozenset())) == 20


def test_ac_nineteen_ticks_leave_one() -> None:
    states = _all(frozenset({1}))
    states[ENTRY.value_cell] = _state("First of month following")
    assert ebp_provisions.unverified_of(ROWS, states) == 1


def test_ac_twenty_ticks_unblock() -> None:
    assert ebp_provisions.unverified_of(ROWS, _all(frozenset({1}))) == 0


def test_a_tick_without_a_value_never_verifies() -> None:
    states = _all(frozenset({1}))
    states[ENTRY.value_cell] = _state(None, frozenset({1}))
    assert ebp_provisions.unverified_of(ROWS, states) == 1


def test_ac_downstream_reads_the_verified_value_never_the_draft() -> None:
    states = _all(frozenset())
    states[ENTRY.value_cell] = _state("First of month following", frozenset({1}))
    assert ebp_provisions.verified_of(ROWS, states) == {"entry_dates": "First of month following"}


async def test_ac_the_guard_is_registered_on_ebp_02s_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    async def left(*_: object) -> int:
        return 3

    monkeypatch.setattr(ebp_provisions, "unverified_count", left)
    tenant = TenantContext(uuid.uuid4(), "human", "x")
    found = await guards.sign_off_block(tenant, "ebp_provisions", uuid.uuid4(), uuid.uuid4())
    assert found == ("provisions_unverified", 3)
    assert await guards.sign_off_block(tenant, "risk_assessment", uuid.uuid4(), None) is None


async def test_a_guard_that_fails_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(*_: object) -> int:
        raise RuntimeError

    monkeypatch.setattr(ebp_provisions, "unverified_count", broken)
    tenant = TenantContext(uuid.uuid4(), "human", "x")
    assert await guards.sign_off_block(tenant, "ebp_provisions", uuid.uuid4(), uuid.uuid4()) == (
        "owner_unavailable",
        1,
    )


def test_ac_review_answers_409_sign_off_blocked_with_the_reason() -> None:
    blocked = SignOffBlocked(facts={"reason": "provisions_unverified", "count": 2})
    assert (blocked.code, blocked.facts) == (
        "sign_off_blocked",
        {"reason": "provisions_unverified", "count": 2},
    )
