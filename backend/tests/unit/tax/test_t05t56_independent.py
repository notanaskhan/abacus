"""T-05-T56 (ADR-078; TASK-7908): independent acceptance tests for the entity return's amber
services part 1: T-05-T17 (tax entity core, 0821), T-05-T20 (workbook and memo tables, 0830),
T-05-T27 (the workbook service), T-05-T33 (the entity TB read model), T-05-T34 (schedule read
models), T-05-T35 (the cell edit) and T-05-T41 (the allocation structure), written from SPEC-651
and the rows' acceptance, not from the implementation.

Row acceptance: "The suite runs against the real services and asserts INV-1 and INV-3 on every
route." INV-1: no agent decides (every writing route's action is `agent: deny`). INV-3: a wall
answers 404 and reveals no counts (every workbook route reads the return through the visibility
check before anything else). Each test names its guard.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import uuid
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import RULES, AuthContext
from abacus.modules.tax import allocation_structure, cell_edit, registry, workbook_service
from abacus.modules.tax.workbook_contract import workbook_router

VERSIONS = Path(__file__).resolve().parents[3] / "migrations/versions"
READS = ("_workbook_read", "load_return", "_memo_read", "_facts(")
BAD_SOURCE = cast(Any, "agent_suggested")  # Any: an invalid source, on purpose


def _migration(name: str) -> ModuleType:
    path = next(VERSIONS.glob(f"{name}_*.py"))
    spec = importlib.util.spec_from_file_location(f"m{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _immutable(m: ModuleType) -> set[str]:
    return set(cast(tuple[str, ...], m.IMMUTABLE))


DRAFT = cast(Any, object())  # Any: an opaque draft the preview hands to the engine


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        cast(Any, "staff"),  # Any: a firm role name stand-in
        None,
    )


# --- T-05-T17 / T-05-T20: forced RLS and insert-only versions -----------------------------------


@pytest.mark.parametrize("name", ["0821", "0830"])
def test_t17_t20_every_table_forced_rls_and_versions_insert_only(name: str) -> None:
    """Guard: each migration's TABLES go through `tenant_table` (forced RLS) and its IMMUTABLE
    tables through `insert_only` plus an immutability trigger; the tax registry lists them."""
    m = _migration(name)
    tables = set(cast(Any, m).TABLES)  # Any: the migration module's constant
    immutable = set(cast(Any, m).IMMUTABLE)  # Any: the migration module's constant
    source = inspect.getsource(m)
    assert tables and immutable <= tables
    assert "tenant_table(op, table)" in source
    assert "insert_only(op, table)" in source and "_immutable BEFORE UPDATE OR DELETE" in source
    assert tables <= set(registry.TABLES)
    assert immutable <= set(registry.INSERT_ONLY)


def test_t17_allocation_versions_and_results_are_insert_only() -> None:
    m = _migration("0821")
    assert {"allocation_structures", "allocation_results"} <= _immutable(m)


def test_t20_memo_versions_and_events_are_insert_only() -> None:
    m = _migration("0830")
    assert {"preparer_memo_versions", "preparer_memo_events"} <= _immutable(m)


# --- T-05-T41: human-only L3 approval; preview never persists -----------------------------------


def test_t41_approved_is_a_persons_row_in_the_database() -> None:
    """Guard: 0821's CHECK binds `approved` to `decided_actor_kind = 'human'` and the session."""
    source = inspect.getsource(_migration("0821"))
    assert "CHECK (status <> 'approved' OR (" in source
    assert "decided_actor_kind = 'human'" in source


def test_t41_approval_is_p04s_l3_sign_off() -> None:
    """Guard: the service records the approval through `sign_target` at level 3 before its own
    row (P-04 refuses an agent, staff and the preparer)."""
    source = inspect.getsource(allocation_structure.approve)
    assert "sign_target(ctx, TARGET, pending.id, 3," in source
    assert RULES["allocation_structure.approve"].decisions.get("agent") in ("deny", None)


def test_t41_preview_never_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()

    async def computed(*_a: object) -> object:
        return sentinel

    def no_write(*_a: object) -> object:
        pytest.fail("a preview opened a unit of work")

    monkeypatch.setattr(allocation_structure, "computed_for", computed)
    monkeypatch.setattr(allocation_structure, "uow", no_write)
    out = asyncio.run(allocation_structure.preview(_ctx(), uuid.uuid4(), 2025, DRAFT))
    assert out is sentinel


# --- T-05-T27: record_value provenance ----------------------------------------------------------


def test_t27_only_engine_or_person_sources_are_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard: `write_cells` refuses any source but formula, engine import, TB link and human,
    and names a cause for each (a person's write is an `edit`)."""
    seen: list[dict[str, object]] = []

    async def record(_tx: object, **kw: object) -> int:
        seen.append(kw)
        return 1

    monkeypatch.setattr(workbook_service, "record_value", record)
    tx = SimpleNamespace(session=None)
    with pytest.raises(workbook_service.CellSourceInvalid):
        asyncio.run(
            workbook_service.write_cells(
                cast(Any, tx),  # Any: a unit-of-work stand-in
                engagement_id=uuid.uuid4(), return_id=uuid.uuid4(),
                writes=[workbook_service.CellWrite("05!F2", None, BAD_SOURCE)],
            )
        )  # fmt: skip
    asyncio.run(
        workbook_service.write_cells(
            cast(Any, tx),  # Any: a unit-of-work stand-in
            engagement_id=uuid.uuid4(), return_id=uuid.uuid4(),
            writes=[workbook_service.CellWrite("05!F2", None, "human", citation_note="Edited")],
        )
    )  # fmt: skip
    assert seen[-1]["value_source"] == "human" and seen[-1]["cause"] == "edit"
    assert seen[-1]["citation_note"] == "Edited"


# --- T-05-T35: 409 expected_version and preparer-only edits -------------------------------------


def _wire_edit(monkeypatch: pytest.MonkeyPatch, *, seq: int, functions: set[str]) -> list[str]:
    notes: list[str] = []

    async def timeline(*_a: object) -> list[SimpleNamespace]:
        return [SimpleNamespace(seq=seq)] if seq else []

    async def held(*_a: object) -> set[str]:
        return functions

    async def raise_note(*_a: object, **kw: object) -> SimpleNamespace:
        notes.append(str(kw["body"]))
        return SimpleNamespace(note=SimpleNamespace(id=uuid.uuid4()))

    def no_write(*_a: object) -> object:
        pytest.fail("a refused edit opened a unit of work")

    monkeypatch.setattr(cell_edit, "field_timeline", timeline)
    monkeypatch.setattr(cell_edit, "functions_on", held)
    monkeypatch.setattr(cell_edit, "raise_review_note", raise_note)
    monkeypatch.setattr(cell_edit, "uow", no_write)
    return notes


def _edit(expected: int, *, run_open: bool = False) -> object:
    return asyncio.run(
        cell_edit.edit_cell(
            _ctx(), return_id=uuid.uuid4(), engagement_id=uuid.uuid4(), form="1065",
            address_text="05!F2", expected_version=expected, value="6866200", formula=None,
            run_open=run_open,
        )
    )  # fmt: skip


def test_t35_a_stale_expected_version_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_edit(monkeypatch, seq=3, functions={"preparer"})
    with pytest.raises(cell_edit.CellVersionConflict):
        _edit(2)


def test_t35_a_run_holds_the_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_edit(monkeypatch, seq=0, functions={"preparer"})
    with pytest.raises(cell_edit.CellsLockedByRun):
        _edit(0, run_open=True)


def test_t35_a_reviewer_proposes_never_overwrites(monkeypatch: pytest.MonkeyPatch) -> None:
    notes = _wire_edit(monkeypatch, seq=0, functions={"detail_reviewer"})
    out = cast(Any, _edit(0))  # Any: the edit outcome
    assert out.value is None and out.proposal_note_id is not None
    assert notes == ["Proposed 05!F2: 6866200"]


def test_t35_neither_function_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire_edit(monkeypatch, seq=0, functions=set())
    with pytest.raises(cell_edit.PreparerFunctionRequired):
        _edit(0)


# --- INV-1 and INV-3 on every workbook route ---------------------------------------------------


def _routes() -> list[Any]:  # Any: Starlette route objects
    return [r for r in workbook_router.routes if hasattr(r, "endpoint")]


def test_inv1_no_writing_route_lets_an_agent_act() -> None:
    """Guard: every POST, PUT, PATCH and DELETE route's matrix action is `agent: deny` (the agent
    proposes through C3; it never edits, signs, approves, imports, exports or starts a run)."""
    writes = [r for r in _routes() if set(r.methods) - {"GET", "HEAD"}]
    assert writes
    for route in writes:
        action = route.openapi_extra["x-abacus-action"]
        assert str(RULES[action].decisions.get("agent")) == "deny", (route.path, action)


def test_inv3_every_route_reads_the_return_through_the_wall_first() -> None:
    """Guard: each route checks the flag and reads the return as the viewer may see it (404 for
    a wall) before any figure or count."""
    for route in _routes():
        source = inspect.getsource(route.endpoint)
        assert "_flag_on(ctx)" in source, route.path
        body = source.split("_flag_on(ctx)", 1)[1]
        if "_not_yet()" in body and not any(r in body for r in READS):
            continue  # a 501 stub answers nothing, so it reveals nothing
        assert any(r in body for r in READS), route.path


def test_inv3_a_wall_answers_404_not_403(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.tax import overview, workbook_contract

    async def walled(*_a: object) -> object:
        raise NotFound("tax_return")

    monkeypatch.setattr(overview, "load_return", walled)
    with pytest.raises(NotFound):
        asyncio.run(
            workbook_contract._workbook_read(_ctx(), uuid.uuid4())  # pyright: ignore[reportPrivateUsage] -- the guard under test
        )
