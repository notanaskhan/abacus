# ac-test-author: ayushkbhatia
"""T-06-T51 (TASK-9009; SPEC-702 F8; CLI-03 a, f; DEC-88; DEC-6015) on the migrated Postgres. Row
acceptance: "A user who cannot read the Feld engagement sees Ridgeline's graph without the Feld
K-1 edge and without a count."

Ridgeline's 2025 1065 hands draft K-1s to the Feld and Shah 1040s (other clients). The partner
reads all three engagements and sees both edges and "Ridgeline 1065 → 2 K-1s at risk"; a senior on
Ridgeline and Shah only sees the Shah edge and "→ 1 K-1 at risk", with no Feld node. Once both
packages are released the banner turns green."""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.modules.tax import k1_relationships as k1

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio


async def _return(seed: Seeder, site: Site, by: Person, form: str) -> uuid.UUID:
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            f"2025 Form {form}",
            by.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, $5, 2025)",
        site.tenant_id,
        item,
        site.engagement_id,
        site.entity_id,
        form,
    )
    return item


async def _k1(
    seed: Seeder, tenant: uuid.UUID, issuer: uuid.UUID, target: uuid.UUID, name: str, by: Person
) -> uuid.UUID:
    recipient = await seed.value(
        "INSERT INTO k1_recipients (tenant_id, work_item_id, engine_ref, display_name, "
        "recipient_kind) VALUES ($1, $2, $3, $4, 'lp') RETURNING id",
        tenant,
        issuer,
        f"P-{name}",
        name,
    )
    package = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO k1_packages (tenant_id, recipient_id, work_item_id, form, tax_year, "
            "version_no) VALUES ($1, $2, $3, '1065', 2025, 1) RETURNING id",
            tenant,
            recipient,
            issuer,
        ),
    )
    await seed.run(
        "INSERT INTO k1_handoffs (tenant_id, package_id, target_work_item_id, shared_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        package,
        target,
        by.user_id,
    )
    return package


async def _graph(net: Net, client: uuid.UUID, who: Person) -> dict[str, object]:
    got = await net.call("GET", f"/v1/clients/{client}/relationship-graph", who)
    assert got.status_code == 200, got.text
    return cast(dict[str, object], got.json())


async def test_t06t51_acceptance_a_hidden_engagement_hides_its_edge_and_its_count(
    net: Net, seed: Seeder
) -> None:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'clients.relationship_map', 'true', 'test-seed', 'T-06-T51')",
        tenant,
    )
    partner, senior = await seed.person(tenant), await seed.person(tenant)
    ridgeline = await seed.site(tenant, partner.user_id, "Ridgeline Partners")
    feld = await seed.site(tenant, partner.user_id, "Feld")
    shah = await seed.site(tenant, partner.user_id, "Shah")
    for site, name in (
        (ridgeline, "Ridgeline Partners, LLC"),
        (feld, "Feld household"),
        (shah, "Shah household"),
    ):
        await seed.run("UPDATE client_entities SET name = $2 WHERE id = $1", site.entity_id, name)
        await seed.member(site, partner, "engagement_partner")
    for site in (ridgeline, shah):
        await seed.member(site, senior, "senior")
    issuer = await _return(seed, ridgeline, partner, "1065")
    to_feld = await _return(seed, feld, partner, "1040")
    to_shah = await _return(seed, shah, partner, "1040")
    packages = [
        await _k1(seed, tenant, issuer, to_feld, "Feld", partner),
        await _k1(seed, tenant, issuer, to_shah, "Shah", partner),
    ]

    full = await _graph(net, ridgeline.client_id, partner)
    k1_edges = [e for e in cast(list[dict[str, object]], full["edges"]) if e["kind"] == "k1"]
    assert sorted(str(e["to_node_id"]) for e in k1_edges) == sorted([str(to_feld), str(to_shah)])
    assert {e["state"] for e in k1_edges} == {"draft"}
    assert full["banner"] == {"tone": "amber", "text": "Ridgeline 1065 → 2 K-1s at risk"}

    partial = await _graph(net, ridgeline.client_id, senior)
    edges = [e for e in cast(list[dict[str, object]], partial["edges"]) if e["kind"] == "k1"]
    assert [str(e["to_node_id"]) for e in edges] == [str(to_shah)]
    node_ids = {str(n["node_id"]) for n in cast(list[dict[str, object]], partial["nodes"])}
    assert str(to_feld) not in node_ids and str(issuer) in node_ids
    assert partial["banner"] == {"tone": "amber", "text": "Ridgeline 1065 → 1 K-1 at risk"}
    assert "Feld" not in str(partial)

    await seed.run_untriggered(
        "UPDATE k1_packages SET status = 'released', released_at = '2026-09-15T15:00:00Z' "
        "WHERE id = ANY($1::uuid[])",
        packages,
    )
    done = await _graph(net, ridgeline.client_id, partner)
    assert done["banner"] == {
        "tone": "green",
        "text": "K-1s released Sep 15 · Feld and Shah 1040s updated",
    }

    outsider = await seed.person(tenant)
    refused = await net.call(
        "GET", f"/v1/clients/{ridgeline.client_id}/relationship-graph", outsider
    )
    assert refused.status_code in (403, 404), refused.text


def test_t06t51_the_banner_is_codes_text() -> None:
    a, b, r = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    from abacus.modules.organisations.api import relationships as rel

    edges = [rel.K1Edge(uuid.uuid4(), r, a, "draft", "K-1")]
    assert k1.banner({r: "Ridgeline Partners, LLC"}, {r: "1065"}, edges, {a: "Feld"}, None) == (
        "amber",
        "Ridgeline 1065 → 1 K-1 at risk",
    )
    released = [rel.K1Edge(uuid.uuid4(), r, b, "released", "K-1")]
    assert k1.banner({r: "Ridgeline"}, {r: "1065"}, released, {b: "Shah"}, None) == (
        "green",
        "K-1s released · Shah 1040s updated",
    )
    assert k1.banner({}, {}, [], {}, None) is None
