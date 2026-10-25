"""P-07-T10 against Postgres (P-07 Story 1.3; DEC-52, DEC-141, DEC-223): "A reveal returns the
value once with one audit row and no log line, an offshore member gets 403, and an SSN write on
a real tenant answers 422." Also: the value is sealed (never in the row, the outbox or the audit
trail), a duplicate TIN is a 409, walls answer 404, the record says who may reveal, and the
route answers `no-store`. Only 9xx fake SSNs (the repository is public)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

import abacus.modules.engagements.api  # registers the client facts and authz lookups
from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    configure_verifier,
    reset_verifier,
)
from abacus.modules.organisations import live
from abacus.modules.organisations.api import (
    TinConflict,
    TinKindNotAllowed,
    seal_tin,
)
from abacus.modules.organisations.tin import (
    REVEAL_LIMIT,
    TinRevealNeedsMfa,
    TinRevealRateLimited,
    clear_tin,
    reveal_tin,
)
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.engagements.api
pytestmark = pytest.mark.asyncio

FAKE_SSN = "900-12-3456"
FAKE_SSN_DIGITS = "900123456"
FAKE_EIN = "90-0000287"


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.admin: AuthContext | None = None

    async def make(self, *, synthetic: bool = True) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Brightwater Hale', $2)",
            self.tenant,
            synthetic,
        )
        await self.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'clients.v2', 'true', 'test-seed', 'P-07-T10 tests')",
            self.tenant,
        )
        return self

    @property
    def tenant_ctx(self) -> TenantContext:
        return TenantContext(self.tenant, "human", "seed")

    async def person(
        self,
        *,
        firm_role: str | None = None,
        offshore: bool = False,
        mfa_minutes_ago: int | None = 1,
    ) -> tuple[AuthContext, str]:
        subject = f"sub-{uuid.uuid4().hex}"
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ($1, $2, $3, 'Daniel Reyes') RETURNING id",
                    ISSUER,
                    subject,
                    f"{subject}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, offshore) "
            "VALUES ($1, $2, $3, 'active', $4)",
            self.tenant,
            user,
            firm_role,
            offshore,
        )
        mfa = (
            None
            if mfa_minutes_ago is None
            else datetime.now(UTC) - timedelta(minutes=mfa_minutes_ago)
        )
        ctx = AuthContext(
            tenant=TenantContext(self.tenant, "human", str(user)),
            user_id=user,
            membership_id=uuid.uuid4(),
            firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
            mfa_at=mfa,
        )
        return ctx, subject

    async def client(self, name: str) -> tuple[uuid.UUID, uuid.UUID]:
        client = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO clients (tenant_id, name, kind) VALUES ($1, $2, 'household') "
                    "RETURNING id",
                    self.tenant,
                    name,
                )
            )
        )
        entity = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name, entity_type) "
                    "VALUES ($1, $2, $3, 'individual') RETURNING id",
                    self.tenant,
                    client,
                    name,
                )
            )
        )
        return client, entity

    async def engagement(self, client: uuid.UUID, entity: uuid.UUID, by: uuid.UUID) -> uuid.UUID:
        return uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type) "
                    "VALUES ($1, $2, $3, 'TY2025 Form 1040', '2025-01-01', '2025-12-31', $4, "
                    "'tax_compliance') RETURNING id",
                    self.tenant,
                    client,
                    entity,
                    by,
                )
            )
        )

    async def member(self, engagement: uuid.UUID, who: AuthContext, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            engagement,
            who.user_id,
            role,
        )

    async def seal(
        self, entity: uuid.UUID, raw: str, kind: str, *, by: AuthContext | None = None
    ) -> None:
        """Seal as a person who may edit the client (a firm admin unless `by` is given)."""
        who = by or self.admin or (await self.person(firm_role="firm_admin"))[0]
        self.admin = self.admin or who
        async with uow(who.tenant) as tx:
            await seal_tin(tx, who, entity, raw, kind)  # pyright: ignore[reportArgumentType] -- a TIN kind code

    async def count(self, sql: str, *args: object) -> int:
        return int(str(await self.seed.value(sql, *args)))


async def _world(
    migrated_db: MigratedDatabase, *, synthetic: bool = True
) -> tuple[_Firm, AuthContext, uuid.UUID, uuid.UUID, uuid.UUID]:
    firm = await _Firm(Seeder(migrated_db.superuser_dsn)).make(synthetic=synthetic)
    partner, _ = await firm.person()
    client, entity = await firm.client("Ellen Feld")
    engagement = await firm.engagement(client, entity, partner.user_id)
    await firm.member(engagement, partner, "engagement_partner")
    return firm, partner, client, entity, engagement


async def test_ac9_reveal_returns_the_value_once_with_one_audit_row_and_no_log_line(
    migrated_db: MigratedDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    firm, partner, client, entity, engagement = await _world(migrated_db)
    await firm.seal(entity, FAKE_SSN, "ssn")
    capsys.readouterr()

    revealed = await reveal_tin(partner, entity, "prepare_return")

    assert revealed.value == FAKE_SSN_DIGITS and revealed.kind == "ssn"
    captured = capsys.readouterr()
    assert FAKE_SSN_DIGITS not in captured.out + captured.err
    assert "3456" not in captured.out + captured.err
    audit = await firm.seed.rows(
        "SELECT action, target_type, target_id, after_ref::text AS after FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'tin.revealed'",
        firm.tenant,
    )
    assert len(audit) == 1
    assert audit[0]["target_id"] == str(entity)
    assert str(revealed.reveal_id) in audit[0]["after"]
    assert FAKE_SSN_DIGITS not in audit[0]["after"]
    reveals = await firm.seed.rows(
        "SELECT user_id, engagement_id, reason_code, actor_kind FROM tin_reveals "
        "WHERE tenant_id = $1",
        firm.tenant,
    )
    assert [(r["user_id"], r["engagement_id"], r["reason_code"]) for r in reveals] == [
        (partner.user_id, engagement, "prepare_return")
    ]
    assert reveals[0]["actor_kind"] == "human"
    assert "tin.reveal" in (await live.client_record(partner, client)).allowed_actions


async def test_ac9_the_tin_is_sealed_and_never_in_the_row_outbox_or_audit_trail(
    migrated_db: MigratedDatabase,
) -> None:
    firm, partner, client, entity, _ = await _world(migrated_db)
    await firm.seal(entity, FAKE_SSN, "ssn")

    row = (
        await firm.seed.rows(
            "SELECT tin_sealed, tin_last4, tin_kind, tin_status, tin_fingerprint "
            "FROM client_entities WHERE id = $1",
            entity,
        )
    )[0]
    assert row["tin_last4"] == "3456" and row["tin_kind"] == "ssn"
    assert row["tin_status"] == "on_file"
    assert FAKE_SSN_DIGITS.encode() not in bytes(row["tin_sealed"])
    assert FAKE_SSN_DIGITS.encode() not in bytes(row["tin_fingerprint"])
    for sql in (
        "SELECT coalesce(string_agg(payload::text, ''), '') FROM outbox WHERE tenant_id = $1",
        "SELECT coalesce(string_agg(coalesce(after_ref::text, '') || "
        "coalesce(before_ref::text, ''), ''), '') FROM audit_events WHERE tenant_id = $1",
    ):
        assert FAKE_SSN_DIGITS not in str(await firm.seed.value(sql, firm.tenant))
    record = await live.client_record(partner, client)
    assert (record.entities[0].tin_kind, record.entities[0].tin_last4) == ("ssn", "3456")


@pytest.mark.xfail(
    strict=True,
    reason="#395 TASK-1207: offshore is a wall until T-01 (DEC-319)",
)
async def test_ac9_an_offshore_member_gets_403_and_nothing_is_logged(
    migrated_db: MigratedDatabase,
) -> None:
    firm, _, client, entity, engagement = await _world(migrated_db)
    await firm.seal(entity, FAKE_SSN, "ssn")
    offshore, _ = await firm.person(offshore=True)
    await firm.member(engagement, offshore, "manager")

    with pytest.raises(Forbidden):
        await reveal_tin(offshore, entity, "review_return")
    assert "tin.reveal" not in (await live.client_record(offshore, client)).allowed_actions
    assert (
        await firm.count("SELECT count(*) FROM tin_reveals WHERE tenant_id = $1", firm.tenant) == 0
    )


async def test_ac9_no_recent_mfa_no_role_or_a_firm_role_alone_is_403(
    migrated_db: MigratedDatabase,
) -> None:
    firm, _, client, entity, engagement = await _world(migrated_db)
    await firm.seal(entity, FAKE_SSN, "ssn")
    stale, _ = await firm.person(mfa_minutes_ago=60)
    await firm.member(engagement, stale, "manager")
    staff, _ = await firm.person()
    await firm.member(engagement, staff, "staff")
    admin, _ = await firm.person(firm_role="firm_admin")

    # Stale MFA is the step-up answer (the role allowed it); no role or a firm role alone is a
    # plain denial at the role layer (security review, DEC-227).
    with pytest.raises(TinRevealNeedsMfa):
        await reveal_tin(stale, entity, "verify_identity")
    for who in (staff, admin):
        with pytest.raises(Forbidden) as denied:
            await reveal_tin(who, entity, "verify_identity")
        assert denied.value.layer != "attribute"
    # Stale MFA still shows the control: the UI steps up (allowed_actions leaves MFA to acting).
    assert "tin.reveal" in (await live.client_record(stale, client)).allowed_actions
    assert "tin.reveal" not in (await live.client_record(admin, client)).allowed_actions
    assert (
        await firm.count("SELECT count(*) FROM tin_reveals WHERE tenant_id = $1", firm.tenant) == 0
    )


async def test_ac9_a_walled_partner_gets_404_and_an_entity_without_a_tin_404(
    migrated_db: MigratedDatabase,
) -> None:
    firm, partner, client, entity, _ = await _world(migrated_db)
    with pytest.raises(NotFound):  # no TIN on file yet
        await reveal_tin(partner, entity, "prepare_return")
    await firm.seal(entity, FAKE_SSN, "ssn")
    admin, _ = await firm.person(firm_role="firm_admin")
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        partner.user_id,
        client,
        admin.user_id,
    )
    with pytest.raises(NotFound):
        await reveal_tin(partner, entity, "prepare_return")


async def test_ac9_an_ssn_on_a_real_firm_is_422_and_an_ein_is_accepted(
    migrated_db: MigratedDatabase,
) -> None:
    firm, partner, _, entity, _ = await _world(migrated_db, synthetic=False)
    for kind in ("ssn", "itin"):
        with pytest.raises(TinKindNotAllowed):
            await firm.seal(entity, FAKE_SSN, kind)
    await firm.seal(entity, FAKE_EIN, "ein")
    revealed = await reveal_tin(partner, entity, "file_or_correct_filing")
    assert revealed.kind == "ein" and revealed.value == "900000287"


async def test_ac9_the_same_tin_twice_in_a_firm_is_409(migrated_db: MigratedDatabase) -> None:
    firm, _, _, entity, _ = await _world(migrated_db)
    _, other = await firm.client("Marcus Feld")
    await firm.seal(entity, FAKE_SSN, "ssn")
    with pytest.raises(TinConflict):
        await firm.seal(other, FAKE_SSN, "ssn")
    # Another firm may hold the same number: fingerprints are per firm.
    elsewhere, *_ = await _world(migrated_db)
    _, theirs = await elsewhere.client("Ellen Feld")
    await elsewhere.seal(theirs, FAKE_SSN, "ssn")


# --- over HTTP: the route answers no-store ------------------------------------------------------


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


async def test_ac9_the_route_answers_no_store_and_refuses_without_mfa(
    migrated_db: MigratedDatabase, idp: FakeIdentityProvider
) -> None:
    firm, _, _, entity, engagement = await _world(migrated_db)
    await firm.seal(entity, FAKE_SSN, "ssn")
    manager, subject = await firm.person()
    await firm.member(engagement, manager, "manager")
    path = f"/v1/client-entities/{entity}/tin/reveal"
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        no_mfa = await http.post(
            path,
            json={"reason": "review_return"},
            headers={"Authorization": f"Bearer {idp.token(subject)}"},
        )
        assert no_mfa.status_code == 403
        assert no_mfa.json()["detail"] == "mfa_step_up_required"  # the UI steps up on this
        assert FAKE_SSN_DIGITS not in no_mfa.text
        answer = await http.post(
            path,
            json={"reason": "review_return"},
            headers={"Authorization": f"Bearer {idp.token(subject, mfa=True)}"},
        )
        assert answer.status_code == 200, answer.text
        assert answer.json()["value"] == FAKE_SSN_DIGITS
        assert answer.headers["cache-control"] == "no-store"
        bad = await http.post(
            path,
            json={"reason": "curiosity"},
            headers={"Authorization": f"Bearer {idp.token(subject, mfa=True)}"},
        )
        assert bad.status_code == 422
    assert (
        await firm.count(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'tin.revealed'",
            firm.tenant,
        )
        == 1
    )


# --- security review (DEC-227) ------------------------------------------------------------------


async def test_ac9_reveals_beyond_the_hourly_cap_are_429_logged_and_audited(
    migrated_db: MigratedDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    firm, partner, _, entity, engagement = await _world(migrated_db)
    await firm.seal(entity, FAKE_SSN, "ssn")
    # An old reveal falls outside the rolling hour; REVEAL_LIMIT - 1 recent ones leave one.
    for minutes in [90] + [5] * (REVEAL_LIMIT - 1):
        await firm.seed.run(
            "INSERT INTO tin_reveals (tenant_id, client_entity_id, engagement_id, user_id, "
            "reason_code, mfa_at, actor_kind, revealed_at) VALUES ($1, $2, $3, $4, "
            "'prepare_return', now(), 'human', now() - make_interval(mins => $5))",
            firm.tenant,
            entity,
            engagement,
            partner.user_id,
            minutes,
        )
    await reveal_tin(partner, entity, "prepare_return")  # the last one inside the cap
    capsys.readouterr()
    with pytest.raises(TinRevealRateLimited) as limited:
        await reveal_tin(partner, entity, "review_return")
    facts = limited.value.facts
    assert facts["limit"] == REVEAL_LIMIT
    assert isinstance(facts["retry_after"], int) and 0 < facts["retry_after"] <= 3600
    out = capsys.readouterr().out
    assert "tin.reveal_throttled" in out and str(partner.user_id) in out
    assert "review_return" in out and FAKE_SSN_DIGITS not in out and "3456" not in out
    assert (
        await firm.count(
            "SELECT count(*) FROM tin_reveals WHERE tenant_id = $1 AND revealed_at > "
            "now() - interval '1 hour'",
            firm.tenant,
        )
        == REVEAL_LIMIT
    )
    assert (
        await firm.count(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'tin.reveal_throttled'",
            firm.tenant,
        )
        == 1
    )
    # Another person's cap is their own.
    other, _ = await firm.person()
    await firm.member(engagement, other, "manager")
    assert (await reveal_tin(other, entity, "prepare_return")).value == FAKE_SSN_DIGITS


async def test_ac9_sealing_needs_a_person_who_may_edit_the_client(
    migrated_db: MigratedDatabase,
) -> None:
    firm, partner_on_team, client, entity, engagement = await _world(migrated_db)
    manager, _ = await firm.person()
    await firm.member(engagement, manager, "manager")  # reads the client, can't edit it
    with pytest.raises(Forbidden):  # no `client.update`: nothing is touched
        await firm.seal(entity, FAKE_SSN, "ssn", by=manager)
    outsider, _ = await firm.person()
    with pytest.raises(NotFound):  # off the client entirely: absent
        await firm.seal(entity, FAKE_SSN, "ssn", by=outsider)
    admin, _ = await firm.person(firm_role="firm_admin")
    walled_admin, _ = await firm.person(firm_role="firm_admin")
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        walled_admin.user_id,
        client,
        admin.user_id,
    )
    with pytest.raises(NotFound):  # a wall reads as absence, never as a conflict
        await firm.seal(entity, FAKE_SSN, "ssn", by=walled_admin)
    with pytest.raises(NotFound):
        async with uow(walled_admin.tenant) as tx:
            await clear_tin(tx, walled_admin, entity)
    assert (
        await firm.count(
            "SELECT count(*) FROM client_entities WHERE id = $1 AND tin_status = 'on_file'",
            entity,
        )
        == 0
    )
    assert partner_on_team.user_id != admin.user_id


async def test_ac9_a_conflict_is_generic_and_a_check_failure_is_not_a_conflict(
    migrated_db: MigratedDatabase,
) -> None:
    firm, _, _, entity, _ = await _world(migrated_db)
    _, other = await firm.client("Marcus Feld")
    await firm.seal(entity, FAKE_SSN, "ssn")
    with pytest.raises(TinConflict) as conflict:
        await firm.seal(other, FAKE_SSN, "ssn")
    assert conflict.value.facts == {}  # no hint of which entity holds it
    with pytest.raises(IntegrityError):  # a CHECK violation (bad kind) is not `tin_conflict`
        await firm.seal(other, "900-55-1234", "passport")
