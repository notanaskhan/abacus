"""I-01-T23 (TASK-6017; DEC-2613): C13's firm scope, without a database.

The rules the projection's firm scope stands on: a firm source must say who it waits on, an
engagement source may not borrow `decides`, an event naming no engagement still reconciles a firm
source (and only a firm source), and the firm-role check admits the firm role alone: never an
engagement role, an agent, or the system.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.identity.api import AuthContext, firm_role_allows
from abacus.modules.identity.staff import FirmRole
from abacus.modules.review import (
    api as _review,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers
)
from abacus.modules.review import gates
from abacus.modules.review.firm_gates import METHODOLOGY, WALL
from abacus.modules.review.gates import GateSource, OpenGate, register_gate_source


async def _none(_t: TenantContext, _e: uuid.UUID | None) -> list[OpenGate]:
    return []


def _person(firm_role: str | None) -> AuthContext:
    user = uuid.uuid4()
    role = cast(FirmRole | None, firm_role)
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), role, None
    )


def test_a_firm_source_must_name_who_it_waits_on() -> None:
    with pytest.raises(ValueError, match="needs `decides` or `assigned_only`"):
        register_gate_source(
            GateSource(
                "t_firm_nobody",
                "decision",
                "methodology.read",
                frozenset({"wall.created"}),
                _none,
                scope="firm",
            )
        )


def test_an_engagement_source_cannot_borrow_decides() -> None:
    with pytest.raises(ValueError, match="`decides` is for firm gates"):
        register_gate_source(
            GateSource(
                "t_eng_decides",
                "decision",
                "letter.read",
                frozenset({"letter.approved"}),
                _none,
                decides="methodology.approve",
            )
        )


def test_the_two_firm_gates_are_registered_as_firm_scope() -> None:
    sources = {s.subject_type: s for s in gates.gate_sources()}
    methodology, wall = sources[METHODOLOGY], sources[WALL]
    assert (methodology.scope, methodology.decides, methodology.assigned_only) == (
        "firm",
        "methodology.approve",
        False,
    )
    assert (wall.scope, wall.decides, wall.assigned_only) == ("firm", None, True)
    assert methodology.events == {
        "methodology.review_requested",
        "methodology_version.approved",
        "methodology_version.discarded",
    }
    assert wall.events == {"wall.created", "wall.approved", "wall.removed"}


async def test_an_event_naming_no_engagement_reconciles_firm_sources_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, uuid.UUID | None]] = []

    async def reconcile(
        _t: uuid.UUID, source: GateSource, eng: uuid.UUID | None, _e: uuid.UUID
    ) -> int:
        calls.append((source.subject_type, eng))
        return 0

    monkeypatch.setattr(gates, "_reconcile", reconcile)
    firm = uuid.uuid4()
    await gates.apply_event(OutboxEvent(uuid.uuid4(), firm, "wall.created", {"wall_id": "x"}))
    assert calls == [(WALL, None)]

    calls.clear()
    engagement = uuid.uuid4()
    await gates.apply_event(
        OutboxEvent(uuid.uuid4(), firm, "letter.approved", {"engagement_id": str(engagement)})
    )
    assert calls == [("letter_partner_approval", engagement)]

    calls.clear()
    await gates.apply_event(OutboxEvent(uuid.uuid4(), firm, "letter.approved", {}))
    assert calls == []  # an engagement source with no engagement named: nothing to reconcile


def test_only_the_firm_role_decides_a_firm_gate() -> None:
    assert firm_role_allows(_person("quality_partner"), "methodology.approve")
    assert firm_role_allows(_person("practice_leader"), "methodology.approve")
    assert not firm_role_allows(_person("firm_admin"), "methodology.approve")
    assert not firm_role_allows(_person(None), "methodology.approve")  # a partner by title only
