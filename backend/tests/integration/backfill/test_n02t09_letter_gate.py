# ac-test-author: ayushkbhatia
"""N-02-T09 (TASK-1730; N-02 §3.12, §8.2; DEC-820): envelope sources and G3.

Acceptance (the task row): "By Fri May 14, 2027 C7 record mode is frozen and Bluestem stays
Accepted until a G3 source is met."

The G3 truth table over its three sources: (a) a completed, non-superseded letter envelope with a
client signature and a firm countersignature; (b) a completed record-mode letter import; (c) a
letter recorded through `letter.record`. Anything else leaves G3 unmet: a client signature alone,
a superseded or voided envelope, another purpose. Also: the source slot fails closed, and
signatures replaced P-07's interim provider.

Boundary: `engagements.api.gate_fact` and `signatures.api`; rows seeded through SQL with
triggers off (the import's own path is N-02-T08's suite).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import gate_fact
from abacus.modules.signatures.api import (
    LETTER,
    UnknownEnvelopeSource,
    envelope_source,
    registered_sources,
)

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
G3: Final = "G3"


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    site: Site
    contact_id: uuid.UUID

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", "test:g3")


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Bluestem")
    await seed.run_untriggered(
        "UPDATE engagements SET status = 'accepted' WHERE id = $1", site.engagement_id
    )
    contact = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
        "VALUES ($1, $2, 'Bluestem signer', 'client_person') RETURNING id",
        tenant,
        site.client_id,
    )
    assert isinstance(contact, uuid.UUID)
    return Firm(net, tenant, admin, site, contact)


async def _envelope(
    firm: Firm,
    *,
    provider: str = "fake",
    status: str = "completed",
    purpose: str = "engagement_letter",
    superseded: bool = False,
    client_signed: bool = True,
    firm_signed: bool = True,
) -> uuid.UUID:
    envelope = uuid.uuid4()
    number = int(str(await firm.net.seed.value("SELECT count(*) + 1 FROM envelopes")))
    await firm.net.seed.run_untriggered(
        "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, client_id, "
        "engagement_id, title, provider, provider_name, status, drafted_by_kind, imported_by, "
        "completed_at, superseded_at, voided_by, voided_at, void_reason) VALUES ($1, $2, $3, $4, "
        "'engagement_letter', $5, $6, 'Letter', $7, $8, $9, 'human', $10, "
        "CASE WHEN $9 = 'completed' THEN now() END, CASE WHEN $11 THEN now() END, "
        "CASE WHEN $9 = 'voided' THEN $12::uuid END, CASE WHEN $9 = 'voided' THEN now() END, "
        "CASE WHEN $9 = 'voided' THEN 'replaced' END)",
        envelope,
        firm.tenant_id,
        number,
        purpose,
        firm.site.client_id,
        firm.site.engagement_id,
        provider,
        "DocuSign" if provider == "record" else None,
        status,
        firm.admin.user_id if provider == "record" else None,
        superseded,
        firm.admin.user_id,
    )
    for order, (party, role, signed) in enumerate(
        (("contact", "signer", client_signed), ("user", "countersigner", firm_signed)), start=1
    ):
        await firm.net.seed.run_untriggered(
            'INSERT INTO envelope_signers (tenant_id, envelope_id, "order", party_kind, '
            "contact_id, user_id, role, identity_method, status, signed_at, signature_method) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, 'email_code', $8, "
            "CASE WHEN $9 THEN now() END, CASE WHEN $9 THEN 'typed' END)",
            firm.tenant_id,
            envelope,
            order,
            party,
            firm.contact_id if party == "contact" else None,
            firm.admin.user_id if party == "user" else None,
            role,
            "signed" if signed else "pending",
            signed,
        )
    return envelope


async def _met(firm: Firm) -> bool:
    return (await gate_fact(firm.system, firm.site.engagement_id, G3)).met


async def _status(firm: Firm) -> object:
    return await firm.net.seed.value(
        "SELECT status FROM engagements WHERE id = $1", firm.site.engagement_id
    )


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_bluestem_stays_accepted_until_a_g3_source_is_met(firm: Firm) -> None:
    assert not await _met(firm)
    await _envelope(firm, status="sent", client_signed=False, firm_signed=False)
    assert not await _met(firm)
    assert await _status(firm) == "accepted"
    await _envelope(firm, provider="record")
    assert await _met(firm)


async def test_ac_c7_record_mode_is_frozen_with_the_letter_source_registered() -> None:
    assert LETTER in registered_sources()
    letter = envelope_source(LETTER)
    assert (letter.gate, letter.retention_record_type) == (G3, "signature_evidence")


# --- The G3 truth table --------------------------------------------------------------------------


async def test_a_client_signature_and_a_firm_countersignature_meet_g3(firm: Firm) -> None:
    await _envelope(firm)
    assert await _met(firm)


@pytest.mark.parametrize(
    ("client_signed", "firm_signed"), [(True, False), (False, True), (False, False)]
)
async def test_a_missing_signature_leaves_g3_unmet(
    firm: Firm, client_signed: bool, firm_signed: bool
) -> None:
    await _envelope(firm, client_signed=client_signed, firm_signed=firm_signed)
    assert not await _met(firm)


async def test_a_superseded_or_voided_letter_leaves_g3_unmet(firm: Firm) -> None:
    await _envelope(firm, superseded=True)
    await _envelope(firm, provider="record", superseded=True)
    await _envelope(firm, status="voided", client_signed=False, firm_signed=False)
    assert not await _met(firm)


async def test_another_purpose_leaves_g3_unmet(firm: Firm) -> None:
    await _envelope(firm, purpose="consent_7216")
    assert not await _met(firm)


async def test_a_letter_recorded_through_letter_record_meets_g3(firm: Firm) -> None:
    await firm.net.seed.run(
        "INSERT INTO engagement_letters (tenant_id, engagement_id, status, letter_date, "
        "recorded_by) VALUES ($1, $2, 'signed', '2026-04-02', 'test-seed')",
        firm.tenant_id,
        firm.site.engagement_id,
    )
    assert await _met(firm)


async def test_an_unregistered_source_fails_closed() -> None:
    with pytest.raises(UnknownEnvelopeSource):
        envelope_source("rep_letter")
