"""P-08-T13 against Postgres (SPEC-320 AC-15 to AC-17; P-08 Stories 6.1 to 6.7): the home composes
one covered scope from its sources in client codes; another scope, or a person with no full-client
grant, answers 404; dismissing the welcome persists per user and scope with a version."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.identity.authz import recording_checks
from abacus.modules.portal.contract import PortalHomeOut
from abacus.modules.portal.home import PortalPreferencesStale, read_home, set_preferences

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _grant(seed: Seeder, who: Person, role: str, kind: str, scope: uuid.UUID) -> None:
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, $3, $4, $5)",
        who.tenant_id,
        who.user_id,
        role,
        kind,
        scope,
    )


async def _client(seed: Seeder, who: Person) -> None:
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        who.tenant_id,
        who.user_id,
    )


async def _household(seed: Seeder) -> tuple[Person, Person, uuid.UUID, uuid.UUID]:
    """A firm, its partner, a client with one engagement, and the client's owner on it (an
    engagement-scope grant: the client admin)."""
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    entity = await seed.entity(tenant)
    client = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    claire = await seed.person(tenant)
    await _client(seed, claire)
    await _grant(seed, claire, "owner", "engagement", engagement)
    return claire, partner, client, engagement


async def _binder(seed: Seeder, claire: Person, engagement: uuid.UUID, partner: Person) -> None:
    """A published binder with three client-visible requests (one done, one past due) and one the
    client never sees."""
    first = await seed.item(claire.tenant_id, engagement, partner.user_id)
    others = [await seed.item(claire.tenant_id, engagement, partner.user_id) for _ in range(3)]
    await seed.run(
        "UPDATE request_lists SET status = 'published', published_at = now(), "
        "published_by = $2 WHERE engagement_id = $1",
        engagement,
        partner.user_id,
    )
    hidden = others[2]
    await seed.run(
        "UPDATE request_items SET client_visible = (id <> $2), status = 'requested', "
        "due_on = current_date + 30 WHERE id = ANY($1::uuid[])",
        [first, *others],
        hidden,
    )
    await seed.run("UPDATE request_items SET status = 'uploaded' WHERE id = $1", others[0])
    # Two days back: past due in every firm time zone (the overdue rule reads the firm's local
    # date, and `current_date` is UTC, so one day back is still today in the US until midnight
    # there).
    await seed.run("UPDATE request_items SET due_on = current_date - 2 WHERE id = $1", others[1])


async def test_ac15_the_home_composes_one_scope_in_client_codes(seed: Seeder) -> None:
    claire, partner, _, engagement = await _household(seed)
    await _binder(seed, claire, engagement, partner)

    view = await read_home(claire.context(), None)
    home = PortalHomeOut.model_validate(asdict(view))

    assert (home.scope.kind, home.scope.id) == ("engagement", engagement)
    assert (home.scope.label, home.scope.role_label) == ("Seeded client", "Owner")
    upload = next(t for t in home.todos if t.kind == "upload")
    assert (upload.count, upload.state) == (2, "overdue")  # derived overdue (P-06)
    assert home.binder is not None
    assert (home.binder.done, home.binder.total, home.binder.sorted_count) == (1, 3, 0)
    [card] = home.work_cards  # the engagement's assurance item, at planning
    assert card.pill.code == "finishing_audit" and card.pill.variant == "state"
    assert [(s.code, s.state) for s in card.stages][:2] == [
        ("planning", "current"),
        ("fieldwork", "upcoming"),
    ]
    assert [(m.user_id, m.role_code) for m in home.team] == [
        (partner.user_id, "engagement_partner")
    ]
    assert home.first_visit and not home.welcome_dismissed and not home.all_done


async def test_ac16_another_scope_or_no_full_grant_answers_404(seed: Seeder) -> None:
    claire, partner, _, _ = await _household(seed)
    other_entity = await seed.entity(claire.tenant_id, "Another client")
    other_client = cast(
        uuid.UUID,
        await seed.value("SELECT client_id FROM client_entities WHERE id = $1", other_entity),
    )
    with pytest.raises(NotFound):
        await read_home(claire.context(), other_client)
    other_engagement = await seed.engagement(claire.tenant_id, other_entity, partner.user_id)
    with pytest.raises(NotFound):
        await read_home(claire.context(), other_engagement)

    sam = await seed.person(claire.tenant_id)
    await _client(seed, sam)
    await _grant(seed, sam, "k1_recipient", "engagement", other_engagement)
    with pytest.raises(NotFound):
        await read_home(sam.context(), None)
    with pytest.raises(NotFound):  # the firm's own partner has no portal home
        await read_home(partner.context(), None)


async def test_ac16_a_grant_covers_only_its_own_targets(seed: Seeder) -> None:
    """A person with a full grant on one client and a client role on another client's engagement
    sees nothing of the second on the first's home (INV-4)."""
    claire, partner, _, engagement = await _household(seed)
    await _binder(seed, claire, engagement, partner)
    other_entity = await seed.entity(claire.tenant_id, "Ridgeline")
    other = await seed.engagement(claire.tenant_id, other_entity, partner.user_id)
    await _grant(seed, claire, "owner", "engagement", other)
    await _binder(seed, claire, other, partner)

    home = await read_home(claire.context(), engagement)
    assert [c.work_item_id for c in home.work_cards] == [
        await seed.value("SELECT id FROM work_items WHERE engagement_id = $1", engagement)
    ]
    assert next(t for t in home.todos if t.kind == "upload").count == 2


async def test_ac17_the_welcome_dismissal_is_versioned_per_scope_and_audited(seed: Seeder) -> None:
    claire, _, _, engagement = await _household(seed)
    ctx = claire.context()

    saved = await set_preferences(ctx, engagement, True, 0)
    assert saved.welcome_dismissed and saved.version == 1 and saved.welcome_dismissed_at
    with pytest.raises(PortalPreferencesStale) as stale:
        await set_preferences(ctx, engagement, True, 0)
    assert stale.value.facts == {"version": 1}
    home = await read_home(ctx, engagement)
    assert home.welcome_dismissed and not home.first_visit
    again = await set_preferences(ctx, engagement, False, 1)
    assert not again.welcome_dismissed and again.version == 2
    with pytest.raises(NotFound):
        await set_preferences(ctx, uuid.uuid4(), True, 0)
    assert (
        await seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'portal_preferences.updated'",
            claire.tenant_id,
        )
        == 2
    )


async def test_both_routes_record_their_action_for_the_route_guard(seed: Seeder) -> None:
    """The guard answers 500 for a success with no recorded check (ADR-020): each route's service
    authorises its own action."""
    claire, _, _, engagement = await _household(seed)
    with recording_checks() as checked:
        await read_home(claire.context(), engagement)
    assert "portal_home.read" in checked
    with recording_checks() as checked:
        await set_preferences(claire.context(), engagement, True, 0)
    assert "portal_preferences.update" in checked


async def test_a_full_grant_with_no_matrix_cells_reads_and_writes_nothing(seed: Seeder) -> None:
    """A `delegate` holds the full shell but no matrix cells until P-09 (DEC-158, DEC-211)."""
    _, _, _, engagement = await _household(seed)
    tenant = cast(
        uuid.UUID, await seed.value("SELECT tenant_id FROM engagements WHERE id = $1", engagement)
    )
    dana = await seed.person(tenant)
    await _client(seed, dana)
    await _grant(seed, dana, "delegate", "engagement", engagement)
    with pytest.raises(NotFound):
        await read_home(dana.context(), engagement)
    with pytest.raises(NotFound):
        await set_preferences(dana.context(), engagement, True, 0)
    assert (
        await seed.value(
            "SELECT count(*) FROM portal_preferences WHERE user_id = $1", dana.user_id
        )
        == 0
    )
