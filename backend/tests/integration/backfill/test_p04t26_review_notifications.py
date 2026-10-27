"""P-04-T26 acceptance (TASK-1462; C16; SPEC-013): the review grammar's seven notification kinds.

"Each kind fans out once per recipient with walls re-checked, and no template text is committed."

Boundary: the relay's handlers (`notifications.api.SUBSCRIPTIONS`), the feed over HTTP, the
database through SQL. Email text is database content (C16): nothing here renders a template.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Final

import pytest

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.notifications import api as notifications

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
Json = dict[str, object]
FEED: Final = "/v1/notifications/feed"
KINDS: Final = {
    "sign_off.went_stale": ("sign_off_stale", "sign_off", "sign_off_id"),
    "review_note.raised": ("review_note_raised", "reviewable_note", "note_id"),
    "decision_card.raised": ("decision_assigned", "decision_card", "card_id"),
    "proposal.routed": ("proposal_routed", "proposal", "proposal_id"),
    "sign_off.requested": ("sign_off_requested", "reviewable", "target_id"),
    "issue.assigned": ("issue_assigned", "issue", "issue_id"),
    "checkpoint.created": ("import_pending_approval", "checkpoint", "checkpoint_id"),
}


@pytest.fixture(autouse=True)
async def no_email() -> AsyncIterator[None]:
    async def nothing(_given: object) -> None:
        return None

    notifications.configure_email_starter(nothing)
    yield
    notifications.configure_email_starter(None)


async def _world(net: Net) -> tuple[Seeder, Site, Person, Person, Person]:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'notifications.v2', 'true', 'test-seed', 'P-04-T26')",
        tenant,
    )
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "p04t26")
    priya, lena = await seed.person(tenant), await seed.person(tenant)
    await seed.member(site, priya, "manager")
    await seed.member(site, lena, "staff")
    await net.wall(admin, lena, site)  # Lena is walled from the client after she joined
    return seed, site, admin, priya, lena


def _payload(kind: str, site: Site, subject: uuid.UUID, people: list[Person]) -> Json:
    ids = [str(p.user_id) for p in people]
    payload: Json = {
        "engagement_id": str(site.engagement_id),
        KINDS[kind][2]: str(subject),
        "recipient_user_ids": ids,
    }
    if kind == "sign_off.went_stale":
        payload["signed_by"] = ids[0]
    if kind == "issue.assigned":
        payload["assignee_user_id"] = ids[0]
    if kind == "proposal.routed":
        payload["approver_user_id"] = ids[0]
    if kind == "checkpoint.created":
        payload["author_kind"] = "import"
    return payload


@pytest.mark.parametrize("event_type", sorted(KINDS))
async def test_ac_each_kind_fans_out_once_per_recipient_with_walls_rechecked(
    net: Net, event_type: str
) -> None:
    seed, site, _, priya, lena = await _world(net)
    kind, subject_type, _ = KINDS[event_type]
    handler = notifications.SUBSCRIPTIONS[event_type]
    for target in (priya, lena):  # one event naming the walled member too, where it names one
        subject = uuid.uuid4()
        event = OutboxEvent(
            uuid.uuid4(), site.tenant_id, event_type, _payload(event_type, site, subject, [target])
        )
        await handler(event)
        await handler(event)  # redelivered: still one row
    rows = await seed.rows(
        "SELECT recipient_user_id, kind, category, subject_type FROM notifications "
        "WHERE tenant_id = $1",
        site.tenant_id,
    )
    assert [tuple(r) for r in rows] == [(priya.user_id, kind, "approval", subject_type)]
    assert lena.user_id not in {r[0] for r in rows}


async def test_ac_only_an_imports_checkpoint_notifies(net: Net) -> None:
    seed, site, _, priya, _lena = await _world(net)
    payload = _payload("checkpoint.created", site, uuid.uuid4(), [priya]) | {
        "author_kind": "agent"
    }
    await notifications.SUBSCRIPTIONS["checkpoint.created"](
        OutboxEvent(uuid.uuid4(), site.tenant_id, "checkpoint.created", payload)
    )
    assert (
        await seed.value("SELECT count(*) FROM notifications WHERE tenant_id = $1", site.tenant_id)
        == 0
    )


async def test_ac_a_routed_proposal_reads_its_facts_and_waits_in_approvals(net: Net) -> None:
    seed, site, _, priya, _lena = await _world(net)
    proposal = await seed.value(
        "INSERT INTO proposals (tenant_id, engagement_id, kind, title, agent_run_id, "
        "routed_to_user_id) VALUES ($1, $2, 'field_change_set', 'AJE-05', $3, $4) RETURNING id",
        site.tenant_id,
        site.engagement_id,
        uuid.uuid4(),
        priya.user_id,
    )
    raj = await seed.person(site.tenant_id)
    await seed.member(site, raj, "senior")
    await notifications.SUBSCRIPTIONS["proposal.routed"](
        OutboxEvent(
            uuid.uuid4(),
            site.tenant_id,
            "proposal.routed",
            {
                "engagement_id": str(site.engagement_id),
                "proposal_id": str(proposal),
                "approver_user_id": str(priya.user_id),
                "by_user": str(raj.user_id),
            },
        )
    )
    # A person routed it: the row reads as Raj's, not the agent's (INV-5; DEC-605).
    actor = await seed.rows(
        "SELECT actor_kind, actor_user_id FROM notifications WHERE tenant_id = $1",
        site.tenant_id,
    )
    assert [tuple(a) for a in actor] == [("human", raj.user_id)]
    response = await net.call("GET", f"{FEED}?tab=approvals", priya)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1 and items[0]["kind"] == "proposal_routed" and items[0]["pending"]
    assert items[0]["facts"] == {
        "proposal_kind": "field_change_set",
        "state": "pending",
        "version": 1,
    }


def test_ac_no_template_text_is_committed() -> None:
    """C16: email bodies are database content; the catalogue holds only the in-app sentence."""
    import abacus.modules.notifications.catalogue as catalogue

    source = Path(catalogue.__file__).read_text(encoding="utf-8")
    for code in ("sign_off_requested", "proposal_routed", "issue_assigned"):
        assert f"notification.{code}" not in source
    for event in KINDS:
        found = notifications.kind_of(KINDS[event][0])
        assert found is not None and found.category == "approval"
