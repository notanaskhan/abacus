"""F-03-T13 acceptance: "Every illegal transition answers 409, accept/decline/hold refuse agent
and system principals, and a non-attest close engagement opens client data on G1+G3 without G2."
(chapter 03 §3.1.3; DEC-39; INV-1)"""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Literal, cast, get_args

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements import transitions as t
from abacus.modules.engagements.acceptance_tables import G1Decision
from abacus.modules.engagements.gate_policy import required_gates
from abacus.modules.engagements.models import EngagementLetter
from abacus.modules.engagements.setup import (
    _blocked,  # pyright: ignore[reportPrivateUsage] -- the gate's pure rule, tested directly
)
from abacus.modules.identity.api import AuthContext, Forbidden

STATES = get_args(t.Status)


def test_the_lifecycle_has_the_eight_states_and_the_chapter_03_moves() -> None:
    assert set(STATES) == {
        "prospect",
        "accepted",
        "declined",
        "contracted",
        "active",
        "on_hold",
        "delivered",
        "archived",
    }
    assert set(t.LIFECYCLE) == {
        ("prospect", "accepted"),
        ("prospect", "declined"),
        ("accepted", "contracted"),
        ("contracted", "active"),
        ("active", "on_hold"),
        ("on_hold", "active"),
        ("active", "delivered"),
        ("delivered", "archived"),
    }
    human = {pair for pair, move in t.LIFECYCLE.items() if move.by == "human"}
    assert human == {
        ("prospect", "accepted"),
        ("prospect", "declined"),
        ("active", "on_hold"),
        ("on_hold", "active"),
    }
    for move in t.LIFECYCLE.values():
        assert (move.action is not None) == (move.by == "human")


@pytest.mark.parametrize(
    ("current", "to"),
    [pair for pair in itertools.product(STATES, STATES) if pair not in t.LIFECYCLE],
)
def test_every_illegal_transition_is_a_409_with_its_states_as_facts(current: str, to: str) -> None:
    with pytest.raises(t.IllegalTransition) as raised:
        t.move_for(current, to)
    assert issubclass(t.IllegalTransition, DomainConflict)  # the API answers 409
    assert raised.value.code == "illegal_transition"
    assert raised.value.facts == {"from_status": current, "to_status": to}


def test_prospect_to_active_is_illegal() -> None:
    with pytest.raises(t.IllegalTransition):
        t.move_for("prospect", "active")


class _Session:
    def __init__(self, status: str) -> None:
        self.status = status
        self.writes = 0

    async def execute(self, stmt: object) -> SimpleNamespace:
        if str(stmt).lstrip().upper().startswith("UPDATE"):  # not SELECT … FOR UPDATE
            self.writes += 1
        return SimpleNamespace(
            one_or_none=lambda: SimpleNamespace(status=self.status, client_id=uuid.uuid4())
        )


class _Tx:
    def __init__(self, status: str) -> None:
        self.session = _Session(status)
        self.recorded: list[str] = []
        self.emitted: list[object] = []

    def record(self, action: str, **_: object) -> None:
        self.recorded.append(action)

    def emit(self, event: object) -> None:
        self.emitted.append(event)


def _principal(kind: str) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # each actor kind
        user,
        uuid.uuid4(),
        "practice_leader",
        datetime.now(UTC),
    )


@pytest.mark.parametrize(
    ("current", "to"),
    [
        ("prospect", "accepted"),
        ("prospect", "declined"),
        ("active", "on_hold"),
        ("on_hold", "active"),
    ],
)
@pytest.mark.parametrize("who", ["system", "agent-principal", "system-principal"])
async def test_accept_decline_and_hold_refuse_agents_and_the_system(
    current: str, to: t.Status, who: str
) -> None:
    tx = _Tx(current)
    by: AuthContext | Literal["system"] = (
        "system" if who == "system" else _principal(who.split("-")[0])
    )
    with pytest.raises(Forbidden):
        await t.transition(
            cast(UnitOfWork, tx),
            uuid.uuid4(),
            to,
            by=by,
            reason="scope_change",
        )
    assert tx.session.writes == 0
    assert tx.recorded == []
    assert tx.emitted == []


async def test_a_system_move_writes_one_audit_event_and_one_outbox_event() -> None:
    tx = _Tx("accepted")
    engagement = uuid.uuid4()
    await t.transition(cast(UnitOfWork, tx), engagement, "contracted", by="system")
    assert tx.session.writes == 1
    assert tx.recorded == ["engagement.contracted"]
    assert len(tx.emitted) == 1
    event = tx.emitted[0]
    assert isinstance(event, t.EngagementStatusChanged)
    assert (event.engagement_id, event.from_status, event.to_status) == (
        engagement,
        "accepted",
        "contracted",
    )


async def test_a_person_cannot_make_a_system_move() -> None:
    tx = _Tx("accepted")
    with pytest.raises(t.IllegalTransition):
        await t.transition(
            cast(UnitOfWork, tx), uuid.uuid4(), "contracted", by=_principal("human")
        )
    assert tx.session.writes == 0


def test_hold_reasons_are_codes() -> None:
    assert all(r.replace("_", "").isalpha() and r.islower() for r in t.HOLD_REASONS)


# --- the per-type gate policy opens client data (§3.1.3) ----------------------------------------


def _accepted() -> G1Decision:
    """CLI-07's accept decision (G1's one source since P-07-T59, DEC-906)."""
    return G1Decision(True, datetime.now(UTC), None)


def _signed() -> EngagementLetter:
    return cast(EngagementLetter, SimpleNamespace(status="signed"))


def _opens(engagement_type: str, *, concluded: bool, letter: bool) -> str | None:
    blocked = _blocked(
        _accepted(),
        _signed() if letter else None,
        gates=frozenset(required_gates(engagement_type)),
        needs_letter=True,
        g2=concluded,
    )
    return None if blocked is None else blocked.code


def test_a_non_attest_close_opens_on_g1_and_g3_without_g2() -> None:
    assert "G2" not in required_gates("cas_monthly_close")
    assert _opens("cas_monthly_close", concluded=False, letter=True) is None
    assert _opens("cas_monthly_close", concluded=False, letter=False) == "letter_missing"


def test_an_audit_still_needs_g2() -> None:
    assert _opens("ebp_audit", concluded=False, letter=True) == "independence_conclusion_missing"
    assert _opens("ebp_audit", concluded=True, letter=True) is None


def test_tax_opens_without_g2_too() -> None:
    assert _opens("tax_compliance", concluded=False, letter=True) is None


def test_each_blocker_names_its_gate() -> None:
    blocked = _blocked(
        None, None, gates=frozenset({"G1", "G2", "G3"}), needs_letter=True, g2=False
    )
    assert blocked is not None
    assert blocked.facts == {"gate": "G1"}
