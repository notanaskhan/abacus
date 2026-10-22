"""F-03-T20: independent acceptance tests (ADR-078) for the engagement lifecycle, the gate
policy and the registration slots, written from chapter 03 §3.1.3 and §2.4 and F-03 stories 1.2
and 1.3, not from the code: "Tests … cover every row of the chapter 03 3.1.3 lifecycle and
gate-policy tables and pass on main." The migration up/down/up and backfill checks are in
tests/integration/test_f03_lifecycle_migrations.py."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Literal, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements import slots
from abacus.modules.engagements.gate_policy import required_gates
from abacus.modules.engagements.transitions import (
    LIFECYCLE,
    EngagementStatusChanged,
    IllegalTransition,
    move_for,
    transition,
)
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz._matrix import ACTIONS

# --- §3.1.3 lifecycle: (into, from, who) as the chapter's table states it ---------------------

# "Who": H = a person (with the roles named), S = the system on a fact.
LIFECYCLE_TABLE: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("accepted", "prospect", "H", ("engagement_partner",)),
    ("declined", "prospect", "H", ("engagement_partner",)),
    ("contracted", "accepted", "S", ()),
    ("active", "contracted", "S", ()),
    ("on_hold", "active", "H", ("engagement_partner", "manager")),
    ("active", "on_hold", "H", ("engagement_partner", "manager")),
    ("delivered", "active", "S", ()),
    ("archived", "delivered", "S", ()),
]


@pytest.mark.parametrize(("into", "source", "who", "roles"), LIFECYCLE_TABLE)
def test_every_row_of_the_lifecycle_table_is_a_legal_move(
    into: str, source: str, who: str, roles: tuple[str, ...]
) -> None:
    move = move_for(source, into)
    assert move.by == ("human" if who == "H" else "system")
    if who == "H":
        assert move.action is not None
        rule = ACTIONS[move.action]
        for role in roles:
            assert rule.get(role) == "allow", (move.action, role)
        # INV-1: agents and the system hold no allow on a human decision.
        assert rule.get("agent", "deny") == "deny"
        assert rule.get("system", "deny") == "deny"
        assert rule.get("mfa_recent") == "required"


def test_the_table_is_all_there_is() -> None:
    assert {(src, into) for into, src, _, _ in LIFECYCLE_TABLE} == set(LIFECYCLE)


@pytest.mark.parametrize(
    ("source", "into"),
    [
        ("prospect", "active"),
        ("declined", "accepted"),
        ("archived", "active"),
        ("on_hold", "delivered"),
    ],
)
def test_story_1_2_an_illegal_move_is_409_illegal_transition(source: str, into: str) -> None:
    with pytest.raises(IllegalTransition) as raised:
        move_for(source, into)
    assert raised.value.code == "illegal_transition"


# --- INV-1 and INV-5 through the transition itself ---------------------------------------------


class _Tx:
    def __init__(self, status: str) -> None:
        self.status = status
        self.updates = 0
        self.audit: list[str] = []
        self.events: list[object] = []

        outer = self

        class _S:
            async def execute(self, stmt: object) -> SimpleNamespace:
                if str(stmt).lstrip().upper().startswith("UPDATE"):
                    outer.updates += 1
                return SimpleNamespace(
                    one_or_none=lambda: SimpleNamespace(
                        status=outer.status, client_id=uuid.uuid4()
                    )
                )

        self.session = _S()

    def record(self, action: str, **_: object) -> None:
        self.audit.append(action)

    def emit(self, event: object) -> None:
        self.events.append(event)


def _actor(kind: str) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), cast(Literal["human"], kind), str(user)),
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


@pytest.mark.parametrize("kind", ["agent", "system", "support"])
async def test_inv1_the_accept_path_refuses_an_agent_or_system_principal(kind: str) -> None:
    tx = _Tx("prospect")
    with pytest.raises(Forbidden):
        await transition(cast(UnitOfWork, tx), uuid.uuid4(), "accepted", by=_actor(kind))
    assert (tx.updates, tx.audit, tx.events) == (0, [], [])


async def test_inv1_the_system_cannot_accept_either() -> None:
    tx = _Tx("prospect")
    with pytest.raises(Forbidden):
        await transition(cast(UnitOfWork, tx), uuid.uuid4(), "accepted", by="system")
    assert tx.updates == 0


async def test_inv5_one_audit_event_and_one_status_changed_event_per_move() -> None:
    tx = _Tx("contracted")
    engagement = uuid.uuid4()
    await transition(cast(UnitOfWork, tx), engagement, "active", by="system")
    assert tx.updates == 1
    assert len(tx.audit) == 1
    assert tx.audit[0].startswith("engagement.")
    assert len(tx.events) == 1
    event = tx.events[0]
    assert isinstance(event, EngagementStatusChanged)
    assert event.event_type == "engagement.status_changed"
    assert (event.engagement_id, event.from_status, event.to_status) == (
        engagement,
        "contracted",
        "active",
    )


# --- §3.1.3 per-type gate policy ----------------------------------------------------------------

ATTEST = [
    "fs_audit",
    "ebp_audit",
    "review",
    "soc1",
    "soc2",
    "agreed_upon_procedures",
    "readiness",
    "internal_audit",
]


@pytest.mark.parametrize("engagement_type", ATTEST)
def test_attest_families_need_g1_to_g9(engagement_type: str) -> None:
    assert required_gates(engagement_type) == [f"G{n}" for n in range(1, 10)]


@pytest.mark.parametrize("engagement_type", ["compilation", "preparation"])
def test_compilation_and_preparation_need_g1_g3_g5_g8_g9(engagement_type: str) -> None:
    assert required_gates(engagement_type) == ["G1", "G3", "G5", "G8", "G9"]


def test_tax_needs_g1_and_g3() -> None:
    assert required_gates("tax_compliance") == ["G1", "G3"]


def test_cas_non_attest_needs_g1_and_g3_not_g2() -> None:
    assert required_gates("cas_monthly_close") == ["G1", "G3"]


def test_notice_needs_g3() -> None:
    assert required_gates("notice_response") == ["G3"]


def test_story_1_3_a_firm_override_tightens_and_never_loosens() -> None:
    stricter = required_gates("tax_compliance", [("G5", "required")])
    assert stricter == ["G1", "G3", "G5"]
    # An override that names no gate, or an unknown one, removes nothing.
    assert required_gates("tax_compliance", [("G1", "off"), ("G12", "required")]) == ["G1", "G3"]


# --- §2.4 fail-closed registration ---------------------------------------------------------------


async def test_an_unregistered_gate_is_unmet(monkeypatch: pytest.MonkeyPatch) -> None:
    # As if no owner had registered G7 (its owner may have, once the app is imported).
    monkeypatch.setattr(slots, "_GATES", {})
    fact = await slots.gate_fact(TenantContext(uuid.uuid4(), "human", "x"), uuid.uuid4(), "G7")
    assert fact.met is False
    assert fact.blockers == ("no_gate_provider",)


def test_an_unregistered_kind_is_refused_409() -> None:
    with pytest.raises(slots.UnknownWorkItemKind) as raised:
        slots.work_item_provider("not-a-kind")
    assert raised.value.code == "unknown_work_item_kind"


def test_only_g1_to_g9_can_be_registered() -> None:
    async def provider(_: TenantContext, __: uuid.UUID) -> slots.GateFact:
        return slots.GateFact(met=True)

    with pytest.raises(ValueError, match="unknown"):
        slots.register_gate_provider("G10", provider)
