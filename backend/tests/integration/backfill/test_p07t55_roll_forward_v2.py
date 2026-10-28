# ac-test-author: ayushkbhatia
"""P-07-T55 (TASK-1713; ENG-13; P-07 Story 7.1; DEC-805): roll-forward v2.

Acceptance (the task row): "Northwind PY2025 rolls into PY2026 with 24 requests as Draft, no
evidence copied, and an active source answers 409."

Also: the draft carries the v1 categories by default (team, template, request list, prior-year
notes) and saves on the version seen; Create makes a Prospect with `prior_engagement_id`, the
carried team and a continuance acceptance record, and answers the same engagement to a replay; a
walled person gets 404; the flag off answers 404; a person's act only.

Boundary: `create_app()` over HTTP as each signed-in person; outcomes through SQL.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, cast

import httpx
import pytest

from abacus.kernel.flags import forget_flags
from abacus.modules.engagements.roll_forward_v2 import next_name, next_year

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response body as the contract shapes it
FLAG: Final = "engagements.roll_forward_v2"
NAME: Final = "Northwind Robotics 401(k) Plan · PY2025"
STATUSES: Final = ("received",) * 11 + ("uploaded",) * 5 + ("requested",) * 6 + ("draft",) * 1


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    margaret: Person  # engagement partner, partner level
    hannah: Person  # manager, manager level
    ana: Person  # staff
    site: Site

    def drafts(self, source: uuid.UUID | None = None) -> str:
        return f"/v1/engagements/{source or self.site.engagement_id}/roll-forward/drafts"

    async def call(
        self, method: str, path: str, who: Person, body: Body | None = None, **headers: str
    ) -> httpx.Response:
        if headers:
            return await self.net.http.request(
                method, path, json=body, headers={**self.net.headers(who), **headers}
            )
        return await self.net.call(method, path, who, body=body)


async def _status(firm: Firm, status: str, engagement: uuid.UUID | None = None) -> None:
    await firm.net.seed.run_untriggered(
        "UPDATE engagements SET status = $2 WHERE id = $1",
        engagement or firm.site.engagement_id,
        status,
    )


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T55')",
        tenant,
        FLAG,
    )
    admin = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant)
    hannah = await seed.person(tenant)
    ana = await seed.person(tenant)
    for who, level in ((margaret, "partner"), (hannah, "manager"), (ana, "staff")):
        await seed.run(
            "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            who.user_id,
            level,
        )
    site = await seed.site(tenant, admin.user_id, "Northwind")
    await seed.run_untriggered(
        "UPDATE engagements SET name = $2, type = 'ebp_audit', status = 'delivered' WHERE id = $1",
        site.engagement_id,
        NAME,
    )
    for n, status in enumerate(STATUSES, start=2):  # the site's own item is the first
        await seed.item(site, f"PBC request {n}", status=status)
    await seed.member(site, margaret, "engagement_partner")
    await seed.member(site, hannah, "manager")
    await seed.member(site, ana, "staff")
    template = await seed.value(
        "INSERT INTO acceptance_questionnaire_templates (tenant_id, name, family, created_by) "
        "VALUES ($1, 'Audit & assurance v3', 'audit_assurance', $2) RETURNING id",
        tenant,
        admin.user_id,
    )
    await seed.run(
        "INSERT INTO acceptance_questionnaire_template_versions "
        "(tenant_id, template_id, version_no, sections, created_by) "
        "VALUES ($1, $2, 1, $3::jsonb, $4)",
        tenant,
        template,
        json.dumps([{"code": "continuance", "title": "Continuance"}]),
        admin.user_id,
    )
    return Firm(net, tenant, admin, margaret, hannah, ana, site)


async def _draft(firm: Firm, who: Person | None = None) -> Body:
    made = await firm.call("POST", firm.drafts(), who or firm.hannah)
    assert made.status_code == 201, made.text
    return cast(Body, made.json())


async def _create(firm: Firm, draft: Body, key: str = "roll-forward-1") -> httpx.Response:
    return await firm.call(
        "POST",
        f"{firm.drafts()}/{draft['id']}/create",
        firm.hannah,
        None,
        **{"Idempotency-Key": key},
    )


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_northwind_py2025_rolls_into_py2026_with_24_requests_as_draft(
    firm: Firm,
) -> None:
    draft = await _draft(firm)
    assert draft["source"]["status"] == "delivered"
    assert draft["name"] == "Northwind Robotics 401(k) Plan · PY2026"
    assert [draft["target_period_start"], draft["target_period_end"]] == [
        "2026-01-01",
        "2026-12-31",
    ]
    assert draft["catalogue"]["request_count"] == 24
    assert draft["catalogue"]["evidence_copied"] == 0
    assert draft["selections"] == {
        "team": True,
        "template": False,  # the source has no methodology pinned
        "request_list": True,
        "prior_year_notes": True,
    }
    assert {m["role"] for m in draft["team"]} == {"engagement_partner", "manager", "staff"}

    created = await _create(firm, draft)
    assert created.status_code == 201, created.text
    out = created.json()
    new_id = uuid.UUID(out["engagement_id"])
    assert out["engagement_status"] == "prospect"
    assert out["prior_engagement_id"] == str(firm.site.engagement_id)
    assert out["requests_created"] == 24
    assert sorted(out["independence_requested_user_ids"]) == sorted(
        str(p.user_id) for p in (firm.margaret, firm.hannah, firm.ana)
    )

    seed = firm.net.seed
    row = (
        await seed.rows(
            "SELECT status, prior_engagement_id, name, fiscal_period_start::text AS s, "
            "fiscal_period_end::text AS e, type FROM engagements WHERE id = $1",
            new_id,
        )
    )[0]
    assert (row["status"], row["prior_engagement_id"], row["type"]) == (
        "prospect",
        firm.site.engagement_id,
        "ebp_audit",
    )
    assert (row["s"], row["e"]) == ("2026-01-01", "2026-12-31")
    items = await seed.rows(
        "SELECT status, client_visible, client_assignee_user_id FROM request_items "
        "WHERE engagement_id = $1",
        new_id,
    )
    assert len(items) == 24
    assert {(r["status"], r["client_visible"]) for r in items} == {("draft", False)}
    assert {r["client_assignee_user_id"] for r in items} == {None}
    # No evidence copied: the new engagement starts with none; last year's is untouched.
    for engagement, count in ((new_id, 0), (firm.site.engagement_id, 1)):
        assert (
            await seed.value(
                "SELECT count(*) FROM evidence_items WHERE engagement_id = $1", engagement
            )
            == count
        )
        assert (
            await seed.value(
                "SELECT count(*) FROM evidence_versions WHERE engagement_id = $1", engagement
            )
            == count
        )
    # A continuance acceptance record (G1 again), nothing accepted.
    record = (
        await seed.rows(
            "SELECT kind, status, id FROM acceptance_records WHERE engagement_id = $1", new_id
        )
    )[0]
    assert (record["kind"], str(record["id"])) == ("continuance", out["acceptance_record_id"])
    assert record["status"] == "draft"
    assert (
        await seed.value(
            "SELECT count(*) FROM acceptance_decisions d JOIN acceptance_records r "
            "ON r.id = d.record_id WHERE r.engagement_id = $1",
            new_id,
        )
        == 0
    )
    # The team is on the new engagement; last year's is unchanged.
    members = await seed.rows(
        "SELECT user_id, role FROM engagement_members WHERE engagement_id = $1", new_id
    )
    assert {(r["user_id"], r["role"]) for r in members} == {
        (firm.margaret.user_id, "engagement_partner"),
        (firm.hannah.user_id, "manager"),
        (firm.ana.user_id, "staff"),
    }
    actions = await seed.rows(
        "SELECT action, actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'engagement.rolled_forward'",
        firm.tenant_id,
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in actions] == [
        ("human", str(firm.hannah.user_id))
    ]


async def test_ac_an_active_source_answers_409_and_writes_nothing(firm: Firm) -> None:
    await _status(firm, "active")
    refused = await firm.call("POST", firm.drafts(), firm.hannah)
    assert refused.status_code == 409, refused.text
    assert refused.json() == {
        "detail": "roll_forward_source_not_released",
        "facts": {"status": "active"},
    }
    assert (
        await firm.net.seed.value(
            "SELECT count(*) FROM roll_forward_drafts WHERE tenant_id = $1", firm.tenant_id
        )
        == 0
    )


async def test_a_source_made_active_after_the_draft_refuses_create(firm: Firm) -> None:
    draft = await _draft(firm)
    await _status(firm, "active")
    refused = await _create(firm, draft)
    assert refused.status_code == 409
    assert refused.json()["detail"] == "roll_forward_source_not_released"
    assert (
        await firm.net.seed.value(
            "SELECT count(*) FROM engagements WHERE prior_engagement_id = $1",
            firm.site.engagement_id,
        )
        == 0
    )


async def test_an_archived_source_rolls_forward_too(firm: Firm) -> None:
    await _status(firm, "archived")
    draft = await _draft(firm)
    assert draft["source"]["status"] == "archived"
    assert (await _create(firm, draft)).status_code == 201


# --- The draft -----------------------------------------------------------------------------------


async def test_skip_choices_save_on_the_version_seen_and_create_carries_only_them(
    firm: Firm,
) -> None:
    draft = await _draft(firm)
    path = f"{firm.drafts()}/{draft['id']}"
    saved = await firm.call(
        "PATCH",
        path,
        firm.hannah,
        {
            "seen_version": 1,
            "selections": {"request_list": False, "prior_year_notes": False},
            "team_user_ids": [str(firm.margaret.user_id), str(firm.hannah.user_id)],
            "name": "Northwind Robotics 401(k) Plan · PY2026 audit",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["version"] == 2
    assert body["selections"]["request_list"] is False
    assert [m["user_id"] for m in body["team"]] == [
        str(firm.margaret.user_id),
        str(firm.hannah.user_id),
    ]
    stale = await firm.call("PATCH", path, firm.hannah, {"seen_version": 1, "name": "Other"})
    assert stale.status_code == 409 and stale.json()["detail"] == "stale_version"
    created = await _create(firm, body)
    assert created.status_code == 201, created.text
    new_id = created.json()["engagement_id"]
    assert created.json()["requests_created"] == 0
    seed = firm.net.seed
    assert (
        await seed.value(
            "SELECT count(*) FROM request_items WHERE engagement_id = $1", uuid.UUID(new_id)
        )
        == 0
    )
    assert (
        await seed.value("SELECT name FROM engagements WHERE id = $1", uuid.UUID(new_id))
        == "Northwind Robotics 401(k) Plan · PY2026 audit"
    )


async def test_invalid_carry_choices_are_refused(firm: Firm) -> None:
    draft = await _draft(firm)
    path = f"{firm.drafts()}/{draft['id']}"
    stranger = await firm.net.seed.person(firm.tenant_id)
    for change, field in (
        ({"team_user_ids": [str(stranger.user_id)]}, "team"),
        ({"template_decision": "current"}, "template"),
        ({"target_period_end": "2025-06-30"}, "target_period_end"),
    ):
        refused = await firm.call("PATCH", path, firm.hannah, {"seen_version": 1, **change})
        assert refused.status_code == 422, (change, refused.text)
        assert refused.json() == {"detail": "roll_forward_invalid", "facts": {"field": field}}


async def test_create_answers_the_same_engagement_to_a_replay_and_to_a_second_key(
    firm: Firm,
) -> None:
    draft = await _draft(firm)
    first = await _create(firm, draft, "roll-forward-a")
    again = await _create(firm, draft, "roll-forward-a")
    other = await _create(firm, draft, "roll-forward-b")
    assert first.status_code == again.status_code == other.status_code == 201
    assert first.json()["engagement_id"] == again.json()["engagement_id"]
    assert other.json()["engagement_id"] == first.json()["engagement_id"]
    assert (
        await firm.net.seed.value(
            "SELECT count(*) FROM engagements WHERE prior_engagement_id = $1",
            firm.site.engagement_id,
        )
        == 1
    )
    assert (
        await firm.net.seed.value(
            "SELECT count(*) FROM request_items WHERE engagement_id = $1",
            uuid.UUID(first.json()["engagement_id"]),
        )
        == 24
    )


async def test_discard_sets_the_draft_aside(firm: Firm) -> None:
    draft = await _draft(firm)
    path = f"{firm.drafts()}/{draft['id']}"
    gone = await firm.call("DELETE", path, firm.hannah)
    assert gone.status_code == 200, gone.text
    assert (await firm.call("GET", path, firm.hannah)).status_code == 404
    assert (await _create(firm, draft)).status_code == 404


# --- Who -----------------------------------------------------------------------------------------


async def test_staff_and_another_persons_draft_are_refused(firm: Firm) -> None:
    staff = await firm.call("POST", firm.drafts(), firm.ana)
    assert staff.status_code == 403
    draft = await _draft(firm)
    theirs = await firm.call("GET", f"{firm.drafts()}/{draft['id']}", firm.margaret)
    assert theirs.status_code == 404  # a draft is its owner's only


async def test_a_walled_manager_gets_404_and_a_firm_admin_may_roll_forward(firm: Firm) -> None:
    await firm.net.wall(firm.admin, firm.hannah, firm.site)
    walled = await firm.call("POST", firm.drafts(), firm.hannah)
    assert walled.status_code == 404
    draft = await _draft(firm, firm.admin)
    # Hannah, walled now, is not available to carry.
    hannah = [m for m in draft["catalogue"]["team"] if m["user_id"] == str(firm.hannah.user_id)]
    assert [m["available"] for m in hannah] == [False]
    assert str(firm.hannah.user_id) not in [m["user_id"] for m in draft["team"]]


async def test_the_flag_off_answers_404(firm: Firm) -> None:
    await firm.net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        firm.tenant_id,
        FLAG,
    )
    forget_flags()
    assert (await firm.call("POST", firm.drafts(), firm.hannah)).status_code == 404


async def test_next_year_and_name() -> None:
    assert next_year(date(2024, 2, 29)) == date(2025, 2, 28)
    assert next_name(NAME, date(2025, 12, 31), date(2026, 12, 31)) == (
        "Northwind Robotics 401(k) Plan · PY2026"
    )
    assert next_name("FY20251 file", date(2025, 6, 30), date(2026, 6, 30)) == "FY20251 file"
