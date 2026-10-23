"""P-07-T16 against Postgres (SPEC-321 AC-18, AC-19; P-07 Story 6.3; DEC-225): "Hannah creates the
Fairhaven EBP audit from a draft in one unit of work and Granite Peak's draft cannot pass step 1
until G1 is met." Also: the catalogue holds 18 types and never single audit, SOC cards need the
attest entitlement, drafts are own-scope and versioned, a duplicate answers 409 until confirmed,
and a created draft answers its first result again."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

import abacus.modules.closes.api  # registers the close kind
import abacus.modules.engagements.api  # registers the gates, kinds and authz lookups
import abacus.modules.notices.api  # registers the notice kind
import abacus.modules.tax.api  # registers the tax_return kind
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.engagements import drafts
from abacus.modules.engagements.drafts import (
    DraftChange,
    DraftIncomplete,
    DraftStaleVersion,
    UnknownEngagementType,
)
from abacus.modules.engagements.record import GateUnmet
from abacus.modules.engagements.service import PossibleDuplicate
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.engagements.api and abacus.modules.tax.api
assert abacus.modules.closes.api and abacus.modules.notices.api
pytestmark = pytest.mark.asyncio


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

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Brightwater Hale', true)",
            self.tenant,
        )
        return self

    async def person(
        self, *, firm_role: str | None = None, level: str | None = None
    ) -> AuthContext:
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Hannah Leclerc') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level) "
            "VALUES ($1, $2, $3, 'active', $4)",
            self.tenant,
            user,
            firm_role,
            level,
        )
        return AuthContext(
            tenant=TenantContext(self.tenant, "human", str(user)),
            user_id=user,
            membership_id=uuid.uuid4(),
            firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )

    async def client(self, name: str) -> tuple[uuid.UUID, uuid.UUID]:
        client = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO clients (tenant_id, name, kind) VALUES ($1, $2, 'plan_sponsor') "
                    "RETURNING id",
                    self.tenant,
                    name,
                )
            )
        )
        entity = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
                    "RETURNING id",
                    self.tenant,
                    client,
                    f"{name} 401(k) Plan",
                )
            )
        )
        return client, entity

    async def prospect(
        self,
        client: tuple[uuid.UUID, uuid.UUID],
        partner: AuthContext,
        *,
        type_: str = "ebp_audit",
        status: str = "accepted",
        accepted: bool = True,
    ) -> uuid.UUID:
        engagement = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                    "VALUES ($1, $2, $3, 'PY2025 EBP Audit', '2025-01-01', '2025-12-31', $4, "
                    "$5, $6) RETURNING id",
                    self.tenant,
                    client[0],
                    client[1],
                    partner.user_id,
                    type_,
                    status,
                )
            )
        )
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'engagement_partner')",
            self.tenant,
            engagement,
            partner.user_id,
        )
        if accepted:
            await self.seed.run(
                "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
                "decided_by, documented_at) VALUES ($1, $2, 'new_client', 'accepted', "
                "'Margaret Okonkwo', 'Acceptance memo')",
                self.tenant,
                engagement,
            )
        return engagement


def _payload(partner: AuthContext, staff: AuthContext) -> dict[str, object]:
    return {
        "name": "PY2025 EBP Audit",
        "standards_code": "gaas_nonissuer_au_c_703",
        "fiscal_period_start": "2025-01-01",
        "fiscal_period_end": "2025-12-31",
        "period_label": "PY2025",
        "team": [
            {"user_id": str(partner.user_id), "role": "engagement_partner"},
            {"user_id": str(staff.user_id), "role": "staff"},
        ],
    }


async def _world(migrated_db: MigratedDatabase) -> tuple[_Firm, AuthContext, AuthContext]:
    firm = await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    hannah = await firm.person(firm_role="firm_admin")
    margaret = await firm.person(level="partner")
    return firm, hannah, margaret


async def test_ac18_the_catalogue_is_18_types_and_never_single_audit(
    migrated_db: MigratedDatabase,
) -> None:
    _, hannah, _ = await _world(migrated_db)
    items = await drafts.catalogue(hannah)
    assert len(items) == 18
    families = [i.entry.family for i in items]
    assert (families.count("tax"), families.count("audit_assurance")) == (8, 8)
    assert "single_audit" not in {i.entry.code for i in items}
    soc = {i.entry.code: i.available for i in items if i.entry.code in ("soc1", "soc2")}
    assert soc == {"soc1": False, "soc2": False}  # no attest entitlement in this firm
    with pytest.raises(UnknownEngagementType):
        await drafts.create_draft(
            hannah,
            client_id=None,
            client_entity_id=None,
            type_code="single_audit",
            step="client_type",
            payload={},
        )


async def test_ac19_fairhaven_is_created_from_a_draft_in_one_unit_of_work(
    migrated_db: MigratedDatabase,
) -> None:
    firm, hannah, margaret = await _world(migrated_db)
    fiona = await firm.person()
    fairhaven = await firm.client("Fairhaven Foods, Inc.")
    target = await firm.prospect(fairhaven, margaret)

    draft = await drafts.create_draft(
        hannah,
        client_id=fairhaven[0],
        client_entity_id=fairhaven[1],
        type_code="ebp_audit",
        step="client_type",
        payload=_payload(margaret, fiona),
    )
    assert {g.gate: g.met for g in draft.gates}["G1"] is True
    check = await drafts.validate_draft(hannah, draft.id, "client_type")
    assert check.valid and not check.problems

    made = await drafts.create_from_draft(hannah, draft.id, confirm_duplicate=False)
    assert made.engagement_id == target and made.engagement_status == "accepted"
    assert len(made.work_item_ids) == 1  # the engagement's one assurance work item
    assert made.independence_requested_user_ids == [fiona.user_id]
    again = await drafts.create_from_draft(hannah, draft.id, confirm_duplicate=False)
    assert again.engagement_id == target  # a created draft answers its first result
    created = await firm.seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 AND action = 'engagement.created'",
        firm.tenant,
    )
    assert len(created) == 1
    label = await firm.seed.value("SELECT period_label FROM engagements WHERE id = $1", target)
    assert label == "PY2025"


async def test_ac19_granite_peak_cannot_pass_step_1_until_g1_is_met(
    migrated_db: MigratedDatabase,
) -> None:
    firm, hannah, margaret = await _world(migrated_db)
    staff = await firm.person()
    granite = await firm.client("Granite Peak")
    draft = await drafts.create_draft(
        hannah,
        client_id=granite[0],
        client_entity_id=granite[1],
        type_code="ebp_audit",
        step="client_type",
        payload=_payload(margaret, staff),
    )
    check = await drafts.validate_draft(hannah, draft.id, "client_type")
    assert not check.valid
    assert {g.gate: g.met for g in check.gates}["G1"] is False
    with pytest.raises(GateUnmet):
        await drafts.create_from_draft(hannah, draft.id, confirm_duplicate=False)
    # A Prospect waiting for the partner's decision still blocks.
    await firm.prospect(granite, margaret, status="prospect", accepted=False)
    assert not (await drafts.validate_draft(hannah, draft.id, "client_type")).valid


async def test_ac19_drafts_are_own_scope_versioned_and_complete_before_create(
    migrated_db: MigratedDatabase,
) -> None:
    firm, hannah, _ = await _world(migrated_db)
    other = await firm.person(firm_role="firm_admin")
    client = await firm.client("Lakeshore")
    draft = await drafts.create_draft(
        hannah,
        client_id=client[0],
        client_entity_id=client[1],
        type_code="fs_audit",
        step="client_type",
        payload={},
    )
    with pytest.raises(NotFound):
        await drafts.get_draft(other, draft.id)
    saved = await drafts.update_draft(
        hannah, draft.id, draft.version, DraftChange(step="period_deadlines")
    )
    assert saved.version == draft.version + 1
    with pytest.raises(DraftStaleVersion):
        await drafts.update_draft(hannah, draft.id, draft.version, DraftChange(step="client_type"))
    with pytest.raises(DraftIncomplete):
        await drafts.create_from_draft(hannah, draft.id, confirm_duplicate=False)
    await drafts.discard_draft(hannah, draft.id)
    with pytest.raises(NotFound):
        await drafts.get_draft(hannah, draft.id)
    staff = await firm.person()
    with pytest.raises(Forbidden):  # no `engagement.create` without a firm role or partner level
        await drafts.catalogue(staff)


async def test_ac19_a_duplicate_answers_409_until_confirmed(migrated_db: MigratedDatabase) -> None:
    firm, hannah, margaret = await _world(migrated_db)
    staff = await firm.person()
    ferris = await firm.client("Morgan & Kai Ferris")
    target = await firm.prospect(ferris, margaret, type_="tax_compliance")
    await firm.prospect(ferris, margaret, type_="tax_compliance", status="active")
    payload = {**_payload(margaret, staff), "name": "TY2025 Form 1040"}
    draft = await drafts.create_draft(
        hannah,
        client_id=ferris[0],
        client_entity_id=ferris[1],
        type_code="form_1040",
        step="client_type",
        payload=payload,
    )
    with pytest.raises(PossibleDuplicate):
        await drafts.create_from_draft(hannah, draft.id, confirm_duplicate=False)
    made = await drafts.create_from_draft(hannah, draft.id, confirm_duplicate=True)
    assert made.engagement_id == target
    forms = await firm.seed.rows(
        "SELECT form, tax_year FROM tax_returns WHERE engagement_id = $1", target
    )
    assert [(r["form"], r["tax_year"]) for r in forms] == [("1040", 2025)]
