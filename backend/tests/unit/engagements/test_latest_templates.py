"""SPEC-025 AC-3 (TASK-047 D3): a new engagement is offered each template's latest version only."""

from __future__ import annotations

from typing import cast

from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.engagements.repository import list_templates


class _Rows:
    def all(self) -> list[object]:
        return []


class _Session:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _Rows:
        self.statements.append(statement)
        return _Rows()


def _sql(statement: object) -> str:
    compiled = statement.compile(dialect=postgresql.dialect())  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType] -- a captured Select
    return " ".join(str(compiled).split())  # pyright: ignore[reportUnknownArgumentType] -- as above


async def _listed(*, latest: bool) -> str:
    session = _Session()
    await list_templates(cast(AsyncSession, session), latest=latest)
    [statement] = session.statements
    return _sql(statement)


async def test_ac3_latest_keeps_only_versions_with_no_newer_one() -> None:
    sql = await _listed(latest=True)
    assert "NOT (EXISTS (SELECT methodology_versions_1.id" in sql
    assert "methodology_versions_1.template_id = methodology_versions.template_id" in sql
    assert "methodology_versions_1.version > methodology_versions.version" in sql


async def test_ac3_without_latest_every_version_is_listed() -> None:
    assert "EXISTS" not in await _listed(latest=False)
