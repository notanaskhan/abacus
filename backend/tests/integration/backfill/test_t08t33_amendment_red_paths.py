# ac-test-author: ayushkbhatia
"""T-08-T33 (TASK-9006; SPEC-710 AC6.3, AC6.6; BH-TAX-02; INV-1; DEC-6012) on the migrated
Postgres. Row acceptance: "Only Neil Ashcroft can approve the Okafor amendment or decide the
Vantage election, both human-only through all five layers."

The Okafor amendment comes from the T-08-T30 suite's fixture; BH-TAX-02 names Neil for the client
as a firm loads it (the standard's workbook, published by its owner)."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.clock import today
from abacus.kernel.errors import DomainConflict
from abacus.modules.identity.api import AuthContext, Forbidden, member_context
from abacus.modules.methodology.api import (
    create_standard,
    import_standard_workbook,
    publish_standard,
    standard_workbook,
)
from abacus.modules.review.api import decide_card
from abacus.modules.tax import amendment_gates, approval

from .okafor_amendment import Okafor
from .support import Person

pytestmark = pytest.mark.asyncio


async def _ctx(tenant: uuid.UUID, who: Person, *, kind: str = "human") -> AuthContext:
    found = await member_context(tenant, who.user_id)
    assert found is not None
    ctx = replace(found, mfa_at=datetime.now(UTC))
    if kind != "human":
        ctx = replace(ctx, tenant=replace(ctx.tenant, actor_kind=kind))
    return ctx


async def _neil(w: Okafor) -> Person:
    neil = await w.seed.person(w.tenant, "practice_leader")
    await w.seed.run(  # a partner owns BH-TAX-02 (methodology's owner rule)
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        w.tenant,
        neil.user_id,
    )
    await w.seed.member(w.site, neil, "engagement_partner")
    daniel = await _ctx(w.tenant, neil)
    standard = await create_standard(
        daniel,
        kind="return_approval_policy",
        key="bh-tax-02",
        name="Return final approval",
        owner_id=neil.user_id,
    )
    payload: dict[str, object] = {
        "kind": "return_approval_policy",
        "code": "BH-TAX-02",
        "rule": "signing_partner_final_approval",
        "applies_to": [
            {"client_id": str(w.site.client_id), "approver_user_id": str(neil.user_id)}
        ],
        "export_condition": "after_final_approval",
    }
    await import_standard_workbook(
        daniel, standard.id, standard_workbook(standard.kind, standard.name, payload)
    )
    await publish_standard(
        daniel, standard.id, effective_from=await today(daniel.tenant), change_summary="Version 1"
    )
    return neil


async def _amend(w: Okafor) -> tuple[str, uuid.UUID]:
    made = await w.net.call(
        "POST",
        f"/v1/tax-returns/{w.original}/amendments",
        w.yusuf,
        body={"kind": "amended_return", "jurisdictions": ["federal"]},
        headers=w.net.keyed(),
    )
    assert made.status_code == 201, made.text
    return made.json()["amendment_id"], uuid.UUID(made.json()["work_item_id"])


async def test_t08t33_acceptance_only_neil_approves_the_okafor_amendment(okafor: Okafor) -> None:
    w = okafor
    neil = await _neil(w)
    amendment, new_return = await _amend(w)
    yusuf = await _ctx(w.tenant, w.yusuf)

    found = await approval.eligibility(yusuf, new_return)
    assert found.signer == neil.user_id  # BH-TAX-02's signer for the client
    assert "amendment_explanation_missing" in {b.kind for b in found.blockers}
    assert approval.blocker_words("amendment_explanation_missing") == (
        "The amendment's Part II explanation is not written."
    )

    row = (await w.net.call("GET", f"/v1/amendments/{amendment}", w.yusuf)).json()
    await w.net.call(
        "PUT",
        f"/v1/amendments/{amendment}/explanation",
        w.yusuf,
        body={"text": "A missed Form 1098 and depreciation on the Ridge Avenue roof."},
        headers={"If-Match": str(row["row_version"])},
    )
    found = await approval.eligibility(yusuf, new_return)
    assert "amendment_explanation_missing" not in {b.kind for b in found.blockers}

    # Neither Yusuf, nor an agent acting for Neil, can approve: layers 3 and 5.
    for ctx in (yusuf, await _ctx(w.tenant, neil, kind="agent")):
        with pytest.raises(Forbidden):
            await approval.approve(ctx, new_return, uuid.uuid4(), "sha256:" + "0" * 64)
    routed = await w.net.call("POST", f"/v1/amendments/{amendment}/routing", w.yusuf)
    assert routed.status_code == 200, routed.text
    told = await w.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'amendment.approval_requested'",
        w.tenant,
    )
    assert [json.loads(r["payload"])["recipient_user_ids"] for r in told] == [[str(neil.user_id)]]


async def _vantage(w: Okafor, neil: Person) -> tuple[uuid.UUID, uuid.UUID]:
    """Vantage Point Realty's TY2024 AAR: one adjustment (unreported parking income 40,000), the
    engine's imputed underpayment 14,800."""
    item = cast(
        uuid.UUID,
        await w.seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2024 AAR', $5) RETURNING id",
            w.tenant,
            w.site.engagement_id,
            w.site.client_id,
            w.site.entity_id,
            neil.user_id,
        ),
    )
    await w.seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year, amends_return_id) VALUES ($1, $2, $3, $4, '1065', 2024, $5)",
        w.tenant,
        item,
        w.site.engagement_id,
        w.site.entity_id,
        w.original,
    )
    await w.seed.run(  # Neil signs the reviewed-year return (BH-TAX-02's signer, assigned)
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'signer', $4)",
        w.tenant,
        item,
        w.site.engagement_id,
        neil.user_id,
    )
    aar = cast(
        uuid.UUID,
        await w.seed.value(
            "INSERT INTO amendments (tenant_id, engagement_id, work_item_id, "
            "original_work_item_id, kind, jurisdictions, created_by) VALUES ($1, $2, $3, $4, "
            "'bba_aar', ARRAY['US'], $5) RETURNING id",
            w.tenant,
            w.site.engagement_id,
            item,
            w.original,
            neil.user_id,
        ),
    )
    await w.seed.run(
        "INSERT INTO aar_adjustments (tenant_id, amendment_id, reviewed_year, description, "
        "amount, position) VALUES ($1, $2, 2024, 'Unreported parking income', 40000, 1)",
        w.tenant,
        aar,
    )
    await w.seed.run(
        "INSERT INTO return_engine_summaries (tenant_id, work_item_id, engine_version, kind, "
        "lines, approved_at) VALUES ($1, $2, 'CCH Axcess 2024', 'final', $3::jsonb, now())",
        w.tenant,
        item,
        json.dumps([{"line_key": "aar.imputed_underpayment", "amount": "14800"}]),
    )
    return aar, item


async def test_t08t33_acceptance_only_neil_decides_the_vantage_election(okafor: Okafor) -> None:
    w = okafor
    neil = await _neil(w)
    aar, item = await _vantage(w, neil)
    neil_ctx = await _ctx(w.tenant, neil)
    assert {b.kind for b in await amendment_gates.amendment_blockers(neil_ctx.tenant, item)} == {
        "bba_election_undecided"
    }
    card = await amendment_gates.raise_election(neil_ctx, aar)
    detail = await w.net.call("GET", f"/v1/decision-cards/{card}", w.yusuf)
    version = detail.json().get("version_no", 1) if detail.status_code == 200 else 1
    figures = await w.seed.value("SELECT options::text FROM decision_cards WHERE id = $1", card)
    assert "14800.00" in str(figures) and "40000.00" in str(figures)
    for ctx in (await _ctx(w.tenant, w.yusuf), await _ctx(w.tenant, neil, kind="agent")):
        with pytest.raises((Forbidden, DomainConflict)):
            await decide_card(
                ctx,
                card,
                option_key="push_out",
                factors=[],
                rationale="Partners pay",
                seen_version=version,
            )
    assert (
        await w.seed.value("SELECT count(*) FROM aar_elections WHERE amendment_id = $1", aar) == 0
    )
    await decide_card(
        neil_ctx,
        card,
        option_key="push_out",
        factors=[],
        rationale="The reviewed-year partners take the adjustment",
        seen_version=version,
    )
    rows = await w.seed.rows(
        "SELECT route, imputed_underpayment, iu_source, decided_by, actor_kind FROM aar_elections "
        "WHERE amendment_id = $1",
        aar,
    )
    assert [
        (
            r["route"],
            str(r["imputed_underpayment"]),
            r["iu_source"],
            r["decided_by"],
            r["actor_kind"],
        )
        for r in rows
    ] == [
        ("push_out", "14800.00", "engine", neil.user_id, "human"),
    ]
    assert await amendment_gates.amendment_blockers(neil_ctx.tenant, item) == []
