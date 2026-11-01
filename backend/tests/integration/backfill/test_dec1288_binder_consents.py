# ac-test-author: ayushkbhatia
"""DEC-1288 (CLI-05 / BND-01; T-01-T14 follow-up): the §7216 consents tag's counts.

A return binder (season `TY2025`) of a client with two consents asked for that year, one signed,
reads "§7216 consents 1 of 2"; a declined consent is not counted, another year's is not, a
non-return season and a client with none carry no tag. The provider is the one T-01 registers on
requests' slot.

Boundary: organisations' `consent_counts` and tax's `binder_consents` against the database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Final

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.requests import binder_index
from abacus.modules.tax.consent_capture import binder_consents

from .support import Net

pytestmark = pytest.mark.asyncio
SHA: Final = bytes(32)  # text_sha256 is the digest itself (bytea)


async def _consent(
    net: Net,
    tenant: uuid.UUID,
    client: uuid.UUID,
    entity: uuid.UUID,
    who: uuid.UUID,
    *,
    purpose: str,
    years: list[int],
    status: str,
) -> None:
    signed = datetime.now(UTC) if status == "signed" else None
    await net.seed.run_untriggered_many(
        [
            (
                "INSERT INTO consents (tenant_id, client_id, client_entity_id, purpose, "
                "tax_years, provider_terms_version, template_version_id, text_sha256, source, "
                "status, created_by, signed_at, expires_at, declined_at) VALUES ($1, $2, $3, $4, "
                "$5, 'v1', gen_random_uuid(), $6, 'record', $7, $8, $9, $10, $11)",
                (
                    tenant,
                    client,
                    entity,
                    purpose,
                    years,
                    SHA,
                    status,
                    who,
                    signed,
                    signed + timedelta(days=365) if signed is not None else None,
                    datetime.now(UTC) if status == "declined" else None,
                ),
            )
        ]
    )


async def test_a_return_binder_reads_one_of_two_and_the_rest_carry_no_tag(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    ferris = await seed.site(tenant, admin.user_id, "Ferris")
    mendez = await seed.site(tenant, admin.user_id, "Mendez")
    for purpose, status in (
        ("use", "signed"),
        ("ai_disclosure", "requested"),
        ("use", "declined"),
    ):
        await _consent(
            net,
            tenant,
            ferris.client_id,
            ferris.entity_id,
            admin.user_id,
            purpose=purpose,
            years=[2025],
            status=status,
        )
    await _consent(  # another year's consent is not this binder's
        net,
        tenant,
        ferris.client_id,
        ferris.entity_id,
        admin.user_id,
        purpose="use",
        years=[2024],
        status="signed",
    )
    system = TenantContext(tenant, "system", "test.dec1288")
    ty, fy, none = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    found = await binder_consents(
        system,
        [
            (ty, ferris.client_id, "TY2025"),
            (fy, ferris.client_id, "FY2025"),
            (none, mendez.client_id, "TY2025"),
        ],
    )
    assert found == {ty: (1, 2)}


def test_t01_fills_the_binder_consents_slot() -> None:
    import abacus.modules.tax.api as tax_api  # registers at import

    assert tax_api.__name__
    assert binder_index._consents is binder_consents  # pyright: ignore[reportPrivateUsage] -- the slot under test
