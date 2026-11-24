"""T-08-T19's planning service on the migrated database (TASK-8914; SPEC-710 AC-27; T-08 AC5.1,
AC5.3 to AC5.5, AC5.7; DEC-5916).

A screen of the Felds' approved TY2025 return writes the bunching opportunity with code's 1,811
and its basis; without both §7216 consents for the joint unit it is Not screened and the
narrator (the model's slot) is never called; once both are signed a re-screen opens it and calls
the narrator; the partner reads it on the strip and the queue; dismiss needs its reason and
restore returns the previous status; a manual add is Open and idempotent on its source; and
`engagement.created` carrying the opportunity's source makes it Accepted with the project.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
)
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import OutboxEvent
from abacus.modules.tax import api as tax_api
from abacus.modules.tax.planning import service as ps

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

SIGNED_AT = datetime(2025, 3, 1, 15, 0, tzinfo=UTC)
SHA = hashlib.sha256(b"planning consent text").digest()
FELD_LINES = [
    {"line_key": "1040.11", "amount": "598030"},
    {"line_key": "scha.5e", "amount": "10591"},
    {"line_key": "scha.8a", "amount": "18240"},
    {"line_key": "scha.11", "amount": "12500"},
    {"line_key": "1040.15", "amount": "496000"},
]
assert tax_api.SUBSCRIPTIONS["tax_return.approved"] is not None  # planning subscribes


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


async def _household(seed: Seeder, tenant: uuid.UUID, partner: Person) -> dict[str, uuid.UUID]:
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name, relationship_partner_id) VALUES ($1, "
            "'Jonah & Claire Feld', $2) RETURNING id",
            tenant,
            partner.user_id,
        ),
    )
    entity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name, entity_type) VALUES ($1, "
            "$2, 'Jonah & Claire Feld', 'household_mfj') RETURNING id",
            tenant,
            client,
        ),
    )
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, period_start, period_end, created_by) VALUES ($1, $2, $3, $4, 'tax_return', "
            "'2025 Form 1040', '2025-01-01', '2025-12-31', $5) RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            partner.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year, filing_status) VALUES ($1, $2, $3, $4, '1040', 2025, 'mfj')",
        tenant,
        item,
        engagement,
        entity,
    )
    await seed.run(
        "INSERT INTO return_engine_summaries (tenant_id, work_item_id, engine_version, kind, "
        "lines, approved_at) VALUES ($1, $2, 'cch-2025.1', 'final', $3::jsonb, $4)",
        tenant,
        item,
        json.dumps(FELD_LINES),
        SIGNED_AT,
    )
    return {"client": client, "entity": entity, "engagement": engagement, "item": item}


async def _consent(
    seed: Seeder, tenant: uuid.UUID, h: dict[str, uuid.UUID], who: Person, purpose: str,
    signers: tuple[bool, bool],
) -> None:  # fmt: skip
    signed = all(signers)
    consent = await seed.value(
        "INSERT INTO consents (tenant_id, client_id, client_entity_id, purpose, tax_years, "
        "provider_terms_version, template_version_id, text_sha256, source, status, created_by, "
        "signed_at) VALUES ($1, $2, $3, $4, '{2025}', 'probe-terms', gen_random_uuid(), $5, "
        "'record', $6, $7, $8) RETURNING id",
        tenant, h["client"], h["entity"], purpose, SHA, "signed" if signed else "requested",
        who.user_id, SIGNED_AT if signed else None,
    )  # fmt: skip
    for index, done in enumerate(signers):
        await seed.run(
            "INSERT INTO consent_signers (tenant_id, consent_id, user_id, signer_role, required, "
            "signed_at, method) VALUES ($1, $2, $3, $4, true, $5, $6)",
            tenant, consent, who.user_id, "taxpayer" if index == 0 else "spouse",
            SIGNED_AT if done else None, "record" if done else None,
        )  # fmt: skip


async def test_ac27_screen_consent_filter_and_human_moves(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    h = await _household(seed, tenant, partner)
    system = TenantContext(tenant, "system", "planning:test")
    calls: list[tuple[uuid.UUID, Sequence[uuid.UUID]]] = []

    async def narrator(_t: TenantContext, return_id: uuid.UUID, ids: Sequence[uuid.UUID]) -> None:
        calls.append((return_id, ids))

    ps.register_planning_narrator(narrator)
    try:
        # Half-signed consents (Claire signed, Jonah did not): Not screened, no model call.
        for purpose in ("use", "ai_disclosure"):
            await _consent(seed, tenant, h, partner, purpose, (True, False))
        first = await ps.screen_return(system, h["item"], "return_approved")
        assert not first.consented and len(first.opportunity_ids) == 1 and calls == []
        row = (
            await seed.rows(
                "SELECT status, est_savings, savings_basis, rule_key FROM planning_opportunities "
                "WHERE id = $1",
                first.opportunity_ids[0],
            )
        )[0]
        assert row["status"] == "not_screened" and str(row["est_savings"]) == "1811.00"
        assert row["rule_key"] == "daf_bunching"
        assert json.loads(row["savings_basis"])["parameter_version"] == "ty2025.v1"

        # Both spouses sign: the re-screen opens the row and calls the narrator once.
        for purpose in ("use", "ai_disclosure"):
            await _consent(seed, tenant, h, partner, purpose, (True, True))
        second = await ps.screen_return(system, h["item"], "consent_completed")
        assert second.consented and second.opportunity_ids == first.opportunity_ids
        assert calls == [(h["item"], list(first.opportunity_ids))]
    finally:
        ps._NARRATOR.clear()  # pyright: ignore[reportPrivateUsage] -- the test's own slot

    ctx = partner.context()
    strip = await ps.summary(ctx, 2025, None)
    assert (strip.clients_to_contact, strip.consent_blocked, str(strip.est_savings)) == (
        1, 0, "1811.00",
    )  # fmt: skip
    found = await ps.opportunity(ctx, first.opportunity_ids[0])
    assert found.status == "open" and found.rationale_source == "template"
    assert "about 1,811" in (found.rationale or "")
    assert ps.RAISE in await ps.allowed(ctx, found)

    dismissed = await ps.dismiss(ctx, found.id, "not_suitable", None)
    assert dismissed.status == "dismissed" and dismissed.previous_status == "open"
    assert [o.id for o in await ps.opportunities(ctx)] == []
    assert [o.id for o in await ps.opportunities(ctx, include_dismissed=True)] == [found.id]
    restored = await ps.restore(ctx, found.id)
    assert restored.status == "open"
    events = await seed.rows(
        "SELECT event, to_status, reason, actor_kind FROM planning_opportunity_events "
        "WHERE opportunity_id = $1 ORDER BY at",
        found.id,
    )
    assert [(e["event"], e["to_status"]) for e in events] == [
        ("screened", "not_screened"), ("screened", "open"), ("dismissed", "dismissed"),
        ("restored", "open"),
    ]  # fmt: skip
    assert events[2]["reason"] == "not_suitable" and events[2]["actor_kind"] == "human"

    manual = await ps.create_manual(
        ctx, h["item"], "Cost segregation study", "txp01_memo", "memo:ridgeline:1"
    )
    again = await ps.create_manual(
        ctx, h["item"], "Cost segregation study", "txp01_memo", "memo:ridgeline:1"
    )
    assert manual.id == again.id and manual.status == "open" and manual.est_savings is None
    assert manual.rule_key.startswith("manual.txp01_memo.")

    prefill = await ps.create_project(ctx, found.id)
    assert prefill.source_ref == f"planning_opportunity:{found.id}"
    project = await seed.engagement(tenant, h["entity"], partner.user_id)
    await ps.on_engagement_created(
        OutboxEvent(
            event_id=uuid.uuid4(), tenant_id=tenant, event_type="engagement.created",
            payload={"engagement_id": str(project), "source_ref": prefill.source_ref},
        )
    )  # fmt: skip
    accepted = await ps.opportunity(ctx, found.id)
    assert accepted.status == "accepted" and accepted.project_engagement_id == project
