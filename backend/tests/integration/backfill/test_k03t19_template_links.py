# ac-test-author: ayushkbhatia
"""K-03-T19 (TASK-9013; K-03 F5; SHL-22; KNW-07; DEC-6019) on the migrated Postgres. Row
acceptance: "With the flag off the existing SPEC-008 and roll-forward tests pass unchanged; with it
on a second pin goes through template.apply_update only."

The flag-off half is the existing suites (SPEC-008's `test_q03t525_engagement_graph_methodology`
and the roll-forward suites), run unchanged. Here, with `templates_v2.enabled` on: the first pin
writes the legacy column and the link to the version's template wrapper; a second pin answers 409
`template_update_required` and changes nothing; an engagement pinned before the flag is refused
the same way; and the version an engagement follows is its link's once the link moves."""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.engagements.api import pinned_version

from .support import Seeder
from .test_q03t525_engagement_graph_methodology import GOOD, World
from .test_q03t525_engagement_graph_methodology import world as world  # the SPEC-008 world

pytestmark = pytest.mark.asyncio


def _name() -> str:
    return f"Core-{uuid.uuid4().hex[:6]}"


async def _flag_on(seed: Seeder, tenant: uuid.UUID) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'templates_v2.enabled', 'true', 'test-seed', 'K-03-T19')",
        tenant,
    )
    forget_flags()


async def _wrap(w: World, methodology_version: str, seq: int = 1) -> uuid.UUID:
    """The methodology version's published template wrapper (1010's bootstrap shape)."""
    seed, tenant = w.seed, w.tenant_id
    template_id = cast(
        uuid.UUID,
        await seed.value(
            "SELECT template_id FROM methodology_versions WHERE id = $1",
            uuid.UUID(methodology_version),
        ),
    )
    wrapper = await seed.value(
        "SELECT id FROM engagement_templates WHERE methodology_template_id = $1", template_id
    )
    if wrapper is None:
        wrapper = await seed.value(
            "INSERT INTO engagement_templates (tenant_id, methodology_template_id, name) "
            "VALUES ($1, $2, 'Core') RETURNING id",
            tenant,
            template_id,
        )
    version = uuid.uuid4()
    await seed.run(
        "INSERT INTO template_versions (id, tenant_id, template_id, seq, label, status, "
        "methodology_version_id, effective_from, fingerprint, origin, published_at) VALUES "
        "($1, $2, $3, $4, $5, 'published', $6, DATE '2026-10-01', $7, 'bootstrap', now())",
        version,
        tenant,
        wrapper,
        seq,
        f"Core v{seq}",
        uuid.UUID(methodology_version),
        f"{seq:x}" * 64,
    )
    return version


async def _items(w: World) -> list[dict[str, object]]:
    rows = await w.seed.rows(
        "SELECT id, description, status FROM request_items WHERE engagement_id = $1 ORDER BY id",
        w.site.engagement_id,
    )
    return [dict(r) for r in rows]


async def test_k03t19_acceptance_flag_on_first_pin_links_and_a_second_is_a_template_update(
    world: World,
) -> None:
    await _flag_on(world.seed, world.tenant_id)
    version = cast(str, (await world.import_(_name(), GOOD)).json()["version_id"])
    wrapper = await _wrap(world, version)

    first = await world.apply(version)
    assert first.status_code == 201, first.text
    link = await world.seed.rows(
        "SELECT template_version_id, state FROM engagement_template_links "
        "WHERE engagement_id = $1",
        world.site.engagement_id,
    )
    assert [(r["template_version_id"], r["state"]) for r in link] == [(wrapper, "current")]
    legacy = await world.seed.value(
        "SELECT methodology_version_id FROM engagements WHERE id = $1", world.site.engagement_id
    )
    assert str(legacy) == version  # the legacy column is kept as the current version
    linked = await world.count(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'engagement.template_linked'"
    )
    assert linked == 1

    before = await _items(world)
    again = await world.apply(version, who="manager")
    assert again.status_code == 409, again.text
    assert "template_update_required" in again.text
    assert await _items(world) == before


async def test_k03t19_an_engagement_pinned_before_the_flag_is_refused_the_same_way(
    world: World,
) -> None:
    version = cast(str, (await world.import_(_name(), GOOD)).json()["version_id"])
    assert (await world.apply(version)).status_code == 201  # flag off: the SPEC-008 pin
    await _flag_on(world.seed, world.tenant_id)
    again = await world.apply(version)
    assert again.status_code == 409 and "template_update_required" in again.text, again.text


async def test_k03t19_a_version_with_no_wrapper_pins_the_legacy_column_only(
    world: World,
) -> None:
    await _flag_on(world.seed, world.tenant_id)
    version = cast(str, (await world.import_(_name(), GOOD)).json()["version_id"])
    assert (await world.apply(version)).status_code == 201
    links = await world.seed.value(
        "SELECT count(*) FROM engagement_template_links WHERE engagement_id = $1",
        world.site.engagement_id,
    )
    assert links == 0


async def test_k03t19_the_followed_version_is_the_links_once_it_moves(world: World) -> None:
    v5 = cast(str, (await world.import_(_name(), GOOD)).json()["version_id"])
    await _flag_on(world.seed, world.tenant_id)
    await _wrap(world, v5, seq=5)
    assert (await world.apply(v5)).status_code == 201
    tenant = TenantContext(world.tenant_id, "system", "test:k03t19")
    engagement = world.site.engagement_id
    assert str(await pinned_version(tenant, engagement, uuid.UUID(v5))) == v5

    # Another methodology version of the same template, wrapped as v6; the link moves to it as
    # K-03-T33's update would (the legacy column stays v5 until then).
    v6 = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO methodology_versions (tenant_id, template_id, version, "
            "source_fingerprint, imported_by, label) SELECT tenant_id, template_id, version + 1, "
            "$2, imported_by, 'Core v6' FROM methodology_versions WHERE id = $1 RETURNING id",
            uuid.UUID(v5),
            "6" * 64,
        ),
    )
    wrapper6 = await _wrap(world, str(v6), seq=6)
    await world.seed.run_untriggered(
        "UPDATE engagement_template_links SET template_version_id = $2, state = 'updated', "
        "updated_from_version_id = template_version_id WHERE engagement_id = $1",
        engagement,
        wrapper6,
    )
    assert await pinned_version(tenant, engagement, uuid.UUID(v5)) == v6
