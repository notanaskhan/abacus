"""C-01-T48 (TASK-8307; ADR-078): independent AC tests for N's red work on the CAS ledger path
(C-01-T10, T16, T17, T18), written outside N's sessions from SPEC-655 F5 and C-01 §7.

ac-test-author: ayushkbhatia

- **CONN-001**: no write method or write route anywhere in `connections` or `closes` reaches a
  provider: no source in either module calls an HTTP write verb on a client, the QBO connector
  declares no write capability, and its reads stay GET under the write-interception harness.
- **Cadence**: the hourly tick only syncs inside the firm's business hours (07:00 to 19:00,
  weekdays, in firm time) and the next opening is always inside them.
- **Snapshot immutability and RLS** are proven against Postgres in
  `tests/integration/test_c01t48_snapshots_ac.py`.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from abacus.modules.connections import ledger_sync
from abacus.modules.connections.connectors import quickbooks_online as qbo

SRC = Path(__file__).parents[3] / "src" / "abacus" / "modules"
WRITE_VERBS = frozenset({"post", "put", "patch", "delete"})
# Router decorators declare the firm's own API (writes to Accrued's database through the unit of
# work), not calls to a provider: `@router.post(...)` is a decorator, never a client call.
ROUTERS = frozenset({"router", "close_work_router", "portal_close_router", "closes_router"})
# The OAuth token exchange is the provider's one read-shaped POST (ADR-040's allowlist); it is in
# the token service, not in these modules.
CHICAGO = ZoneInfo("America/Chicago")
HOURS = {"start": "07:00", "end": "19:00"}


def _write_calls(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    decorators = {
        id(d.func)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for d in node.decorator_list
        if isinstance(d, ast.Call)
    }
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or id(node.func) in decorators:
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in WRITE_VERBS:
            owner = func.value
            name = owner.id if isinstance(owner, ast.Name) else ""
            if name in ROUTERS or name.endswith("_router"):
                continue
            found.append((node.lineno, func.attr))
    return found


@pytest.mark.parametrize("module", ["connections", "closes", "ledger"])
def test_conn001_no_source_calls_a_write_verb_on_a_client(module: str) -> None:
    offenders = {
        str(p.relative_to(SRC)): calls
        for p in sorted((SRC / module).rglob("*.py"))
        if (calls := _write_calls(p))
    }
    assert offenders == {}, offenders


def test_conn001_the_qbo_connector_declares_no_write() -> None:
    connector_cls = qbo.QuickBooksOnlineConnector
    writes = [
        name
        for name in dir(connector_cls)
        if any(name.startswith(v) for v in ("write", "post", "put", "delete", "create", "update"))
    ]
    assert writes == []


@pytest.mark.parametrize(
    ("local", "inside"),
    [
        (datetime(2026, 9, 14, 6, 59, tzinfo=CHICAGO), False),  # Monday before opening
        (datetime(2026, 9, 14, 7, 0, tzinfo=CHICAGO), True),
        (datetime(2026, 9, 14, 18, 59, tzinfo=CHICAGO), True),
        (datetime(2026, 9, 14, 19, 0, tzinfo=CHICAGO), False),  # closing is exclusive
        (datetime(2026, 9, 12, 12, 0, tzinfo=CHICAGO), False),  # Saturday
        (datetime(2026, 9, 13, 12, 0, tzinfo=CHICAGO), False),  # Sunday
    ],
)
def test_cadence_syncs_only_inside_business_hours(local: datetime, inside: bool) -> None:
    assert ledger_sync.in_business_hours(local.astimezone(UTC), HOURS, CHICAGO) is inside


def test_cadence_is_hourly_and_the_next_opening_is_inside_hours() -> None:
    assert timedelta(hours=1) == ledger_sync.TICK
    start = datetime(2026, 9, 11, 19, 30, tzinfo=CHICAGO)  # Friday after closing
    for step in range(0, 72 * 4):
        at = (start + timedelta(minutes=15 * step)).astimezone(UTC)
        opening = ledger_sync.next_opening(at, HOURS, CHICAGO)
        assert opening >= at
        assert ledger_sync.in_business_hours(opening, HOURS, CHICAGO)
    friday_night = ledger_sync.next_opening(start.astimezone(UTC), HOURS, CHICAGO)
    assert friday_night.astimezone(CHICAGO) == datetime(2026, 9, 14, 7, 0, tzinfo=CHICAGO)
