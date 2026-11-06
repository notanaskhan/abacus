"""A-06-T11 (TASK-3014; A-06 §4.3; SPEC-642; DEC-2063): the findings service.

Row acceptance: "The Northwind list returns bands 1 + 2 + 1 + 5 = 9 with badge 3, an uncited agent
finding is refused, and resolve or not-applicable by an agent principal is denied." The list over
the Northwind seed is the integration suite's; here: the bands foot to the rows, the badge counts
the proposed deficiencies, an agent's finding without its run's verified citations is refused
before anything is written, and the matrix denies the agent both acts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from abacus.modules.assurance import findings
from abacus.modules.assurance.findings import Finding, NewFinding, UncitedFinding
from abacus.modules.identity.authz import _matrix
from abacus.modules.sampling.api import (
    misstatement_per_item,
    projected_misstatement,
    projection_carried,
)


def _finding(proposed: str | None, concluded: str | None, status: str | None) -> Finding:
    return Finding(
        uuid.uuid4(), uuid.uuid4(), "F-01", "t", "control_deficiency", "under_evaluation",
        status, proposed, concluded, None, "", datetime.now(UTC), None, {}, None, "open", (),
    )  # fmt: skip


def test_ac_the_bands_foot_to_the_rows_and_the_badge_counts_proposed() -> None:
    rows = [
        _finding("material_weakness", "material_weakness", "concluded"),
        _finding("significant_deficiency", None, "proposed"),
        _finding("significant_deficiency", None, "proposed"),
        _finding("deficiency", None, "proposed"),
        *(_finding(None, None, None) for _ in range(5)),
    ]
    bands = [r.band for r in rows]
    assert [bands.count(b) for b in findings.BANDS] == [1, 2, 1, 5]
    assert sum(1 for r in rows if r.deficiency_status == "proposed") == 3


async def test_ac_an_uncited_agent_finding_is_refused() -> None:
    agent = SimpleNamespace(tenant=SimpleNamespace(actor_kind="agent"), tenant_id=uuid.uuid4())

    async def engagement(_t: object, _w: uuid.UUID) -> uuid.UUID:
        return uuid.uuid4()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(findings, "work_item_engagement", engagement)
        new = NewFinding(uuid.uuid4(), "Late deposit", "control_deficiency", None, ())
        with pytest.raises(UncitedFinding):
            await findings.record_finding(agent, uuid.uuid4(), new)  # pyright: ignore[reportArgumentType] -- a stand-in agent


@pytest.mark.parametrize("action", ["finding.resolve", "finding.mark_not_applicable"])
def test_ac_the_agent_may_not_resolve_or_mark_not_applicable(action: str) -> None:
    assert _matrix.ACTIONS[action].get("agent") == "deny"


def test_ac_the_projection_reads_2140_over_25_times_412_and_carries_35300() -> None:
    exact = projected_misstatement(Decimal("2140.00"), 25, 412)
    assert exact == Decimal("35267.20")
    assert projection_carried(exact) == Decimal("35300.00")
    assert misstatement_per_item(Decimal("2140.00"), 25) == Decimal("85.60")


@pytest.mark.parametrize(
    ("exact", "carried"),
    [
        ("150.00", "200.00"),  # half away from zero
        ("-150.00", "-200.00"),
        ("149.99", "100.00"),
        ("49.99", "49.99"),  # never zero: a misstatement under 50 keeps its figure
    ],
)
def test_the_carried_figure_is_the_nearest_hundred(exact: str, carried: str) -> None:
    assert projection_carried(Decimal(exact)) == Decimal(carried)


def test_only_a_person_concludes_a_consultation() -> None:
    cells = _matrix.ACTIONS["consultation.conclude"]
    assert (cells.get("agent"), cells.get("system")) == ("deny", "deny")
