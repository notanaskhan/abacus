# ac-test-author: ayushkbhatia
"""P-06-T17: independent AC tests (ADR-078) for P-06-T05, T06, T07, T10 and T11 (C5 binders and
requests, SPEC-319).

The rows promise: publishing a non-intake binder before G3 answers 409 `binder_gate_unmet` and
nothing leaves (T07); publish and send are idempotent on their `Idempotency-Key`, so a retry
returns the stored response and holds one effect (T06); every binder transition the contract
lists, and the refusals between them (T07); a request is sent only with a due date, an unchanged
model-drafted wording answers 409 `model_text_not_permitted` while the firm's P-25 setting is off
and sends nothing (T10, DV-11), and a request that was ever sent is never deleted (T05, T10);
DEC-38's publish and send cells (partner and manager; senior only by firm setting; staff send but
do not publish; the agent never); walls answer 404 on binder, publish and send and leave walled
binders out of the index's rows, tiles and totals with no hidden count (T11, INV-3, DEC-43); and
the client preview never shows a draft (INV-4). The Undo of publish and send (a voided grant
sends nothing) is in the shared C3 suite, `tests/contracts/undo/`, where T17 registers both.

Boundary: `create_app()` over HTTP on the migrated Postgres (`net`, `seed` from this directory);
business time frozen on a synthetic firm. Expectations: `docs/contracts/c5-requests-binders.md`
§2, §6, §7; DEC-38, DEC-43, DEC-136; P-06 rows T05 to T11.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast

import asyncpg
import httpx
import pytest

from abacus.kernel.clock import frozen

from .support import Net, Person, Role, Seeder, Site

T0: Final = datetime.fromisoformat("2026-09-14T09:42:00-05:00")
Json = dict[str, object]


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    partner: Person
    manager: Person
    senior: Person
    staff: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def call(
        self,
        who: Person,
        method: str,
        path: str,
        body: Json | None = None,
        *,
        key: str | None = None,
        at: datetime = T0,
    ) -> httpx.Response:
        headers = {**self.net.headers(who), "Idempotency-Key": key or uuid.uuid4().hex}
        with frozen(at):
            return await self.net.http.request(method, path, json=body, headers=headers)

    async def binder(self, kind: str = "pbc", who: Person | None = None) -> uuid.UUID:
        work_item = await self.seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1", self.site.engagement_id
        )
        response = await self.call(
            who or self.manager,
            "POST",
            "/v1/binders",
            {"work_item_id": str(work_item), "kind": kind, "name": "2025 Binder"},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["id"])

    async def request(
        self,
        binder: uuid.UUID,
        *,
        due: bool = True,
        wording: str = "Brokerage statements",
        visible: bool = False,
    ) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by, client_visible, due_on) "
                "VALUES ($1, $2, $3, $4, 'Income', $5, $7, $6) RETURNING id",
                self.tenant_id,
                self.site.engagement_id,
                binder,
                wording,
                self.manager.user_id,
                datetime(2026, 10, 1).date() if due else None,
                visible,
            ),
        )

    def item_path(self, item: uuid.UUID) -> str:
        return f"/v1/engagements/{self.site.engagement_id}/request-items/{item}"

    async def audits(self, action: str, target: uuid.UUID) -> int:
        return int(
            cast(
                int,
                await self.seed.value(
                    "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = $2 "
                    "AND target_id = $3",
                    self.tenant_id,
                    action,
                    str(target),
                ),
            )
        )

    async def held(self, event_type: str) -> int:
        return int(
            cast(
                int,
                await self.seed.value(
                    "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = $2",
                    self.tenant_id,
                    event_type,
                ),
            )
        )

    async def binder_status(self, binder: uuid.UUID) -> str:
        return str(await self.seed.value("SELECT status FROM request_lists WHERE id = $1", binder))

    async def item_status(self, item: uuid.UUID) -> str:
        return str(await self.seed.value("SELECT status FROM request_items WHERE id = $1", item))


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant_id)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'binders.engine', 'true', 'test-seed', 'P-06-T17')",
        tenant_id,
    )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Feld")
    team: dict[str, Person] = {}
    for role in ("engagement_partner", "manager", "senior", "staff"):
        team[role] = await seed.person(tenant_id)
        await seed.member(site, team[role], cast(Role, role))
    return Firm(
        net,
        tenant_id,
        admin,
        team["engagement_partner"],
        team["manager"],
        team["senior"],
        team["staff"],
        site,
    )


# --- T07: G3 and the binder's transitions --------------------------------------------------------


async def test_t07_a_pbc_binder_publishes_only_after_g3_and_nothing_leaves(firm: Firm) -> None:
    """The firm requires a letter and none is recorded, so G3 is unmet. (DEC-39 (b) makes G3
    strict whatever the firm's letter policy; that gap is ED-010, held in
    `test_acceptance_independence_letter.py`.)"""
    await firm.seed.run(
        "UPDATE firms SET require_letter = true WHERE tenant_id = $1", firm.tenant_id
    )
    binder = await firm.binder("pbc")
    await firm.request(binder, visible=True)
    response = await firm.call(firm.manager, "POST", f"/v1/binders/{binder}/publish")
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "binder_gate_unmet", "facts": {"gate": "G3"}}
    assert await firm.binder_status(binder) == "draft"
    assert await firm.audits("binder.published", binder) == 0
    assert await firm.held("binder.published") == 0


async def test_t07_an_intake_binder_publishes_before_g3(firm: Firm) -> None:
    binder = await firm.binder("intake")
    item = await firm.request(binder, visible=True)  # publish sends the client-visible requests
    response = await firm.call(firm.manager, "POST", f"/v1/binders/{binder}/publish")
    assert response.status_code == 200, response.text
    assert await firm.binder_status(binder) == "published"
    assert await firm.item_status(item) == "requested"
    assert await firm.audits("binder.published", binder) == 1


async def test_t07_every_binder_transition_and_its_refusals(firm: Firm) -> None:
    binder = await firm.binder("intake")
    await firm.request(binder)
    publish = f"/v1/binders/{binder}/publish"
    assert (await firm.call(firm.manager, "POST", publish)).status_code == 200
    again = await firm.call(firm.manager, "POST", publish)  # already published
    assert again.status_code == 409 and again.json()["detail"] == "binder_not_draft"
    no_reason = await firm.call(firm.manager, "POST", f"/v1/binders/{binder}/unpublish", {})
    assert no_reason.status_code == 422
    blank = await firm.call(
        firm.manager, "POST", f"/v1/binders/{binder}/unpublish", {"reason": " "}
    )
    assert blank.status_code == 422
    assert await firm.binder_status(binder) == "published"
    unpublished = await firm.call(
        firm.manager,
        "POST",
        f"/v1/binders/{binder}/unpublish",
        {"reason": "Wrong recipients"},
        at=T0.replace(minute=50),
    )
    assert unpublished.status_code == 200, unpublished.text
    assert await firm.binder_status(binder) == "unpublished"
    assert await firm.audits("binder.unpublished", binder) == 1
    twice = await firm.call(
        firm.manager,
        "POST",
        f"/v1/binders/{binder}/unpublish",
        {"reason": "Again"},
        at=T0.replace(minute=51),
    )
    assert twice.status_code == 409 and twice.json()["detail"] == "binder_not_published"
    republished = await firm.call(firm.manager, "POST", publish, at=T0.replace(minute=55))
    assert republished.status_code == 200, republished.text
    assert await firm.binder_status(binder) == "published"


async def test_t06_a_retried_publish_returns_the_stored_response_and_holds_one_effect(
    firm: Firm,
) -> None:
    binder = await firm.binder("intake")
    await firm.request(binder)
    key = uuid.uuid4().hex
    first = await firm.call(firm.manager, "POST", f"/v1/binders/{binder}/publish", key=key)
    retry = await firm.call(
        firm.manager, "POST", f"/v1/binders/{binder}/publish", key=key, at=T0.replace(second=3)
    )
    assert first.status_code == 200, first.text
    assert (retry.status_code, retry.json()) == (first.status_code, first.json())
    assert await firm.audits("binder.published", binder) == 1
    assert await firm.held("binder.published") == 1


# --- T10: send, model text, delete ---------------------------------------------------------------


async def test_t10_send_needs_a_due_date(firm: Firm) -> None:
    binder = await firm.binder("intake")
    item = await firm.request(binder, due=False)
    response = await firm.call(firm.manager, "POST", f"{firm.item_path(item)}/send")
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "due_date_required"
    assert await firm.item_status(item) == "draft"
    assert await firm.held("request_item.sent") == 0


async def test_t10_unchanged_model_wording_is_refused_and_sends_nothing(firm: Firm) -> None:
    """DV-11: while the firm's P-25 setting is off, a request the agent drafted is sent only once a
    person has changed its wording."""
    binder = await firm.binder("intake")
    wording = "Please upload the 2025 brokerage statements"
    item = await firm.request(binder, wording=wording)
    await firm.seed.run(
        "UPDATE request_items SET drafted_by_run_id = $2, drafted_wording_source = 'model', "
        "drafted_wording_fingerprint = $3 WHERE id = $1",
        item,
        uuid.uuid4(),
        hashlib.sha256(wording.encode()).hexdigest(),
    )
    refused = await firm.call(firm.manager, "POST", f"{firm.item_path(item)}/send")
    assert refused.status_code == 409, refused.text
    assert refused.json() == {"detail": "model_text_not_permitted"}
    assert await firm.item_status(item) == "draft"
    assert await firm.held("request_item.sent") == 0
    assert await firm.audits("request_item.sent", item) == 0
    edited = await firm.call(
        firm.manager,
        "PATCH",
        firm.item_path(item),
        {"description": "Upload your 2025 brokerage statements for every account"},
    )
    assert edited.status_code == 200, edited.text
    sent = await firm.call(firm.manager, "POST", f"{firm.item_path(item)}/send")
    assert sent.status_code == 200, sent.text
    assert await firm.item_status(item) == "requested"


async def test_t06_a_retried_send_holds_one_email(firm: Firm) -> None:
    binder = await firm.binder("intake")
    item = await firm.request(binder)
    key = uuid.uuid4().hex
    first = await firm.call(firm.staff, "POST", f"{firm.item_path(item)}/send", key=key)
    retry = await firm.call(
        firm.staff, "POST", f"{firm.item_path(item)}/send", key=key, at=T0.replace(second=2)
    )
    assert first.status_code == 200, first.text
    assert (retry.status_code, retry.json()) == (first.status_code, first.json())
    assert await firm.held("request_item.sent") == 1
    assert await firm.audits("request_item.sent", item) == 1


async def test_t05_t10_only_a_never_sent_draft_is_deleted(firm: Firm) -> None:
    binder = await firm.binder("intake")
    draft, sent = await firm.request(binder), await firm.request(binder)
    assert (
        await firm.call(firm.manager, "POST", f"{firm.item_path(sent)}/send")
    ).status_code == 200
    refused = await firm.call(
        firm.manager, "DELETE", firm.item_path(sent), at=T0.replace(minute=50)
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "request_already_sent"
    deleted = await firm.call(firm.manager, "DELETE", firm.item_path(draft))
    assert deleted.status_code in (200, 204), deleted.text
    # T05: the database refuses soft-deleting a request that was ever sent, whoever asks.
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.run("UPDATE request_items SET deleted_at = now() WHERE id = $1", sent)


# --- DEC-38: who may publish and send ------------------------------------------------------------


async def test_dec38_senior_publishes_only_by_firm_setting_and_staff_never(firm: Firm) -> None:
    binder = await firm.binder("intake")
    await firm.request(binder)
    for who in (firm.senior, firm.staff):
        response = await firm.call(who, "POST", f"/v1/binders/{binder}/publish")
        assert response.status_code == 403, response.text
    assert await firm.binder_status(binder) == "draft"
    created = await firm.call(
        firm.staff,
        "POST",
        "/v1/binders",
        {
            "work_item_id": str(
                await firm.seed.value(
                    "SELECT id FROM work_items WHERE engagement_id = $1", firm.site.engagement_id
                )
            ),
            "kind": "pbc",
        },
    )
    assert created.status_code == 403  # create is partner and manager (senior by setting)
    partner = await firm.call(firm.partner, "POST", f"/v1/binders/{binder}/publish")
    assert partner.status_code == 200, partner.text


async def test_dec38_staff_and_above_send_inside_a_binder(firm: Firm) -> None:
    binder = await firm.binder("intake")
    for who in (firm.partner, firm.manager, firm.senior, firm.staff):
        item = await firm.request(binder)
        response = await firm.call(who, "POST", f"{firm.item_path(item)}/send")
        assert response.status_code == 200, (who, response.text)
    outsider = await firm.seed.person(firm.tenant_id)  # a member of the firm, not of the team
    item = await firm.request(binder)
    response = await firm.call(outsider, "POST", f"{firm.item_path(item)}/send")
    assert response.status_code in (403, 404)
    assert await firm.item_status(item) == "draft"


# --- INV-3 walls and T11's index; INV-4 drafts ---------------------------------------------------


async def test_inv3_a_walled_member_gets_404_on_binder_publish_and_send(firm: Firm) -> None:
    binder = await firm.binder("intake")
    item = await firm.request(binder)
    await firm.net.wall(firm.admin, firm.manager, firm.site)
    for method, path in (
        ("GET", f"/v1/binders/{binder}"),
        ("GET", f"/v1/binders/{binder}/requests"),
        ("POST", f"/v1/binders/{binder}/publish"),
        ("POST", f"{firm.item_path(item)}/send"),
    ):
        response = await firm.call(firm.manager, method, path)
        assert response.status_code == 404, (path, response.text)
        assert response.json() == {"detail": "not found"}
    assert await firm.binder_status(binder) == "draft"
    assert await firm.item_status(item) == "draft"


async def test_t11_the_index_leaves_walled_binders_out_of_rows_tiles_and_totals(
    firm: Firm,
) -> None:
    walled = await firm.binder("intake")
    other_site = await firm.seed.site(firm.tenant_id, firm.admin.user_id, "Granite")
    await firm.seed.member(other_site, firm.manager, "manager")
    work_item = await firm.seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1", other_site.engagement_id
    )
    created = await firm.call(
        firm.manager,
        "POST",
        "/v1/binders",
        {"work_item_id": str(work_item), "kind": "pbc", "name": "Granite 2025"},
    )
    assert created.status_code == 201, created.text
    visible = created.json()["id"]
    before = await firm.call(firm.manager, "GET", "/v1/binders")
    assert before.status_code == 200, before.text
    assert {str(walled), visible} <= {str(i["id"]) for i in before.json()["items"]}
    await firm.net.wall(firm.admin, firm.manager, firm.site)
    after = await firm.call(firm.manager, "GET", "/v1/binders")
    assert after.status_code == 200, after.text
    body = cast(Json, after.json())
    rows = cast(list[Json], body["items"])
    behind = {
        str(r["id"])
        for r in await firm.seed.rows(
            "SELECT id FROM request_lists WHERE engagement_id = $1", firm.site.engagement_id
        )
    }
    assert str(walled) in behind
    assert visible in {str(r["id"]) for r in rows}
    assert not behind & {str(r["id"]) for r in rows}
    assert not any(b in after.text for b in behind) and firm.site.marker not in after.text
    assert body.get("total") == len(rows)
    counts = body.get("counts")
    if isinstance(counts, dict):
        assert sum(v for v in cast(Json, counts).values() if isinstance(v, int)) <= len(rows)
    assert "hidden" not in after.text.lower()


async def test_inv4_the_client_preview_never_shows_a_draft(firm: Firm) -> None:
    binder = await firm.binder("intake")
    sent = await firm.request(binder, wording="Brokerage statements, sent")
    assert (
        await firm.call(firm.manager, "POST", f"{firm.item_path(sent)}/send")
    ).status_code == 200
    draft = await firm.request(binder, wording="Draft wording nobody outside may see")
    preview = await firm.call(
        firm.manager, "GET", f"/v1/binders/{binder}/client-preview", at=T0.replace(minute=50)
    )
    assert preview.status_code == 200, preview.text
    assert str(draft) not in preview.text
    assert "Draft wording nobody outside may see" not in preview.text
    assert str(sent) in preview.text
