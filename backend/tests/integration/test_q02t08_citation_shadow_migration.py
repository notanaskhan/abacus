"""Q-02-T08 (TASK-1210; migration 0158) on a private database: the back-fill marks citations a
shadow run wrote before 0158, and their relinked successors, and nothing else; after it, the
insert trigger keeps the flag right whatever the writer passed. The owner is held to row-level
security, so a back-fill that forgot to unforce it would change nothing (security review)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0157"


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _run(seed: Seeder, tenant: uuid.UUID, *, shadow: bool) -> uuid.UUID:
    made = uuid.uuid4()
    async with seed.held() as conn:
        await conn.execute("SET session_replication_role = replica")  # no firm, engagement
        await conn.execute(
            "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope, status, shadow, finished_at) VALUES ($1, $2, "
            "'evidence.upload_reviewer', 1, $3, $4, ARRAY['evidence.read'], 'completed', $5, "
            "now())",
            made,
            tenant,
            uuid.uuid4(),
            uuid.uuid4(),
            shadow,
        )
    return made


_INSERT = (
    "INSERT INTO citations (id, tenant_id, cited_from_type, cited_from_id, n, kind, source_type, "
    "source_id, locator, verified, verifier_version, supersedes_id, created_by_kind, "
    "created_by_run_id, created_by_user_id) VALUES ($1, $2, 'upload_review', $3, 1, "
    "'document_text', 'evidence_version', $4, '{}', true, 'v1', $5, $6, $7, $8)"
)
_INSERT_FLAGGED = (
    "INSERT INTO citations (id, tenant_id, cited_from_type, cited_from_id, n, kind, source_type, "
    "source_id, locator, verified, verifier_version, supersedes_id, created_by_kind, "
    "created_by_run_id, created_by_user_id, shadow) VALUES ($1, $2, 'upload_review', $3, 1, "
    "'document_text', 'evidence_version', $4, '{}', true, 'v1', $5, $6, $7, $8, $9)"
)


async def _citation(
    seed: Seeder,
    tenant: uuid.UUID,
    *,
    run: uuid.UUID | None,
    supersedes: uuid.UUID | None = None,
    shadow: bool | None = None,
) -> uuid.UUID:
    """A citation as its writer would insert it; `shadow` given only after 0158."""
    made = uuid.uuid4()
    args: list[object] = [
        made,
        tenant,
        uuid.uuid4(),
        uuid.uuid4(),
        supersedes,
        "agent" if run is not None else "human",
        run,
        None if run is not None else uuid.uuid4(),
    ]
    async with seed.held() as conn:
        if shadow is None:
            await conn.execute(_INSERT, *args)
        else:
            await conn.execute(_INSERT_FLAGGED, *args, shadow)
    return made


def test_the_back_fill_marks_shadow_runs_citations_and_their_successors(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    tenant = uuid.uuid4()

    async def before() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
        hidden_run = await _run(seed, tenant, shadow=True)
        live_run = await _run(seed, tenant, shadow=False)
        hidden = await _citation(seed, tenant, run=hidden_run)
        moved = await _citation(seed, tenant, run=None, supersedes=hidden)  # a person's relink
        live = await _citation(seed, tenant, run=live_run)
        human = await _citation(seed, tenant, run=None)
        return hidden, moved, live, human

    hidden, moved, live, human = asyncio.run(before())
    migrate(private_db.owner_url, "head")
    rows = asyncio.run(seed.rows("SELECT id, shadow FROM citations WHERE tenant_id = $1", tenant))
    assert {r["id"]: r["shadow"] for r in rows} == {
        hidden: True,
        moved: True,
        live: False,
        human: False,
    }


def test_the_insert_trigger_follows_the_run_and_the_predecessor(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, "head")
    tenant = uuid.uuid4()

    async def scenario() -> dict[uuid.UUID, bool]:
        hidden_run = await _run(seed, tenant, shadow=True)
        live_run = await _run(seed, tenant, shadow=False)
        forgot = await _citation(seed, tenant, run=hidden_run, shadow=False)
        successor = await _citation(seed, tenant, run=None, supersedes=forgot, shadow=False)
        live = await _citation(seed, tenant, run=live_run, shadow=False)
        rows = await seed.rows("SELECT id, shadow FROM citations WHERE tenant_id = $1", tenant)
        found = {r["id"]: r["shadow"] for r in rows}
        assert found == {forgot: True, successor: True, live: False}
        return found

    asyncio.run(scenario())
