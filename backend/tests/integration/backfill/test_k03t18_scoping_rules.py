# ac-test-author: ayushkbhatia
"""K-03-T18 (TASK-9011; K-03 §3.3; SHT-03 a, b, e; DEC-6017) on the migrated Postgres. Row
acceptance: "Goldens give Harlow & Pike 'Shows 3 steps · 2 sheets · hides 1 · adds 6 requests',
Granite Peak 'Shows 1 step · hides 0', rules 2 and 7 answer 422 naming both rules, and no model is
called."

Margaret (the quality partner) saves FS v6's six rules on the draft, previews them as Harlow &
Pike (a group audit with a component auditor and no inventory answer yet) and as Granite Peak (a
single entity whose inventory is a significant risk), is refused a seventh rule that hides
BH-FS-720 while rule 2 shows it, and reads Harlow & Pike's own evaluation through its template
link. The model gateway is replaced by one that fails the test if anything reaches it."""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest

import abacus.ai_gateway as gateway

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

GROUP = "engagement.profile.group_audit"
FIRST_YEAR = "engagement.profile.first_year"
PERFORMED = "group_scoping.components.performed_by"
INVENTORY = "risk_register.inventory.significant"


def _code(response: httpx.Response) -> str:
    return str(response.json().get("code") or response.json().get("detail"))


def _rule(
    n: int, when: list[dict[str, str]], then: str, target: str, kind: str | None = "step"
) -> dict[str, object]:
    return {
        "rule_id": str(uuid.UUID(int=n)),
        "position": n,
        "when": when,
        "then": then,
        "targets": [target],
        "target_kind": None if then == "add_requests" else kind,
    }


GROUP_YES = {"source": GROUP, "operator": "is", "value": "yes"}
FS_V6: list[dict[str, object]] = [
    _rule(1, [GROUP_YES], "show", "BH-FS-700"),
    _rule(2, [GROUP_YES], "show", "BH-FS-720"),
    {
        **_rule(3, [GROUP_YES, {"source": PERFORMED, "operator": "includes",
                                "value": "component_auditor"}], "show", "BH-FS-710"),
        "group_op": "and",
    },
    _rule(4, [GROUP_YES], "add_requests", "group_requests"),
    _rule(5, [GROUP_YES], "hide", "materiality_form.single_entity_benchmark", "section"),
    _rule(6, [{"source": INVENTORY, "operator": "is", "value": "yes"}], "show", "BH-FS-345"),
]  # fmt: skip


async def _audit(seed: Seeder, site: Site, *, group: bool) -> uuid.UUID:
    """The site's assurance work item, marked a group audit or not."""
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            site.engagement_id,
        ),
    )
    await seed.run_untriggered(
        "INSERT INTO assurance_work_items (work_item_id, tenant_id, engagement_id, "
        "assurance_type, is_group_audit) VALUES ($1, $2, $3, 'fs_audit', $4) "
        "ON CONFLICT (work_item_id) DO UPDATE SET is_group_audit = EXCLUDED.is_group_audit",
        item,
        site.tenant_id,
        site.engagement_id,
        group,
    )
    return item


async def _draft(net: Net, seed: Seeder, tenant: uuid.UUID, owner: Person) -> uuid.UUID:
    methodology = uuid.uuid4()
    await seed.run(
        "INSERT INTO methodology_templates (id, tenant_id, name, created_by, engagement_types, "
        "family) VALUES ($1, $2, 'BH Audit Methodology · FS', $3, '{fs_audit}', 'fs')",
        methodology,
        tenant,
        owner.user_id,
    )
    template = await seed.value(
        "INSERT INTO engagement_templates (tenant_id, methodology_template_id, name, family, "
        "owner_user_id) VALUES ($1, $2, 'FS audit', 'fs', $3) RETURNING id",
        tenant,
        methodology,
        owner.user_id,
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
        "UPDATE template_versions SET status = 'published', effective_from = DATE '2026-10-01', "
        "fingerprint = $2, published_by = $3, published_at = now() WHERE id = $1",
        published,
        "c" * 64,
        owner.user_id,
    )
    made = await net.call(
        "POST",
        f"/v1/engagement-templates/{template}/versions",
        owner,
        body={"from_version_id": str(published)},
        headers=net.keyed(),
    )
    assert made.status_code == 201, made.text
    draft = uuid.UUID(made.json()["version_id"])
    for position, (sheet, step) in enumerate(
        (("group_scoping", "BH-FS-700"), ("component_tracker", "BH-FS-710")), start=1
    ):
        await seed.run(
            "INSERT INTO template_sheet_definitions (tenant_id, template_version_id, sheet_key, "
            "title, step_key, row_source, position) VALUES ($1, $2, $3, $3, $4, 'manual', $5)",
            tenant,
            draft,
            sheet,
            step,
            position,
        )
    for n in range(1, 8):  # six group requests and one every engagement gets
        await seed.run(
            "INSERT INTO template_requests (tenant_id, template_version_id, request_key, "
            "group_key, title, position) VALUES ($1, $2, $3, $4, $5, $6)",
            tenant,
            draft,
            f"GR-{n}",
            "group_requests" if n <= 6 else None,
            f"Request {n}",
            n,
        )
    return draft


async def test_k03t18_acceptance_goldens_conflict_and_no_model(
    net: Net, seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def refuse(*_: object, **__: object) -> None:
        raise AssertionError("a scoping rule reached the model gateway")

    monkeypatch.setattr(gateway, "call", refuse)
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'templates_v2.enabled', 'true', 'test-seed', 'K-03-T18')",
        tenant,
    )
    owner = await seed.person(tenant, "quality_partner")
    harlow = await seed.site(tenant, owner.user_id, "Harlow & Pike")
    granite = await seed.site(tenant, owner.user_id, "Granite Peak")
    for site in (harlow, granite):
        await seed.member(site, owner, "engagement_partner")
        await seed.attest(tenant, site.engagement_id)
    h_item = await _audit(seed, harlow, group=True)
    await seed.run_untriggered(
        "INSERT INTO components (tenant_id, engagement_id, work_item_id, consolidation_entity_id, "
        "planned_work, performed_by, component_auditor_id, created_by) VALUES "
        "($1, $2, $3, $4, 'full_scope', 'component_auditor', $5, $6), "
        "($1, $2, $3, $7, 'full_scope', 'group_team', NULL, $6)",
        tenant,
        harlow.engagement_id,
        h_item,
        uuid.uuid4(),
        uuid.uuid4(),
        owner.user_id,
        uuid.uuid4(),
    )
    g_item = await _audit(seed, granite, group=False)
    await seed.run_untriggered(
        "INSERT INTO risk_register_rows (tenant_id, engagement_id, work_item_id, code, level, "
        "area_key, area_label, assertions, inherent_risk, control_risk, rmm, significance, "
        "content_hash) VALUES ($1, $2, $3, 'R4', 'assertion', 'inventory', 'Inventory', "
        "'{valuation}', 'high', 'max', 'high', 'approved', $4)",
        tenant,
        granite.engagement_id,
        g_item,
        "b" * 64,
    )
    draft = await _draft(net, seed, tenant, owner)
    base = f"/v1/template-versions/{draft}"

    sources = await net.call("GET", f"{base}/scoping-sources", owner)
    assert sources.status_code == 200, sources.text
    labels = {s["key"]: s["label"] for s in sources.json()["items"]}
    sep = " \u203a "
    assert labels[GROUP] == sep.join(("Engagement", "Profile", "Group audit (SAS 149)"))
    assert labels[INVENTORY] == sep.join(("Scoping", "Audit areas", "Inventory · Significant"))

    etag = (await net.call("GET", f"{base}/scoping-rules", owner)).json()["etag"]
    saved = await net.call(
        "PUT",
        f"{base}/scoping-rules",
        owner,
        body={"items": FS_V6},
        headers={"If-Match": f'"{etag}"'} | net.keyed(),
    )
    assert saved.status_code == 200, saved.text
    assert [r["position"] for r in saved.json()["items"]] == [1, 2, 3, 4, 5, 6]
    assert saved.json()["items"][3]["then"] == "add_requests"
    etag = saved.json()["etag"]
    version = (await net.call("GET", base, owner)).json()
    assert (version["rail"]["requests"], version["rail"]["requests_by_rule"]) == (7, 6)
    assert version["rail"]["scoping_rules"] == 6

    async def preview(site: Site | None) -> dict[str, object]:
        body = {"blank": True} if site is None else {"engagement_id": str(site.engagement_id)}
        got = await net.call("POST", f"{base}/scoping-rules/preview", owner, body=body)
        assert got.status_code == 200, got.text
        return cast(dict[str, object], got.json())

    def results(found: dict[str, object]) -> list[str]:
        return [str(r["result"]) for r in cast(list[dict[str, object]], found["rows"])]

    as_harlow = await preview(harlow)
    assert as_harlow["summary"] == "Shows 3 steps · 2 sheets · hides 1 · adds 6 requests"
    assert results(as_harlow) == ["shows", "shows", "shows", "shows", "hides", "no_answer"]
    as_granite = await preview(granite)
    assert as_granite["summary"] == "Shows 1 step · hides 0"
    assert results(as_granite) == ["no_change"] * 5 + ["shows"]
    assert results(await preview(None)) == ["no_answer"] * 6

    rule7 = _rule(7, [{"source": FIRST_YEAR, "operator": "is", "value": "yes"}], "hide",
                  "BH-FS-720")  # fmt: skip
    conflict = await net.call(
        "PUT",
        f"{base}/scoping-rules",
        owner,
        body={"items": [*FS_V6, rule7]},
        headers={"If-Match": f'"{etag}"'} | net.keyed(),
    )
    assert conflict.status_code == 422, conflict.text
    assert _code(conflict) == "rule_conflict"
    facts = conflict.json()["facts"]
    assert (facts["first"], facts["second"], facts["target"]) == (2, 7, "BH-FS-720")

    unknown = _rule(7, [{"source": "planning.nothing", "operator": "is", "value": "x"}], "show",
                    "BH-FS-999")  # fmt: skip
    refused = await net.call(
        "PUT",
        f"{base}/scoping-rules",
        owner,
        body={"items": [*FS_V6, unknown]},
        headers={"If-Match": f'"{etag}"'} | net.keyed(),
    )
    assert refused.status_code == 422 and _code(refused) == "unknown_source", refused.text
    events = await seed.rows(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'scoping_rule.edited'",
        tenant,
    )
    assert [str(e["actor_id"]) for e in events] == [str(owner.user_id)]  # refusals wrote none

    await seed.run(
        "INSERT INTO engagement_template_links (tenant_id, engagement_id, template_id, "
        "template_version_id) SELECT $1, $2, template_id, id FROM template_versions WHERE id = $3",
        tenant,
        harlow.engagement_id,
        draft,
    )
    own = await net.call("GET", f"/v1/engagements/{harlow.engagement_id}/scoping", owner)
    assert own.status_code == 200, own.text
    assert [(i["position"], i["result"]) for i in own.json()["items"]] == [
        (1, "shows"), (2, "shows"), (3, "shows"), (4, "shows"), (5, "hides"), (6, "no_answer"),
    ]  # fmt: skip

    outsider = await seed.person(tenant)
    walled = await net.call(
        "POST",
        f"{base}/scoping-rules/preview",
        outsider,
        body={"engagement_id": str(harlow.engagement_id)},
    )
    assert walled.status_code in (403, 404), walled.text
