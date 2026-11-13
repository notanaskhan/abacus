"""W-02-T18 (ADR-078; TASK-7912): independent acceptance tests for W-02-T06 (sessions v2 data),
T09 (the session list), T10 (context options and summaries) and T11 (the amber tools), written
from SPEC-653 and the rows' acceptance, not from the implementation.

Row acceptance: "Tests pass and fail if a walled session leaks a row, count or search hit or the
picker lists an inaccessible client." Each test names its guard.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.workbench import registry, session_context, session_list, sessions

ME = uuid.uuid4()
OPEN, WALLED, LOCKED = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def _ctx() -> AuthContext:
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(ME)),
        ME,
        uuid.uuid4(),
        cast(Any, "staff"),  # Any: a firm role name stand-in
        None,
    )


# --- T09: membership verdicts (DEC-87, DEC-43) --------------------------------------------------


def _wire_access(monkeypatch: pytest.MonkeyPatch, *, firm_reads: bool = False) -> None:
    async def walls(*_a: object) -> set[uuid.UUID]:
        return {WALLED}

    async def team(*_a: object) -> frozenset[uuid.UUID]:
        return frozenset({OPEN})

    monkeypatch.setattr(sessions, "walled_from", walls)
    monkeypatch.setattr(sessions, "_clients_on_team", team)
    monkeypatch.setattr(sessions, "firm_role_allows", lambda *_a: firm_reads)  # pyright: ignore[reportUnknownLambdaType] -- a stand-in rule


@pytest.mark.parametrize(
    ("clients", "verdict"),
    [([], "open"), ([OPEN], "open"), ([LOCKED], "locked"), ([OPEN, WALLED], "omitted")],
)
def test_t09_verdict_by_client_scope(
    monkeypatch: pytest.MonkeyPatch, clients: list[uuid.UUID], verdict: str
) -> None:
    """Guard: a wall on any client omits; a client off the viewer's teams locks."""
    _wire_access(monkeypatch)
    assert asyncio.run(sessions.viewer_access(_ctx(), clients)) == verdict


def test_t09_a_firm_reader_still_never_sees_a_walled_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_access(monkeypatch, firm_reads=True)
    assert asyncio.run(sessions.viewer_access(_ctx(), [WALLED])) == "omitted"
    assert asyncio.run(sessions.viewer_access(_ctx(), [LOCKED])) == "open"


# --- T09: walled rows leak nothing: rows, counts, search ---------------------------------------


def _raw(title: str, clients: list[uuid.UUID], state: str) -> dict[str, object]:
    return {
        "id": uuid.uuid4(), "title": title, "owner_user_id": ME, "origin": "manual",
        "state": state, "last_item_at": datetime(2026, 9, 14, tzinfo=UTC), "client_scope": clients,
        "context_refs": [], "title_source": "auto", "renamed_at": None,
        "created_at": datetime(2026, 9, 14, tzinfo=UTC),
    }  # fmt: skip


def _wire_list(monkeypatch: pytest.MonkeyPatch, raw: list[dict[str, object]]) -> None:
    @asynccontextmanager
    async def session(_t: object):  # noqa: ANN202 -- a stand-in tenant_session
        result = SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: raw))

        async def execute(*_a: object) -> object:
            return result

        yield SimpleNamespace(execute=execute)

    async def roles(*_a: object) -> list[uuid.UUID]:
        return []

    async def names(ids: object) -> dict[uuid.UUID, str]:
        return {ME: "Hannah Leclerc"}

    async def access(_ctx: object, clients: list[uuid.UUID]) -> str:
        return "omitted" if WALLED in clients else ("locked" if LOCKED in clients else "open")

    monkeypatch.setattr(session_list, "tenant_session", session)
    monkeypatch.setattr(session_list, "my_engagement_roles", roles)
    monkeypatch.setattr(session_list, "display_names", names)
    monkeypatch.setattr(session_list, "viewer_access", access)


def test_t09_a_walled_session_adds_no_row_no_count_no_search_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = [
        _raw("Northwind plan questions", [OPEN], "running"),
        _raw("Copperleaf K-3 workpapers", [WALLED], "running"),
        _raw("Explain Copperleaf payroll change", [LOCKED], "awaiting_answer"),
    ]
    _wire_list(monkeypatch, raw)
    listed = asyncio.run(session_list.list_sessions(_ctx()))
    titles = [r.title for r in listed.rows]
    assert "Copperleaf K-3 workpapers" not in titles
    assert listed.total == 2 and listed.running == 1 and listed.needs_answer == 1
    searched = asyncio.run(session_list.list_sessions(_ctx(), q="K-3"))
    assert searched.rows == () and searched.total == 0
    locked = next(r for r in listed.rows if r.title.startswith("Explain"))
    assert locked.locked


def test_t09_search_matches_titles_only() -> None:
    row = session_list.Row(
        uuid.uuid4(), "Season progress", ME, "", "manual", "live", None, "auto", False, "v"
    )
    assert session_list.matches(row, "all", "PROGRESS", ME)
    assert not session_list.matches(row, "all", "Northwind", ME)


# --- T06: insert-only items, soft delete -------------------------------------------------------


def test_t06_items_are_insert_only_and_sessions_soft_delete() -> None:
    assert "session_items" in registry.INSERT_ONLY
    assert "session_items" not in registry.UPDATE_COLUMNS
    updatable = registry.UPDATE_COLUMNS["workbench_sessions"]
    assert {"deleted_at", "deleted_by"} <= updatable
    import inspect

    source = inspect.getsource(session_list.delete_session)
    assert "DELETE FROM" not in source.upper().replace("DELETED", "")


# --- T10: the picker lists only what the viewer can open ----------------------------------------


def _engagement(client: uuid.UUID, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), client_id=client, client_entity_id=uuid.uuid4(),
        client_entity_name=name, name="PY2025 EBP Audit",
        fiscal_period_start=date(2025, 1, 1), fiscal_period_end=date(2025, 12, 31),
    )  # fmt: skip


def test_t10_options_come_only_from_openable_engagements(monkeypatch: pytest.MonkeyPatch) -> None:
    northwind = _engagement(OPEN, "Northwind Robotics 401(k) Plan")

    async def engagements_for(_ctx: object) -> list[SimpleNamespace]:
        return [northwind]  # the server's visible() set: Copperleaf is not in it

    monkeypatch.setattr(session_context, "engagements_for", engagements_for)
    options = asyncio.run(session_context.all_options(_ctx()))
    assert options
    assert {o.engagement_id for o in options} == {northwind.id}
    assert not any("Copperleaf" in o.title for o in options)


def test_t10_attaching_a_record_off_the_list_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def nothing(_ctx: object) -> list[object]:
        return []

    monkeypatch.setattr(session_context, "all_options", nothing)
    with pytest.raises(NotFound):
        asyncio.run(
            session_context.attach(_ctx(), uuid.uuid4(), [("client_entity", uuid.uuid4())])
        )


# --- T11: the season counts foot ---------------------------------------------------------------


def test_t11_season_counts_foot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard: returns = open + done = Σ by_status = Σ offices (open + done); counts only."""
    from abacus.kernel import clock
    from abacus.modules.organisations import api as organisations_api
    from abacus.modules.tax import board as tax_board
    from abacus.modules.tax import tools

    chicago, denver = uuid.uuid4(), uuid.uuid4()
    e1, e2 = uuid.uuid4(), uuid.uuid4()
    done = sorted(tax_board.DONE)[0]

    def row(status: str, office: uuid.UUID, engagement: uuid.UUID) -> tuple[object, object]:
        facts = SimpleNamespace(office_id=office, engagement_id=engagement)
        return SimpleNamespace(status=status), facts

    rows = [
        row("in_preparation", chicago, e1),
        row("in_review", chicago, e1),
        row(done, denver, e2),
    ]

    async def board(*_a: object) -> SimpleNamespace:
        return SimpleNamespace(rows=rows, tax_year=2025)

    async def offices(*_a: object) -> list[tuple[uuid.UUID, str]]:
        return [(chicago, "Chicago"), (denver, "Denver")]

    async def today(*_a: object) -> date:
        return date(2026, 9, 14)

    monkeypatch.setattr(tax_board, "_board", board)
    monkeypatch.setattr(tax_board, "_due", lambda _r: None)  # pyright: ignore[reportUnknownLambdaType] -- no due dates
    monkeypatch.setattr(organisations_api, "firm_offices", offices)
    monkeypatch.setattr(clock, "today", today)
    agent = SimpleNamespace(tenant=TenantContext(uuid.uuid4(), "agent", "run:1"))
    out = asyncio.run(
        tools.season_counts(
            cast(Any, agent), tools.SeasonIn(tax_year=2025)
        )  # Any: a stand-in agent
    )
    assert out.returns == out.open + out.done == 3
    assert sum(s.count for s in out.by_status) == out.returns
    assert sum(o.open + o.done for o in out.by_office) == out.returns
    assert out.engagements == 2 and out.engagements_with_two_returns == 1
    assert {o.office for o in out.by_office} == {"Chicago", "Denver"}
