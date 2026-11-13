"""A-05-T16 (TASK-3022; A-05 §3 F2; DEC-2069): the EBP-02 provisions service's rules.

Row acceptance: "Sign off answers 409 provisions_unverified until all 20 ticks exist, and EBP-03
reads the entry rule from the verified provision, never from the draft." Here: the count the
sign-off guard reports, that only a current tick on an existing value verifies, that downstream
readers get verified values only, that the guard is registered on EBP-02's kind, that review turns
an owner's block into 409 `sign_off_blocked`, and that a guard that fails blocks.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

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


@pytest.mark.parametrize(
    ("asked", "diff"),
    [
        (1, (2, ("Long-term part-time", "Catch-up"))),
        (2, None),
        (None, None),
    ],
)
async def test_a17_the_review_reads_its_paper_sign_offs_hashes_and_what_the_latest_adds(
    monkeypatch: pytest.MonkeyPatch, asked: int | None, diff: tuple[int, tuple[str, ...]] | None
) -> None:
    paper = uuid.uuid4()
    signer = uuid.uuid4()
    at = datetime(2026, 9, 17, 15, 10, tzinfo=UTC)

    async def item(*_a: object) -> object:
        return SimpleNamespace(engagement_id=uuid.uuid4())

    async def review_row(_t: object, _w: object, no: int | None) -> object:
        latest = no in (None, 2)
        return SimpleNamespace(review_no=2 if latest else 1, amendment_in_force=latest)

    async def paper_of(*_a: object) -> uuid.UUID:
        return paper

    async def states(*_a: object) -> dict[str, FieldState]:
        found = _all(frozenset())
        return {k: replace(v, content_hash=f"sha256:{k}") for k, v in found.items()}

    async def facts(*_a: object) -> object:
        return SimpleNamespace(content_hash="h")

    async def signed(*_a: object) -> dict[uuid.UUID, list[object]]:
        return {
            paper: [
                SimpleNamespace(level=1, signed_by=signer, signed_at=at, stale=False),
                SimpleNamespace(level=2, signed_by=None, signed_at=None, stale=False),
            ]
        }

    monkeypatch.setattr(ebp_provisions, "assurance_item", item)
    monkeypatch.setattr(ebp_provisions, "_review_row", review_row)
    monkeypatch.setattr(ebp_provisions, "paper_of_kind", paper_of)
    monkeypatch.setattr(ebp_provisions, "_states", states)
    monkeypatch.setattr(ebp_provisions, "reviewable_facts", facts)
    monkeypatch.setattr(ebp_provisions, "sign_off_states", signed)

    async def no_documents(*_a: object) -> tuple[dict[str, object], None]:
        return {}, None  # A-05-T16 (DEC-2489): no SPD or amendment value keyed

    monkeypatch.setattr(ebp_provisions, "_documents", no_documents)
    ctx = SimpleNamespace(tenant=None)
    found = await ebp_provisions.review_of(ctx, uuid.uuid4(), asked)  # pyright: ignore[reportArgumentType] -- the stubs read `tenant`
    assert found.workpaper_id == paper
    assert [(s.level, s.user_id) for s in found.sign_offs] == [(1, signer)]
    entry = next(p for p in found.provisions if p.provision.key == "entry_dates")
    assert entry.value_hash == f"sha256:{ENTRY.value_cell}"
    if diff is None:
        assert found.version_diff is None
    else:
        assert found.version_diff is not None
        assert found.version_diff.current_no == diff[0]
        assert set(found.version_diff.added_labels) == set(diff[1])
