"""Shared fakes for the identity unit tests (no database).

`authorise` reads a person's membership facts only when a rule has a member condition
(`not_offshore`, `level_in`, a service-line scope). These suites test roles and layers, so by
default the person is an onshore staff member with no level. A test of the conditions themselves
patches `authz.member_facts` again, and its patch wins (test_matrix_conditions.py).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace

import pytest

from abacus.modules.identity import authz
from abacus.modules.identity.authz import Resource, TargetFacts
from abacus.modules.identity.authz.matrix import FUNCTIONS
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import MemberFacts

MeetConditions = Callable[[Resource, AuthContext, str], Resource]


@pytest.fixture(autouse=True)
def onshore_member(monkeypatch: pytest.MonkeyPatch) -> None:
    async def facts(*_: object) -> MemberFacts:
        return MemberFacts(level=None, offshore=False, service_lines=frozenset(), client=False)

    monkeypatch.setattr(authz, "member_facts", facts)


@pytest.fixture
def conditions_met(monkeypatch: pytest.MonkeyPatch) -> MeetConditions:
    """For suites testing other layers (walls, independence) on every allowed (action, role):
    the resource's work-item and target facts meet the matrix conditions (P-04-T15: the person
    holds every function, prepared nothing, and the card is reserved to their role and to them).
    The conditions' own allow and deny cases live in test_matrix_conditions.py and the generated
    security suite."""

    async def every_function(*_: object) -> frozenset[str]:
        return frozenset(FUNCTIONS)

    monkeypatch.setattr(authz.LOOKUPS, "functions", every_function)

    def meet(resource: Resource, ctx: AuthContext, role: str) -> Resource:
        return replace(
            resource,
            work_item_id=uuid.uuid4(),
            target=TargetFacts(
                preparer_user_ids=frozenset(), reserved_role=role, reserved_user_id=ctx.user_id
            ),
        )

    return meet
