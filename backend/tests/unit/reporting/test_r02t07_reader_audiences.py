"""R-02-T07 (TASK-6107; R-02 §3.9, §3.11, §3.15 AC-38, AC-41; DEC-93): who reaches a deliverable.

Written from R-02 §3, not the implementation: a grant reaches an audience by role and scope. Dana's
management grant reads the work item's draft but never a governance letter; under her `tcwg` grant
she reads the committee's letters and nothing of management's; Victoria (tcwg only) reads the room;
Sam Ortiz (third party) and a K-1 recipient read nothing here; a narrower grant never widens.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting.deliverable_reads import (
    Audience,
    ReaderVersion,
    covers,
    reader_version,
)

CLIENT, ENGAGEMENT, WORK_ITEM, ROOM, OTHER = (uuid4() for _ in range(5))
ENTITY = uuid4()


def _reach(
    role: str,
    grant_kind: str,
    grant_scope: UUID,
    audience: Audience,
    *,
    engagement: UUID | None = ENGAGEMENT,
    work_item: UUID | None = None,
) -> bool:
    facts_engagement = engagement if grant_kind in ("engagement", "work_item") else None
    facts_work_item = work_item if grant_kind == "work_item" else None
    if grant_kind == "governance_room":
        facts_engagement, facts_work_item = ENGAGEMENT, WORK_ITEM
    return covers(
        role,
        grant_kind,
        grant_scope,
        CLIENT,
        facts_engagement,
        facts_work_item,
        audience,
        ENGAGEMENT,
        ENTITY,
    )


def test_dana_s_management_grant_reads_the_draft_but_never_the_room() -> None:
    assert _reach("plan_administrator", "engagement", ENGAGEMENT, Audience("work_item", WORK_ITEM))
    assert not _reach(
        "plan_administrator", "engagement", ENGAGEMENT, Audience("governance_room", ROOM)
    )


def test_a_tcwg_grant_reads_its_room_and_nothing_of_management_s() -> None:
    assert _reach("tcwg", "governance_room", ROOM, Audience("governance_room", ROOM))
    assert not _reach("tcwg", "governance_room", ROOM, Audience("governance_room", OTHER))
    assert not _reach("tcwg", "governance_room", ROOM, Audience("work_item", WORK_ITEM))
    assert not _reach("tcwg", "governance_room", ROOM, Audience("client", CLIENT))


@pytest.mark.parametrize(
    "role", ["third_party", "delegate", "k1_recipient", "prospect", "component_auditor"]
)
def test_these_roles_read_no_c10_deliverable(role: str) -> None:
    assert not _reach(role, "client", CLIENT, Audience("client", CLIENT))
    assert not _reach(role, "engagement", ENGAGEMENT, Audience("work_item", WORK_ITEM))


def test_a_narrower_grant_never_widens() -> None:
    other_item = Audience("work_item", OTHER)
    assert not _reach("owner", "work_item", WORK_ITEM, other_item, work_item=WORK_ITEM)
    assert _reach(
        "owner", "work_item", WORK_ITEM, Audience("work_item", WORK_ITEM), work_item=WORK_ITEM
    )
    # a work-item grant does not reach the engagement-wide audience
    assert not _reach(
        "owner", "work_item", WORK_ITEM, Audience("engagement", ENGAGEMENT), work_item=WORK_ITEM
    )


def test_a_client_wide_grant_reaches_client_and_engagement_audiences() -> None:
    assert _reach("owner", "client", CLIENT, Audience("client", CLIENT))
    assert _reach("owner", "client", CLIENT, Audience("engagement", ENGAGEMENT))
    assert _reach("owner", "client", CLIENT, Audience("client_entity", ENTITY))
    assert not _reach("owner", "client", CLIENT, Audience("client_entity", OTHER))


def test_an_engagement_grant_on_another_engagement_reaches_nothing() -> None:
    assert not _reach(
        "owner", "engagement", OTHER, Audience("work_item", WORK_ITEM), engagement=OTHER
    )


def _ctx(*, client: bool, actor: str = "human") -> AuthContext:
    return AuthContext(
        TenantContext(uuid4(), actor, str(uuid4())),  # type: ignore[arg-type]
        uuid4(),
        uuid4(),
        None,
        datetime(2026, 10, 8, tzinfo=UTC),
        client=client,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client", "actor"), [(False, "human"), (True, "agent"), (True, "support")]
)
async def test_firm_agent_and_support_principals_get_404_before_any_read(
    client: bool, actor: str
) -> None:
    with pytest.raises(NotFound):
        await reader_version(_ctx(client=client, actor=actor), uuid4(), 1)


def test_the_servable_handover_carries_no_grant_or_kind() -> None:
    reader = ReaderVersion(
        deliverable_id=uuid4(),
        version_id=uuid4(),
        version_no=3,
        evidence_version_id=uuid4(),
        is_draft=True,
        watermarked=True,
        page_count=14,
        kind="fs_draft",
        title="Financial statements and supplemental schedules",
        client_id=CLIENT,
        engagement_id=ENGAGEMENT,
        work_item_id=WORK_ITEM,
        tri=False,
        contact_id=uuid4(),
        grant_id=uuid4(),
    )
    servable = reader.servable()
    assert servable.version_id == reader.version_id
    assert servable.page_count == 14 and servable.watermarked
    assert not hasattr(servable, "grant_id")
