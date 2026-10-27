# ac-test-author: ayushkbhatia
"""P-04-T13: independent AC tests (ADR-078) for the four P-04 migrations (0093 review core, 0094
cards, checkpoints and issues, 0095 suggestions and proposals, 0102 approval grants).

The rows promise: row-level security forced on every table (T03); `sign_offs` and every decision
table insert-only, so UPDATE or DELETE raises `insufficient_privilege` (T03, T05); human-only
CHECKs bound to the session's `app.actor_kind` and `app.actor_id`, so agent, system, support and
policy actors, and a person claiming someone else's id, are refused at the database (T03, T04,
T05; ADR-005, INV-1); one decision per card (T04); an Undo row more than 10 seconds after its
decision, or after the decision's grant was consumed, refused by trigger (T05; DEC-24, ADR-161);
on a grant only `used_at` and `voided_at` move, once (T10). The session database was migrated
up, down and up by `provisioned_database` (schema_check's path) before these run, so they hold
after the round trip; `test_t13_*_detects_*` show the probes fail when a human-only CHECK or an
insert-only trigger is removed, on a private database.

Boundary: SQL as the superuser with the actor GUCs a unit of work sets (`agent_tests.Seeder.
as_actor`), and as the app role for row-level security. Expectations come from P-04 §4.2 and the
T03, T04, T05 and T10 rows, ADR-160 and ADR-161, never from the migration bodies.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Final

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

T0: Final = "2026-09-14T09:41:00-05:00"
TABLES: Final = {
    "0093": (
        "sign_offs",
        "review_notes",
        "review_note_events",
        "field_value_versions",
        "human_gates",
    ),
    "0094": (
        "decision_cards",
        "decisions",
        "checkpoints",
        "checkpoint_diffs",
        "checkpoint_decisions",
        "issues",
        "issue_events",
        "issue_links",
    ),
    "0095": (
        "suggestions",
        "suggestion_decisions",
        "proposals",
        "proposal_rows",
        "proposal_decisions",
    ),
    "0102": ("approval_grants",),
}
INSERT_ONLY: Final = (
    "sign_offs",
    "review_note_events",
    "field_value_versions",
    "decisions",
    "checkpoint_diffs",
    "checkpoint_decisions",
    "issue_events",
    "suggestion_decisions",
    "proposal_rows",
    "proposal_decisions",
)
WRITES: Final = {
    "sign_offs": (
        ("UPDATE", "UPDATE sign_offs SET created_at = created_at WHERE id = $1"),
        ("DELETE", "DELETE FROM sign_offs WHERE id = $1"),
    ),
    "decisions": (
        ("UPDATE", "UPDATE decisions SET created_at = created_at WHERE id = $1"),
        ("DELETE", "DELETE FROM decisions WHERE id = $1"),
    ),
    "checkpoint_decisions": (
        ("UPDATE", "UPDATE checkpoint_decisions SET created_at = created_at WHERE id = $1"),
        ("DELETE", "DELETE FROM checkpoint_decisions WHERE id = $1"),
    ),
    "suggestion_decisions": (
        ("UPDATE", "UPDATE suggestion_decisions SET created_at = created_at WHERE id = $1"),
        ("DELETE", "DELETE FROM suggestion_decisions WHERE id = $1"),
    ),
    "proposal_decisions": (
        ("UPDATE", "UPDATE proposal_decisions SET created_at = created_at WHERE id = $1"),
        ("DELETE", "DELETE FROM proposal_decisions WHERE id = $1"),
    ),
}
FOREIGN_COUNTS: Final = {
    "decisions": "SELECT count(*) FROM decisions WHERE tenant_id = $1",
    "proposal_decisions": "SELECT count(*) FROM proposal_decisions WHERE tenant_id = $1",
    "decision_cards": "SELECT count(*) FROM decision_cards WHERE tenant_id = $1",
    "proposals": "SELECT count(*) FROM proposals WHERE tenant_id = $1",
    "checkpoints": "SELECT count(*) FROM checkpoints WHERE tenant_id = $1",
    "suggestions": "SELECT count(*) FROM suggestions WHERE tenant_id = $1",
}
NOT_A_PERSON: Final = (
    ("agent", "agent:screener"),
    ("system", "system:worker"),
    ("support", "support:break-glass"),
    ("policy", "policy:BH-TAX-02"),
)


def _sha() -> str:
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


class World:
    """One synthetic firm with an engagement, a decision card, a checkpoint, a suggestion and a
    proposal: one target for each human-only table."""

    def __init__(
        self, seed: Seeder, tenant: uuid.UUID, engagement: uuid.UUID, person: uuid.UUID
    ) -> None:
        self.seed, self.tenant, self.engagement, self.person = seed, tenant, engagement, person
        self.card = uuid.uuid4()
        self.checkpoint = uuid.uuid4()
        self.suggestion = uuid.uuid4()
        self.proposal = uuid.uuid4()

    @property
    def hannah(self) -> tuple[str, str]:
        return ("human", str(self.person))

    async def targets(self) -> None:
        agent = ("agent", "agent:probe")
        await self.seed.as_actor(
            self.tenant,
            agent,
            "INSERT INTO decision_cards (id, tenant_id, engagement_id, kind, question_key, "
            "reserved_role, options, raised_by_kind, raised_by_id) VALUES ($1, $2, $3, "
            "'materiality', 'materiality.overall', 'engagement_partner', "
            "'[{\"key\": \"accept\"}]', 'agent', 'agent:probe')",
            self.card,
            self.tenant,
            self.engagement,
            at=T0,
        )
        await self.seed.as_actor(
            self.tenant,
            agent,
            "INSERT INTO checkpoints (id, tenant_id, target_type, target_id, seq, author_kind, "
            "author_ref, cause, status, content_hash, name) VALUES ($1, $2, 'workpaper', $3, 1, "
            "'agent', 'agent:probe', 'agent_run', 'proposed', $4, 'Checkpoint 6')",
            self.checkpoint,
            self.tenant,
            uuid.uuid4(),
            _sha(),
            at=T0,
        )
        await self.seed.as_actor(
            self.tenant,
            agent,
            "INSERT INTO suggestions (id, tenant_id, target_type, target_id, field_key, "
            "proposed_value, agent_run_id) VALUES ($1, $2, 'workpaper', $3, 'C14', "
            '\'{"t": "decimal", "v": "2310"}\', $4)',
            self.suggestion,
            self.tenant,
            uuid.uuid4(),
            uuid.uuid4(),
            at=T0,
        )
        await self.seed.as_actor(
            self.tenant,
            agent,
            "INSERT INTO proposals (id, tenant_id, engagement_id, kind, title, agent_run_id) "
            "VALUES ($1, $2, $3, 'field_change_set', 'Feld K-1 treatment', $4)",
            self.proposal,
            self.tenant,
            self.engagement,
            uuid.uuid4(),
            at=T0,
        )

    # One human-only insert per table, by `who`; each returns the new row's id.
    async def sign_off(self, who: tuple[str, str], at: str = T0) -> uuid.UUID:
        made = uuid.uuid4()
        await self.seed.as_actor(
            self.tenant,
            who,
            "INSERT INTO sign_offs (id, tenant_id, engagement_id, target_type, target_id, level, "
            "content_hash, signed_by) VALUES ($1, $2, $3, 'workpaper', $4, 1, $5, $6)",
            made,
            self.tenant,
            self.engagement,
            uuid.uuid4(),
            _sha(),
            self.person,
            at=at,
        )
        return made

    async def decision(self, who: tuple[str, str], at: str = T0) -> uuid.UUID:
        made = uuid.uuid4()
        await self.seed.as_actor(
            self.tenant,
            who,
            "INSERT INTO decisions (id, tenant_id, card_id, option_key, rationale_sealed, "
            "seen_card_version, decided_by) VALUES ($1, $2, $3, 'accept', '\\x01', 1, $4)",
            made,
            self.tenant,
            self.card,
            self.person,
            at=at,
        )
        return made

    async def checkpoint_decision(self, who: tuple[str, str], at: str = T0) -> uuid.UUID:
        made = uuid.uuid4()
        await self.seed.as_actor(
            self.tenant,
            who,
            "INSERT INTO checkpoint_decisions (id, tenant_id, checkpoint_id, decision, "
            "decided_by) VALUES ($1, $2, $3, 'approved', $4)",
            made,
            self.tenant,
            self.checkpoint,
            self.person,
            at=at,
        )
        return made

    async def suggestion_decision(
        self, who: tuple[str, str], at: str = T0, *, undoes: uuid.UUID | None = None
    ) -> uuid.UUID:
        made = uuid.uuid4()
        await self.seed.as_actor(
            self.tenant,
            who,
            "INSERT INTO suggestion_decisions (id, tenant_id, suggestion_id, decision, "
            "decided_by, undoes_decision_id) VALUES ($1, $2, $3, $4, $5, $6)",
            made,
            self.tenant,
            self.suggestion,
            "undone" if undoes else "adopted",
            self.person,
            undoes,
            at=at,
        )
        return made

    async def proposal_decision(
        self,
        who: tuple[str, str],
        at: str = T0,
        *,
        undoes: uuid.UUID | None = None,
        grant: uuid.UUID | None = None,
    ) -> uuid.UUID:
        made = uuid.uuid4()
        await self.seed.as_actor(
            self.tenant,
            who,
            "INSERT INTO proposal_decisions (id, tenant_id, proposal_id, decision, seen_version, "
            "decided_by, undoes_decision_id, approval_grant_id) "
            "VALUES ($1, $2, $3, $4, 1, $5, $6, $7)",
            made,
            self.tenant,
            self.proposal,
            "undone" if undoes else "approved",
            self.person,
            undoes,
            grant,
            at=at,
        )
        return made

    async def grant(self) -> uuid.UUID:
        made = uuid.uuid4()
        await self.seed.as_actor(
            self.tenant,
            self.hannah,
            "INSERT INTO approval_grants (id, tenant_id, subject_type, subject_id, action, "
            "approver_user_id, engagement_id, payload_sha256, not_before, expires_at) VALUES "
            "($1, $2, 'proposal', $3, 'proposal.approve', $4, $5, $6, "
            "$7::timestamptz + interval '10 seconds', $7::timestamptz + interval '1 day')",
            made,
            self.tenant,
            self.proposal,
            self.person,
            self.engagement,
            _sha(),
            datetime.fromisoformat(T0),
            at=T0,
        )
        return made


async def _world(seed: Seeder) -> World:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    world = World(seed, tenant, engagement, person.user_id)
    await world.targets()
    return world


# --- probes: each returns what it found wrong; empty means the rule holds ------------------------


async def rls_problems(seed: Seeder) -> list[str]:
    found: list[str] = []
    for migration, tables in TABLES.items():
        for table in tables:
            rows = await seed.rows(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = $1 AND relnamespace = 'public'::regnamespace",
                table,
            )
            if not rows:
                found.append(f"{migration}: {table} does not exist")
            elif not (rows[0]["relrowsecurity"] and rows[0]["relforcerowsecurity"]):
                found.append(f"{migration}: {table} row-level security is not forced")
    return found


async def human_only_problems(world: World) -> list[str]:
    """Every decision table refuses each non-person actor, and a person writing as someone else."""
    writers = {
        "sign_offs": world.sign_off,
        "decisions": world.decision,
        "checkpoint_decisions": world.checkpoint_decision,
        "suggestion_decisions": world.suggestion_decision,
        "proposal_decisions": world.proposal_decision,
    }
    found: list[str] = []
    for table, write in writers.items():
        for actor in NOT_A_PERSON:
            try:
                await write(actor)
            except asyncpg.CheckViolationError:
                continue
            except asyncpg.PostgresError as other:
                found.append(f"{table}: {actor[0]} refused by {type(other).__name__}, not a CHECK")
                continue
            found.append(f"{table}: accepted from {actor[0]}")
    return found


def _dsn(app_url: str) -> str:
    return app_url.replace("postgresql+asyncpg://", "postgresql://")


async def insert_only_problems(world: World, app_url: str) -> list[str]:
    """UPDATE and DELETE of a decision row, as the app role in the row's own firm, raise
    insufficient_privilege."""
    made = {
        "sign_offs": await world.sign_off(world.hannah),
        "checkpoint_decisions": await world.checkpoint_decision(world.hannah),
        "suggestion_decisions": await world.suggestion_decision(world.hannah),
        "proposal_decisions": await world.proposal_decision(world.hannah),
        "decisions": await world.decision(world.hannah),
    }
    found: list[str] = []
    conn = await asyncpg.connect(_dsn(app_url))
    try:
        for table, row in made.items():
            for verb, statement in WRITES[table]:
                try:
                    async with conn.transaction():
                        await conn.execute(
                            "SELECT set_config('app.tenant_id', $1, true)", str(world.tenant)
                        )
                        await conn.execute(
                            "SELECT set_config('app.actor_kind', 'human', true), "
                            "set_config('app.actor_id', $1, true)",
                            str(world.person),
                        )
                        done = await conn.execute(statement, row)
                except asyncpg.InsufficientPrivilegeError:
                    continue
                found.append(f"{table}: {verb} allowed ({done})")
    finally:
        await conn.close()
    return found


TRIGGERED: Final = (
    "decisions",
    "checkpoint_decisions",
    "suggestion_decisions",
    "proposal_decisions",
)


async def owner_problems(seed: Seeder) -> list[str]:
    """The decision tables' own triggers refuse UPDATE and DELETE even to the table owner and the
    superuser (who skip privileges and row-level security)."""
    world = await _world(seed)
    made = {
        "decisions": await world.decision(world.hannah),
        "checkpoint_decisions": await world.checkpoint_decision(world.hannah),
        "suggestion_decisions": await world.suggestion_decision(world.hannah),
        "proposal_decisions": await world.proposal_decision(world.hannah),
    }
    found: list[str] = []
    for table, row in made.items():
        for verb, statement in WRITES[table]:
            try:
                await world.seed.run(statement, row)
            except asyncpg.InsufficientPrivilegeError:
                continue
            found.append(f"{table}: {verb} allowed to the owner")
    return found


def _db_seed(database: sc.Database) -> Seeder:
    return Seeder(database.superuser_dsn)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


# --- T03, T04, T05, T10: the rules hold ----------------------------------------------------------


async def test_t03_row_level_security_is_forced_on_every_table_of_the_four_migrations(
    seed: Seeder,
) -> None:
    assert await rls_problems(seed) == []


async def test_t03_the_app_role_sees_no_other_firms_review_rows(
    migrated_db: MigratedDatabase, seed: Seeder
) -> None:
    mine, theirs = await _world(seed), await _world(seed)
    await theirs.decision(theirs.hannah)
    await theirs.proposal_decision(theirs.hannah)
    conn = await asyncpg.connect(_dsn(migrated_db.app_url))
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(mine.tenant))
            for table, sql in FOREIGN_COUNTS.items():
                count = await conn.fetchval(sql, theirs.tenant)
                assert count == 0, table
    finally:
        await conn.close()


@pytest.mark.parametrize("actor", NOT_A_PERSON, ids=[a[0] for a in NOT_A_PERSON])
async def test_t04_t05_no_actor_but_a_person_may_write_a_decision(
    seed: Seeder, actor: tuple[str, str]
) -> None:
    world = await _world(seed)
    for write in (
        world.sign_off,
        world.decision,
        world.checkpoint_decision,
        world.suggestion_decision,
        world.proposal_decision,
    ):
        with pytest.raises(asyncpg.CheckViolationError):
            await write(actor)


async def test_t04_t05_the_person_must_be_the_session_actor(seed: Seeder) -> None:
    """A row claiming a person other than the session's actor is refused: the CHECK is bound to
    `app.actor_id`, not to the column the writer fills in."""
    world = await _world(seed)
    impostor = ("human", str(uuid.uuid4()))
    made = uuid.uuid4()
    with pytest.raises(asyncpg.CheckViolationError):
        await world.seed.as_actor(
            world.tenant,
            impostor,
            "INSERT INTO decisions (id, tenant_id, card_id, option_key, rationale_sealed, "
            "seen_card_version, decided_by, actor_kind, actor_id) "
            "VALUES ($1, $2, $3, 'accept', '\\x01', 1, $4, 'human', $5)",
            made,
            world.tenant,
            world.card,
            world.person,
            str(world.person),  # the column names Hannah; the session is someone else
            at=T0,
        )
    assert await human_only_problems(world) == []
    await world.decision(world.hannah)  # the control: Hannah as herself is allowed


async def test_t03_t05_decision_rows_are_insert_only(
    migrated_db: MigratedDatabase, seed: Seeder
) -> None:
    world = await _world(seed)
    assert await insert_only_problems(world, migrated_db.app_url) == []
    assert await owner_problems(world.seed) == []


async def test_t03_t05_every_insert_only_table_refuses_update_and_delete(seed: Seeder) -> None:
    """The remaining insert-only tables: a write statement is refused even when it names no row
    the trigger would see, so the refusal is the table's, not an accident of an empty table."""
    found: list[str] = []
    for table in INSERT_ONLY:
        triggers = await seed.rows(
            "SELECT event_manipulation FROM information_schema.triggers "
            "WHERE event_object_table = $1 AND action_timing = 'BEFORE'",
            table,
        )
        events = {str(r["event_manipulation"]) for r in triggers}
        for verb in ("UPDATE", "DELETE"):
            granted = await seed.value(
                "SELECT has_table_privilege('abacus_app', $1, $2)", f"public.{table}", verb
            )
            if granted and verb not in events:
                found.append(f"{table}: {verb} is neither revoked nor refused by a trigger")
    assert found == []


async def test_t04_one_decision_per_card(seed: Seeder) -> None:
    world = await _world(seed)
    await world.decision(world.hannah)
    with pytest.raises(asyncpg.UniqueViolationError):
        await world.decision(world.hannah, "2026-09-14T09:45:00-05:00")


async def test_t05_undo_inside_ten_seconds_once_and_never_after(seed: Seeder) -> None:
    world = await _world(seed)
    approved = await world.proposal_decision(world.hannah)
    await world.proposal_decision(world.hannah, "2026-09-14T09:41:09-05:00", undoes=approved)
    with pytest.raises(asyncpg.PostgresError, match="undo_window_closed"):  # a second Undo
        await world.proposal_decision(world.hannah, "2026-09-14T09:41:09-05:00", undoes=approved)
    late = await world.proposal_decision(world.hannah, "2026-09-14T09:41:00-05:00")
    with pytest.raises(asyncpg.PostgresError, match="undo_window_closed"):
        await world.proposal_decision(world.hannah, "2026-09-14T09:41:11-05:00", undoes=late)


async def test_t05_undo_after_the_grant_was_consumed_is_refused(seed: Seeder) -> None:
    world = await _world(seed)
    grant = await world.grant()
    approved = await world.proposal_decision(world.hannah, grant=grant)
    await world.seed.run(  # the held effect started: the dispatcher consumed the grant
        "UPDATE approval_grants SET used_at = now(), consumer_ref = $2 WHERE id = $1",
        grant,
        uuid.uuid4(),
    )
    with pytest.raises(asyncpg.PostgresError, match=r"effect_started|undo_window_closed"):
        await world.proposal_decision(world.hannah, "2026-09-14T09:41:05-05:00", undoes=approved)


async def test_t05_a_suggestion_undo_follows_the_same_window(seed: Seeder) -> None:
    world = await _world(seed)
    adopted = await world.suggestion_decision(world.hannah)
    with pytest.raises(asyncpg.PostgresError, match="undo_window_closed"):
        await world.suggestion_decision(
            world.hannah, "2026-09-14T09:41:10.5-05:00", undoes=adopted
        )


async def test_t10_a_grant_settles_once_and_nothing_else_on_it_moves(seed: Seeder) -> None:
    world = await _world(seed)
    grant = await world.grant()
    with pytest.raises(asyncpg.PostgresError):
        await world.seed.run(
            "UPDATE approval_grants SET payload_sha256 = $2 WHERE id = $1", grant, _sha()
        )
    with pytest.raises(asyncpg.PostgresError):
        await world.seed.run(
            "UPDATE approval_grants SET not_before = not_before - interval '1 hour' WHERE id = $1",
            grant,
        )
    await world.seed.run("UPDATE approval_grants SET voided_at = now() WHERE id = $1", grant)
    with pytest.raises(asyncpg.PostgresError):  # voided, it can never be used
        await world.seed.run(
            "UPDATE approval_grants SET used_at = now(), consumer_ref = $2 WHERE id = $1",
            grant,
            uuid.uuid4(),
        )
    with pytest.raises(asyncpg.PostgresError):  # nor voided again
        await world.seed.run("UPDATE approval_grants SET voided_at = now() WHERE id = $1", grant)


# --- and the probes fail when a CHECK or a trigger is removed ------------------------------------


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def test_t13_the_human_only_probe_detects_a_removed_check(private_db: sc.Database) -> None:
    seed = _db_seed(private_db)

    async def run() -> list[str]:
        world = await _world(seed)
        assert await human_only_problems(world) == []
        rows = await seed.rows(
            "SELECT conrelid::regclass::text AS t, conname FROM pg_constraint "
            "WHERE conname LIKE '%human_only' AND conrelid::regclass::text = ANY($1)",
            [
                "sign_offs",
                "decisions",
                "checkpoint_decisions",
                "suggestion_decisions",
                "proposal_decisions",
            ],
        )
        assert len(rows) == 5
        for row in rows:
            await seed.run(f"ALTER TABLE {row['t']} DROP CONSTRAINT {row['conname']}")
        # 0213 (P-04-T23, DEC-506) added a second guard on `decisions`: `decided_by` must be the
        # transaction's actor, which no non-person actor id can be. It refuses the same writes, so
        # the probe reports a hole in `decisions` only once both guards are gone.
        # 0230 (P-04-T24, DEC-601) added the same second guard on both agent decision tables.
        partial = await human_only_problems(await _world(seed))
        for guarded in ("decisions", "suggestion_decisions", "proposal_decisions"):
            assert not any(p.startswith(f"{guarded}:") for p in partial), partial
        for guarded in ("decisions", "suggestion_decisions", "proposal_decisions"):
            await seed.run(f"ALTER TABLE {guarded} DROP CONSTRAINT {guarded}_decider_is_the_actor")
        return await human_only_problems(await _world(seed))

    found = asyncio.run(run())
    for table in (
        "sign_offs",
        "decisions",
        "checkpoint_decisions",
        "suggestion_decisions",
        "proposal_decisions",
    ):
        assert any(p.startswith(f"{table}: accepted from agent") for p in found), table


def test_t13_the_insert_only_probes_detect_a_removed_trigger_or_grant(
    private_db: sc.Database,
) -> None:
    seed = _db_seed(private_db)

    async def run() -> tuple[list[str], list[str]]:
        world = await _world(seed)
        assert await owner_problems(world.seed) == []
        assert await insert_only_problems(world, private_db.app_url) == []
        for table in TRIGGERED:
            await seed.run(f"ALTER TABLE {table} DISABLE TRIGGER USER")
        await seed.run("GRANT UPDATE, DELETE ON sign_offs TO abacus_app")
        again = await _world(seed)
        return await owner_problems(seed), await insert_only_problems(again, private_db.app_url)

    owner, app = asyncio.run(run())
    for table in TRIGGERED:
        assert f"{table}: UPDATE allowed to the owner" in owner, table
        assert f"{table}: DELETE allowed to the owner" in owner, table
    assert any(p.startswith("sign_offs: UPDATE allowed") for p in app)
    assert any(p.startswith("sign_offs: DELETE allowed") for p in app)
