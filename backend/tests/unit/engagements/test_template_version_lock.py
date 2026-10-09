"""SPEC-008 (fix): a template's next version is numbered under an advisory lock, never a row lock
on `methodology_templates`, which is insert-only for the app (`FOR UPDATE` needs UPDATE)."""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.engagements.repository import lock_or_insert_template


class _Result:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value

    def scalar_one(self) -> object:
        return self.value


class _Session:
    """The insert finds the name taken; the lookup returns the existing template."""

    def __init__(self, existing: uuid.UUID) -> None:
        self.existing = existing
        self.sql: list[str] = []

    async def execute(self, statement: object) -> _Result:
        compiled = statement.compile(dialect=postgresql.dialect())  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType] -- a captured statement
        self.sql.append(" ".join(str(compiled).split()))  # pyright: ignore[reportUnknownArgumentType] -- as above
        return _Result(None if len(self.sql) == 1 else self.existing)


async def test_an_existing_template_is_locked_with_an_advisory_lock_not_for_update() -> None:
    existing = uuid.uuid4()
    session = _Session(existing)
    found = await lock_or_insert_template(
        cast(AsyncSession, session),
        tenant_id=uuid.uuid4(),
        name="Audit",
        created_by=uuid.uuid4(),
    )
    assert found == (existing, False)
    assert not any("FOR UPDATE" in sql for sql in session.sql)
    assert "pg_advisory_xact_lock(hashtextextended(" in session.sql[-1]
