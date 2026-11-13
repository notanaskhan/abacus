"""Independent AC tests for A-04-T25 and T31 (A-04-T36; ADR-078; SPEC-620 AC6, AC7).

Written apart from the builds: Sheet!Cell addresses stay stable, a proposed severity never
becomes a conclusion, routing is one unit of work and answers 503 before A-06 registers, the
gap-days golden is 92, the reliance card is refused while the gap is open, request drafts are
never sent by code, and every client and third-party principal, the agent and the system are
denied the writes (INV-1, INV-4). Walls answer 404 through `_gate` (INV-3), on the route source.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from abacus.kernel.errors import DomainUnavailable
from abacus.modules.assurance import internal_control as ic
from abacus.modules.assurance import planning_contract, soc_reports
from abacus.modules.assurance.compute import soc_gap

ROOT = Path(__file__).resolve().parents[4]
MATRIX = cast(
    dict[str, dict[str, str]],
    yaml.safe_load((ROOT / "docs/architecture/permission-matrix/assurance.yaml").read_text())[
        "actions"
    ],
)
WRITES = (
    "control.edit",
    "deficiency.propose_severity",
    "exception.route",
    "service_org.edit",
    "soc_report.evaluate",
)
DENIED = ("client_admin", "client_contributor", "third_party", "client_service", "agent", "system")
PLAN_YEAR = {"plan_year_start": date(2025, 1, 1), "plan_year_end": date(2025, 12, 31)}


def _strings(fn: object) -> list[str]:
    tree = ast.parse(inspect.getsource(cast(Any, fn)).lstrip())  # Any: test doubles and JSON
    return [
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


# --- T25: internal control ---------------------------------------------------------------------


def test_sheet_addresses_are_the_sheet_row_with_header_row_one() -> None:
    """Exceptions!D2 is row 2 in every version: derived from the row number, never stored."""
    row = cast(Any, SimpleNamespace(sheet_row=2))  # Any: test doubles and JSON
    assert ic.ControlException.address.fget(row) == "Exceptions!D2"  # type: ignore[attr-defined] -- APIRoute carries methods and openapi_extra
    row.sheet_row = 8
    assert ic.ControlException.address.fget(row) == "Exceptions!D8"  # type: ignore[attr-defined] -- APIRoute carries methods and openapi_extra


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_a_proposal_never_writes_a_concluded_severity() -> None:
    for text in _strings(ic.propose_severity):
        assert "concluded_severity" not in text
        assert "'concluded'" not in text


def test_routing_answers_503_until_a_router_registers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ic, "_ROUTERS", {})
    assert not ic.exception_route_available("finding")
    assert not ic.exception_route_available("misstatement")
    assert issubclass(ic.RouteNotAvailable, DomainUnavailable)
    assert ic.RouteNotAvailable.code == "route_not_available"


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_routing_calls_the_router_inside_the_unit_of_work() -> None:
    source = inspect.getsource(ic.route_exception)
    uow_at = source.index("async with uow(")
    assert source.index("router(", uow_at) > uow_at
    assert "routed_ref" in source[uow_at:]


# --- T31: SOC 1 evaluation ---------------------------------------------------------------------


def test_gap_days_golden_is_92_for_keystone() -> None:
    g = soc_gap.gap(
        **PLAN_YEAR,
        period_start=date(2024, 10, 1),
        period_end=date(2025, 9, 30),
        bridge_received=False,
    )
    assert (g.days, g.start, g.end) == (92, date(2025, 10, 1), date(2025, 12, 31))


@given(
    start=st.dates(min_value=date(2024, 1, 1), max_value=date(2025, 12, 31)),
    length=st.integers(min_value=0, max_value=730),
)
def test_gap_days_never_exceed_the_plan_year(start: date, length: int) -> None:
    from datetime import timedelta

    g = soc_gap.gap(
        **PLAN_YEAR,
        period_start=start,
        period_end=start + timedelta(days=length),
        bridge_received=False,
    )
    assert 0 <= g.days <= 365
    again = soc_gap.gap(
        **PLAN_YEAR,
        period_start=start,
        period_end=start + timedelta(days=length),
        bridge_received=False,
    )
    assert g.stamp.inputs_hash == again.stamp.inputs_hash


def test_reliance_is_refused_while_the_gap_is_open_and_allowed_once_bridged() -> None:
    open_gap = soc_gap.gap(
        **PLAN_YEAR,
        period_start=date(2024, 10, 1),
        period_end=date(2025, 9, 30),
        bridge_received=False,
    )
    bridged = soc_gap.gap(
        **PLAN_YEAR,
        period_start=date(2024, 10, 1),
        period_end=date(2025, 9, 30),
        bridge_received=True,
    )
    cuecs = [SimpleNamespace(n=1, status="evidenced")]
    blocking = soc_reports._blocking  # pyright: ignore[reportPrivateUsage] -- the helper under test
    opened = cast("soc_reports.SocReport", SimpleNamespace(gap=open_gap, cuecs=cuecs))
    closed = cast("soc_reports.SocReport", SimpleNamespace(gap=bridged, cuecs=cuecs))
    assert isinstance(blocking(opened), soc_reports.GapOpen)
    assert blocking(closed) is None


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_request_drafts_are_never_sent_by_code() -> None:
    source = inspect.getsource(soc_reports.request_drafts)
    for word in ("send(", ".send", "send_request", "notify("):
        assert word not in source


# --- principals --------------------------------------------------------------------------------


@pytest.mark.parametrize("action", WRITES)
def test_every_write_denies_clients_third_parties_the_agent_and_the_system(action: str) -> None:
    cell = MATRIX[action]
    for principal in DENIED:
        assert cell[principal] == "deny", (action, principal)
    assert cell["independence"] == "required"


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_every_route_gates_before_reading() -> None:
    """Walls answer 404 from `_gate` before any read (INV-3): no route body reads first."""
    for name in (
        "control_exceptions_route",
        "exception_propose_severity_route",
    ):
        body = inspect.getsource(getattr(planning_contract, name))
        assert body.index("await _gate(") < body.index("from abacus.modules.assurance")
