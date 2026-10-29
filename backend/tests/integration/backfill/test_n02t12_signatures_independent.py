# ac-test-author: ayushkbhatia
"""N-02-T12 (TASK-1743; ADR-078 independent; N-02-T07, T08, T09; SPEC-381 AC-1, AC-2, AC-3,
AC-16, AC-17; DEC-833): signatures v1 and record mode, from the spec and the matrix, not from
T07-T09's own suites.

Acceptance (the task row): "The suite passes on N's code and fails on a planted UPDATE of
signature_evidence or an agent-principal import."

- Forced RLS on every signatures table, and another firm's rows invisible to the app role.
- Insert-only: `signature_evidence` and `envelope_events` refuse UPDATE and DELETE for the app
  role and the owner alike (the planted UPDATE).
- COMPLIANCE: every record of an import is locked until the firm's retain-until, which the bucket
  never lets anyone shorten.
- The scanner fails closed (error and timeout refuse, nothing staged); the attestation is
  required.
- G3 over its three sources: a provider letter envelope signed by both parties, a record-mode
  letter import, a letter recorded through `letter.record`; any one meets it, none leaves it
  unmet, another purpose never meets it.
- INV-1: an agent and the system are refused `envelope.import_record` at the matrix, at
  `authorise` and at the database (the agent-principal import).
- INV-3: a walled person's stage and import answer 404 with no count, before any file check.
- INV-5: the importer is named on the envelope, the audit event, the outbox event and the
  write-once manifest.

Boundary: `create_app()` over HTTP as each signed-in person; `identity.api.authorise` with an
agent and a system context; the database as the app role (asyncpg) and as the owner.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, cast

import asyncpg
import httpx
import pytest
from botocore.exceptions import ClientError

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.scanning import inject_verdict
from abacus.kernel.storage import s3_client
from abacus.modules.engagements.api import gate_fact, get_ref
from abacus.modules.evidence import records, storage
from abacus.modules.identity.api import (
    Forbidden,
    agent_context_for_run,
    authorise,
    member_context,
    system_context_for_run,
)
from abacus.modules.identity.authz._matrix import ACTIONS

from .support import Migrated, Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a request or response body as the contract shapes it
FLAG: Final = "signatures.envelopes"
ACTION: Final = "envelope.import_record"
EVIDENCE: Final = "n02t12-evidence"
RECORDS: Final = "n02t12-records"
MASTER: Final = b"n02t12-independent-master-key-012345678"
FLOOR_YEARS: Final = 7
G3: Final = "G3"

# SPEC-381 §9: the human-only verbs (the matrix must deny the agent and the system each one).
HUMAN_ONLY: Final = (
    "envelope.send",
    "envelope.remind",
    "envelope.void",
    "envelope.import_record",
    "envelope.record_wet_signature",
    "envelope.countersign",
    "letter.approve",
    "letter.send",
    "letter.amend",
)
SIGNATURES_TABLES: Final = (
    "envelope_numbers",
    "envelopes",
    "envelope_documents",
    "envelope_signers",
    "envelope_fields",
    "envelope_events",
    "envelope_provider_calls",
    "signature_evidence",
    "envelope_policies",
    "signing_sessions",
    "esign_disclosures",
    "esign_acceptances",
    "envelope_import_files",
)
INSERT_ONLY: Final = ("signature_evidence", "envelope_events")


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    for bucket in (EVIDENCE, RECORDS):
        client.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    records.configure_records(raw, RECORDS)
    yield
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    forget_flags()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person  # Firm Admin: sets walls
    grace: Person  # Firm Admin and manager on the engagement: imports
    other: Person  # another manager on the engagement
    site: Site
    contact_id: uuid.UUID

    async def stage(self, who: Person, content: bytes, name: str = "letter.pdf") -> httpx.Response:
        return await self.net.http.post(
            "/v1/envelopes/import/files",
            params={
                "filename": name,
                "client_id": str(self.site.client_id),
                "engagement_id": str(self.site.engagement_id),
            },
            content=content,
            headers={**self.net.headers(who), "Content-Type": "application/octet-stream"},
        )

    async def import_(self, who: Person, body: Body, attempt: str | None = None) -> httpx.Response:
        return await self.net.http.post(
            "/v1/envelopes/import",
            json=body,
            headers={
                **self.net.headers(who),
                "Idempotency-Key": attempt or f"n02t12-{uuid.uuid4().hex}",
            },
        )

    def body(self, uploads: list[str], purpose: str = "engagement_letter") -> Body:
        return {
            "purpose": purpose,
            "client_id": str(self.site.client_id),
            "engagement_id": str(self.site.engagement_id),
            "title": "Engagement letter, signed",
            "provider_name": "DocuSign",
            "signers": [
                {"contact_id": str(self.contact_id), "signed_on": "2026-04-02"}
                | {"identity_method": "email_code"},
                {"user_id": str(self.grace.user_id), "role": "countersigner"}
                | {"signed_on": "2026-04-03", "identity_method": "firm_sso"},
            ],
            "upload_ids": uploads,
            "attested": True,
        }

    async def staged(self, who: Person | None = None) -> list[str]:
        """A fresh letter and certificate, staged; unique bytes so no two tests share a hash."""
        mark = uuid.uuid4().hex.encode()
        ids: list[str] = []
        for part, name in ((b"letter", "letter.pdf"), (b"certificate", "certificate.pdf")):
            content = b"%PDF-1.7\n% " + part + b" " + mark + b"\n%%EOF\n"
            response = await self.stage(who or self.grace, content, name)
            assert response.status_code == 201, response.text
            ids.append(cast(Body, response.json())["id"])
        return ids

    async def imported(self, purpose: str = "engagement_letter") -> uuid.UUID:
        response = await self.import_(self.grace, self.body(await self.staged(), purpose))
        assert response.status_code == 201, response.text
        return uuid.UUID(cast(Body, response.json())["row"]["id"])

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", "test:n02t12")


async def _firm(net: Net, label: str) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'N-02-T12')",
        tenant,
        FLAG,
    )
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    other = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, label)
    await seed.member(site, grace, "manager")
    await seed.member(site, other, "manager")
    contact = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, $3, 'client_person') RETURNING id",
            tenant,
            site.client_id,
            f"{label} signer",
        ),
    )
    # The firm's signature_evidence policy, written as tenant_session would (its trigger reads
    # the tenant).
    await seed.run(
        "WITH t AS (SELECT set_config('app.tenant_id', $1::text, true)) "
        "INSERT INTO retention_policies (tenant_id, record_type, service_line, firm_years, "
        "clock_start_event, updated_by) SELECT $1::uuid, 'signature_evidence', 'any', $2, "
        "'event_date', 'test-seed' FROM t",
        str(tenant),
        FLOOR_YEARS,
    )
    return Firm(net, tenant, admin, grace, other, site, contact)


@pytest.fixture
async def firm(net: Net) -> Firm:
    return await _firm(net, "Copperleaf")


@pytest.fixture
async def app_role(migrated_db: Migrated) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(
        migrated_db.app_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    yield conn
    await conn.close()


async def _as_app(
    conn: asyncpg.Connection,
    tenant: uuid.UUID,
    statement: str,
    *args: object,
    actor_kind: str = "human",
    actor_id: uuid.UUID | None = None,
) -> object:
    """One statement as the app role, in a transaction that names the tenant and the actor."""
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(tenant))
        await conn.execute("SELECT set_config('app.actor_kind', $1, true)", actor_kind)
        await conn.execute(
            "SELECT set_config('app.actor_id', $1, true)", str(actor_id or uuid.uuid4())
        )
        return await conn.fetchval(statement, *args)


# --- The acceptance: a planted UPDATE of signature_evidence fails ------------------------------


@pytest.mark.parametrize("table", INSERT_ONLY)
async def test_ac_the_app_role_cannot_update_or_delete_insert_only_rows(
    firm: Firm, app_role: asyncpg.Connection, table: str
) -> None:
    envelope = await firm.imported()
    for statement in (
        f"UPDATE {table} SET envelope_id = envelope_id WHERE envelope_id = $1",  # noqa: S608  # table names are this module's constants
        f"DELETE FROM {table} WHERE envelope_id = $1",  # noqa: S608
    ):
        with pytest.raises(asyncpg.PostgresError):
            await _as_app(
                app_role, firm.tenant_id, statement, envelope, actor_id=firm.grace.user_id
            )
    count = await firm.net.seed.value(
        f"SELECT count(*) FROM {table} WHERE envelope_id = $1",  # noqa: S608
        envelope,
    )
    assert cast(int, count) >= 1


@pytest.mark.parametrize("table", INSERT_ONLY)
async def test_ac_the_owner_cannot_update_insert_only_rows_either(firm: Firm, table: str) -> None:
    envelope = await firm.imported()
    with pytest.raises(asyncpg.PostgresError, match="insert-only"):
        await firm.net.seed.run(
            f"UPDATE {table} SET envelope_id = envelope_id WHERE envelope_id = $1",  # noqa: S608
            envelope,
        )


async def test_ac_signature_evidence_is_unchanged_after_the_attempts(
    firm: Firm, app_role: asyncpg.Connection
) -> None:
    envelope = await firm.imported()
    before = await firm.net.seed.rows(
        "SELECT id, identity_result, signature_method, document_sha256s, package_sha256 "
        "FROM signature_evidence WHERE envelope_id = $1 ORDER BY id",
        envelope,
    )
    with pytest.raises(asyncpg.PostgresError):
        await _as_app(
            app_role,
            firm.tenant_id,
            "UPDATE signature_evidence SET identity_result = 'planted' WHERE envelope_id = $1",
            envelope,
            actor_id=firm.grace.user_id,
        )
    after = await firm.net.seed.rows(
        "SELECT id, identity_result, signature_method, document_sha256s, package_sha256 "
        "FROM signature_evidence WHERE envelope_id = $1 ORDER BY id",
        envelope,
    )
    assert [dict(r) for r in after] == [dict(r) for r in before]
    assert len(after) == 2  # one row per signer


# --- The acceptance: an agent-principal import fails (INV-1) -----------------------------------


@pytest.mark.parametrize("action", HUMAN_ONLY)
async def test_ac_the_matrix_denies_the_agent_and_the_system_every_human_only_verb(
    action: str,
) -> None:
    row = ACTIONS[action]
    assert (row.get("agent"), row.get("system")) == ("deny", "deny"), action


async def test_ac_authorise_refuses_an_agent_holding_import_in_its_task_scope(firm: Firm) -> None:
    run = uuid.uuid4()
    await firm.net.seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, status, finished_at) VALUES ($1, $2, 'engagement.agent', "
        "1, $3, $4, $5, 'completed', now())",
        run,
        firm.tenant_id,
        firm.site.engagement_id,
        firm.grace.user_id,
        [ACTION],
    )
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=run,
        agent_id="engagement.agent",
        engagement_id=firm.site.engagement_id,
        task_scope=frozenset({ACTION}),
        initiator_user_id=firm.grace.user_id,
    )
    grace = await member_context(firm.tenant_id, firm.grace.user_id)
    assert grace is not None
    resource = (await get_ref(grace, firm.site.engagement_id)).resource()
    await authorise(grace, ACTION, resource)  # the importer herself may
    with pytest.raises(Forbidden):
        await authorise(agent, ACTION, resource)


async def test_ac_authorise_refuses_the_system(firm: Firm) -> None:
    grace = await member_context(firm.tenant_id, firm.grace.user_id)
    assert grace is not None
    resource = (await get_ref(grace, firm.site.engagement_id)).resource()
    system = system_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=firm.site.engagement_id,
        on_behalf_of=firm.grace.user_id,
    )
    with pytest.raises(Forbidden):
        await authorise(system, ACTION, resource)


async def _record_envelope(
    conn: asyncpg.Connection,
    firm: Firm,
    *,
    actor_kind: str,
    actor_id: uuid.UUID,
) -> object:
    return await _as_app(
        conn,
        firm.tenant_id,
        "INSERT INTO envelopes (tenant_id, number, purpose, policy_family, client_id, "
        "engagement_id, title, provider, provider_name, status, drafted_by_kind, imported_by, "
        "completed_at) VALUES ($1, $2, 'engagement_letter', 'engagement_letter', $3, $4, "
        "'Letter', 'record', 'DocuSign', 'completed', 'human', $5, now()) RETURNING id",
        firm.tenant_id,
        900_000 + uuid.uuid4().int % 99_999,
        firm.site.client_id,
        firm.site.engagement_id,
        firm.grace.user_id,
        actor_kind=actor_kind,
        actor_id=actor_id,
    )


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_ac_the_database_refuses_an_import_by_a_non_person(
    firm: Firm, app_role: asyncpg.Connection, kind: str
) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="imported by a person"):
        await _record_envelope(app_role, firm, actor_kind=kind, actor_id=firm.grace.user_id)
    assert not await firm.net.seed.value(
        "SELECT count(*) FROM envelopes WHERE tenant_id = $1", firm.tenant_id
    )


async def test_the_database_refuses_an_import_in_another_persons_name(
    firm: Firm, app_role: asyncpg.Connection
) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await _record_envelope(app_role, firm, actor_kind="human", actor_id=firm.other.user_id)
    made = await _record_envelope(app_role, firm, actor_kind="human", actor_id=firm.grace.user_id)
    assert isinstance(made, uuid.UUID)  # the control: the named person passes


# --- Forced RLS and tenant isolation ------------------------------------------------------------


async def test_every_signatures_table_forces_row_level_security(firm: Firm) -> None:
    rows = await firm.net.seed.rows(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relname = ANY($1::text[]) AND relkind = 'r'",
        list(SIGNATURES_TABLES),
    )
    found = {r["relname"]: (r["relrowsecurity"], r["relforcerowsecurity"]) for r in rows}
    assert found == dict.fromkeys(SIGNATURES_TABLES, (True, True))


async def test_another_firms_envelope_rows_are_invisible_to_the_app_role(
    net: Net, firm: Firm, app_role: asyncpg.Connection
) -> None:
    mine = await firm.imported()
    theirs = await _firm(net, "Ridgeline")
    await theirs.imported()
    for table in (
        "envelopes",
        "envelope_documents",
        "envelope_signers",
        "envelope_events",
        "signature_evidence",
        "envelope_import_files",
    ):
        seen = await _as_app(
            app_role,
            firm.tenant_id,
            f"SELECT count(*) FROM {table} WHERE tenant_id = $1",  # noqa: S608
            theirs.tenant_id,
        )
        assert seen == 0, table
        owned = await net.seed.value(
            f"SELECT count(*) FROM {table} WHERE tenant_id = $1",  # noqa: S608
            theirs.tenant_id,
        )
        assert cast(int, owned) >= 1, table  # the rows exist; RLS hides them
    assert (
        await _as_app(
            app_role, firm.tenant_id, "SELECT count(*) FROM envelopes WHERE id = $1", mine
        )
        == 1
    )


async def test_another_firms_person_cannot_import_into_this_client(net: Net, firm: Firm) -> None:
    theirs = await _firm(net, "Ridgeline")
    uploads = await firm.staged()
    staged = await firm.stage(theirs.grace, b"%PDF-1.7\n% cross-tenant\n%%EOF\n")
    assert staged.status_code == 404
    response = await firm.import_(theirs.grace, firm.body(uploads))
    assert response.status_code == 404
    assert not await net.seed.value(
        "SELECT count(*) FROM envelopes WHERE tenant_id = $1", firm.tenant_id
    )


# --- COMPLIANCE retention ----------------------------------------------------------------------


def _locks(raw: S3Client, tenant: uuid.UUID) -> dict[str, tuple[str, datetime]]:
    listed = raw.list_objects_v2(Bucket=RECORDS, Prefix=f"records/{tenant}/signature_evidence/")
    out: dict[str, tuple[str, datetime]] = {}
    for item in listed.get("Contents", []):
        key = item.get("Key", "")
        retention = raw.get_object_retention(Bucket=RECORDS, Key=key)["Retention"]
        until = retention.get("RetainUntilDate")
        assert until is not None, key
        out[key] = (str(retention.get("Mode")), until)
    return out


async def test_every_record_is_locked_in_compliance_mode_until_the_firms_floor(
    firm: Firm, raw: S3Client
) -> None:
    envelope = await firm.imported()
    locks = _locks(raw, firm.tenant_id)
    assert len(locks) == 3  # the letter, the certificate, the manifest
    floor = datetime.now(UTC) + timedelta(days=365 * FLOOR_YEARS)
    for key, (mode, until) in locks.items():
        assert mode == "COMPLIANCE", key
        assert until >= floor - timedelta(days=2), key
    kept = await firm.net.seed.rows(
        "SELECT DISTINCT retain_until FROM signature_evidence WHERE envelope_id = $1", envelope
    )
    assert len(kept) == 1
    assert kept[0]["retain_until"] >= (floor - timedelta(days=2)).date()


async def test_the_bucket_never_shortens_a_records_lock(firm: Firm, raw: S3Client) -> None:
    await firm.imported()
    for key, (_, until) in _locks(raw, firm.tenant_id).items():
        for mode in ("COMPLIANCE", "GOVERNANCE"):
            with pytest.raises(ClientError):
                raw.put_object_retention(
                    Bucket=RECORDS,
                    Key=key,
                    Retention={"Mode": mode, "RetainUntilDate": until - timedelta(days=365)},
                    BypassGovernanceRetention=True,
                )
        version = raw.head_object(Bucket=RECORDS, Key=key)["VersionId"]
        with pytest.raises(ClientError):  # the locked version itself, not a delete marker
            raw.delete_object(
                Bucket=RECORDS, Key=key, VersionId=version, BypassGovernanceRetention=True
            )
        assert _locks(raw, firm.tenant_id)[key][1] == until


# --- The scanner fails closed; the attestation is required -------------------------------------


@pytest.mark.parametrize("verdict", ["error", "timeout", "infected"])
async def test_a_file_the_scanner_cannot_clear_is_refused_and_nothing_is_staged(
    firm: Firm, verdict: str
) -> None:
    content = b"%PDF-1.7\n% " + verdict.encode() + uuid.uuid4().hex.encode() + b"\n%%EOF\n"
    inject_verdict(hashlib.sha256(content).hexdigest(), verdict)  # type: ignore[arg-type]  # parametrised over the InjectedVerdict values
    response = await firm.stage(firm.grace, content)
    assert response.status_code == 422, response.text
    assert not await firm.net.seed.value(
        "SELECT count(*) FROM envelope_import_files WHERE tenant_id = $1", firm.tenant_id
    )


@pytest.mark.parametrize("attested", [False, None])
async def test_an_import_without_the_attestation_is_refused(
    firm: Firm, attested: bool | None
) -> None:
    body = firm.body(await firm.staged())
    if attested is None:
        del body["attested"]
    else:
        body["attested"] = attested
    response = await firm.import_(firm.grace, body)
    assert response.status_code == 422, response.text
    assert not await firm.net.seed.value(
        "SELECT count(*) FROM envelopes WHERE tenant_id = $1", firm.tenant_id
    )


# --- G3 over its three sources (AC-2) -----------------------------------------------------------


async def _provider_letter(firm: Firm) -> None:
    """A completed provider letter envelope, client-signed and countersigned (no provider path is
    built yet, so the rows are seeded with the triggers off)."""
    envelope = uuid.uuid4()
    seed = firm.net.seed
    await seed.run_untriggered(
        "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, client_id, "
        "engagement_id, title, provider, status, drafted_by_kind, completed_at) VALUES ($1, $2, "
        "$3, 'engagement_letter', 'engagement_letter', $4, $5, 'Letter', 'fake', 'completed', "
        "'human', now())",
        envelope,
        firm.tenant_id,
        800_000 + uuid.uuid4().int % 99_999,
        firm.site.client_id,
        firm.site.engagement_id,
    )
    for order, party, role in ((1, "contact", "signer"), (2, "user", "countersigner")):
        await seed.run_untriggered(
            'INSERT INTO envelope_signers (tenant_id, envelope_id, "order", party_kind, '
            "contact_id, user_id, role, identity_method, status, signed_at, signature_method) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, 'email_code', 'signed', now(), 'typed')",
            firm.tenant_id,
            envelope,
            order,
            party,
            firm.contact_id if party == "contact" else None,
            firm.grace.user_id if party == "user" else None,
            role,
        )


async def _recorded_letter(firm: Firm) -> None:
    await firm.net.seed.run(
        "INSERT INTO engagement_letters (tenant_id, engagement_id, status, letter_date, "
        "recorded_by) VALUES ($1, $2, 'signed', '2026-04-02', 'test-seed')",
        firm.tenant_id,
        firm.site.engagement_id,
    )


SOURCES: Final = ("provider", "record", "letter_record")


@pytest.mark.parametrize(
    "present",
    [
        frozenset(subset)
        for size in range(len(SOURCES) + 1)
        for subset in itertools.combinations(SOURCES, size)
    ],
    ids=lambda s: "+".join(sorted(s)) or "none",
)
async def test_ac2_g3_is_met_by_any_one_source_and_unmet_by_none(
    firm: Firm, present: frozenset[str]
) -> None:
    if "provider" in present:
        await _provider_letter(firm)
    if "record" in present:
        await firm.imported()
    if "letter_record" in present:
        await _recorded_letter(firm)
    fact = await gate_fact(firm.system, firm.site.engagement_id, G3)
    assert fact.met is bool(present)


async def test_ac2_a_record_import_of_another_purpose_never_meets_g3(firm: Firm) -> None:
    await firm.imported(purpose="consent_7216")
    assert not (await gate_fact(firm.system, firm.site.engagement_id, G3)).met


# --- INV-3: the wall answers 404 with no count --------------------------------------------------


async def test_inv3_a_walled_person_is_answered_404_before_any_file_check(firm: Firm) -> None:
    uploads = await firm.staged()  # Grace's files: real and unconsumed
    await firm.net.wall(firm.admin, firm.other, firm.site)
    staged = await firm.stage(firm.other, b"%PDF-1.7\n% walled\n%%EOF\n")
    imported = await firm.import_(firm.other, firm.body(uploads))
    for response in (staged, imported):
        assert response.status_code == 404, response.text
        text = response.text
        assert "count" not in text
        assert "import_file_unavailable" not in text  # the wall comes before the file check
        assert str(firm.site.engagement_id) not in text
    assert not await firm.net.seed.value(
        "SELECT count(*) FROM envelopes WHERE tenant_id = $1", firm.tenant_id
    )
    still = await firm.net.seed.value(
        "SELECT count(*) FROM envelope_import_files "
        "WHERE tenant_id = $1 AND consumed_envelope_id IS NULL",
        firm.tenant_id,
    )
    assert still == 2


# --- INV-5: the importer is named everywhere ----------------------------------------------------


async def test_inv5_the_importer_is_named_on_every_record(firm: Firm, raw: S3Client) -> None:
    envelope = await firm.imported()
    seed = firm.net.seed
    grace = str(firm.grace.user_id)
    row = await seed.rows(
        "SELECT imported_by, drafted_by, drafted_by_kind FROM envelopes WHERE id = $1", envelope
    )
    assert (str(row[0]["imported_by"]), str(row[0]["drafted_by"])) == (grace, grace)
    assert row[0]["drafted_by_kind"] == "human"
    audit = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'envelope.imported'",
        firm.tenant_id,
    )
    assert [(a["actor_kind"], a["actor_id"]) for a in audit] == [("human", grace)]
    outbox = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'envelope.completed'",
        firm.tenant_id,
    )
    assert len(outbox) == 1
    assert grace in str(outbox[0]["payload"])
    package = await seed.value(
        "SELECT DISTINCT package_sha256 FROM signature_evidence WHERE envelope_id = $1", envelope
    )
    stored = raw.get_object(
        Bucket=RECORDS, Key=f"records/{firm.tenant_id}/signature_evidence/{package}"
    )
    manifest = json.loads(stored["Body"].read())
    assert manifest["imported_by"] == grace
    assert manifest["attested"] is True
    assert manifest["envelope_id"] == str(envelope)
