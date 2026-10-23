"""Shared fakes for the identity unit tests (no database).

`authorise` reads a person's membership facts only when a rule has a member condition
(`not_offshore`, `level_in`, a service-line scope). These suites test roles and layers, so by
default the person is an onshore staff member with no level. A test of the conditions themselves
patches `authz.member_facts` again, and its patch wins (test_matrix_conditions.py).
"""

from __future__ import annotations

import pytest

from abacus.modules.identity import authz
from abacus.modules.identity.repository import MemberFacts


@pytest.fixture(autouse=True)
def onshore_member(monkeypatch: pytest.MonkeyPatch) -> None:
    async def facts(*_: object) -> MemberFacts:
        return MemberFacts(level=None, offshore=False, service_lines=frozenset(), client=False)

    monkeypatch.setattr(authz, "member_facts", facts)
