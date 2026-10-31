"""N-02-T32 (TASK-2410; N-02 §3.11, §4.2; ENG-04; C11; DEC-1458) against Postgres: the composed
engagement letter.

The row's acceptance: Ridgeline's letter renders through C11 with the fee 18,500 computed from
6,500 and 12,000, and the engineer's fee shown but not added. Also: a draft edit is a new
version (the old one superseded, its content never rewritten), fee wording is never a person's
text, a template's clause, variable or section must exist, overrides are plain text, a stale
`If-Match` is refused, and a sent letter takes no edit.

The template version is a probe inserted as the superuser (firm content arrives through P-11's
import, never a seed); the names follow the ENG-04 handoff.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import cast

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.engagements import letters
from abacus.modules.engagements.letter_contract import (
    FeeLineIn,
    InstallmentIn,
    LetterDraftIn,
    LetterFeesIn,
    ThirdPartyFeeIn,
)
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting import api as c11

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

VARIABLES = [
    {"key": key, "label": key, "value_type": "text"}
    for key in (
        "client.name",
        "client.signer",
        "firm.signer",
        "letter.date",
        "fee.total",
        "fee.breakdown",
        "billing.schedule",
        "third_party_fee.summary",
    )
]
CLAUSES: list[dict[str, object]] = [
    {"clause_id": cid, "title": title, "standard": [], "default_enabled": True}
    for cid, title in (
        ("scope", "Scope of services"),
        ("timing", "Timing and the §754 deadline"),
        ("reliance", "Reliance on the engineer's study"),
        ("fees", "Fees and billing"),
    )
]


def _clause(clause_id: str, *, non_standard: bool = False) -> dict[str, object]:
    return {
        "type": "clause",
        "clause_id": clause_id,
        "enabled": True,
        "non_standard": non_standard,
        "blocks": [],
    }


BODY = [
    {
        "type": "section",
        "id": "scope",
        "title": "1. Scope of services",
        "blocks": [_clause("scope")],
    },
    {
        "type": "section",
        "id": "timing",
        "title": "3. Timing and the section 754 deadline",
        "blocks": [_clause("timing", non_standard=True), _clause("reliance", non_standard=True)],
    },
    {"type": "section", "id": "fees", "title": "6. Fees and billing", "blocks": [_clause("fees")]},
]
RIDGELINE_FEES = LetterFeesIn(
    basis="fixed",
    lines=[
        FeeLineIn(label="for the section 754 work", amount_cents=6_500_00),
        FeeLineIn(label="for cost segregation coordination and Form 3115", amount_cents=12_000_00),
    ],
    installments=[
        InstallmentIn(label="on signature", share_bp=5_000),
        InstallmentIn(label="on Form 3115 delivery", share_bp=5_000),
    ],
    third_party=[
        ThirdPartyFeeIn(payee="Tallgrass Cost Engineering, LLC", estimated_cents=9_800_00)
    ],
)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> object:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
def fresh_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(c11, "_REGISTRY", {})


async def ridgeline(seed: Seeder) -> tuple[AuthContext, uuid.UUID, uuid.UUID]:
    tenant = await seed.firm()
    daniel = await seed.person(tenant)
    await seed.run("UPDATE users SET display_name = 'Daniel Reyes' WHERE id = $1", daniel.user_id)
    entity = await seed.entity(tenant, "Ridgeline Property Partners, LP")
    engagement = await seed.engagement(tenant, entity, daniel.user_id)
    await seed.member(engagement, daniel, "engagement_partner")
    client = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    owen = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, title) "
            "VALUES ($1, $2, 'Owen Calder', 'client_person', $3) RETURNING id",
            tenant,
            client,
            "Managing Member, Ridgeline GP LLC (general partner)",
        ),
    )
    await seed.run(
        "INSERT INTO engagement_contacts (tenant_id, engagement_id, contact_id, designation, "
        "designated_by) VALUES ($1, $2, $3, 'signing_officer', $4)",
        tenant,
        engagement,
        owen,
        daniel.user_id,
    )
    template_version = await _template(seed, tenant, daniel)
    return daniel.context(), engagement, template_version


async def _template(seed: Seeder, tenant: uuid.UUID, by: Person) -> uuid.UUID:
    template = await seed.value(
        "INSERT INTO report_templates (tenant_id, family, name, created_by_user_id) "
        "VALUES ($1, 'engagement_letter', 'BH Tax Advisory Letter', $2) RETURNING id",
        tenant,
        by.user_id,
    )
    content = json.dumps([BODY, CLAUSES, VARIABLES], sort_keys=True)
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO report_template_versions (tenant_id, template_id, version_no, "
            "layout_key, body, clauses, variables, source, content_sha256, "
            "imported_by_user_id) VALUES ($1, $2, 4, 'letter', $3::jsonb, $4::jsonb, $5::jsonb, "
            "'import', $6, $7) RETURNING id",
            tenant,
            template,
            json.dumps(BODY),
            json.dumps(CLAUSES),
            json.dumps(VARIABLES),
            hashlib.sha256(content.encode()).hexdigest(),
            by.user_id,
        ),
    )


def draft_of(template_version: uuid.UUID, **over: object) -> LetterDraftIn:
    base: dict[str, object] = {
        "template_version_id": template_version,
        "clause_states": {},
        "variables": {},
        "fees": RIDGELINE_FEES,
    }
    return LetterDraftIn.model_validate({**base, **over})


async def test_ac1_ridgelines_fee_is_computed_and_the_engineers_is_not_added(
    seed: Seeder,
) -> None:
    ctx, engagement, template_version = await ridgeline(seed)
    view = await letters.draft_letter(ctx, engagement, draft_of(template_version), '"0"')

    assert view.fees is not None
    assert view.fees.total_cents == 18_500_00
    assert [i.amount_cents for i in view.fees.installments] == [9_250_00, 9_250_00]
    assert [(t.estimated_cents, t.included_in_total) for t in view.fees.third_party] == [
        (9_800_00, False)
    ]
    values = {v.key: v.value for v in view.variables}
    assert values["fee.total"] == "$18,500"
    assert values["billing.schedule"] == "$9,250 on signature · $9,250 on Form 3115 delivery"
    assert values["third_party_fee.summary"] == (
        "Est. $9,800 · billed by Tallgrass Cost Engineering, LLC"
    )
    assert values["client.signer"] == (
        "Owen Calder · Managing Member, Ridgeline GP LLC (general partner)"
    )
    assert values["firm.signer"] == "Daniel Reyes, Partner"
    reasons = {v.key: v.reason for v in view.variables}
    assert reasons["approver_of_record"] == "cas_only"
    assert reasons["ebp.limited_scope_election"] == "ebp_only"
    assert view.status == "draft"
    assert view.version == 1
    assert view.redline_count == 2  # the two clauses the template marks non-standard
    assert (view.template_name, view.template_version_no) == ("BH Tax Advisory Letter", 4)
    assert [(s.order, s.name, s.role) for s in view.signers] == [
        (1, "Owen Calder", "client"),
        (2, "Daniel Reyes", "firm"),
    ]
    assert len(view.paper) == 3

    # Rendered through C11: the letter version names the C11 draft and its content hash.
    rows = await seed.rows(
        "SELECT v.content_hash AS letter_hash, g.content_hash, g.mode, d.kind, d.owner_id "
        "FROM engagement_letter_versions v "
        "JOIN generated_documents d ON d.id = v.generated_document_id "
        "JOIN generated_document_versions g ON g.generated_document_id = d.id "
        "WHERE v.engagement_id = $1",
        engagement,
    )
    assert [(r["kind"], r["owner_id"], r["mode"]) for r in rows] == [
        ("engagement_letter", engagement, "draft")
    ]
    assert rows[0]["letter_hash"] == rows[0]["content_hash"]
    stored = await seed.value(
        "SELECT variables ->> 'fee.total' FROM engagement_letter_versions "
        "WHERE engagement_id = $1",
        engagement,
    )
    assert stored == "$18,500"


async def test_ac1_an_edit_is_a_new_version_and_the_old_one_is_never_rewritten(
    seed: Seeder,
) -> None:
    ctx, engagement, template_version = await ridgeline(seed)
    await letters.draft_letter(ctx, engagement, draft_of(template_version), '"0"')
    second = await letters.draft_letter(
        ctx, engagement, draft_of(template_version, clause_states={"reliance": "off"}), '"1"'
    )
    assert second.version == 2
    assert {c.key: c.state for c in second.clauses}["reliance"] == "off"
    assert second.redline_count == 3  # a clause switched off adds to the redline
    versions = await seed.rows(
        "SELECT version_no, status FROM engagement_letter_versions WHERE engagement_id = $1 "
        "ORDER BY version_no",
        engagement,
    )
    assert [(v["version_no"], v["status"]) for v in versions] == [(1, "superseded"), (2, "draft")]
    # Even the owner cannot rewrite a version's content: the guard trigger refuses it.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(
            "UPDATE engagement_letter_versions SET variables = '{}'::jsonb "
            "WHERE engagement_id = $1",
            engagement,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(
            "DELETE FROM engagement_letter_versions WHERE engagement_id = $1", engagement
        )


async def test_fee_wording_is_never_a_persons_text_and_shares_must_foot(seed: Seeder) -> None:
    ctx, engagement, template_version = await ridgeline(seed)
    with pytest.raises(letters.ComputedVariable):
        await letters.draft_letter(
            ctx, engagement, draft_of(template_version, variables={"fee.total": "$1"}), '"0"'
        )
    uneven = RIDGELINE_FEES.model_copy(
        update={"installments": [InstallmentIn(label="on signature", share_bp=6_000)]}
    )
    with pytest.raises(letters.FeesDoNotFoot):
        await letters.draft_letter(ctx, engagement, draft_of(template_version, fees=uneven), '"0"')


async def test_unknown_parts_markup_and_stale_versions_are_refused(seed: Seeder) -> None:
    ctx, engagement, template_version = await ridgeline(seed)
    with pytest.raises(letters.UnknownLetterPart):
        await letters.draft_letter(
            ctx, engagement, draft_of(template_version, clause_states={"nope": "off"}), '"0"'
        )
    with pytest.raises(letters.MarkupNotAllowed):
        await letters.draft_letter(
            ctx,
            engagement,
            draft_of(template_version, section_overrides={"timing": "<b>Due</b> Sep 15"}),
            '"0"',
        )
    with pytest.raises(letters.LetterStale):
        await letters.draft_letter(ctx, engagement, draft_of(template_version), '"3"')
    assert (
        await seed.value(
            "SELECT count(*) FROM engagement_letter_versions WHERE engagement_id = $1", engagement
        )
        == 0
    )


async def test_a_sent_letter_takes_no_edit(seed: Seeder) -> None:
    ctx, engagement, template_version = await ridgeline(seed)
    await letters.draft_letter(ctx, engagement, draft_of(template_version), '"0"')
    hash_ = cast(
        str,
        await seed.value(
            "SELECT content_hash FROM engagement_letter_versions WHERE engagement_id = $1",
            engagement,
        ),
    )
    # 0563 (N-02-T33): only the approving person's own transaction approves a version.
    await seed.as_actor(
        ctx.tenant_id,
        ("human", str(ctx.user_id)),
        "UPDATE engagement_letter_versions SET status = 'partner_approved', approved_by = $1, "
        "approved_at = now(), approval_content_hash = $2 WHERE engagement_id = $3",
        ctx.user_id,
        hash_,
        engagement,
    )
    await seed.run(
        "UPDATE engagement_letter_versions SET status = 'sent', envelope_id = $1 "
        "WHERE engagement_id = $2",
        uuid.uuid4(),
        engagement,
    )
    with pytest.raises(letters.LetterLocked):
        await letters.draft_letter(ctx, engagement, draft_of(template_version), '"1"')
    view = await letters.composed_letter(ctx, engagement)
    assert view.status == "sent"
    assert "letter.draft" not in view.allowed_actions


def test_money_is_computed_by_code() -> None:
    fees = letters.compute_fees(
        RIDGELINE_FEES.model_copy(
            update={
                "lines": [FeeLineIn(label="fee", amount_cents=100_01)],
                "installments": [
                    InstallmentIn(label="a", share_bp=3_333),
                    InstallmentIn(label="b", share_bp=3_333),
                    InstallmentIn(label="c", share_bp=3_334),
                ],
            }
        )
    )
    assert sum(i.amount_cents for i in fees.installments) == fees.total_cents == 100_01
    assert letters.money(1_850_000) == "$18,500"
    assert letters.money(1_850_050) == "$18,500.50"
