"""Q-02-T22: independent acceptance tests (ADR-078) for actor attribution, the dormant policy
actor, the human-only guard and `access_events`, against Postgres.

Written from the plan, not from the code: Q-02 §3.3 AC-15, AC-16 and AC-17, §3.5 AC-23 and AC-25,
§5's migration rows for `NNNN_audit_attribution`, `NNNN_human_only_guard` and `NNNN_access_events`,
and the epic's INV-5 ("every Q-02 audit event names a person, '<person> via Agent', or the
system"). Each rule is met with a seeded violation and a control that the same write is allowed
when the rule holds, so a test cannot pass by refusing everything.

The register of human-only actions is `docs/architecture/human-only-actions.yaml`, the AC's own
source. Where the code does not yet meet the plan, the test is a strict xfail naming the gap.
Seeding runs as the superuser through the shared `Seeder`; behaviour under test runs as the app
role (`uow`, `tenant_session`, `record_reads`, `create_app()`). Every value is synthetic.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import asyncpg
import httpx
import pytest
import yaml
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from types_boto3_s3 import S3Client

from abacus.api import create_app
from abacus.kernel.access import AccessSubject, record_reads, register_access_kind
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import (
    ActorKind,
    TenantContext,
    configure_engine,
    dispose_engine,
    tenant_session,
)
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import Target, uow
from abacus.modules.evidence import storage
from abacus.modules.identity.api import (
    agent_context_for_run,
    configure_verifier,
    reset_verifier,
    system_context_for_run,
)
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.quality import banned_patterns

from .agent_tests.support import Migrated, Person, Seeder

REPO = Path(__file__).resolve().parents[3]
REGISTER = REPO / "docs/architecture/human-only-actions.yaml"
HUMAN_ONLY: tuple[str, ...] = tuple(
    str(entry["action"])
    for entry in cast(
        list[dict[str, object]],
        cast(dict[str, object], yaml.safe_load(REGISTER.read_text(encoding="utf-8")))["actions"],
    )
)
# An audit row in a transaction that carries its tenant, actor and (AC-15) the person it acts
# for, as `app.on_behalf_of`: what the unit of work's transaction would carry.
AUDIT = (
    "WITH s AS (SELECT set_config('app.on_behalf_of', coalesce($8::text, ''), true) AS v) "
    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, target_id, "
    "on_behalf_of_user_id, policy_ref) "
    "SELECT $1::uuid, $2::text, $3::text, $4::text, 'probe', $5::text, $6::uuid, $7::text FROM s"
)
NEUTRAL = "probe.recorded"  # an action on no list: what any actor may record
POLICY_REF = "policy:thresholds:v1"
MARKER = "HOSTILE-MARKER-6620"
SSN = "900-12-3456"
PROBE_KIND = "probe_acceptance.read"
register_access_kind(PROBE_KIND, ["restricted"])


# --- fixtures -----------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
def owner(migrated_db: Migrated) -> Seeder:
    """The schema owner: a role that is neither the app nor the superuser."""
    return Seeder(migrated_db.owner_url.replace("postgresql+asyncpg://", "postgresql://", 1))


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    person: Person


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    return Firm(tenant_id, await seed.person(tenant_id))


async def _rows(
    seed: Seeder, tenant_id: uuid.UUID, action: str = NEUTRAL
) -> list[dict[str, object]]:
    rows = await seed.rows(
        "SELECT actor_kind, actor_id, on_behalf_of_user_id, policy_ref FROM audit_events "
        "WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
        tenant_id,
        action,
    )
    return [dict(r) for r in rows]


async def _record(ctx: TenantContext, action: str = NEUTRAL) -> None:
    async with uow(ctx) as tx:
        tx.record(action, target=Target("probe", uuid.uuid4()))


def _actor(kind: str) -> tuple[str, str]:
    return kind, f"{kind}:probe:{uuid.uuid4()}"


# --- INV-5: the grammar's facts, per actor kind (AC-15, AC-16) -----------------------------------


async def test_q02_t22_a_persons_row_names_the_person(seed: Seeder, firm: Firm) -> None:
    ctx = TenantContext(firm.tenant_id, "human", str(firm.person.user_id))
    await _record(ctx)
    [row] = await _rows(seed, firm.tenant_id)
    assert row["actor_kind"] == "human"
    assert uuid.UUID(str(row["actor_id"])) == firm.person.user_id


async def test_q02_t22_an_agents_row_names_the_person_it_acted_for(
    seed: Seeder, firm: Firm
) -> None:
    """AC-15: "Ana Cruz via Agent", from the run the agent was issued for."""
    run_id = uuid.uuid4()
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=run_id,
        agent_id="evidence.screener",
        engagement_id=None,
        task_scope=frozenset(),
        initiator_user_id=firm.person.user_id,
    )
    await _record(agent.tenant)
    [row] = await _rows(seed, firm.tenant_id)
    assert row["actor_kind"] == "agent"
    assert row["on_behalf_of_user_id"] == firm.person.user_id
    assert str(run_id) in str(row["actor_id"])  # which run, so the trace can be followed
    assert str(firm.person.user_id) not in str(row["actor_id"])  # the agent is not the person


async def test_q02_t22_a_system_row_names_the_person_its_run_is_for(
    seed: Seeder, firm: Firm
) -> None:
    run_id = uuid.uuid4()
    system = system_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=run_id,
        engagement_id=uuid.uuid4(),
        on_behalf_of=firm.person.user_id,
    )
    await _record(system.tenant)
    [row] = await _rows(seed, firm.tenant_id)
    assert row["actor_kind"] == "system"
    assert row["on_behalf_of_user_id"] == firm.person.user_id
    assert str(run_id) in str(row["actor_id"])


async def test_q02_t22_a_support_row_names_its_session(seed: Seeder, firm: Firm) -> None:
    session_id = uuid.uuid4()
    await _record(TenantContext(firm.tenant_id, "support", f"support:{session_id}"))
    [row] = await _rows(seed, firm.tenant_id)
    assert row["actor_kind"] == "support"
    assert str(session_id) in str(row["actor_id"])


async def test_q02_t22_an_agent_row_without_a_person_is_refused(seed: Seeder, firm: Firm) -> None:
    agent = _actor("agent")
    with pytest.raises(asyncpg.CheckViolationError):
        await _audit(seed, firm.tenant_id, agent, NEUTRAL)
    # The control: the same row naming its person is written.
    await _audit(seed, firm.tenant_id, agent, NEUTRAL, firm.person.user_id)
    assert len(await _rows(seed, firm.tenant_id)) == 1


async def test_q02_t22_the_unit_of_work_cannot_commit_an_agent_row_without_a_person(
    seed: Seeder, firm: Firm
) -> None:
    """Through the app role: a context that names no person never gets an agent row in."""
    orphan = TenantContext(firm.tenant_id, "agent", f"agent:probe:{uuid.uuid4()}")
    with pytest.raises(DBAPIError):
        await _record(orphan)
    assert await _rows(seed, firm.tenant_id) == []


async def _audit(
    seed: Seeder,
    tenant_id: uuid.UUID,
    actor: tuple[str, str],
    action: str,
    person: uuid.UUID | None = None,
    ref: str | None = None,
    *,
    transaction_person: uuid.UUID | None = None,
) -> None:
    """One audit row written straight to the database. Its transaction acts for `person` unless
    `transaction_person` names someone else."""
    acting = transaction_person or person
    await seed.as_actor(
        tenant_id,
        actor,
        AUDIT,
        tenant_id,
        *actor,
        action,
        str(uuid.uuid4()),
        person,
        ref,
        None if acting is None else str(acting),
    )


async def test_q02_t22_an_agent_row_naming_its_transactions_person_is_written(
    seed: Seeder, firm: Firm
) -> None:
    await _audit(seed, firm.tenant_id, _actor("agent"), NEUTRAL, firm.person.user_id)
    [row] = await _rows(seed, firm.tenant_id)
    assert row["on_behalf_of_user_id"] == firm.person.user_id


async def test_q02_t22_an_agent_row_names_the_transactions_person_and_no_other(
    seed: Seeder, firm: Firm
) -> None:
    other = await seed.person(firm.tenant_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await _audit(
            seed,
            firm.tenant_id,
            _actor("agent"),
            NEUTRAL,
            other.user_id,
            transaction_person=firm.person.user_id,
        )
    assert await _rows(seed, firm.tenant_id) == []


async def test_q02_t22_a_policy_row_needs_its_policy(seed: Seeder, firm: Firm) -> None:
    """AC-16: the dormant `policy` actor names the published policy it applied."""
    policy = _actor("policy")
    for missing in (None, ""):
        with pytest.raises(asyncpg.CheckViolationError):
            await _audit(seed, firm.tenant_id, policy, NEUTRAL, None, missing)
    await _audit(seed, firm.tenant_id, policy, NEUTRAL, None, POLICY_REF)
    [row] = await _rows(seed, firm.tenant_id)
    assert (row["actor_kind"], row["policy_ref"]) == ("policy", POLICY_REF)


async def test_q02_t22_a_policy_context_built_outside_the_kernel_records_nothing(
    seed: Seeder, firm: Firm
) -> None:
    """AC-16: dormant. A module that forges a policy context gets no audit row in."""
    forged = TenantContext(firm.tenant_id, cast(ActorKind, "policy"), "policy:forged")
    with pytest.raises(DBAPIError):
        await _record(forged)
    assert await _rows(seed, firm.tenant_id) == []


def test_q02_t22_a_banned_pattern_refuses_a_policy_context_in_a_module(tmp_path: Path) -> None:
    module = tmp_path / "src/abacus/modules/engagements/service.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "from abacus.kernel.db import TenantContext\n\n\n"
        "def as_policy(tenant):\n"
        '    return TenantContext(tenant, "policy", "policy:thresholds:v1")\n',
        encoding="utf-8",
    )
    found = banned_patterns.scan(tmp_path)
    assert any(v.path.endswith("engagements/service.py") and v.line == 5 for v in found), found


# --- the human-only guard (AC-17) ---------------------------------------------------------------


def test_q02_t22_the_register_holds_the_acs_examples() -> None:
    for action in (
        "sign_off.recorded",
        "report.released",
        "evidence.accepted",
        "legal_hold.placed",
        "firm_export.approved",
        "firm.ai_client_data_opted_in",
    ):
        assert action in HUMAN_ONLY, action
    assert len(set(HUMAN_ONLY)) == len(HUMAN_ONLY)


@pytest.mark.parametrize("kind", ["agent", "policy"])
@pytest.mark.parametrize("action", HUMAN_ONLY)
async def test_q02_t22_every_listed_action_is_refused_to_agent_and_policy(
    seed: Seeder, firm: Firm, kind: str, action: str
) -> None:
    """At the database, independently of the permission matrix: the row is otherwise valid (it
    names its person or its policy), so only the guard can refuse it."""
    actor = _actor(kind)
    person = firm.person.user_id if kind == "agent" else None
    ref = POLICY_REF if kind == "policy" else None
    with pytest.raises(asyncpg.PostgresError) as raised:
        await _audit(seed, firm.tenant_id, actor, action, person, ref)
    assert not isinstance(raised.value, asyncpg.CheckViolationError), raised.value
    assert await _rows(seed, firm.tenant_id, action) == []
    # The control: the same actor may record an action on no list.
    await _audit(seed, firm.tenant_id, actor, NEUTRAL, person, ref)
    assert len(await _rows(seed, firm.tenant_id)) == 1


async def test_q02_t22_a_person_may_record_every_listed_action(seed: Seeder, firm: Firm) -> None:
    human = ("human", str(firm.person.user_id))
    for action in HUMAN_ONLY:
        await _audit(seed, firm.tenant_id, human, action)
    for action in HUMAN_ONLY:
        assert len(await _rows(seed, firm.tenant_id, action)) == 1, action


@pytest.mark.parametrize("action", ["sign_off.recorded", "report.released", "evidence.accepted"])
async def test_q02_t22_an_agent_context_cannot_commit_a_listed_action(
    seed: Seeder, firm: Firm, action: str
) -> None:
    """Through the unit of work as the app role: the transaction raises and nothing commits."""
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="evidence.screener",
        engagement_id=None,
        task_scope=frozenset({"evidence.accept", "sign_off.record", "report.release"}),
        initiator_user_id=firm.person.user_id,
    )
    with pytest.raises(DBAPIError):
        await _record(agent.tenant, action)
    assert await _rows(seed, firm.tenant_id, action) == []


async def test_q02_t22_a_persons_decision_cannot_be_rewritten_as_an_agents(
    seed: Seeder, firm: Firm
) -> None:
    human = ("human", str(firm.person.user_id))
    await _audit(seed, firm.tenant_id, human, "sign_off.recorded", None, None)
    with pytest.raises(asyncpg.PostgresError):
        await seed.run(
            "UPDATE audit_events SET actor_kind = 'agent', actor_id = 'agent:probe:x', "
            "on_behalf_of_user_id = $2 WHERE tenant_id = $1 AND action = 'sign_off.recorded'",
            firm.tenant_id,
            firm.person.user_id,
        )
    [row] = await _rows(seed, firm.tenant_id, "sign_off.recorded")
    assert row["actor_kind"] == "human"


# --- access_events: identifier-only rows (AC-23) -------------------------------------------------


IDENTIFIER_TYPES = frozenset({"uuid", "bigint", "smallint", "timestamp with time zone"})
# The text columns the plan's table has, each constrained to a closed vocabulary or an identifier.
NAMED_TEXT = frozenset({"actor_kind", "kind", "subject_type", "flags"})


async def test_q02_t22_access_events_has_no_column_for_a_name_quote_or_value(seed: Seeder) -> None:
    rows = await seed.rows(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'access_events'"
    )
    free = sorted(
        str(r["column_name"])
        for r in rows
        if r["data_type"] not in IDENTIFIER_TYPES and r["column_name"] not in NAMED_TEXT
    )
    assert free == []


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("kind", f"evidence_content.read {SSN}"),
        ("kind", "Bank statement.pdf"),
        ("subject_type", "Q4 bank statement.pdf"),
        ("subject_type", SSN),
        ("flags", [SSN]),
        ("flags", ["restricted", MARKER]),
        ("actor_kind", "Ana Cruz"),
    ],
)
async def test_q02_t22_free_text_never_fits_an_access_row(
    seed: Seeder, firm: Firm, column: str, value: object
) -> None:
    """A seeded violation of each constrained column, written as the superuser: refused."""
    values: dict[str, object] = {
        "actor_kind": "human",
        "kind": PROBE_KIND,
        "subject_type": "evidence_version",
        "flags": ["restricted"],
    }
    values[column] = value
    human = ("human", str(firm.person.user_id))
    with pytest.raises(asyncpg.PostgresError):
        await seed.as_actor(
            firm.tenant_id,
            human,
            "INSERT INTO access_events (tenant_id, actor_kind, actor_id, kind, subject_type, "
            "subject_id, flags) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            firm.tenant_id,
            values["actor_kind"],
            firm.person.user_id,
            values["kind"],
            values["subject_type"],
            uuid.uuid4(),
            values["flags"],
        )


async def test_q02_t22_the_writer_refuses_a_subject_that_is_not_an_identifier(firm: Firm) -> None:
    ctx = TenantContext(firm.tenant_id, "human", str(firm.person.user_id))
    for subject_type in ("Q4 bank statement.pdf", SSN, MARKER):
        with pytest.raises(ValueError):
            await record_reads(ctx, PROBE_KIND, [AccessSubject(subject_type, uuid.uuid4())])
    with pytest.raises(ValueError):
        await record_reads(
            ctx, "free text kind", [AccessSubject("evidence_version", uuid.uuid4())]
        )
    with pytest.raises(ValueError):
        await record_reads(
            ctx, PROBE_KIND, [AccessSubject("evidence_version", uuid.uuid4())], flags=[SSN]
        )


async def test_q02_t22_the_writer_writes_one_identifier_only_row_per_subject(
    seed: Seeder, firm: Firm
) -> None:
    ctx = TenantContext(firm.tenant_id, "human", str(firm.person.user_id))
    client, engagement = uuid.uuid4(), uuid.uuid4()
    subjects = [
        AccessSubject("evidence_version", uuid.uuid4(), client_id=client, engagement_id=engagement)
        for _ in range(3)
    ]
    assert await record_reads(ctx, PROBE_KIND, subjects) == 3
    rows = await seed.rows(
        "SELECT actor_kind, actor_id, kind, subject_type, subject_id, client_id, engagement_id "
        "FROM access_events WHERE tenant_id = $1 ORDER BY id",
        firm.tenant_id,
    )
    assert [r["subject_id"] for r in rows] == [s.subject_id for s in subjects]
    for r in rows:
        assert (r["actor_kind"], r["actor_id"], r["kind"]) == (
            "human",
            firm.person.user_id,
            PROBE_KIND,
        )
        assert (r["client_id"], r["engagement_id"]) == (client, engagement)


# The evidence store, so a download is a real one.
MASTER = b"q02-t22-acceptance-master-key-0123456789"
BUCKET = f"q02-t22-{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="module")
def bucket(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client
    listing = client.list_object_versions(Bucket=BUCKET)
    for entry in [*listing.get("Versions", []), *listing.get("DeleteMarkers", [])]:
        client.delete_object(
            Bucket=BUCKET,
            Key=entry.get("Key", ""),
            VersionId=entry.get("VersionId", ""),
            BypassGovernanceRetention=True,
        )
    client.delete_bucket(Bucket=BUCKET)


@pytest.fixture
def evidence_store(bucket: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


async def test_q02_t22_ac23_a_download_leaves_one_identifier_only_access_row(
    seed: Seeder, firm: Firm, evidence_store: None, idp: FakeIdentityProvider
) -> None:
    """AC-23: Ana downloads an evidence version: one row with the tenant, actor, kind
    `evidence_content.read`, the version, the client and engagement; no file name, quote or
    value."""
    tenant = firm.tenant_id
    entity_id = await seed.entity(tenant)
    engagement_id = await seed.engagement(tenant, entity_id, firm.person.user_id)
    await seed.member(engagement_id, firm.person, "staff")
    client_id = await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity_id)
    title = f"Bank statement {MARKER}"
    content = f"Account holder SSN {SSN}; balance 1,234.56; {MARKER}".encode()
    stored = await storage.put(tenant, content)
    item_id = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, $3, 'human', $4) RETURNING id",
        tenant,
        engagement_id,
        title,
        str(firm.person.user_id),
    )
    version_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, $6, $7, 'application/pdf', "
            "'upload', 'uploaded') RETURNING id",
            tenant,
            engagement_id,
            item_id,
            stored.fingerprint,
            stored.key,
            stored.version_id,
            stored.size,
        ),
    )
    subject = str(
        await seed.value("SELECT idp_subject FROM users WHERE id = $1", firm.person.user_id)
    )
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.get(
            f"/v1/engagements/{engagement_id}/evidence-versions/{version_id}/content",
            headers={"Authorization": f"Bearer {idp.token(subject)}"},
        )
    assert response.status_code == 200, response.text
    assert response.content == content
    rows = await seed.rows(
        "SELECT row_to_json(a)::text AS row, actor_kind, actor_id, kind, subject_type, "
        "subject_id, client_id, engagement_id FROM access_events a WHERE tenant_id = $1",
        tenant,
    )
    [row] = rows
    assert row["actor_kind"] == "human"
    assert row["actor_id"] == firm.person.user_id
    assert row["kind"] == "evidence_content.read"
    assert (row["subject_type"], row["subject_id"]) == ("evidence_version", version_id)
    assert (row["client_id"], row["engagement_id"]) == (client_id, engagement_id)
    dumped = str(row["row"])
    for leak in (MARKER, SSN, "Bank statement", "1,234.56", stored.key, stored.fingerprint):
        assert leak not in dumped, leak
    assert json.loads(dumped)["tenant_id"] == str(tenant)


# --- access_events: isolation and insert-only (AC-25) --------------------------------------------


async def _two_firms_with_rows(seed: Seeder) -> tuple[Firm, Firm]:
    firms: list[Firm] = []
    for _ in range(2):
        tenant = await seed.firm()
        who = Firm(tenant, await seed.person(tenant))
        ctx = TenantContext(tenant, "human", str(who.person.user_id))
        await record_reads(ctx, PROBE_KIND, [AccessSubject("evidence_version", uuid.uuid4())])
        firms.append(who)
    return firms[0], firms[1]


async def test_q02_t22_ac25_tenant_b_never_reads_tenant_as_rows(seed: Seeder) -> None:
    a, b = await _two_firms_with_rows(seed)
    async with tenant_session(TenantContext(b.tenant_id, "human", str(b.person.user_id))) as s:
        seen = (await s.execute(text("SELECT tenant_id FROM access_events"))).scalars().all()
        named = (
            await s.execute(
                text("SELECT count(*) FROM access_events WHERE tenant_id = :a"),
                {"a": a.tenant_id},
            )
        ).scalar_one()
    assert set(seen) == {b.tenant_id}
    assert named == 0


async def test_q02_t22_ac25_tenant_b_cannot_write_a_row_for_tenant_a(seed: Seeder) -> None:
    a, b = await _two_firms_with_rows(seed)
    with pytest.raises(DBAPIError):
        async with tenant_session(TenantContext(b.tenant_id, "human", str(b.person.user_id))) as s:
            await s.execute(
                text(
                    "INSERT INTO access_events (tenant_id, actor_kind, kind, subject_type, "
                    "subject_id) VALUES (:a, 'human', :kind, 'evidence_version', :id)"
                ),
                {"a": a.tenant_id, "kind": PROBE_KIND, "id": uuid.uuid4()},
            )
    count = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1", a.tenant_id
    )
    assert count == 1


# The partitions migration 0105 creates (§5: monthly, plus a default), each read directly.
MIGRATION_PARTITIONS = {
    "access_events_default": text("SELECT count(*) FROM access_events_default"),
    "access_events_2026_10": text("SELECT count(*) FROM access_events_2026_10"),
    "access_events_2026_11": text("SELECT count(*) FROM access_events_2026_11"),
    "access_events_2026_12": text("SELECT count(*) FROM access_events_2026_12"),
    "access_events_2027_01": text("SELECT count(*) FROM access_events_2027_01"),
    "access_events_2027_02": text("SELECT count(*) FROM access_events_2027_02"),
    "access_events_2027_03": text("SELECT count(*) FROM access_events_2027_03"),
}


async def _partitions(seed: Seeder) -> list[str]:
    rows = await seed.rows(
        "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
        "WHERE i.inhparent = 'public.access_events'::regclass ORDER BY 1"
    )
    return [str(r["relname"]) for r in rows]


async def test_q02_t22_ac25_the_app_cannot_read_a_partition_directly(seed: Seeder) -> None:
    """Partitions bypass nothing: the app reaches rows only through the parent's policy."""
    a, _ = await _two_firms_with_rows(seed)
    assert set(MIGRATION_PARTITIONS) <= set(await _partitions(seed))
    for read in MIGRATION_PARTITIONS.values():
        with pytest.raises(DBAPIError):
            async with tenant_session(
                TenantContext(a.tenant_id, "human", str(a.person.user_id))
            ) as s:
                await s.execute(read)


@pytest.mark.parametrize("statement", ["UPDATE", "DELETE"])
async def test_q02_t22_ac25_the_app_cannot_change_or_remove_a_row(
    seed: Seeder, statement: str
) -> None:
    a, _ = await _two_firms_with_rows(seed)
    sql = {
        "UPDATE": "UPDATE access_events SET subject_type = 'altered'",
        "DELETE": "DELETE FROM access_events",
    }[statement]
    with pytest.raises(DBAPIError):
        async with tenant_session(TenantContext(a.tenant_id, "human", str(a.person.user_id))) as s:
            await s.execute(text(sql))
    count = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND subject_type <> 'altered'",
        a.tenant_id,
    )
    assert count == 1


@pytest.mark.parametrize("role", ["superuser", "owner"])
async def test_q02_t22_ac25_no_role_changes_or_removes_a_row_in_any_partition(
    seed: Seeder, owner: Seeder, role: str
) -> None:
    """A row in every partition (each month and the default), then UPDATE, DELETE and TRUNCATE
    against the parent and against the partition itself, by roles that hold every privilege."""
    who = seed if role == "superuser" else owner
    tenant = await seed.firm()
    person = await seed.person(tenant)
    human = ("human", str(person.user_id))
    partitions = await _partitions(seed)
    for partition in partitions:
        bounds = await seed.value(
            "SELECT pg_get_expr(c.relpartbound, c.oid) FROM pg_class c WHERE relname = $1",
            partition,
        )
        at = "2031-06-15" if "DEFAULT" in str(bounds) else str(bounds).split("'")[1]
        await seed.as_actor(
            tenant,
            human,
            "INSERT INTO access_events (tenant_id, occurred_at, actor_kind, actor_id, kind, "
            "subject_type, subject_id) VALUES ($1, $2::date + interval '1 day', 'human', $3, $4, "
            "'evidence_version', $5)",
            tenant,
            date.fromisoformat(at[:10]),
            person.user_id,
            PROBE_KIND,
            uuid.uuid4(),
        )
    before = await seed.value("SELECT count(*) FROM access_events WHERE tenant_id = $1", tenant)
    assert before == len(partitions)
    # Each statement is quoted by the database (`format('%I')`), never built in Python.
    statements = await seed.rows(
        "SELECT t, format('UPDATE public.%I SET subject_type = ''altered'' "
        "WHERE tenant_id = $1', t) AS up, format('DELETE FROM public.%I WHERE tenant_id = $1', "
        "t) AS del, format('TRUNCATE public.%I', t) AS trunc "
        "FROM unnest($1::text[]) AS t",
        ["access_events", *partitions],
    )
    assert len(statements) == len(partitions) + 1
    for row in statements:
        for sql in (str(row["up"]), str(row["del"])):
            with pytest.raises(asyncpg.PostgresError):
                await who.as_actor(tenant, human, sql, tenant)
        with pytest.raises(asyncpg.PostgresError):
            await who.run(str(row["trunc"]))
    after = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND subject_type <> 'altered'",
        tenant,
    )
    assert after == before
