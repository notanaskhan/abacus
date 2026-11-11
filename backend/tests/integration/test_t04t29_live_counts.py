"""T-04-T29 (TASK-6828; SPEC-649): the return's counts reach a second tab. An issue raised or moved
announces `issue.status_changed` (identifiers and the status word only), and the invalidation
subscriber turns it into one `realtime_events` row on the engagement topic, which the SPA's
`engagement:<id>` stream answers by refetching the workspace summary. Worksheet fields name each
section's id, the SHL-12 target of a section sign-off."""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.notifications.realtime import on_outbox_event
from abacus.modules.review.api import create_issue, move_issue

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Feld, feld_return
from .test_t01t25_engine_export import engines as engines  # the autouse fixture

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


def _payload(raw: object) -> dict[str, object]:
    found = json.loads(raw) if isinstance(raw, str) else raw
    return cast(dict[str, object], found)


async def test_an_issue_raised_and_resolved_announces_its_status(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    issue = await _issue(feld, "missing_information", "K-1 box 18A: obligations' state")
    await move_issue(feld.samuel, issue, "resolved", 1)
    rows = await feld.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'issue.status_changed'",
        feld.tenant,
    )
    payloads = [_payload(r["payload"]) for r in rows]
    mine = [p for p in payloads if p["issue_id"] == str(issue)]
    # The outbox id is a UUID, so the rows carry no order: both moves, one event each.
    assert sorted(str(p["status"]) for p in mine) == ["open", "resolved"]
    assert set(mine[0]) >= {"issue_id", "engagement_id", "status"}
    assert "title" not in mine[0]  # identifiers only (ADR-031)


async def test_the_event_invalidates_the_engagement_topic(migrated_db: MigratedDatabase) -> None:
    feld = await feld_return(migrated_db)
    issue = await _issue(feld, "review_point", "New York City residency")
    engagement = await feld.seed.value("SELECT engagement_id FROM issues WHERE id = $1", issue)
    before = await feld.seed.value(
        "SELECT count(*) FROM realtime_events WHERE tenant_id = $1 AND topic = $2",
        feld.tenant,
        f"engagement:{engagement}",
    )
    await on_outbox_event(
        OutboxEvent(
            uuid.uuid4(),
            feld.tenant,
            "issue.status_changed",
            {"issue_id": str(issue), "engagement_id": str(engagement), "status": "open"},
        )
    )
    rows = await feld.seed.rows(
        "SELECT topic, ref_type, ref_id FROM realtime_events WHERE tenant_id = $1 AND topic = $2 "
        "ORDER BY seq",
        feld.tenant,
        f"engagement:{engagement}",
    )
    assert len(rows) == cast(int, before) + 1
    assert (rows[-1]["ref_type"], rows[-1]["ref_id"]) == ("issue", issue)
