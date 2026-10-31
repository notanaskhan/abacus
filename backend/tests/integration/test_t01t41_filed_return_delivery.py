"""T-01-T41 (TASK-2524; T-01 §3.14; DEC-1571) against Postgres: "Claire Feld sees 2025 Form 1040
filed and accepted with a download on her home after two-step, and Meera Shah sees nothing of
the Feld household."

The Feld return (T-01-T19's world) with the engine's client copy filed through the bridge
(T-01-T26), an approved delivery packet (T-01-T35) and the return Accepted (T-01-T37's acks).
Grace Holloway (client service) publishes; Claire holds the household engagement's grant; Meera
Shah is another client's person.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import cast

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.portal import home
from abacus.modules.tax import filed_delivery
from abacus.modules.tax.engine_files import engine_documents
from abacus_tools.fakes.cch_axcess import CchAxcessFake, Export

from . import test_t01t37_transmission_acks as t01t37
from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Feld, Json, call_as, engines, feld_return

__all__ = ["engines"]
_member = t01t37._member  # pyright: ignore[reportPrivateUsage] -- T-01-T37's staff member seed

FELD = Export("2025I:FeldJ", 2025, "1040", ())


async def _client(feld: Feld, engagement: uuid.UUID) -> AuthContext:
    who = await feld.seed.person(feld.tenant)
    await feld.seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        feld.tenant,
        who.user_id,
    )
    await feld.seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        feld.tenant,
        who.user_id,
        engagement,
    )
    return replace(who.context(), client=True)


async def _accepted(feld: Feld, grace: AuthContext) -> uuid.UUID:
    """The client copy filed from the engine, the packet approved, the return Accepted."""
    name = "2025I_FeldJ_V3_client_copy.pdf"
    uploaded = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-imports",
        params={"kind": "pdfs"},
        headers={"X-File-Name": name},
        content=CchAxcessFake().pdf_files(FELD, 3)[name],
    )
    assert uploaded.status_code == 201, uploaded.text
    (copy,) = await engine_documents(feld.samuel.tenant, feld.item, "client_copy")
    await feld.seed.run(
        "INSERT INTO delivery_packets (tenant_id, return_id, version, items, prepared_by, "
        "status, approved_by, approved_at) VALUES ($1, $2, 1, $3::jsonb, $4, 'approved', $5, "
        "abacus_now())",
        feld.tenant,
        feld.item,
        json.dumps([{"kind": "client_copy", "evidence_version_id": str(copy), "included": True}]),
        grace.user_id,
        feld.samuel.user_id,
    )
    await feld.seed.run(
        "UPDATE tax_returns SET status = 'accepted' WHERE work_item_id = $1", feld.item
    )
    return copy


async def test_ac_claire_sees_her_filed_return_and_downloads_it_after_two_step(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    await feld.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.delivery_efile', 'true', 't01-t41', 'T-01-T41')",
        feld.tenant,
    )
    grace = await _member(feld.seed, feld, "Grace Holloway", "client_service")
    early = await call_as(grace)(
        "POST",
        f"/v1/tax-returns/{feld.item}/deliverables:publish",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert (early.status_code, early.json()["detail"]) == (409, "return_not_accepted")
    await _accepted(feld, grace)
    published = await call_as(grace)(
        "POST",
        f"/v1/tax-returns/{feld.item}/deliverables:publish",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert published.status_code == 200, published.text
    delivery = uuid.UUID(cast(str, cast(Json, published.json())["delivery_id"]))
    again = await call_as(grace)(
        "POST",
        f"/v1/tax-returns/{feld.item}/deliverables:publish",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert cast(Json, again.json())["delivery_id"] == str(delivery)  # the same release
    audited = await feld.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE action = 'return.delivered' "
        "AND target_id = $1",
        str(feld.item),
    )
    assert [(a["actor_kind"], a["actor_id"]) for a in audited] == [("human", str(grace.user_id))]
    announced = await feld.seed.value(
        "SELECT count(*) FROM outbox WHERE event_type = 'return.delivered' "
        "AND payload ->> 'return_id' = $1",
        str(feld.item),
    )
    assert announced == 1  # publishing again is the same release, announced once

    claire = await _client(feld, cast(uuid.UUID, feld.engagement))
    view = await home.read_home(claire, None)
    rows = [e for e in view.earlier if e.kind == "return_filed"]
    assert [(r.facts["tax_year"], r.facts["form"], r.facts["download_ready"]) for r in rows] == [
        (2025, "1040", True)
    ]
    assert rows[0].facts["delivery_id"] == str(delivery)

    before_two_step = replace(claire, mfa_at=None, portal_second_step=False)
    with pytest.raises(filed_delivery.MfaRequired):
        await filed_delivery.client_copy(before_two_step, delivery)
    copy = await filed_delivery.client_copy(claire, delivery)
    assert copy.content.startswith(b"%PDF-")
    assert copy.file_name == "2025 Form 1040 client copy.pdf"
    downloads = await feld.seed.value(
        "SELECT count(*) FROM audit_events WHERE action = 'filed_return.downloaded' "
        "AND actor_id = $1",
        str(claire.user_id),
    )
    assert downloads == 1


async def test_ac_meera_shah_sees_nothing_of_the_feld_household(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    await feld.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.delivery_efile', 'true', 't01-t41', 'T-01-T41')",
        feld.tenant,
    )
    grace = await _member(feld.seed, feld, "Grace Holloway", "client_service")
    await _accepted(feld, grace)
    delivered = await filed_delivery.publish(grace, feld.item)
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
    with pytest.raises(NotFound):
        await filed_delivery.client_copy(meera, delivered.id)
    try:
        view = await home.read_home(meera, None)
    except NotFound:
        return  # nothing of hers to show, and nothing of the Feld household
    assert [e for e in view.earlier if e.kind == "return_filed"] == []


async def test_only_a_person_publishes_and_a_firm_user_never_downloads_as_a_client(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    grace = await _member(feld.seed, feld, "Grace Holloway", "client_service")
    await _accepted(feld, grace)
    delivered = await filed_delivery.publish(grace, feld.item)
    from abacus.kernel.db import TenantContext
    from abacus.modules.identity.api import Forbidden

    for kind in ("agent", "system", "support"):
        planted = replace(grace, tenant=TenantContext(feld.tenant, kind, f"{kind}:planted"))
        with pytest.raises(Forbidden):
            await filed_delivery.publish(planted, feld.item)
    with pytest.raises(NotFound):
        await filed_delivery.client_copy(grace, delivered.id)
