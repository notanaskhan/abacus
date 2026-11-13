"""W-02-T09 (TASK-7711; W-02 §3.1, §3.2; SPEC-653 AC-L1 to L6, AC-V1 to V3; DEC-4714): WB-01's list.

Row acceptance: "Exactly 8 rows and Running 3; walled rows leak nowhere." Filters and counts,
title-only search, walled rows omitted with no count, locked rows metadata only; rename and
delete are the owner's.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from abacus.modules.workbench import session_list as sl
from abacus.modules.workbench.session_list import NotSessionOwner, Row, matches, version_of

ME = uuid.uuid4()
OTHER = uuid.uuid4()
NOW = datetime(2026, 9, 14, 9, 24, tzinfo=UTC)


def _row(title: str, state: str = "live", origin: str = "manual", owner: uuid.UUID = ME) -> Row:
    return Row(
        uuid.uuid4(), title, owner, "Hannah Leclerc", origin, state, NOW, "auto", False, "v"
    )


def test_filters_and_title_only_search() -> None:
    running = _row("Copperleaf close run", "running", "engagement_run", OTHER)
    asked = _row("Season progress", "awaiting_answer", "schedule")
    mine = _row("Contributions receivable")
    assert matches(running, "running", None, ME) and not matches(mine, "running", None, ME)
    assert matches(asked, "needs_answer", None, ME)
    assert matches(running, "via_agent", None, ME) and not matches(mine, "via_agent", None, ME)
    assert matches(mine, "mine", None, ME) and not matches(running, "mine", None, ME)
    assert matches(mine, "all", "receivable", ME)
    assert not matches(mine, "all", "K-3", ME)  # "No sessions match 'K-3'."


def test_the_version_follows_title_and_rename_time() -> None:
    first = version_of("New session", None)
    assert first == version_of("New session", None)
    assert first != version_of("Renamed", None)
    assert version_of("Renamed", NOW) != version_of("Renamed", NOW + timedelta(seconds=1))


@pytest.fixture
def candidates(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:  # Any: SQL rows
    rows: list[dict[str, Any]] = []

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def execute(self, *a: object) -> _Session:
            return self

        def mappings(self) -> _Session:
            return self

        def all(self) -> list[dict[str, Any]]:
            return rows

    async def roles(tenant: object, user: object) -> dict[uuid.UUID, str]:
        return {}

    async def names(ids: object) -> dict[uuid.UUID, str]:
        return {}

    async def access(ctx: object, clients: list[uuid.UUID], opened: object = None) -> str:
        if "walled" in [str(c) for c in clients]:
            return "omitted"
        return "locked" if clients else "open"

    monkeypatch.setattr(sl, "tenant_session", lambda tenant: _Session())
    monkeypatch.setattr(sl, "my_engagement_roles", roles)
    monkeypatch.setattr(sl, "display_names", names)
    monkeypatch.setattr(sl, "viewer_access", access)
    return rows


def _raw(title: str, state: str, scope: list[Any] | None = None) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(), "title": title, "owner_user_id": ME, "origin": "manual",
        "state": state, "last_item_at": NOW, "client_scope": scope or [], "context_refs": [],
        "title_source": "auto", "renamed_at": None, "created_at": NOW,
    }  # fmt: skip


def test_eight_rows_running_three_and_walled_rows_leak_nowhere(
    candidates: list[dict[str, Any]],
) -> None:
    states = ["awaiting_answer", "ready_for_review", "running", "running", "running", "live",
              "complete", "complete"]  # fmt: skip
    candidates.extend(_raw(f"Session {n}", s) for n, s in enumerate(states))
    candidates.append(_raw("Walled Northwind", "running", ["walled"]))
    ctx: Any = type("C", (), {"tenant": object(), "user_id": ME})()
    listed = asyncio.run(sl.list_sessions(ctx))
    assert len(listed.rows) == 8 and listed.total == 8
    assert (listed.running, listed.needs_answer) == (3, 1)
    assert all("Walled" not in r.title for r in listed.rows)
    running = asyncio.run(sl.list_sessions(ctx, "running"))
    assert len(running.rows) == 3


def test_a_locked_row_is_metadata_only(candidates: list[dict[str, Any]]) -> None:
    from abacus.modules.workbench.sessions_contract import summary_of

    candidates.append(_raw("Explain Copperleaf July→August payroll change", "ready_for_review",
                           [uuid.uuid4()]))  # fmt: skip
    ctx: Any = type("C", (), {"tenant": object(), "user_id": ME})()
    (row,) = asyncio.run(sl.list_sessions(ctx)).rows
    out = summary_of(row)
    assert out.locked and not out.ready_for_review and not out.needs_answer


def test_rename_by_someone_else_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Tx:
        session: Any = None

    class _Result:
        def first(self) -> Any:  # noqa: ANN401 -- Any: a stand-in SQL row
            return type("R", (), {"owner_user_id": OTHER, "deleted_at": None, "title": "t",
                                  "renamed_at": None})()  # fmt: skip

    class _Session:
        async def execute(self, *a: object) -> _Result:
            return _Result()

    tx = _Tx()
    tx.session = _Session()
    ctx: Any = type("C", (), {"tenant": object(), "user_id": ME})()
    with pytest.raises(NotSessionOwner):
        asyncio.run(sl._owned(tx, ctx, uuid.uuid4()))  # type: ignore[arg-type]
