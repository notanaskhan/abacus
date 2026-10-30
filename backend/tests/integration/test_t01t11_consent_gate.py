"""T-01-T11 (TASK-2212; SPEC-501 AC-17 to AC-20; T-01 §3.2; ADR-167) against Postgres: the read
half of C19 condition 6 (`organisations.api`) and the gateway wired to it.

The row's acceptance: a synthetic Ferris context is refused with consent_7216 and audited, a
revocation takes effect on the next call, and existing audit-agent boundary tests stay green
(those run unchanged in tests/unit/ai_gateway). Also: both spouses must sign, expiry and the
year bind, a material provider-terms change means re-consent, `require_tri_consent` names the
taxpayer and writes access events, and the matrix's `consent_given` reads the same rows.

Consent rows are synthetic probes inserted as record mode would write them (capture is
T-01-T10); no consent text is stored (AGENTS 16).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from abacus.ai_gateway import DataSubject, boundary
from abacus.ai_gateway.boundary import DataBoundaryRefused, enforce_boundary
from abacus.kernel import provider_terms
from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.provider_terms import TermsEntry
from abacus.modules.engagements import api as engagements_api  # registers the gateway's check
from abacus.modules.identity.api import consent_given
from abacus.modules.organisations import api as organisations_api
from abacus.modules.organisations.api import TriSubject

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

SIGNED_AT = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)
NOW = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
SHA = hashlib.sha256(b"probe consent text").digest()
assert engagements_api  # imported for its registration


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
class Household:
    tenant: uuid.UUID
    user: uuid.UUID
    client: uuid.UUID
    taxpayer: uuid.UUID
    spouse: uuid.UUID

    @property
    def ctx(self) -> TenantContext:
        return TenantContext(self.tenant, "system", "test:consent_gate")


@pytest.fixture
async def household(seed: Seeder) -> Household:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe household') RETURNING id",
            tenant,
        ),
    )
    entities = [
        cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, $3) RETURNING id",
                tenant,
                client,
                name,
            ),
        )
        for name in ("Probe taxpayer", "Probe spouse")
    ]
    return Household(tenant, person.user_id, client, entities[0], entities[1])


async def _consent(
    seed: Seeder,
    h: Household,
    entity: uuid.UUID,
    purpose: str,
    *,
    years: tuple[int, ...] = (2025,),
    signers: tuple[bool, ...] = (True,),
    expires_at: datetime | None = None,
    terms: str = "probe-terms",
) -> uuid.UUID:
    """A consent and its required signers; signed when every signer signed (record mode)."""
    signed = all(signers)
    consent = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO consents (tenant_id, client_id, client_entity_id, purpose, tax_years, "
            "provider_terms_version, template_version_id, text_sha256, source, status, "
            "created_by, signed_at, expires_at) VALUES ($1, $2, $3, $4, $5, $6, "
            "gen_random_uuid(), $7, 'record', $8, $9, $10, $11) RETURNING id",
            h.tenant,
            h.client,
            entity,
            purpose,
            list(years),
            terms,
            SHA,
            "signed" if signed else "requested",
            h.user,
            SIGNED_AT if signed else None,
            expires_at,
        ),
    )
    for index, done in enumerate(signers):
        await seed.run(
            "INSERT INTO consent_signers (tenant_id, consent_id, user_id, signer_role, "
            "required, signed_at, method) VALUES ($1, $2, $3, $4, true, $5, $6)",
            h.tenant,
            consent,
            h.user,
            "taxpayer" if index == 0 else "spouse",
            SIGNED_AT if done else None,
            "record" if done else None,
        )
    return consent


async def _both(seed: Seeder, h: Household, entity: uuid.UUID, **kwargs: object) -> None:
    for purpose in ("use", "ai_disclosure"):
        await _consent(seed, h, entity, purpose, **kwargs)  # type: ignore[arg-type] -- passed through


async def test_ac18_both_purposes_for_both_spouses_are_valid(
    seed: Seeder, household: Household
) -> None:
    await _both(seed, household, household.taxpayer)
    await _both(seed, household, household.spouse)
    with frozen(NOW):
        verdict = await organisations_api.tri_consent_verdict(
            household.ctx, [household.taxpayer, household.spouse], NOW, tax_year=2025
        )
        covering = await organisations_api.covering_consents(
            household.ctx,
            [TriSubject(household.taxpayer, 2025), TriSubject(household.spouse, 2025)],
            NOW,
        )
    assert verdict.valid and verdict.missing == ()
    assert covering is not None and len(covering) == 4


async def test_ac17_a_ferris_set_one_of_two_signed_is_refused_and_audited(
    seed: Seeder, household: Household, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The joint use consent waits on the spouse: requested, 1 of 2 signed.
    await _consent(seed, household, household.taxpayer, "use", signers=(True, False))
    await _consent(seed, household, household.taxpayer, "ai_disclosure")

    async def synthetic(_tenant: TenantContext) -> bool:
        return True

    monkeypatch.setattr(boundary, "_check", synthetic)
    with frozen(NOW):
        verdict = await organisations_api.tri_consent_verdict(
            household.ctx, [household.taxpayer], NOW, tax_year=2025
        )
        with pytest.raises(DataBoundaryRefused) as refused:
            await enforce_boundary(
                household.ctx,
                "fake",
                "evidence.screen@v0",
                subjects=(DataSubject(household.taxpayer, 2025),),
            )
    assert not verdict.valid and verdict.missing == ((household.taxpayer, "use"),)
    assert refused.value.reason == "consent_7216"
    audited = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'ai.boundary_refused'",
        household.tenant,
    )
    assert audited == 1


async def test_ac19_a_revocation_binds_the_next_call(seed: Seeder, household: Household) -> None:
    await _both(seed, household, household.taxpayer)
    subjects = (DataSubject(household.taxpayer, 2025),)
    with frozen(NOW):
        assert await enforce_boundary(household.ctx, "fake", "p@v0", subjects=subjects) is None
    await seed.run(
        "UPDATE consents SET status = 'revoked', revoked_at = $2 WHERE tenant_id = $1 "
        "AND purpose = 'ai_disclosure'",
        household.tenant,
        NOW - timedelta(minutes=1),
    )
    with frozen(NOW), pytest.raises(DataBoundaryRefused):
        await enforce_boundary(household.ctx, "fake", "p@v0", subjects=subjects)


async def test_ac19_expiry_and_the_year_bind(seed: Seeder, household: Household) -> None:
    await _both(seed, household, household.taxpayer, expires_at=NOW + timedelta(days=1))
    ctx, subjects = household.ctx, [household.taxpayer]
    with frozen(NOW):
        assert (
            await organisations_api.tri_consent_verdict(ctx, subjects, NOW, tax_year=2025)
        ).valid
        assert not (
            await organisations_api.tri_consent_verdict(ctx, subjects, NOW, tax_year=2026)
        ).valid
    later = NOW + timedelta(days=2)
    with frozen(later):
        assert not (
            await organisations_api.tri_consent_verdict(ctx, subjects, later, tax_year=2025)
        ).valid


async def test_ac19_a_material_provider_terms_change_means_re_consent(
    seed: Seeder, household: Household, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _both(seed, household, household.taxpayer, terms="material-a")
    entry = TermsEntry("bedrock", "AWS", "us-east-1", NOW.date(), NOW.date() + timedelta(days=30))

    def covering(material: str) -> object:
        def found(_route: str, _on: object) -> TermsEntry:
            return replace(entry, material=material)

        return found

    ctx, subjects = household.ctx, [household.taxpayer]
    monkeypatch.setattr(provider_terms, "covering", covering("material-a"))
    assert (await organisations_api.tri_consent_verdict(ctx, subjects, NOW, tax_year=2025)).valid
    monkeypatch.setattr(provider_terms, "covering", covering("material-b"))
    assert not (
        await organisations_api.tri_consent_verdict(ctx, subjects, NOW, tax_year=2025)
    ).valid


async def test_ac20_require_tri_consent_names_the_taxpayer_and_records_reads(
    seed: Seeder, household: Household
) -> None:
    await _both(seed, household, household.taxpayer)
    with frozen(NOW):
        with pytest.raises(organisations_api.TriConsentRequired) as missing:
            await organisations_api.require_tri_consent(
                household.ctx, [TriSubject(household.spouse, 2025)]
            )
        covering = await organisations_api.require_tri_consent(
            household.ctx, [TriSubject(household.taxpayer, 2025)]
        )
    assert missing.value.facts == {"client_entity_id": str(household.spouse), "purpose": "use"}
    reads = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND kind = 'tri.tool_read'",
        household.tenant,
    )
    assert reads == 1 + len(covering)  # the taxpayer and each covering consent


async def test_ac21_the_matrix_reads_the_same_rows(seed: Seeder, household: Household) -> None:
    await _consent(seed, household, household.taxpayer, "use")
    with frozen(NOW):
        assert await consent_given(household.ctx, household.taxpayer, "use", NOW)
        assert not await consent_given(household.ctx, household.taxpayer, "ai_disclosure", NOW)
        assert not await consent_given(household.ctx, household.spouse, "use", NOW)
