"""SPEC-304 (TASK-305): the audit log explorer pages newest first, names people, and is for firm
admins, the practice leader and the quality partner only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import AuditFilter, AuditRow
from abacus.modules.audit_trail import service as subject
from abacus.modules.identity.authz.matrix import RULES

U = uuid.uuid4()


def _row(seq: int, kind: str = "human", actor: str = str(U)) -> AuditRow:
    return AuditRow(
        seq,
        datetime(2026, 10, 20, tzinfo=UTC),
        kind,
        actor,
        "finding.raised",
        "finding",
        str(uuid.uuid4()),
        None,
        {"count": 1},
        None,
    )


class _Session:
    async def __aenter__(self) -> object:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:  # fakes record the calls
    calls: dict[str, Any] = {}  # fakes record the calls

    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        calls["action"] = action

    async def audit_page(
        _s: object, where: AuditFilter, before: int | None, limit: int
    ) -> list[AuditRow]:
        calls["where"], calls["before"], calls["limit"] = where, before, limit
        return [_row(9), _row(8, "agent", "engagement.agent"), _row(7)][:limit]

    async def names_of(ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return {i: "Dana Leader" for i in ids}

    async def readable(_ctx: object, rows: list[AuditRow]) -> list[AuditRow]:
        return list(rows)  # walls and roles are `test_targets.py`'s; here the reader sees all

    monkeypatch.setattr(subject, "readable", readable)
    monkeypatch.setattr(subject, "authorise", authorise)
    monkeypatch.setattr(subject, "audit_page", audit_page)
    monkeypatch.setattr(subject, "names_of", names_of)

    def session(*_: object) -> _Session:
        return _Session()

    monkeypatch.setattr(subject, "tenant_session", session)
    return calls


async def test_ac1_ac2_pages_back_with_a_cursor_and_names_people(
    seen: dict[str, Any],  # fakes record the calls
) -> None:
    ctx: Any = SimpleNamespace(  # a fake stands in for the person's context
        tenant=TenantContext(uuid.uuid4(), "human", "u"), tenant_id=uuid.uuid4()
    )
    page = await subject.events(ctx, AuditFilter(action="finding.raised"), 100, limit=2)
    assert seen["action"] == "audit.read"
    assert seen["limit"] == 3 and seen["before"] == 100  # one extra row tells there's more
    assert [e.seq for e in page.events] == [9, 8]
    assert page.next_before == 8
    assert page.events[0].actor_name == "Dana Leader"
    assert page.events[1].actor_name is None  # the agent: no person
    last = await subject.events(ctx, AuditFilter(), None, limit=5)
    assert last.next_before is None


def test_ac4_only_firm_level_roles_read_the_trail() -> None:
    decisions = RULES["audit.read"].decisions
    assert set(decisions) == {"firm_admin", "practice_leader", "quality_partner"}
