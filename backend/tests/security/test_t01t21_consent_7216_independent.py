# ac-test-author: ayushkbhatia (T-01-T21; independent of T-01-T08, T-01-T11 and T-01-T12)
"""I-7216 (T-01-T21; TASK-2319; T-01 §3.1, §3.2; C19 condition 6; ADR-078; DEC-1365) against
Postgres, written from the contract, not the implementation.

Property: for every combination of a consent's status, its signers, its expiry, the year asked
and the provider terms it was signed under, `organisations.api.tri_consent_verdict` is valid
exactly when an oracle written here from C19 says both `use` and `ai_disclosure` are in force:
signed, every required signer signed (both spouses on a joint unit), not revoked, not expired at
the business time asked, covering the year, and under the current material terms. Plus: one purpose
alone never passes; a revocation binds the very next verdict; the expiry follows the clock it is
asked at; an unknown subject is refused; the shared eval case pack names exactly these cases; and
an agent spec declaring `tri` refuses to load without the consent checks.
"""

from __future__ import annotations

import hashlib
import itertools
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.kernel import provider_terms
from abacus.kernel.db import TenantContext
from abacus.kernel.provider_terms import TermsEntry
from abacus.modules.agents import spec as agent_spec
from abacus.modules.organisations import api as organisations_api

from .support import Seeder

AT = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
SIGNED_AT = AT - timedelta(days=13)
SHA = hashlib.sha256(b"synthetic consent text").digest()
CURRENT, OLD = "material-current", "material-old"
PACK = Path(__file__).resolve().parents[3] / "evals" / "_shared" / "consent_7216" / "cases.yaml"
STATUSES = ("signed", "requested", "declined", "revoked")
SIGNERS = ((True,), (True, False), (True, True))
EXPIRY = ("none", "future", "past")
YEARS = ((2025,), (2024,))
TERMS = (CURRENT, OLD)


@dataclass(frozen=True)
class Case:
    status: str
    signers: tuple[bool, ...]
    expiry: str
    years: tuple[int, ...]
    terms: str

    def in_force(self) -> bool:
        """The oracle, from C19 condition 6 (not from the query under test)."""
        return (
            self.status == "signed"
            and all(self.signers)
            and self.expiry != "past"
            and 2025 in self.years
            and self.terms == CURRENT
        )


CASES = [Case(*c) for c in itertools.product(STATUSES, SIGNERS, EXPIRY, YEARS, TERMS)]


@pytest.fixture(autouse=True)
def terms(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = TermsEntry("bedrock", "AWS", "us-east-1", AT.date(), AT.date() + timedelta(days=30))

    def covering(_route: str, _on: object) -> TermsEntry:
        return replace(entry, material=CURRENT)

    monkeypatch.setattr(provider_terms, "covering", covering)


@dataclass(frozen=True)
class Firm:
    seed: Seeder
    tenant: uuid.UUID
    user: uuid.UUID
    client: uuid.UUID

    @property
    def ctx(self) -> TenantContext:
        return TenantContext(self.tenant, "system", "test:i7216")

    async def entity(self, name: str) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
                "RETURNING id",
                self.tenant,
                self.client,
                name,
            ),
        )

    async def consent(self, entity: uuid.UUID, purpose: str, case: Case) -> uuid.UUID:
        signed = case.status in ("signed", "revoked")
        expires = {"none": None, "future": AT + timedelta(days=30), "past": AT - timedelta(days=1)}
        consent = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO consents (tenant_id, client_id, client_entity_id, purpose, "
                "tax_years, provider_terms_version, template_version_id, text_sha256, source, "
                "status, created_by, signed_at, expires_at, declined_at, revoked_at) VALUES "
                "($1, $2, $3, $4, $5, $6, gen_random_uuid(), $7, 'record', $8, $9, $10, $11, "
                "$12, $13) RETURNING id",
                self.tenant,
                self.client,
                entity,
                purpose,
                list(case.years),
                case.terms,
                SHA,
                case.status,
                self.user,
                SIGNED_AT if signed else None,
                expires[case.expiry],
                SIGNED_AT if case.status == "declined" else None,
                AT - timedelta(hours=1) if case.status == "revoked" else None,
            ),
        )
        for role, done in zip(("taxpayer", "spouse"), case.signers, strict=False):
            await self.seed.run(
                "INSERT INTO consent_signers (tenant_id, consent_id, user_id, signer_role, "
                "required, signed_at, method) VALUES ($1, $2, $3, $4, true, $5, $6)",
                self.tenant,
                consent,
                self.user,
                role,
                SIGNED_AT if done else None,
                "record" if done else None,
            )
        return consent


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Synthetic household') "
            "RETURNING id",
            tenant,
        ),
    )
    return Firm(seed, tenant, person.user_id, client)


async def test_i7216_the_verdict_matches_the_oracle_over_every_combination(firm: Firm) -> None:
    entities: dict[uuid.UUID, Case] = {}
    for n, case in enumerate(CASES):
        entity = await firm.entity(f"Synthetic taxpayer {n}")
        for purpose in ("use", "ai_disclosure"):
            await firm.consent(entity, purpose, case)
        entities[entity] = case
    wrong: list[Case] = []
    for entity, case in entities.items():
        verdict = await organisations_api.tri_consent_verdict(
            firm.ctx, [entity], AT, tax_year=2025
        )
        if verdict.valid != case.in_force():
            wrong.append(case)
    assert wrong == []
    assert any(c.in_force() for c in CASES) and not all(c.in_force() for c in CASES)


async def test_i7216_one_purpose_alone_never_passes(firm: Firm) -> None:
    good = Case("signed", (True, True), "none", (2025,), CURRENT)
    for only in ("use", "ai_disclosure"):
        entity = await firm.entity(f"Only {only}")
        await firm.consent(entity, only, good)
        verdict = await organisations_api.tri_consent_verdict(
            firm.ctx, [entity], AT, tax_year=2025
        )
        assert not verdict.valid
        assert [p for _e, p in verdict.missing] == [
            p for p in ("use", "ai_disclosure") if p != only
        ]


async def test_i7216_a_revocation_binds_the_next_verdict(firm: Firm) -> None:
    good = Case("signed", (True,), "none", (2025,), CURRENT)
    entity = await firm.entity("Revoked next")
    use = await firm.consent(entity, "use", good)
    await firm.consent(entity, "ai_disclosure", good)
    assert (await organisations_api.tri_consent_verdict(firm.ctx, [entity], AT)).valid
    await firm.seed.run(
        "UPDATE consents SET status = 'revoked', revoked_at = $2 WHERE id = $1",
        use,
        AT - timedelta(minutes=1),
    )
    assert not (await organisations_api.tri_consent_verdict(firm.ctx, [entity], AT)).valid


async def test_i7216_expiry_follows_the_business_time_asked(firm: Firm) -> None:
    good = Case("signed", (True,), "future", (2025,), CURRENT)
    entity = await firm.entity("Expiring")
    for purpose in ("use", "ai_disclosure"):
        await firm.consent(entity, purpose, good)
    assert (await organisations_api.tri_consent_verdict(firm.ctx, [entity], AT)).valid
    later = AT + timedelta(days=31)
    assert not (await organisations_api.tri_consent_verdict(firm.ctx, [entity], later)).valid


async def test_i7216_an_unknown_subject_is_refused_and_none_is_not_valid(firm: Firm) -> None:
    unknown = await organisations_api.tri_consent_verdict(firm.ctx, [uuid.uuid4()], AT)
    assert not unknown.valid and len(unknown.missing) == 2
    assert not (await organisations_api.tri_consent_verdict(firm.ctx, [], AT)).valid


def test_the_shared_eval_pack_names_the_c19_cases() -> None:
    cases = cast(list[dict[str, object]], yaml.safe_load(PACK.read_text())["cases"])
    names = {str(c["id"]) for c in cases}
    assert {
        "ferris_one_of_two_signed",
        "stein_declined",
        "thornbury_not_requested",
        "expired",
        "joint_return_one_spouse",
    } <= names
    assert all(c["expect"] == "refused_consent_7216" for c in cases)


def test_a_spec_declaring_tri_refuses_to_load_without_the_consent_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planted = next(iter(agent_spec.AGENTS.values()))
    tri = agent_spec.AgentSpec.model_validate(
        {**planted.model_dump(), "data_classes": frozenset({"tri"})}
    )

    def never(_purpose: str) -> bool:
        return False

    def always(_purpose: str) -> bool:
        return True

    monkeypatch.setattr(agent_spec, "consent_registered", never)
    with pytest.raises(ValueError, match="tri"):
        agent_spec.validate_data_classes(tri)
    monkeypatch.setattr(agent_spec, "consent_registered", always)
    agent_spec.validate_data_classes(tri)
