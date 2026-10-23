"""F-03-T35: the foundation journey on the J02 data path (Copperleaf), against Postgres.

"The test walks client, prospect, accepted, contracted, 12 close work items, request uploaded and
received, with every invariant asserted." Sources: F-03 sections 1 and 3.1 to 3.5; SPEC-047
AC-11, AC-13 and AC-15; chapter 10 section 10.6 (INV-1, INV-3, INV-4, INV-5).

The walk:
- Priya Raman (practice leader) creates Copperleaf's "2026 Close" for a new client and holds its
  engagement partner role as the creator.
- She records the G1 decision with fresh MFA, then her independence. The agent is refused.
- She records the signed letter (G3) and creates the 12 monthly closes.
- She asks for the July bank statements. Tess Moreno (Copperleaf, `owner` grant) uploads them,
  and Priya accepts them.
- Lena Park (firm admin) is walled from Copperleaf. Ashford, a second client, has its own
  engagement and request.

Every step goes through `create_app()` as the app role with the fake identity provider, except
`create_work_item`, which has no route (engagements.api is its entry). Seeding goes through the
shared Seeder as the superuser: people, the wall and the grant. Where the code does not yet do
what the plan says, a separate strict xfail names the gap, and the walk goes round it in the open.
Nothing is weakened.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, cast

import httpx
import pytest
from types_boto3_s3 import S3Client

import abacus.modules.closes.api  # registers the close work-item kind
from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.storage import s3_client
from abacus.modules.engagements.api import create_work_item
from abacus.modules.evidence import storage
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    authorise,
    configure_verifier,
    engagement_resource,
    reset_verifier,
)
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)
from abacus.modules.identity.service import TENANT_HEADER
from abacus_tools.fakes.identity import FakeIdentityProvider

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert abacus.modules.closes.api

Json = dict[str, Any]  # parsed JSON bodies, untyped by httpx
MASTER: Final = b"journey-test-master-key-0123456789abcdef"
BUCKET: Final = f"journey-{uuid.uuid4().hex[:12]}"
PDF: Final = b"%PDF-1.4\n% Copperleaf July bank statement (synthetic)\n%%EOF\n"
PERIODS: Final = tuple(f"2026-{month:02d}" for month in range(1, 13))

# INV-1 (chapter 10 section 10.6): the tables whose rows are final verbs. A table that is not
# built yet, or has no `actor_kind`, is passed over and joins the check when it lands.
_AGENT_ROWS = "SELECT count(*) FROM {} WHERE tenant_id = $1 AND actor_kind = 'agent'"
FINAL_VERB_TABLES: Final = (
    "sign_offs",
    "decisions",
    "review_decisions",
    "report_releases",
    "posting_batches",
    "engine_exports",
    "envelopes",
    "messages",
)


# --- fixtures ------------------------------------------------------------------------------------


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    """Each test runs on its own event loop: fresh pools, pointed at the app and identity roles."""
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture(scope="module")
def bucket_client(s3_settings: dict[str, str]) -> Iterator[S3Client]:
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


@pytest.fixture(autouse=True)
def evidence_storage(bucket_client: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket_client, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# --- the cast ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Who:
    name: str
    user_id: uuid.UUID
    subject: str
    tenant_id: uuid.UUID

    def context(self) -> AuthContext:
        return AuthContext(
            TenantContext(self.tenant_id, "human", str(self.user_id)),
            self.user_id,
            uuid.uuid4(),
            None,
            datetime.now(UTC),
        )


@dataclass
class Journey:
    seed: Seeder
    http: httpx.AsyncClient
    idp: FakeIdentityProvider
    tenant: uuid.UUID

    async def person(self, name: str, *, firm_role: str | None = None) -> Who:
        """A person in the firm, through the shared Seeder, renamed to the persona."""
        made = await self.seed.person(self.tenant)
        await self.seed.run("UPDATE users SET display_name = $2 WHERE id = $1", made.user_id, name)
        if firm_role is not None:
            await self.seed.run(
                "UPDATE memberships SET firm_role = $3 WHERE tenant_id = $1 AND user_id = $2",
                self.tenant,
                made.user_id,
                firm_role,
            )
        subject = str(
            await self.seed.value("SELECT idp_subject FROM users WHERE id = $1", made.user_id)
        )
        return Who(name, made.user_id, subject, self.tenant)

    async def client_user(self, name: str, engagement: uuid.UUID) -> Who:
        """A client user with an `owner` grant on one engagement (F-03-T26, P-09)."""
        who = await self.person(name)
        await self.seed.run(
            "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            who.user_id,
        )
        await self.seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $2, 'owner', 'engagement', $3)",
            self.tenant,
            who.user_id,
            engagement,
        )
        return who

    def headers(self, who: Who, *, mfa: bool = False) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.idp.token(who.subject, mfa=mfa)}",
            TENANT_HEADER: str(self.tenant),
        }

    async def get(self, who: Who, path: str) -> httpx.Response:
        return await self.http.get(path, headers=self.headers(who))

    async def post(self, who: Who, path: str, body: Json | None = None) -> httpx.Response:
        return await self.http.post(path, json=body or {}, headers=self.headers(who))

    async def put(self, who: Who, path: str, body: Json, *, mfa: bool = False) -> httpx.Response:
        return await self.http.put(path, json=body, headers=self.headers(who, mfa=mfa))

    async def status(self, engagement: uuid.UUID) -> str:
        return str(
            await self.seed.value("SELECT status FROM engagements WHERE id = $1", engagement)
        )

    async def prospect(self, engagement: uuid.UUID) -> None:
        await self.seed.run("UPDATE engagements SET status = 'prospect' WHERE id = $1", engagement)

    async def item_status(self, item: uuid.UUID) -> str:
        return await self.seed.item_status(item)

    async def create(self, who: Who, client: str, name: str) -> Json:
        response = await self.post(
            who,
            "/v1/engagements",
            {
                "name": name,
                "client_name": client,
                "client_entity_name": client,
                "fiscal_period_start": "2026-01-01",
                "fiscal_period_end": "2026-12-31",
                "type": "cas_monthly_close",
                "confirm_new": True,
            },
        )
        assert response.status_code == 201, response.text
        return cast(Json, response.json())

    async def accept(self, who: Who, engagement: uuid.UUID) -> httpx.Response:
        return await self.put(
            who,
            f"/v1/engagements/{engagement}/acceptance",
            {
                "decision": "accepted",
                "documented_at": "Acceptance memo, client file",
                "independence_concluded": True,
                "independence_documented_at": "Independence memo, client file",
            },
            mfa=True,
        )

    async def letter(self, who: Who, engagement: uuid.UUID) -> httpx.Response:
        return await self.put(
            who,
            f"/v1/engagements/{engagement}/letter",
            {"status": "signed", "letter_date": "2026-01-05"},
        )

    async def request(self, who: Who, engagement: uuid.UUID, description: str) -> uuid.UUID:
        response = await self.post(
            who,
            f"/v1/engagements/{engagement}/request-items",
            {"description": description, "audit_area": "Cash"},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(str(cast(Json, response.json())["id"]))

    async def upload(self, who: Who, engagement: uuid.UUID, item: uuid.UUID) -> httpx.Response:
        return await self.http.post(
            f"/v1/engagements/{engagement}/request-items/{item}/uploads",
            params={"filename": "copperleaf-july-bank.pdf"},
            content=PDF,
            headers={**self.headers(who), "Content-Type": "application/pdf"},
        )

    async def audit(self, since: int) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT seq, action, actor_kind, actor_id, on_behalf_of_user_id AS on_behalf_of, "
            "target_type, target_id "
            "FROM audit_events WHERE tenant_id = $1 AND seq > $2 ORDER BY seq",
            self.tenant,
            since,
        )
        return [dict(r) for r in rows]

    async def last_seq(self) -> int:
        found = await self.seed.value(
            "SELECT coalesce(max(seq), 0) FROM audit_events WHERE tenant_id = $1", self.tenant
        )
        return int(cast(int, found))


async def _journey(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Journey:
    tenant = await seed.firm()
    await seed.run(
        "UPDATE firms SET name = 'Brightwater Hale LLP', synthetic = true WHERE tenant_id = $1",
        tenant,
    )
    return Journey(seed, http, idp, tenant)


def _agent(journey: Journey, engagement: uuid.UUID, initiator: Who, action: str) -> AgentContext:
    """The agent principal, with the action in its task scope and the partner as initiator."""
    run = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(journey.tenant, "agent", f"agent:journey:{run}", initiator.user_id),
        agent_id="journey",
        agent_run_id=run,
        engagement_id=engagement,
        task_scope=frozenset({action}),
        initiator=initiator.context(),
        issued_by=_ISSUER,
    )


# ================================================================================================
# The walk
# ================================================================================================


async def test_j02_copperleaf_walks_from_client_to_a_received_request(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    j = await _journey(seed, http, idp)
    priya = await j.person("Priya Raman", firm_role="practice_leader")
    lena = await j.person("Lena Park", firm_role="firm_admin")
    start = await j.last_seq()

    # --- the client and its engagement -------------------------------------------------------
    copperleaf = await j.create(priya, "Copperleaf Coffee Roasters, Inc.", "2026 Close")
    engagement = uuid.UUID(str(copperleaf["id"]))
    client = uuid.UUID(
        str(await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement))
    )
    assert await seed.value("SELECT name FROM clients WHERE id = $1", client) == (
        "Copperleaf Coffee Roasters, Inc."
    )
    assert await seed.value("SELECT type FROM engagements WHERE id = $1", engagement) == (
        "cas_monthly_close"
    )
    assert await seed.value("SELECT is_attest_client FROM clients WHERE id = $1", client) is False
    # A non-attest engagement holds no assurance work item, only its primary entity (C1 section 1).
    assert (
        await seed.value("SELECT count(*) FROM work_items WHERE engagement_id = $1", engagement)
        == 0
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM engagement_entities "
            "WHERE engagement_id = $1 AND role = 'primary'",
            engagement,
        )
        == 1
    )

    # Ashford: another client, its own engagement and request (for INV-3 and INV-4).
    ashford = uuid.UUID(str((await j.create(priya, "Ashford Mills", "2026 Close"))["id"]))
    # F-03 section 1: a new engagement starts in `prospect`. The create route still writes the
    # column default `active` (strict xfail below), so the walk puts both where the plan starts.
    for made in (engagement, ashford):
        await j.prospect(made)

    # Lena is walled from Copperleaf (seeded: walls arrive through their own admin route).
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        j.tenant,
        lena.user_id,
        client,
        priya.user_id,
    )

    # --- G1: accepted, by a person; never by the agent (INV-1) --------------------------------
    agent = _agent(j, engagement, priya, "acceptance.record")
    with pytest.raises(Forbidden):
        await authorise(
            agent, "acceptance.record", await engagement_resource(agent.tenant, engagement)
        )
    assert (await j.accept(priya, engagement)).status_code == 200
    assert await j.status(engagement) == "accepted"
    assert (await j.accept(priya, ashford)).status_code == 200
    # Priya confirms her own independence (SPEC-025 AC-5): the staff gate before client data.
    for made in (engagement, ashford):
        confirmed = await j.post(priya, f"/v1/engagements/{made}/independence", {"confirm": True})
        assert confirmed.status_code == 200, confirmed.text

    # --- G3: the letter -----------------------------------------------------------------------
    # The engagement should now read `contracted` ("Letter signed"); it stays `accepted` (strict
    # xfail below). The gate itself opens: the letter is signed and nothing blocks client data.
    signed = await j.letter(priya, engagement)
    assert signed.status_code == 200, signed.text
    setup = cast(Json, signed.json())
    assert cast(Json, setup["letter"])["status"] == "signed"
    assert setup["blocked"] is None
    assert (await j.letter(priya, ashford)).status_code == 200

    # --- 12 monthly closes (C1; SPEC-047 AC-11) -----------------------------------------------
    for period in PERIODS:
        await create_work_item(
            priya.context(),
            engagement,
            "close",
            name=f"{period} close",
            details={"period": period},
        )
    await create_work_item(
        priya.context(), ashford, "close", name="2026-07 close", details={"period": "2026-07"}
    )
    listed = await j.get(priya, f"/v1/work-items?engagement_id={engagement}&kind=close")
    assert listed.status_code == 200, listed.text
    page = cast(Json, listed.json())
    assert page["total"] == 12
    periods = await seed.rows("SELECT period FROM closes WHERE engagement_id = $1", engagement)
    assert sorted(str(r["period"]) for r in periods) == list(PERIODS)

    # --- the request: uploaded by the client, received by Priya -------------------------------
    july = await j.request(priya, engagement, "July 2026 bank statements, all operating accounts")
    other = await j.request(priya, ashford, "July 2026 bank statements")
    tess = await j.client_user("Tess Moreno", engagement)
    assert await j.item_status(july) == "requested"

    uploaded = await j.upload(tess, engagement, july)
    assert uploaded.status_code == 201, uploaded.text
    version = uuid.UUID(str(cast(Json, uploaded.json())["evidence_version_id"]))
    assert await j.item_status(july) == "uploaded"

    accepted = await j.post(
        priya, f"/v1/engagements/{engagement}/evidence-versions/{version}/decision/accept"
    )
    assert accepted.status_code == 201, accepted.text
    assert await j.item_status(july) == "received"

    # --- INV-1: no final verb by the agent ----------------------------------------------------
    agent = _agent(j, engagement, priya, "evidence.accept")
    with pytest.raises(Forbidden):
        await authorise(
            agent, "evidence.accept", await engagement_resource(agent.tenant, engagement)
        )
    checked: list[str] = []
    for table in FINAL_VERB_TABLES:
        has_kind = await seed.value(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = $1 AND column_name = 'actor_kind'",
            table,
        )
        if not has_kind:
            continue  # not built yet, or no actor column: it joins the check when it lands
        agent_rows = await seed.value(_AGENT_ROWS.format(table), j.tenant)
        assert agent_rows == 0, table
        checked.append(table)
    assert "review_decisions" in checked
    decided = await seed.rows(
        "SELECT decision, actor_kind, actor_id FROM review_decisions WHERE tenant_id = $1",
        j.tenant,
    )
    assert [tuple(r) for r in decided] == [("accept", "human", str(priya.user_id))]

    # --- INV-3: Lena, walled, gets 404 and no data --------------------------------------------
    for path in (
        f"/v1/engagements/{engagement}",
        f"/v1/engagements/{engagement}/request-items",
        f"/v1/engagements/{engagement}/request-items/{july}/uploads",
        f"/v1/engagements/{engagement}/work-items",
    ):
        walled = await j.get(lena, path)
        assert walled.status_code == 404, (path, walled.status_code)
    listed_for_lena = cast(list[Json], (await j.get(lena, "/v1/engagements")).json())
    assert str(engagement) not in {str(e["id"]) for e in listed_for_lena}
    assert str(ashford) in {str(e["id"]) for e in listed_for_lena}
    lena_work = cast(Json, (await j.get(lena, "/v1/work-items")).json())
    assert all(str(r["engagement_id"]) != str(engagement) for r in lena_work["items"])
    # No count leaks either: only Ashford's one close counts, never Copperleaf's twelve.
    assert lena_work["total"] == 1

    # The database side (chapter 10 section 10.6): no read event for the walled client.
    assert (
        await seed.value(
            "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND actor_id = $2 "
            "AND (engagement_id = $3 OR client_id = $4)",
            j.tenant,
            lena.user_id,
            engagement,
            client,
        )
        == 0
    )

    # --- INV-4: Tess sees only her grant ------------------------------------------------------
    mine = await j.get(tess, f"/v1/engagements/{engagement}/request-items")
    assert mine.status_code == 200, mine.text
    assert {str(r["id"]) for r in cast(list[Json], mine.json())} == {str(july)}
    # A crafted URL to Ashford's scope is refused with no data. Whether it is told apart from a
    # record that does not exist (404 parity, F-03 story 5.2) is the strict xfail below.
    for path in (
        f"/v1/engagements/{ashford}",
        f"/v1/engagements/{ashford}/request-items",
        f"/v1/engagements/{ashford}/request-items/{other}/uploads",
    ):
        crafted = await j.get(tess, path)
        assert crafted.status_code in (403, 404), (path, crafted.status_code)
        assert str(other) not in crafted.text and "Ashford" not in crafted.text
    refused = await j.upload(tess, ashford, other)
    assert refused.status_code in (403, 404), refused.text
    assert await j.item_status(other) == "requested"  # untouched
    assert (
        await seed.value(
            "SELECT count(*) FROM evidence_versions WHERE engagement_id = $1", ashford
        )
        == 0
    )

    # The database side: every read event of Tess's falls within her grant.
    assert (
        await seed.value(
            "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND actor_id = $2 "
            "AND engagement_id IS DISTINCT FROM $3",
            j.tenant,
            tess.user_id,
            engagement,
        )
        == 0
    )

    # --- INV-5: every state change is attributed to the person who made it --------------------
    events = await j.audit(start)
    by_action: dict[str, list[dict[str, object]]] = {}
    for event in events:
        by_action.setdefault(str(event["action"]), []).append(event)
    assert {e["actor_kind"] for e in events} <= {"human", "system"}
    for action in ("engagement.created", "engagement.accepted", "engagement.letter_recorded"):
        rows = [e for e in by_action.get(action, []) if e["target_id"] == str(engagement)]
        assert len(rows) == 1, (action, rows)
        assert rows[0]["actor_kind"] == "human"
        assert rows[0]["actor_id"] == str(priya.user_id)
        assert rows[0]["on_behalf_of"] is None
    closes = [
        e for e in by_action.get("work_item.created", []) if e["target_id"] == str(engagement)
    ]
    assert len(closes) == 12
    assert {(e["actor_kind"], e["actor_id"]) for e in closes} == {("human", str(priya.user_id))}
    upload_rows = by_action.get("evidence.uploaded", [])
    assert [(e["actor_kind"], e["actor_id"]) for e in upload_rows] == [
        ("human", str(tess.user_id))
    ]
    assert not any(e["actor_kind"] == "agent" for e in events)
    # Every person-made change names one of the two people who acted, never anyone else.
    people = {str(priya.user_id), str(tess.user_id)}
    assert {str(e["actor_id"]) for e in events if e["actor_kind"] == "human"} <= people

    def who_did(action: str, target: uuid.UUID | None = None) -> list[tuple[object, object]]:
        return [
            (e["actor_kind"], e["actor_id"])
            for e in by_action.get(action, [])
            if target is None or e["target_id"] == str(target)
        ]

    # The request's two moves: uploaded by Tess, received by Priya's decision.
    assert who_did("request_item.uploaded", july) == [("human", str(tess.user_id))]
    assert who_did("request_item.received", july) == [("human", str(priya.user_id))]
    assert who_did("review_decision.created") == [("human", str(priya.user_id))]
    # The lifecycle move has its outbox event beside its audit row (SPEC-047 AC-15).
    moves = await seed.rows(
        "SELECT payload->>'from_status' AS f, payload->>'to_status' AS t FROM outbox "
        "WHERE tenant_id = $1 AND event_type = 'engagement.status_changed' "
        "AND payload->>'engagement_id' = $2 ORDER BY id",
        j.tenant,
        str(engagement),
    )
    assert (moves[0]["f"], moves[0]["t"]) == ("prospect", "accepted")
    assert len(moves) == len(
        [e for e in by_action.get("engagement.accepted", []) if e["target_id"] == str(engagement)]
    )


# ================================================================================================
# Where the code does not yet do what the plan says (strict xfails; each names the gap)
# ================================================================================================


async def _priya(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> tuple[Journey, Who]:
    j = await _journey(seed, http, idp)
    return j, await j.person("Priya Raman", firm_role="practice_leader")


@pytest.mark.xfail(
    strict=True,
    reason="BUG: POST /v1/engagements writes the column default `active`. F-03 section 1 and "
    "story 1.2 start a new engagement in `prospect`; insert_engagement sets no status and "
    "migration 0069 kept DEFAULT 'active'. See #338.",
)
async def test_a_new_engagement_starts_in_prospect(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    j, priya = await _priya(seed, http, idp)
    made = await j.create(priya, "Copperleaf Coffee Roasters, Inc.", "2026 Close")
    assert await j.status(uuid.UUID(str(made["id"]))) == "prospect"


@pytest.mark.xfail(
    strict=True,
    reason="BUG: recording the signed letter leaves an accepted engagement `accepted`. "
    "transitions.LIFECYCLE has the system move accepted -> contracted, but record_letter never "
    "makes it (F-03 section 4: `contracted` follows `letter.record`). See #338.",
)
async def test_recording_the_signed_letter_moves_accepted_to_contracted(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    j, priya = await _priya(seed, http, idp)
    engagement = uuid.UUID(
        str((await j.create(priya, "Copperleaf Coffee Roasters, Inc.", "2026 Close"))["id"])
    )
    await j.prospect(engagement)
    assert (await j.accept(priya, engagement)).status_code == 200
    assert await j.status(engagement) == "accepted"
    assert (await j.letter(priya, engagement)).status_code == 200
    assert await j.status(engagement) == "contracted"


@pytest.mark.xfail(
    strict=True,
    reason="BUG: a client user gets 403 for another client's engagement and 404 for one that "
    "does not exist, which tells the two apart. F-03 story 5.2 and POR-02e (INV-4; DEC-43) "
    "answer 404. See #338.",
)
async def test_another_clients_engagement_answers_as_if_it_did_not_exist(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    j, priya = await _priya(seed, http, idp)
    mine = uuid.UUID(
        str((await j.create(priya, "Copperleaf Coffee Roasters, Inc.", "2026"))["id"])
    )
    theirs = uuid.UUID(str((await j.create(priya, "Ashford Mills", "2026"))["id"]))
    tess = await j.client_user("Tess Moreno", mine)
    missing = await j.get(tess, f"/v1/engagements/{uuid.uuid4()}")
    assert missing.status_code == 404
    other = await j.get(tess, f"/v1/engagements/{theirs}")
    assert (other.status_code, other.json()) == (missing.status_code, missing.json())


@pytest.mark.xfail(
    strict=True,
    reason="BUG: a request on an engagement with no work item yet (a new CAS close) answers 500: "
    "the default binder's insert into request_lists violates its work-item foreign key instead "
    "of a refusal the person can act on. See #338.",
)
async def test_a_request_before_any_work_item_is_refused_not_a_server_error(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    j, priya = await _priya(seed, http, idp)
    engagement = uuid.UUID(
        str((await j.create(priya, "Copperleaf Coffee Roasters, Inc.", "2026 Close"))["id"])
    )
    response = await j.post(
        priya,
        f"/v1/engagements/{engagement}/request-items",
        {"description": "July 2026 bank statements", "audit_area": "Cash"},
    )
    assert 400 <= response.status_code < 500, response.text
