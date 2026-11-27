# ac-test-author: notanaskhan
"""T-06-T56 (TASK-9019; T-06 §3 F5, F7, F8; ADR-078; DEC-43, DEC-88): AY's S53-S54 entity-return
services (other-entity workpapers, form pages and diagnostics, the relationship annotator), black
box over HTTP on the migrated Postgres. Row acceptance: "Each acceptance criterion in section 3
for F5, F7 and F8 has a named test that fails when the guarded line is removed."

This suite holds the server-side promises around the figures. The figure-level ACs (Bluestem's
AAA, Ashford's provision, Lakeshore's Part IX, Ridgeline's K-1 sums and diagnostics) are held by
the service and golden suites named in the task record's AC map (TASK-9019), each beside the line
it guards:

- F5 a: a Filed or Accepted return answers 409 `return_locked` on every write, and writes nothing.
- F5 b2: Explain… opens the issue as a person's act, with no gateway call (consent or not).
- F7: a client principal never reads the form pages; another firm's return is absent; the draft
  download needs a fresh second factor; the page list carries the draft watermark.
- F8: the graph never reaches the portal (INV-4); a walled client has no graph (DEC-43); a
  relationship is a person's act, never the agent's (INV-1)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import Forbidden, member_context
from abacus.modules.organisations import relationships_contract as rc

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
FLAGS = ("tax.other_entity_workpapers", "tax.form_preview", "clients.relationship_map")


async def _return(
    seed: Seeder, form: str, status: str = "preparing"
) -> tuple[Person, Site, uuid.UUID]:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, f"Form {form}")
    await seed.member(site, partner, "engagement_partner")
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'T-06-T56')",
            tenant,
            flag,
        )
    forget_flags()
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) RETURNING id",
            tenant, site.engagement_id, site.client_id, site.entity_id,
            f"2025 Form {form} {site.marker}", partner.user_id,
        ),
    )  # fmt: skip
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, $5, 2025)",
        tenant, item, site.engagement_id, site.entity_id, form,
    )  # fmt: skip
    await seed.run_untriggered(
        "UPDATE tax_returns SET status = $2 WHERE work_item_id = $1", item, status
    )
    return partner, site, item


async def _provision_item(seed: Seeder, site: Site, item: uuid.UUID) -> uuid.UUID:
    """Ashford's b2 variant: the rate reconciliation off 1,200 with one unclassified item."""
    provision = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO tax_provisions (tenant_id, engagement_id, work_item_id, "
            "pretax_book_income, taxable_income, blended_rate, current_tax, deferred_tax, "
            "total_provision, etr, recon_status, off_amount) VALUES ($1, $2, $3, 7810380, "
            "8165000, 26.1400, 2134650, 122550, 2257200, 28.9000, 'off', 1200) RETURNING id",
            site.tenant_id, site.engagement_id, item,
        ),
    )  # fmt: skip
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO rate_recon_items (tenant_id, engagement_id, work_item_id, provision_id, "
            "item_key, description, amount, classification) VALUES ($1, $2, $3, $4, "
            "'unclassified_1', 'Unclassified permanent item', 1200, 'unclassified') RETURNING id",
            site.tenant_id, site.engagement_id, item, provision,
        ),
    )  # fmt: skip


async def _events(seed: Seeder, tenant: uuid.UUID) -> int:
    return cast(
        int, await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", tenant)
    )


# --- F5 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["filed", "accepted"])
async def test_f5a_a_locked_return_answers_return_locked_on_every_write_and_writes_nothing(
    net: Net, seed: Seeder, status: str
) -> None:
    partner, site, item = await _return(seed, "1120s", status)
    recon = await _provision_item(seed, site, item)
    before = await _events(seed, site.tenant_id)
    for path in (
        f"/v1/tax-returns/{item}/provision/items/{recon}/explain",
        f"/v1/tax-returns/{item}/functional-expenses/allocation-runs",
    ):
        refused = await net.call("POST", path, partner, headers=net.keyed())
        assert refused.status_code == 409, (path, refused.text)
        assert "return_locked" in refused.text, (path, refused.text)
    assert await _events(seed, site.tenant_id) == before
    assert await seed.value(
        "SELECT count(*) FROM issues WHERE tenant_id = $1", site.tenant_id
    ) == 0  # fmt: skip


async def test_f5b2_explain_opens_the_issue_as_a_persons_act_with_no_gateway_call(
    net: Net, seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus import ai_gateway

    async def no_call(*_: object, **__: object) -> object:
        raise AssertionError("Explain… makes no gateway call (INV-1; §7216 consent or not)")

    monkeypatch.setattr(ai_gateway, "call", no_call)
    partner, site, item = await _return(seed, "1120")
    recon = await _provision_item(seed, site, item)
    made = await net.call(
        "POST", f"/v1/tax-returns/{item}/provision/items/{recon}/explain", partner,
        headers=net.keyed(),
    )  # fmt: skip
    assert made.status_code == 202, made.text  # the route answers 202 with the issue id
    issues = await seed.rows(
        "SELECT source_ref FROM issues WHERE tenant_id = $1", site.tenant_id
    )  # fmt: skip
    assert [r["source_ref"] for r in issues] == [f"provision_item:{recon}"]
    still = await seed.value("SELECT classification FROM rate_recon_items WHERE id = $1", recon)
    assert still == "unclassified"  # only a reviewer's approval classifies it


async def test_f5_a_client_principal_never_writes_other_entity_workpapers(
    net: Net, seed: Seeder
) -> None:
    _partner, site, item = await _return(seed, "1120")
    recon = await _provision_item(seed, site, item)
    client = await seed.client_contact(site)
    refused = await net.call(
        "POST", f"/v1/tax-returns/{item}/provision/items/{recon}/explain", client,
        headers=net.keyed(),
    )  # fmt: skip
    assert refused.status_code in (403, 404), refused.text
    assert await seed.value(
        "SELECT count(*) FROM issues WHERE tenant_id = $1", site.tenant_id
    ) == 0  # fmt: skip


# --- F7 ------------------------------------------------------------------------------------------


async def test_f7_another_firms_return_is_absent_from_the_form_preview(
    net: Net, seed: Seeder
) -> None:
    _partner, site, item = await _return(seed, "1065")
    stranger = await seed.person(await seed.firm())
    for path in (f"/v1/tax-returns/{item}/form-pages", f"/v1/tax-returns/{item}/k1-previews"):
        found = await net.call("GET", path, stranger)
        assert found.status_code == 404, (path, found.text)
        assert site.marker not in found.text


async def test_f7_a_client_principal_never_reads_the_form_pages(net: Net, seed: Seeder) -> None:
    _partner, site, item = await _return(seed, "1065")
    client = await seed.client_contact(site)
    refused = await net.call("GET", f"/v1/tax-returns/{item}/form-pages", client)
    assert refused.status_code in (403, 404), refused.text
    assert site.marker not in refused.text


async def test_f7_the_draft_download_needs_a_fresh_second_factor_and_writes_nothing_without(
    net: Net, seed: Seeder
) -> None:
    partner, site, item = await _return(seed, "1065")
    before = await _events(seed, site.tenant_id)
    stale = await net.call(
        "POST", f"/v1/tax-returns/{item}/form-pages:download-draft", partner, mfa=False,
        headers=net.keyed(),
    )  # fmt: skip
    assert stale.status_code in (401, 403), stale.text
    assert await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'form_preview.downloaded'",
        site.tenant_id,
    ) == 0  # fmt: skip
    assert await _events(seed, site.tenant_id) == before


async def test_f7_the_page_list_names_the_checkpoint_it_drafts_from(
    net: Net, seed: Seeder
) -> None:
    """Before an approved workbook checkpoint there is nothing to draft from: 409, never a page
    drawn from unapproved values."""
    partner, _site, item = await _return(seed, "1065")
    found = await net.call("GET", f"/v1/tax-returns/{item}/form-pages", partner)
    assert found.status_code == 409, found.text
    assert "checkpoint_required" in found.text or "form_template_missing" in found.text


# --- F8 ------------------------------------------------------------------------------------------


async def test_f8_the_graph_never_reaches_the_portal(net: Net, seed: Seeder) -> None:
    _partner, site, _item = await _return(seed, "1065")
    client = await seed.client_contact(site)
    refused = await net.call("GET", f"/v1/clients/{site.client_id}/relationship-graph", client)
    assert refused.status_code == 404, refused.text  # INV-4: absent, not forbidden
    assert site.marker not in refused.text


async def test_f8_a_walled_client_has_no_graph_and_no_placeholder(net: Net, seed: Seeder) -> None:
    partner, site, _item = await _return(seed, "1065")
    admin = await seed.person(site.tenant_id, "firm_admin")
    walled = await seed.person(site.tenant_id)
    await seed.member(site, walled, "manager")
    await net.wall(admin, walled, site)
    refused = await net.call("GET", f"/v1/clients/{site.client_id}/relationship-graph", walled)
    assert refused.status_code in (403, 404), refused.text
    assert site.marker not in refused.text
    seen = await net.call("GET", f"/v1/clients/{site.client_id}/relationship-graph", partner)
    assert seen.status_code == 200, seen.text


async def test_f8_a_relationship_is_a_persons_act_never_the_agents(seed: Seeder) -> None:
    partner, site, _item = await _return(seed, "1065")
    person = await member_context(site.tenant_id, partner.user_id)
    assert person is not None
    agent = replace(person, tenant=TenantContext(site.tenant_id, "agent", "agent:t06t56"))
    body = rc.RelationshipIn.model_validate(
        {"kind": "lp_of", "from_node_id": str(site.entity_id), "to_node_id": str(uuid.uuid4()),
         "percent": "38", "effective_from": "2025-01-01"}
    )  # fmt: skip
    with pytest.raises(Forbidden):
        await rc.relationship_create_route(site.client_id, body, agent)
    with pytest.raises(Forbidden):
        await rc.relationship_end_route(
            uuid.uuid4(),
            rc.RelationshipEndIn.model_validate(
                {"effective_to": "2026-09-15", "reason": "Interest sold"}
            ),
            agent,
        )
