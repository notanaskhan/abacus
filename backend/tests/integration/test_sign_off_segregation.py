"""P-04-T15 against Postgres: a preparer never signs L2 or L3 on their own target (R-SO-3,
`not_preparer_of_target`; DEC-216), through `review.api.record_sign_off` with the target's facts.

The target's preparers come from its owner's own records (`ReviewableFacts`: for a trial balance
who adopted a version or annotated it, for a mapping set who created or edited it) and from
everyone who has signed L1 on it, on any content. A target type with no registered facts has no
known preparers, so L2 and L3 deny (fail closed). The matrix denies; the service answers a known
preparer with 409 `preparer_cannot_review`.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext, Forbidden, engagement_resource
from abacus.modules.review.api import (
    PreparerCannotReview,
    ReviewableFacts,
    content_hash,
    record_sign_off,
    register_reviewable_facts,
    reviewable_facts,
)

from .agent_tests.support import Person, Role, Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
V1 = content_hash({"cells": {"C14": {"raw": "2190", "tickmarks": []}}, "citations": []})
V2 = content_hash({"cells": {"C14": {"raw": "2310", "tickmarks": []}}, "citations": []})
# A test owner's records: target id -> who prepared it.
OWNED: dict[uuid.UUID, frozenset[uuid.UUID]] = {}


async def _owned_facts(_tenant: TenantContext, target_id: uuid.UUID) -> ReviewableFacts | None:
    if target_id not in OWNED:
        return None
    return ReviewableFacts("probe_owned", target_id, uuid.uuid4(), V2, 1, OWNED[target_id])


register_reviewable_facts("probe_owned", _owned_facts)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


class Team:
    def __init__(self, seed: Seeder, tenant: uuid.UUID, engagement: uuid.UUID) -> None:
        self.seed, self.tenant, self.engagement = seed, tenant, engagement

    async def sign(
        self, who: Person, target_type: str, target: uuid.UUID, level: int, digest: str
    ) -> None:
        ctx = _ctx(who)
        resource = await engagement_resource(ctx.tenant, self.engagement)
        async with uow(ctx.tenant) as tx:
            await record_sign_off(
                tx, ctx, resource, self.engagement, target_type, target, level, digest
            )


async def _team(seed: Seeder, roles: tuple[Role, ...]) -> tuple[Team, list[Person], uuid.UUID]:
    tenant = await seed.firm()
    people = [await seed.person(tenant) for _ in roles]
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, people[0].user_id)
    for who, role in zip(people, roles, strict=True):
        await seed.member(engagement, who, role)
    return Team(seed, tenant, engagement), people, entity


async def test_rso3_the_l1_signer_is_refused_l2_and_l3_and_another_reviewer_signs(
    migrated_db: MigratedDatabase,
) -> None:
    team, (marcus, hannah), _ = await _team(
        Seeder(migrated_db.superuser_dsn), ("manager", "engagement_partner")
    )
    target = uuid.uuid4()
    OWNED[target] = frozenset()
    await team.sign(marcus, "probe_owned", target, 1, V2)
    for level in (2, 3):
        with pytest.raises(PreparerCannotReview):
            await team.sign(marcus, "probe_owned", target, level, V2)
    await team.sign(hannah, "probe_owned", target, 2, V2)
    await team.sign(hannah, "probe_owned", target, 3, V2)
    rows = await team.seed.rows(
        "SELECT level, signed_by FROM sign_offs WHERE target_id = $1 ORDER BY level", target
    )
    assert [(r["level"], r["signed_by"]) for r in rows] == [
        (1, marcus.user_id),
        (2, hannah.user_id),
        (3, hannah.user_id),
    ]


async def test_rso3_an_l1_signer_on_earlier_content_and_the_owners_preparers_are_refused(
    migrated_db: MigratedDatabase,
) -> None:
    team, (marcus, kevin, carol, hannah), _ = await _team(
        Seeder(migrated_db.superuser_dsn),
        ("manager", "manager", "manager", "engagement_partner"),
    )
    target = uuid.uuid4()
    OWNED[target] = frozenset({carol.user_id})  # the owner's records: Carol prepared it
    await team.sign(marcus, "probe_owned", target, 1, V1)  # then the content changed
    await team.sign(kevin, "probe_owned", target, 1, V2)
    for who in (marcus, kevin, carol):
        with pytest.raises(PreparerCannotReview):
            await team.sign(who, "probe_owned", target, 2, V2)
    await team.sign(hannah, "probe_owned", target, 2, V2)


async def test_a_type_without_registered_facts_denies_l2_and_l3_to_everyone(
    migrated_db: MigratedDatabase,
) -> None:
    team, (marcus, hannah), _ = await _team(
        Seeder(migrated_db.superuser_dsn), ("manager", "engagement_partner")
    )
    target = uuid.uuid4()
    await team.sign(marcus, "probe_unowned", target, 1, V2)  # L1 has no segregation condition
    for level in (2, 3):
        with pytest.raises(Forbidden):
            await team.sign(hannah, "probe_unowned", target, level, V2)
    assert (
        await team.seed.value("SELECT count(*) FROM sign_offs WHERE target_id = $1", target) == 1
    )


# --- The assurance owners: trial balances and mapping sets ---------------------------------------

FINGERPRINT = "f" * 64


async def _trial_balance(
    team: Team, entity: uuid.UUID, adopter: Person, annotator: Person
) -> uuid.UUID:
    seed = team.seed
    work_item = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 LIMIT 1", team.engagement
    )
    if work_item is None:
        work_item = await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) SELECT tenant_id, id, client_id, client_entity_id, "
            "'assurance', 'Audit', $3 FROM engagements WHERE tenant_id = $1 AND id = $2 "
            "RETURNING id",
            team.tenant,
            team.engagement,
            adopter.user_id,
        )
    snapshot = await seed.value(
        "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, period_end, "
        "pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit) "
        "VALUES ($1, $2, '2025-01-01', '2025-12-31', now(), 'fake', $3, 0, 0, 0) RETURNING id",
        team.tenant,
        entity,
        hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
    )
    tb = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO trial_balances (tenant_id, engagement_id, work_item_id, "
            "client_entity_id, period_start, period_end, created_by) "
            "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
            team.tenant,
            team.engagement,
            work_item,
            entity,
            adopter.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO trial_balance_versions (tenant_id, trial_balance_id, client_entity_id, "
        "version_no, snapshot_id, adopted_by, actor_kind, content_fingerprint) "
        "VALUES ($1, $2, $3, 1, $4, $5, 'human', $6)",
        team.tenant,
        tb,
        entity,
        snapshot,
        adopter.user_id,
        FINGERPRINT,
    )
    await seed.run(
        "INSERT INTO trial_balance_annotations (tenant_id, trial_balance_id, account_code, area, "
        "set_by) VALUES ($1, $2, '1000', 'Cash', $3)",
        team.tenant,
        tb,
        annotator.user_id,
    )
    return tb


async def _mapping_set(team: Team, tb: uuid.UUID, creator: Person, editor: Person) -> uuid.UUID:
    seed = team.seed
    grouping_set = await seed.value(
        "INSERT INTO grouping_sets (tenant_id, key, name, created_by) "
        "VALUES ($1, $2, 'Standard', $3) RETURNING id",
        team.tenant,
        f"std-{uuid.uuid4().hex[:6]}",
        creator.user_id,
    )
    version = await seed.value(
        "INSERT INTO grouping_set_versions (tenant_id, grouping_set_id, version, payload_hash, "
        "created_by) VALUES ($1, $2, 1, $3, $4) RETURNING id",
        team.tenant,
        grouping_set,
        FINGERPRINT,
        creator.user_id,
    )
    mapping_set = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO mapping_sets (tenant_id, engagement_id, trial_balance_id, "
            "grouping_set_version_id, created_by) VALUES ($1, $2, $3, $4, $5) RETURNING id",
            team.tenant,
            team.engagement,
            tb,
            version,
            creator.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO mapping_set_edits (tenant_id, mapping_set_id, account_code, edited_by, "
        "actor_kind) VALUES ($1, $2, '1000', $3, 'human')",
        team.tenant,
        mapping_set,
        editor.user_id,
    )
    return mapping_set


async def test_trial_balance_and_mapping_set_preparers_come_from_their_records(
    migrated_db: MigratedDatabase,
) -> None:
    team, (adopter, annotator, editor, signer, reviewer), entity = await _team(
        Seeder(migrated_db.superuser_dsn),
        ("manager", "manager", "manager", "manager", "engagement_partner"),
    )
    tb = await _trial_balance(team, entity, adopter, annotator)
    mapping_set = await _mapping_set(team, tb, adopter, editor)
    me = TenantContext(team.tenant, "human", str(reviewer.user_id))

    tb_facts = await reviewable_facts(me, "trial_balance", tb)
    assert tb_facts.preparer_user_ids == {adopter.user_id, annotator.user_id}
    assert (tb_facts.engagement_id, tb_facts.version_no) == (team.engagement, 1)
    map_facts = await reviewable_facts(me, "mapping_set", mapping_set)
    assert map_facts.preparer_user_ids == {adopter.user_id, editor.user_id}
    assert map_facts.engagement_id == team.engagement

    for target_type, target, preparers in (
        ("trial_balance", tb, (adopter, annotator)),
        ("mapping_set", mapping_set, (adopter, editor)),
    ):
        await team.sign(signer, target_type, target, 1, V2)
        for who in preparers:
            for level in (2, 3):
                with pytest.raises(PreparerCannotReview):
                    await team.sign(who, target_type, target, level, V2)
        await team.sign(reviewer, target_type, target, 2, V2)
