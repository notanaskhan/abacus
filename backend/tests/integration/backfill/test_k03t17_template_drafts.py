# ac-test-author: ayushkbhatia
"""K-03-T17 (TASK-9010; K-03 F2; KNW-06 a, b; DEC-6016) on the migrated Postgres. Row acceptance:
"PUT with a stale ETag answers 412, a second draft answers 409 draft_exists, a published version
answers 409 not_draft, and every save writes one audit event attributed to the QM owner."

Brightwater Hale's FS template has a published "FS v5" with one sheet. The quality partner (the
template's owner) starts "FS v6" from it: the sheet is copied, a save at ETag 0 lands and moves
the ETag to 1, a second save at 0 answers 412, a second draft answers 409 `draft_exists`, and a
save on the published v5 answers 409 `not_draft`. Each landed save is one audit event, the
quality partner's."""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest

from abacus.kernel.errors import DomainPreconditionFailed
from abacus.modules.methodology import template_drafts as td

from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

_SHEET: dict[str, object] = {
    "sheet_key": "lead_cash",
    "title": "Cash lead sheet",
    "step_key": None,
    "row_source": "manual",
    "sections": [],
    "position": 1,
}


async def _fs_template(seed: Seeder) -> tuple[uuid.UUID, Person, uuid.UUID, uuid.UUID]:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'templates_v2.enabled', 'true', 'test-seed', 'K-03-T17')",
        tenant,
    )
    owner = await seed.person(tenant, "quality_partner")
    methodology = uuid.uuid4()
    await seed.run(
        "INSERT INTO methodology_templates (id, tenant_id, name, created_by, engagement_types, "
        "family) VALUES ($1, $2, 'BH Audit Methodology · FS', $3, '{fs_audit}', 'fs')",
        methodology,
        tenant,
        owner.user_id,
    )
    template = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO engagement_templates (tenant_id, methodology_template_id, name, family, "
            "owner_user_id) VALUES ($1, $2, 'FS audit', 'fs', $3) RETURNING id",
            tenant,
            methodology,
            owner.user_id,
        ),
    )
    published = uuid.uuid4()
    await seed.run(
        "INSERT INTO template_versions (id, tenant_id, template_id, seq, label, created_by) "
        "VALUES ($1, $2, $3, 5, 'FS v5', $4)",
        published,
        tenant,
        template,
        owner.user_id,
    )
    await seed.run(
        "INSERT INTO template_sheet_definitions (tenant_id, template_version_id, sheet_key, "
        "title, row_source, sections, position) VALUES ($1, $2, 'lead_cash', 'Cash lead sheet', "
        "'manual', '[]'::jsonb, 1)",
        tenant,
        published,
    )
    await seed.run(
        "UPDATE template_versions SET status = 'published', effective_from = DATE '2026-10-01', "
        "fingerprint = $2, published_by = $3, published_at = now() WHERE id = $1",
        published,
        "c" * 64,
        owner.user_id,
    )
    return tenant, owner, template, published


def _code(response: httpx.Response) -> str:
    return str(response.json().get("code") or response.json().get("detail"))


async def _saves(seed: Seeder, tenant: uuid.UUID) -> list[tuple[str, str]]:
    rows = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'template_version.component_changed' ORDER BY occurred_at, id",
        tenant,
    )
    return [(str(r["actor_kind"]), str(r["actor_id"])) for r in rows]


async def test_k03t17_acceptance_etag_drafts_and_one_audit_event_per_save(
    net: Net, seed: Seeder
) -> None:
    tenant, owner, template, published = await _fs_template(seed)

    made = await net.call(
        "POST",
        f"/v1/engagement-templates/{template}/versions",
        owner,
        body={"from_version_id": str(published)},
        headers=net.keyed(),
    )
    assert made.status_code == 201, made.text
    draft = made.json()
    assert (draft["status"], draft["label"], draft["draft_etag"]) == ("draft", "FS v6", 0)
    assert draft["based_on_version_id"] == str(published)
    assert draft["rail"]["sheets"] == 1  # the base's components were copied
    version = draft["version_id"]

    second = await net.call(
        "POST",
        f"/v1/engagement-templates/{template}/versions",
        owner,
        body={"from_version_id": str(published)},
        headers=net.keyed(),
    )
    assert second.status_code == 409, second.text
    assert _code(second) == "draft_exists"

    read = await net.call("GET", f"/v1/template-versions/{version}/components/sheets", owner)
    assert read.status_code == 200, read.text
    assert read.json()["etag"] == 0
    rows = cast(list[dict[str, object]], read.json()["body"]["rows"])
    assert [r["sheet_key"] for r in rows] == ["lead_cash"]

    renamed = {**_SHEET, "title": "Cash and equivalents lead"}
    saved = await net.call(
        "PUT",
        f"/v1/template-versions/{version}/components/sheets",
        owner,
        body={"body": {"rows": [renamed, {**_SHEET, "sheet_key": "lead_ar", "position": 2}]}},
        headers={"If-Match": '"0"'} | net.keyed(),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["etag"] == 1
    titles = [r["title"] for r in saved.json()["body"]["rows"]]
    assert titles == ["Cash and equivalents lead", "Cash lead sheet"]
    assert await _saves(seed, tenant) == [("human", str(owner.user_id))]

    stale = await net.call(
        "PUT",
        f"/v1/template-versions/{version}/components/sheets",
        owner,
        body={"body": {"rows": [_SHEET]}},
        headers={"If-Match": '"0"'} | net.keyed(),
    )
    assert stale.status_code == 412, stale.text
    assert _code(stale) == "precondition_failed"

    frozen = await net.call(
        "PUT",
        f"/v1/template-versions/{published}/components/sheets",
        owner,
        body={"body": {"rows": [_SHEET]}},
        headers={"If-Match": '"0"'} | net.keyed(),
    )
    assert frozen.status_code == 409, frozen.text
    assert _code(frozen) == "not_draft"

    again = await net.call(
        "PUT",
        f"/v1/template-versions/{version}/components/sheets",
        owner,
        body={"body": {"rows": [_SHEET]}},
        headers={"If-Match": '"1"'} | net.keyed(),
    )
    assert again.status_code == 200, again.text
    assert again.json()["etag"] == 2
    # Two landed saves, two events, both the quality partner's; the refused ones wrote none.
    assert await _saves(seed, tenant) == [("human", str(owner.user_id))] * 2
    count = await seed.value(
        "SELECT count(*) FROM template_sheet_definitions WHERE template_version_id = $1",
        published,
    )
    assert count == 1  # the published base is untouched

    staff = await seed.person(tenant)
    refused = await net.call(
        "PUT",
        f"/v1/template-versions/{version}/components/sheets",
        staff,
        body={"body": {"rows": [_SHEET]}},
        headers={"If-Match": '"2"'} | net.keyed(),
    )
    assert refused.status_code in (403, 404), refused.text


def test_k03t17_labels_and_etags_are_codes() -> None:
    assert td.next_label("FS v5", 6) == "FS v6"
    assert td.etag_of('W/"7"') == 7
    assert td.etag_of("3") == 3
    with pytest.raises(DomainPreconditionFailed):
        td.etag_of('"abc"')
