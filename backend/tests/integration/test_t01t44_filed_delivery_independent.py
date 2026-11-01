"""T-01-T44 (TASK-2620; ADR-078) against Postgres: independent tests for T-01-T41's filed-return
delivery, through the portal route a client actually calls (`GET /v1/portal/filed-returns/{id}/
download`), not the service.

Row acceptance: "...including a planted cross-household download that answers 404."

- A person of another household asking for the Feld delivery id gets 404 and nothing is audited
  (INV-3: no count, no hint).
- Claire before her portal second step gets 403 `mfa_required`; after it, the PDF, and exactly one
  `filed_return.downloaded` audit row per download that names no file content.
- A firm member (not a client principal) never downloads through the portal route.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import cast

from abacus.modules.identity.api import AuthContext

from . import test_t01t41_filed_return_delivery as t01t41
from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Feld, Json, call_as, engines, feld_return

__all__ = ["engines"]
# T-01-T41's seeds for the Feld world (an accepted return, a client grant, a staff member).
_accepted = t01t41._accepted  # pyright: ignore[reportPrivateUsage] -- T-01-T41's seed
_client = t01t41._client  # pyright: ignore[reportPrivateUsage] -- T-01-T41's seed
_member = t01t41._member  # pyright: ignore[reportPrivateUsage] -- T-01-T41's seed


async def _delivered(
    migrated_db: MigratedDatabase,
) -> tuple[Feld, AuthContext, uuid.UUID]:
    feld = await feld_return(migrated_db)
    await feld.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.delivery_efile', 'true', 't01-t44', 'T-01-T44')",
        feld.tenant,
    )
    grace = await _member(feld.seed, feld, "Grace Holloway", "client_service")
    await _accepted(feld, grace)
    published = await call_as(grace)(
        "POST",
        f"/v1/tax-returns/{feld.item}/deliverables:publish",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert published.status_code == 200, published.text
    return feld, grace, uuid.UUID(cast(str, cast(Json, published.json())["delivery_id"]))


async def _downloads(feld: Feld, actor: uuid.UUID) -> int:
    return cast(
        int,
        await feld.seed.value(
            "SELECT count(*) FROM audit_events WHERE action = 'filed_return.downloaded' "
            "AND actor_id = $1",
            str(actor),
        ),
    )


async def test_ac_a_planted_cross_household_download_answers_404(
    migrated_db: MigratedDatabase,
) -> None:
    feld, _grace, delivery = await _delivered(migrated_db)
    shah = await feld.seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Shah Household') RETURNING id",
        feld.tenant,
    )
    entity = await feld.seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Shah') "
        "RETURNING id",
        feld.tenant,
        shah,
    )
    elsewhere = cast(
        uuid.UUID,
        await feld.seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, "
            "'Shah TY2025', '2025-01-01', '2025-12-31', $4) RETURNING id",
            feld.tenant,
            shah,
            entity,
            feld.samuel.user_id,
        ),
    )
    meera = await _client(feld, elsewhere)
    planted = await call_as(meera)("GET", f"/v1/portal/filed-returns/{delivery}/download")
    assert planted.status_code == 404, planted.text
    assert b"%PDF" not in planted.content
    assert await _downloads(feld, meera.user_id) == 0
    unknown = await call_as(meera)("GET", f"/v1/portal/filed-returns/{uuid.uuid4()}/download")
    assert unknown.status_code == 404  # the same answer as the planted id: nothing to tell apart


async def test_ac_the_second_step_gates_the_download_and_each_download_is_audited(
    migrated_db: MigratedDatabase,
) -> None:
    feld, _grace, delivery = await _delivered(migrated_db)
    claire = await _client(feld, cast(uuid.UUID, feld.engagement))
    early = replace(claire, mfa_at=None, portal_second_step=False)
    refused = await call_as(early)("GET", f"/v1/portal/filed-returns/{delivery}/download")
    assert refused.status_code == 403, refused.text
    assert await _downloads(feld, claire.user_id) == 0
    for n in (1, 2):
        got = await call_as(claire)("GET", f"/v1/portal/filed-returns/{delivery}/download")
        assert got.status_code == 200, got.text
        assert got.headers["content-type"].startswith("application/pdf")
        assert got.content.startswith(b"%PDF-")
        assert await _downloads(feld, claire.user_id) == n
    audited = await feld.seed.rows(
        "SELECT after_ref FROM audit_events WHERE action = 'filed_return.downloaded' "
        "AND actor_id = $1",
        str(claire.user_id),
    )
    assert len(audited) == 2  # one audit event per download
    assert all(
        "PDF" not in str(a["after_ref"]) and "1040" not in str(a["after_ref"]) for a in audited
    )


async def test_a_firm_member_never_downloads_through_the_portal_route(
    migrated_db: MigratedDatabase,
) -> None:
    _feld, grace, delivery = await _delivered(migrated_db)
    staff = await call_as(grace)("GET", f"/v1/portal/filed-returns/{delivery}/download")
    assert staff.status_code in (403, 404), staff.text
    assert b"%PDF" not in staff.content
