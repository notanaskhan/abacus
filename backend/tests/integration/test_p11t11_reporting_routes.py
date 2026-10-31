"""P-11-T11 (TASK-2513; C11 v1; P-11 §4.3; SPEC-520 AC-14, AC-17 to AC-19, AC-22, AC-23, AC-26)
against Postgres: the generated-document routes, the render job and the sealed snapshot.

The row's acceptance: a walled user gets 404 with no count, a client principal is refused on
every reporting route (404, the frozen C11 order; DEC-1561), and regenerate from an agent or
worker context is refused. Also: the version's snapshot is sealed with it (0522) and insert-only;
the render job records the files and the field regions once and fails with its code; compare and
changes read the sealed values; regenerate is idempotent per key and refused once locked.

The kind is a probe (`notice_response`) with synthetic values; the template version's parts come
from a stub of methodology's read, and the renderer is stubbed (the isolated child's engine is
P-11-T07's, proven by its own tests).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator, Mapping
from types import SimpleNamespace
from typing import cast

import asyncpg
import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.evidence import storage
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.reporting import api as c11
from abacus.modules.reporting import documents as docs
from abacus.modules.reporting import reads, render_job
from abacus.modules.reporting.render.core import LocatedOutput, RenderInput, RenderOutput
from abacus.modules.reporting.render.head import RenderRefused as RenderingRefused
from abacus.modules.reporting.render.regions import PageSize, Region

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

MASTER = b"reporting-routes-master-key-0123456789"
BUCKET = f"evidence-reporting-{uuid.uuid4().hex[:12]}"
KIND = "notice_response"
DECLARED = ("client.name", "notice.number")
PDF = b"%PDF-1.7\n% probe render for the routes\n"
BODY: list[object] = [
    {
        "type": "paragraph",
        "runs": [{"type": "text", "text": "Re notice"}, {"type": "var", "key": "notice.number"}],
    },
    {"type": "clause", "clause_id": "fees", "enabled": True, "non_standard": False, "blocks": []},
]
CLAUSES: list[object] = [
    {
        "clause_id": "fees",
        "title": "Fees",
        "default_enabled": True,
        "standard": [
            {
                "type": "paragraph",
                "runs": [
                    {"type": "text", "text": "Prepared for"},
                    {"type": "var", "key": "client.name"},
                ],
            }
        ],
    }
]
VARIABLES = (
    {"key": "client.name", "label": "Client name", "value_type": "name"},
    {"key": "notice.number", "label": "Notice number", "value_type": "text"},
)


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def configured(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> object:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


class Probe:
    def __init__(self) -> None:
        self.values: dict[str, str] = {"client.name": "Probe client", "notice.number": "N-1"}
        self.renders = 0
        self.refuse: str | None = None


@pytest.fixture(autouse=True)
def probe(monkeypatch: pytest.MonkeyPatch) -> Iterator[Probe]:
    state = Probe()

    async def provider(owner: c11.OwnerRef, scope: c11.RenderScope) -> Mapping[str, str]:
        return dict(state.values)

    async def approval(ref: c11.ApprovalRef) -> tuple[uuid.UUID, str] | None:
        return None

    async def keys(session: object, version_id: uuid.UUID) -> tuple[str, ...]:
        return DECLARED

    async def parts(session: object, version_id: uuid.UUID) -> object:
        return SimpleNamespace(
            version_id=version_id,
            layout_key="letter",
            body=BODY,
            clauses=CLAUSES,
            variable_keys=DECLARED,
            template_name="Probe notice response v1",
            version_no=1,
            variables=VARIABLES,
            template_id=uuid.UUID(int=7),
            sample_data={},
        )

    def located(request: RenderInput) -> LocatedOutput:
        state.renders += 1
        if state.refuse is not None:
            raise RenderingRefused(state.refuse)
        values = request.values
        return LocatedOutput(
            RenderOutput(PDF, 1, hashlib.sha256(PDF).hexdigest(), ()),
            (Region("notice.number", 1, 1, (72.0, 100.0, 120.0, 112.0), values["notice.number"]),),
            (PageSize(612.0, 792.0),),
        )

    async def flag_on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(docs, "report_template_variable_keys", keys)
    monkeypatch.setattr(reads, "report_template_parts", parts)
    monkeypatch.setattr(render_job, "report_template_parts", parts)
    monkeypatch.setattr(render_job, "render_located_isolated", located)
    monkeypatch.setattr(reads, "flag_enabled", flag_on)
    monkeypatch.setattr(c11, "_REGISTRY", {})
    c11.register_document_kind(
        c11.DocumentKind(
            kind=KIND, layout="letter", variables_provider=provider, approval_provider=approval
        )
    )
    yield state


async def _world(seed: Seeder) -> tuple[Person, uuid.UUID, uuid.UUID]:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    client = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    return partner, engagement, client


async def _draft(who: Person, engagement: uuid.UUID, client: uuid.UUID) -> uuid.UUID:
    async with uow(TenantContext(who.tenant_id, "human", str(who.user_id))) as tx:
        ticket = await c11.render(
            tx,
            c11.RenderRequest(
                kind=KIND,
                owner_ref=c11.OwnerRef("notice", uuid.uuid4()),
                scope=c11.RenderScope(client_id=client, engagement_id=engagement),
                template_version_id=uuid.uuid4(),
                requested_by=c11.Requester("human", user_id=who.user_id),
            ),
        )
    return ticket.generated_document_id


def _client_ctx(who: Person) -> AuthContext:
    ctx = who.context()
    return AuthContext(
        tenant=ctx.tenant,
        user_id=ctx.user_id,
        membership_id=ctx.membership_id,
        firm_role=None,
        mfa_at=ctx.mfa_at,
        client=True,
    )


async def _every_route(ctx: AuthContext, document_id: uuid.UUID) -> list[type[object]]:
    refused: list[type[object]] = []
    calls = (
        lambda: reads.read(ctx, document_id),
        lambda: reads.fields(ctx, document_id, 1),
        lambda: reads.compare(ctx, document_id, 1, "standard"),
        lambda: reads.changes(ctx, document_id),
        lambda: reads.regenerate(ctx, document_id, f"key-{uuid.uuid4().hex}"),
        lambda: reads.preview(ctx, uuid.uuid4(), 1),
    )
    for call in calls:
        try:
            await call()
        except (NotFound, Forbidden, reads.NotAPerson) as error:
            refused.append(type(error))
        else:
            refused.append(type(None))
    return refused


async def test_ac26_a_walled_person_gets_404_with_no_count(seed: Seeder) -> None:
    partner, engagement, client = await _world(seed)
    walled = await seed.person(partner.tenant_id)
    await seed.member(engagement, walled, "manager")
    document_id = await _draft(partner, engagement, client)
    await reads.read(walled.context(), document_id)  # a team member reads it before the wall
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        partner.tenant_id,
        walled.user_id,
        client,
        partner.user_id,
    )
    refused = await _every_route(walled.context(), document_id)
    assert refused[:5] == [NotFound] * 5  # the document routes: 404, never 403
    with pytest.raises(NotFound) as missing:
        await reads.read(walled.context(), document_id)
    assert str(document_id) not in str(missing.value)


async def test_ac26_a_client_principal_is_refused_on_every_reporting_route(seed: Seeder) -> None:
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    assert await _every_route(_client_ctx(partner), document_id) == [NotFound] * 6


async def test_ac18_regenerate_from_an_agent_or_worker_context_is_refused(seed: Seeder) -> None:
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    for kind in ("system", "agent"):
        ctx = partner.context()
        other = AuthContext(
            tenant=TenantContext(partner.tenant_id, kind, f"{kind}-actor"),
            user_id=ctx.user_id,
            membership_id=ctx.membership_id,
            firm_role=None,
            mfa_at=ctx.mfa_at,
        )
        with pytest.raises(reads.NotAPerson):
            await reads.regenerate(other, document_id, f"key-{uuid.uuid4().hex}")
    with pytest.raises(c11.RenderRefused):
        async with uow(TenantContext(partner.tenant_id, "system", "worker")) as tx:
            await c11.regenerate(tx, document_id, c11.Requester("system"))
    versions = await seed.value(
        "SELECT count(*) FROM generated_document_versions WHERE generated_document_id = $1",
        document_id,
    )
    assert versions == 1


async def test_the_snapshot_is_sealed_with_the_version_and_never_changes(seed: Seeder) -> None:
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    row = await seed.rows(
        "SELECT s.snapshot::text AS snap, s.snapshot_sha256, v.snapshot_sha256 AS version_sha "
        "FROM generated_document_snapshots s JOIN generated_document_versions v "
        "ON v.id = s.version_id WHERE v.generated_document_id = $1",
        document_id,
    )
    assert len(row) == 1 and row[0]["snapshot_sha256"] == row[0]["version_sha"]
    assert "N-1" in row[0]["snap"]
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("UPDATE generated_document_snapshots SET snapshot = '{}'::jsonb")


async def test_the_render_job_records_files_and_regions_once(seed: Seeder, probe: Probe) -> None:
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    event = OutboxEvent(
        event_id=uuid.uuid4(),
        tenant_id=partner.tenant_id,
        event_type=c11.RENDER_REQUESTED,
        payload={"generated_document_id": str(document_id), "version_no": 1},
    )
    await c11.SUBSCRIPTIONS[c11.RENDER_REQUESTED](event)
    await c11.SUBSCRIPTIONS[c11.RENDER_REQUESTED](event)  # redelivery: no second render
    assert probe.renders == 1
    out = await reads.read(partner.context(), document_id)
    assert out.status == "draft" and out.current_version == 1
    (version,) = out.versions
    assert [f.format for f in version.files] == ["pdf"]
    assert version.files[0].render_hash == hashlib.sha256(PDF).hexdigest()
    assert version.requested_by.kind == "human" and version.requested_by.label == "Test person"
    assert out.allowed_actions == ["regenerate"]
    regions = await reads.fields(partner.context(), document_id, 1)
    assert [(r.field_key, r.page, r.value_text) for r in regions.items] == [
        ("notice.number", 1, "N-1")
    ]
    assert regions.items[0].match_id.startswith("gd:")


async def test_a_refused_render_fails_the_job_with_its_code(seed: Seeder, probe: Probe) -> None:
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    probe.refuse = "missing_glyph"
    await render_job.run(partner.tenant_id, document_id, 1)
    job = await seed.rows(
        "SELECT status, failure_code FROM render_jobs WHERE generated_document_id = $1",
        document_id,
    )
    assert [(j["status"], j["failure_code"]) for j in job] == [("failed", "missing_glyph")]
    events = await seed.value(
        "SELECT count(*) FROM generated_document_events WHERE generated_document_id = $1 "
        "AND kind = 'render_failed'",
        document_id,
    )
    assert events == 1
    assert (
        await seed.value(
            "SELECT count(*) FROM generated_document_files f JOIN generated_document_versions v "
            "ON v.id = f.version_id WHERE v.generated_document_id = $1",
            document_id,
        )
        == 0
    )
    assert "generated_document.render_failed" in await seed.actions(partner.tenant_id)


async def test_ac17_ac23_changes_regenerate_and_compare(seed: Seeder, probe: Probe) -> None:
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    ctx = partner.context()
    assert (await reads.changes(ctx, document_id)).items == []
    probe.values["notice.number"] = "N-2"
    (changed,) = (await reads.changes(ctx, document_id)).items
    assert (changed.key, changed.label, changed.was, changed.now, changed.masked) == (
        "notice.number",
        "Notice number",
        "N-1",
        "N-2",
        False,
    )
    key = f"key-{uuid.uuid4().hex}"
    first = await reads.regenerate(ctx, document_id, key)
    again = await reads.regenerate(ctx, document_id, key)  # the same key: the same answer
    assert (first.version_no, again.version_no) == (2, 2)
    diff = await reads.compare(ctx, document_id, 2, "1")
    ops = [(o.op, o.text) for b in diff.blocks for o in b.ops if o.op != "equal"]
    assert ops == [("delete", "N-1"), ("insert", "N-2")]
    assert {b.block_id for b in diff.blocks} == {"block:1", "clause:fees"}
    standard = await reads.compare(ctx, document_id, 2, "standard")
    assert all(o.op == "equal" for b in standard.blocks for o in b.ops)
    assert "generated_document.regenerated" in await seed.actions(partner.tenant_id)


async def test_ac19_a_locked_document_takes_no_regenerate(seed: Seeder) -> None:
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    async with uow(TenantContext(partner.tenant_id, "system", "consumer")) as tx:
        await c11.lock(tx, document_id, "envelope:completed")
    out = await reads.read(partner.context(), document_id)
    assert out.status == "locked" and out.allowed_actions == []
    with pytest.raises(reads.DocumentLocked):
        await reads.regenerate(partner.context(), document_id, f"key-{uuid.uuid4().hex}")


async def test_a_masked_change_never_shows_a_tin(seed: Seeder, probe: Probe) -> None:
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    probe.values["client.name"] = "Probe client 123-45-6789"
    (changed,) = (await reads.changes(partner.context(), document_id)).items
    assert (changed.was, changed.now, changed.masked) == (None, None, True)
