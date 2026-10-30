"""T-01-T12 (TASK-2213; SPEC-501 AC-24 to AC-27; T-01 §3.3, §3.4) against Postgres: the TRI MFA
predicate, the offshore-disclosure provider and the SSN unlock.

The row's acceptance: Claire Feld must complete two-step verification on her 1040 scope, an
offshore member sees only consented clients with masked TINs, and SSN entry works on a real
tenant only after the gate is registered (the seal path's before and after are pinned in
`test_tin_reveal.py` and P-07-T13's suite). "Sees only consented clients" is offshore's
assignment rule (DEC-319, TASK-1207: offshore is not a wall): a member may be put on a client's
work only under a valid consent, and every TIN they read is masked.

Rows are synthetic probes (AGENTS 16).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import column, select, table

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.modules.engagements.work_items import mfa_tri_scope
from abacus.modules.identity.api import OFFSHORE_DISCLOSURE, consent_given
from abacus.modules.identity.mfa_floor import FLOOR
from abacus.modules.identity.offshore import (
    OffshoreConsentRequired,
    assert_assignable,
    mask_tins,
    offshore_consented,
)
from abacus.modules.identity.slots import consent_column, consented_count
from abacus.modules.organisations.contract import MaskedTinOut, TinRevealOut

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

SHA = hashlib.sha256(b"probe consent text").digest()
SIGNED_AT = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@dataclass(frozen=True)
class Firm:
    tenant: uuid.UUID
    partner: uuid.UUID
    client: uuid.UUID
    entities: tuple[uuid.UUID, ...]
    engagement: uuid.UUID

    @property
    def ctx(self) -> TenantContext:
        return TenantContext(self.tenant, "system", "test:tri_rails")


async def _firm(seed: Seeder, *, entities: int = 2) -> Firm:
    tenant = await seed.firm()
    partner = (await seed.person(tenant)).user_id
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe client') RETURNING id",
            tenant,
        ),
    )
    ids = tuple(
        [
            cast(
                uuid.UUID,
                await seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name) "
                    "VALUES ($1, $2, $3) RETURNING id",
                    tenant,
                    client,
                    f"Probe entity {n}",
                ),
            )
            for n in range(entities)
        ]
    )
    engagement = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) "
            "VALUES ($1, $2, $3, 'Probe 2025', '2025-01-01', '2025-12-31', $4) RETURNING id",
            tenant,
            client,
            ids[0],
            partner,
        ),
    )
    return Firm(tenant, partner, client, ids, engagement)


async def _work_item(seed: Seeder, firm: Firm, kind: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, $4, 'Probe item', $5) RETURNING id",
            firm.tenant,
            firm.engagement,
            firm.client,
            kind,
            firm.partner,
        ),
    )


async def _client_person(
    seed: Seeder, firm: Firm, scope_kind: str, scope_id: uuid.UUID
) -> uuid.UUID:
    person = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://identity.abacus.local', $1, $2, 'Probe client') RETURNING id",
            f"sub-{uuid.uuid4().hex}",
            f"{uuid.uuid4().hex}@example.test",
        ),
    )
    # A client access grant needs a client membership (0084, 0146).
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status, kind) "
        "VALUES ($1, $2, NULL, 'active', 'client')",
        firm.tenant,
        person,
    )
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
        "granted_by, status) VALUES ($1, $2, 'contributor', $3, $4, $5, 'active')",
        firm.tenant,
        person,
        scope_kind,
        scope_id,
        firm.partner,
    )
    return person


async def _offshore_consent(
    seed: Seeder, firm: Firm, entity: uuid.UUID, *, signed: bool = True
) -> uuid.UUID:
    consent = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO consents (tenant_id, client_id, client_entity_id, purpose, tax_years, "
            "provider_terms_version, template_version_id, text_sha256, source, status, "
            "created_by, signed_at) VALUES ($1, $2, $3, 'offshore_disclosure', '{2025}', "
            "'probe', gen_random_uuid(), $4, 'record', $5, $6, $7) RETURNING id",
            firm.tenant,
            firm.client,
            entity,
            SHA,
            "signed" if signed else "requested",
            firm.partner,
            SIGNED_AT if signed else None,
        ),
    )
    await seed.run(
        "INSERT INTO consent_signers (tenant_id, consent_id, user_id, signer_role, required, "
        "signed_at, method) VALUES ($1, $2, $3, 'taxpayer', true, $4, $5)",
        firm.tenant,
        consent,
        firm.partner,
        SIGNED_AT if signed else None,
        "record" if signed else None,
    )
    return consent


# --- AC-24: the TRI MFA predicate ----------------------------------------------------------------


async def test_ac24_a_grant_on_a_tax_return_needs_the_second_step(seed: Seeder) -> None:
    firm = await _firm(seed)
    feld_1040 = await _work_item(seed, firm, "tax_return")
    claire = await _client_person(seed, firm, "work_item", feld_1040)
    assert await mfa_tri_scope(firm.ctx, claire)
    assert "tri_scope" in FLOOR


async def test_ac24_an_engagement_holding_a_return_or_a_k1_package_counts_too(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    engagement_person = await _client_person(seed, firm, "engagement", firm.engagement)
    assert not await mfa_tri_scope(firm.ctx, engagement_person)  # no return yet
    await _work_item(seed, firm, "tax_return")
    assert await mfa_tri_scope(firm.ctx, engagement_person)
    k1 = await _client_person(seed, firm, "k1_package", uuid.uuid4())
    assert await mfa_tri_scope(firm.ctx, k1)


async def test_ac24_other_scopes_are_not_tri_bearing(seed: Seeder) -> None:
    firm = await _firm(seed)
    # One assurance work item per engagement (0068): the engagement's own, if it already has one.
    existing = await seed.value(
        "SELECT id FROM work_items WHERE tenant_id = $1 AND engagement_id = $2 "
        "AND kind = 'assurance'",
        firm.tenant,
        firm.engagement,
    )
    audit = (
        cast(uuid.UUID, existing)
        if existing is not None
        else await _work_item(seed, firm, "assurance")
    )
    person = await _client_person(seed, firm, "work_item", audit)
    assert not await mfa_tri_scope(firm.ctx, person)


# --- AC-25: the offshore-disclosure provider -----------------------------------------------------


async def test_ac25_every_taxpayer_entity_must_hold_the_consent(seed: Seeder) -> None:
    firm = await _firm(seed)
    now = datetime.now(UTC)
    await _offshore_consent(seed, firm, firm.entities[0])
    assert not await offshore_consented(firm.ctx, firm.client)  # one of two
    assert not await consent_given(firm.ctx, firm.client, OFFSHORE_DISCLOSURE, now)
    await _offshore_consent(seed, firm, firm.entities[1], signed=False)
    assert not await offshore_consented(firm.ctx, firm.client)  # requested is not in force
    await _offshore_consent(seed, firm, firm.entities[1])
    assert await offshore_consented(firm.ctx, firm.client)
    assert await consented_count(firm.ctx, OFFSHORE_DISCLOSURE) == 1


async def test_ac25_the_predicate_and_the_check_agree(seed: Seeder) -> None:
    firm = await _firm(seed, entities=1)
    other = await _firm(seed, entities=1)
    await _offshore_consent(seed, firm, firm.entities[0])
    predicate = consent_column(OFFSHORE_DISCLOSURE)
    assert predicate is not None
    clients = table("clients", column("id"))
    async with tenant_session(firm.ctx) as session:
        covered = set(
            (
                await session.execute(
                    select(clients.c.id).where(predicate(clients.c.id, OFFSHORE_DISCLOSURE))
                )
            ).scalars()
        )
    assert covered == {firm.client}
    assert not await offshore_consented(other.ctx, other.client)


async def test_ac25_a_revoked_or_expired_consent_stops_covering(seed: Seeder) -> None:
    firm = await _firm(seed, entities=1)
    consent = await _offshore_consent(seed, firm, firm.entities[0])
    assert await offshore_consented(firm.ctx, firm.client)
    await seed.run(
        "UPDATE consents SET expires_at = $2 WHERE id = $1",
        consent,
        datetime.now(UTC) - timedelta(minutes=1),
    )
    assert not await offshore_consented(firm.ctx, firm.client)


async def test_ac26_an_offshore_member_is_assigned_only_under_consent(seed: Seeder) -> None:
    firm = await _firm(seed, entities=1)
    offshore = (await seed.person(firm.tenant)).user_id
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant,
        offshore,
    )
    with pytest.raises(OffshoreConsentRequired):
        await assert_assignable(firm.ctx, offshore, firm.client)
    await _offshore_consent(seed, firm, firm.entities[0])
    await assert_assignable(firm.ctx, offshore, firm.client)


def test_ac27_tin_fields_are_tri_and_masked_for_offshore_readers() -> None:
    masked = mask_tins(TinRevealOut(entity_id=uuid.uuid4(), kind="ssn", value="123456789"))
    assert masked.value == "•••-••-6789"
    brief = mask_tins(MaskedTinOut(kind="ssn", presence="on_file", last4="6789"))
    assert brief.last4 is None  # nullable: null rather than a mask
    # p07_clients v1 is frozen: the TIN fields are gated by `pii_kind=tin` (what the offshore mask
    # and the reveal's TRI rails key off); `x-tri` lands with the contract's v2 (DEC-1272).
    for model, name in ((TinRevealOut, "value"), (MaskedTinOut, "last4")):
        extra = cast(dict[str, object], model.model_fields[name].json_schema_extra or {})
        assert extra.get("x-pii-kind") == "tin", (model.__name__, name)
