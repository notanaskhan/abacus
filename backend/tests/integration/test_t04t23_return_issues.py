"""T-04-T23 (TASK-6724; SPEC-649 AC-4.1, AC-4.2, AC-5.2; 0800): the Feld return's issues.

Row acceptance (held here): "Feld shows 4 open issues (2 Missing information, 1 Action required,
1 Review point) and 3 resolved, the Draft K-1 issue resolves only when the K-1 is released". The
seven issues are raised here as T-04-T28's slice will raise them; "the activity read lists 24
events" needs T-04-T28's whole Feld timeline (flagged in TASK-6724).
"""

from __future__ import annotations

import uuid
from typing import cast

import asyncpg
import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.review.api import IssueSystemResolvedOnly, create_issue, move_issue
from abacus.modules.tax.return_issues import (
    checkpoint_chip,
    issue_counts,
    on_k1_package_released,
    raise_draft_k1_issue,
)

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Feld, engines, feld_return  # noqa: F401 -- fixtures

pytestmark = pytest.mark.asyncio


async def _issue(feld: Feld, kind: str, title: str) -> uuid.UUID:
    return await create_issue(
        feld.samuel,
        record_type="tax_return",
        record_id=feld.item,
        kind=kind,
        priority="medium",
        title=title,
        internal_note=None,
        client_wording=None,
        client_contact_id=None,
        assignee_user_id=None,
        assignee_agent=False,
        blocks=(),
        work_item_id=feld.item,
    )


async def _seven(feld: Feld) -> tuple[uuid.UUID, uuid.UUID]:
    package = uuid.uuid4()
    await _issue(feld, "missing_information", "K-1 box 18A: obligations' state")
    await _issue(feld, "missing_information", "Estimated payments: Q3 and Q4 receipts")
    draft = await raise_draft_k1_issue(
        feld.samuel, return_id=feld.item, package_id=package, assignee_user_id=feld.samuel.user_id
    )
    await _issue(feld, "review_point", "New York City residency")
    for title in ("W-2 box 12 code", "1099-INT payer", "Organizer: dependents"):
        done = await _issue(feld, "missing_information", title)
        await move_issue(feld.samuel, done, "resolved", 1)
    return draft, package


async def test_ac_feld_shows_4_open_by_kind_and_3_resolved(migrated_db: MigratedDatabase) -> None:
    feld = await feld_return(migrated_db)
    await _seven(feld)
    counts = await issue_counts(feld.samuel, feld.item)
    assert counts.open_total == 4
    assert counts.open_by_kind == {
        "Missing information": 2,
        "Action required": 1,
        "Review point": 1,
    }
    assert counts.resolved == 3


async def test_ac_the_draft_k1_issue_resolves_only_when_the_k1_is_released(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    draft, package = await _seven(feld)
    with pytest.raises(IssueSystemResolvedOnly):
        await move_issue(feld.samuel, draft, "resolved", 1)
    with pytest.raises(asyncpg.CheckViolationError):  # and the database refuses it too
        await feld.seed.as_actor(
            feld.tenant,
            ("human", str(feld.samuel.user_id)),
            "INSERT INTO issue_events (tenant_id, issue_id, event) VALUES ($1, $2, 'resolved')",
            feld.tenant,
            draft,
        )
    await on_k1_package_released(
        OutboxEvent(
            uuid.uuid4(),
            feld.tenant,
            "k1_package.released",
            {"package_id": str(package), "work_item_id": str(uuid.uuid4())},
        )
    )
    row = await feld.seed.rows(
        "SELECT i.status, e.actor_kind FROM issues i JOIN issue_events e ON e.issue_id = i.id "
        "WHERE i.id = $1 AND e.event = 'system_resolved'",
        draft,
    )
    assert [(r["status"], r["actor_kind"]) for r in row] == [("resolved", "system")]
    counts = await issue_counts(feld.samuel, feld.item)
    assert (counts.open_total, counts.resolved) == (3, 4)


async def test_the_checkpoint_chip_reads_the_returns_checkpoints(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    chip = await checkpoint_chip(feld.samuel, feld.item)
    assert chip.state in ("proposed", "no_changes")
    assert chip.proposed == cast(
        int,
        await feld.seed.value(
            "SELECT count(*) FROM checkpoints WHERE target_id = $1 AND status = 'proposed'",
            feld.item,
        ),
    )
