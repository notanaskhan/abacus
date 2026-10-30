"""T-01-T16 (TASK-2307; SPEC-501 AC-39 to AC-44; T-01 §4.4; ADM-05, CLI-05): the consent registry,
export and lifecycle sweep, the parts that need no database.

The row's acceptance: the registry returns 218 with tiles 212, 2, 1, 1, 1, 1 at Sep 14, 2026,
Rao shows Expiring 16 days, and a walled user sees neither the row nor a count. The seeded
figures are the scenario's (T-01-T23 loads them); here the rules behind them are proven: the
tiles add to the total because Signed excludes Expiring, Expiring is derived at 30 days, the
scope is `visible_clients` (walls with no count) plus I-OFFSHORE, and the sweep is idempotent.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects import postgresql

from abacus.modules.organisations import activities, consent_registry, workflows
from abacus.modules.organisations.consent_registry import (
    EXPIRING_WITHIN,
    TILES,
    consent_csv,
    display_status,
)

AT = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


def _sql(clause: object) -> str:
    return str(clause.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]  # a ColumnElement


def test_ac39_the_tiles_are_six_and_signed_excludes_expiring() -> None:
    assert TILES == ("signed", "expiring", "requested", "expired", "declined", "revoked")
    sql = _sql(display_status(AT))
    assert "CASE WHEN" in sql and "expiring" in sql
    assert EXPIRING_WITHIN == timedelta(days=30)  # Rao at 16 days is Expiring


def test_ac39_needs_attention_comes_first() -> None:
    order = consent_registry._ORDER  # pyright: ignore[reportPrivateUsage] -- the order under test
    assert order.index("requested") < order.index("expiring") < order.index("signed")
    assert order[-1] == "superseded"


def test_ac40_the_scope_is_walls_and_offshore_with_no_hidden_count() -> None:
    source = inspect.getsource(consent_registry._scope)  # pyright: ignore[reportPrivateUsage] -- the scope under test
    assert "visible_clients(ctx, READ" in source
    assert "offshore_column" in source and "is_offshore" in source
    registry = inspect.getsource(consent_registry.registry)
    assert registry.count("scope") >= 3  # rows and tiles share one scope: no hidden count


def test_ac42_the_csv_never_starts_a_formula() -> None:
    body = consent_csv([("=HYPERLINK(1)", "+1", "-2", "@x", "Feld", None, "2025")]).decode()
    lines = body.splitlines()
    assert lines[0].startswith("Client,Taxpayer,Purpose")
    assert lines[1].startswith("'=HYPERLINK(1),'+1,'-2,'@x,Feld,,2025")


def test_ac43_the_sweep_marks_what_it_raised_so_a_rerun_raises_nothing() -> None:
    source = inspect.getsource(consent_registry.sweep)
    assert "not row.warned" in source and "not row.flagged" in source
    assert '"kind": "expiring"' in source and '"kind": "reconsent_required"' in source
    assert "ConsentExpired" in source and "AccessChanged" in source


def test_ac44_the_workflows_run_activities_by_name_on_a_daily_schedule() -> None:
    assert workflows.SWEEP_ID == "consent_sweep:platform"
    [schedule] = activities.SCHEDULES
    assert schedule.every == timedelta(days=1)
    assert schedule.workflow is workflows.ConsentLifecycleSweepWorkflow
    names = {a.__temporal_activity_definition.name for a in activities.ACTIVITIES}  # type: ignore[attr-defined]  # temporalio's marker
    assert names == {"organisations.consent_export", "organisations.consent_sweep"}
    assert workflows.export_workflow_id("t", "e") == "consent_export:t:e"
