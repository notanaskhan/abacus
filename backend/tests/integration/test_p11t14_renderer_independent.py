# ac-test-author: ayushkbhatia
"""P-11-T14 (ADR-078; TASK-2526; SPEC-520 AC-15, AC-16, AC-26, AC-27; INV-1, INV-3, INV-4,
INV-5): the renderer's independent suite against Postgres, written from the SPEC and C11 v1
rather than the code. The image-bound half (fetcher, escaping, bytes, watermark) is
`tests/golden_render/test_p11t14_renderer_independent.py`.

The row's acceptance: "Every rule is proven by tests written outside the implementing session
and all pass against the merged renderer." Here:

- INV-1: an agent's render is a draft at the service and at the database; a final is a person's.
- The final-render rule: no final without a person's approval of this draft's hash.
- Insert-only: versions, files, fields, events and snapshots refuse UPDATE and DELETE.
- INV-3, INV-4: a walled person and a client principal get nothing.
- INV-5: every audit row of a render names its actor, and the agent's names its person.

The probe kind and its fixtures are P-11-T08's (`notice_response`, synthetic values).
"""

from __future__ import annotations

import uuid
from typing import cast

import asyncpg
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.reporting import api as c11
from abacus.modules.reporting import reads

from .agent_tests.support import Seeder
from .test_p11t08_render_service import Values, _request, _world, engines, seed, values
from .test_p11t11_reporting_routes import _client_ctx, _draft
from .test_p11t11_reporting_routes import _world as _team_world

__all__ = ["engines", "seed", "values"]

INSERT_ONLY = (
    "generated_document_versions",
    "generated_document_files",
    "generated_document_fields",
    "generated_document_events",
    "generated_document_snapshots",
)


async def _agent_draft(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant, user, client = await _world(seed)
    run = uuid.uuid4()
    agent = c11.Requester("agent", run_id=run, on_behalf_of_user_id=user)
    async with uow(TenantContext(tenant, "agent", f"agent:drafter:{run}", user)) as tx:
        ticket = await c11.render(tx, _request(client, uuid.uuid4(), agent))
    return tenant, user, run, ticket.generated_document_id


async def test_inv1_an_agent_never_holds_a_final_at_the_service_or_the_database(
    seed: Seeder, values: Values
) -> None:
    tenant, user, run, document = await _agent_draft(seed)
    agent = c11.Requester("agent", run_id=run, on_behalf_of_user_id=user)
    approval = c11.ApprovalRef("probe", uuid.uuid4(), "a" * 64)
    with pytest.raises(c11.RenderRefused):
        c11.check_render_request(
            _request(uuid.uuid4(), uuid.uuid4(), agent, mode="final", approval_ref=approval)
        )
    for kind in ("system",):
        with pytest.raises(c11.RenderRefused):
            async with uow(TenantContext(tenant, "system", "reporting:planted")) as tx:
                await c11.render_final(tx, document, approval, c11.Requester(kind))  # type: ignore[arg-type]  # a planted non-person
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO generated_document_versions (tenant_id, generated_document_id, "
            "version_no, mode, layout_key, layout_version, snapshot_key, snapshot_sha256, "
            "content_hash, engine_version, approval_ref, requested_by_kind, "
            "requested_by_run_id) SELECT tenant_id, generated_document_id, 9, 'final', "
            "layout_key, layout_version, snapshot_key, snapshot_sha256, content_hash, "
            "engine_version, jsonb_build_object('kind', 'probe', 'id', gen_random_uuid(), "
            "'content_hash', content_hash, 'approver_user_id', $2::uuid), 'agent', $3 "
            "FROM generated_document_versions WHERE generated_document_id = $1",
            document,
            user,
            run,
        )


async def test_a_final_needs_a_persons_approval_of_this_drafts_hash(
    seed: Seeder, values: Values
) -> None:
    tenant, user, client = await _world(seed)
    person = c11.Requester("human", user_id=user)
    ctx = TenantContext(tenant, "human", str(user))
    async with uow(ctx) as tx:
        ticket = await c11.render(tx, _request(client, uuid.uuid4(), person))
    drafted = cast(
        str,
        await seed.value(
            "SELECT content_hash FROM generated_document_versions WHERE generated_document_id = $1",
            ticket.generated_document_id,
        ),
    )
    # A stale hash is refused too (409), but here the hash is right and no person approved it.
    approval = c11.ApprovalRef("probe", uuid.uuid4(), drafted)
    values.approved = None
    with pytest.raises(c11.RenderRefused) as refused:
        async with uow(ctx) as tx:
            await c11.render_final(tx, ticket.generated_document_id, approval, person)
    assert refused.value.code == "final_requires_approval"
    finals = await seed.value(
        "SELECT count(*) FROM generated_document_versions WHERE generated_document_id = $1 "
        "AND mode = 'final'",
        ticket.generated_document_id,
    )
    assert finals == 0


async def test_versions_files_fields_events_and_snapshots_are_insert_only(
    seed: Seeder, values: Values
) -> None:
    _tenant, _user, _run, document = await _agent_draft(seed)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(
            "UPDATE generated_document_versions SET engine_version = 'x' "
            "WHERE generated_document_id = $1",
            document,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(
            "DELETE FROM generated_document_versions WHERE generated_document_id = $1", document
        )
    guarded = await seed.rows(
        "SELECT c.relname, t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE NOT t.tgisinternal AND c.relname = ANY($1::text[]) "
        "AND t.tgfoid = 'reporting_rows_immutable'::regproc",
        list(INSERT_ONLY),
    )
    assert {r["relname"] for r in guarded} == set(INSERT_ONLY)
    for table in INSERT_ONLY:
        assert any(r["tgname"] == f"{table}_immutable" for r in guarded), table


async def test_inv5_every_audit_row_of_a_render_names_its_actor(
    seed: Seeder, values: Values
) -> None:
    tenant, user, run, _document = await _agent_draft(seed)
    rows = await seed.rows(
        "SELECT actor_kind, actor_id, on_behalf_of_user_id FROM audit_events "
        "WHERE tenant_id = $1 AND action LIKE 'generated_document%'",
        tenant,
    )
    assert rows, "the render is audited"
    for row in rows:
        assert row["actor_kind"] == "agent" and str(run) in str(row["actor_id"])
        assert row["on_behalf_of_user_id"] == user  # "<person> via Agent"


async def test_inv3_inv4_a_walled_person_and_a_client_get_nothing(
    seed: Seeder, values: Values
) -> None:
    partner, engagement, client = await _team_world(seed)
    document = await _draft(partner, engagement, client)
    walled = await seed.person(partner.tenant_id)
    await seed.member(engagement, walled, "manager")
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        partner.tenant_id,
        walled.user_id,
        client,
        partner.user_id,
    )
    for ctx in (walled.context(), _client_ctx(partner)):
        with pytest.raises(NotFound):
            await reads.read(ctx, document)
        with pytest.raises(NotFound):
            await reads.fields(ctx, document, 1)
    found = cast(
        int, await seed.value("SELECT count(*) FROM generated_documents WHERE id = $1", document)
    )
    assert found == 1  # it exists; they are told nothing
