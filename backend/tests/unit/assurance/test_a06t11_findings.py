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
from types import SimpleNamespace

import pytest

from abacus.modules.assurance import findings
from abacus.modules.assurance.findings import Finding, NewFinding, UncitedFinding
from abacus.modules.identity.authz import _matrix


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


def test_only_a_person_concludes_a_consultation() -> None:
    cells = _matrix.ACTIONS["consultation.conclude"]
    assert (cells.get("agent"), cells.get("system")) == ("deny", "deny")
