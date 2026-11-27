# ac-test-author: ayushkbhatia
"""T-06-T50 (TASK-9008; T-06 F7; TAX-11; DEC-6014) on the migrated Postgres. Row acceptance:
"Diagnostics on Ridgeline create no new issue when a matching TXP-10 issue exists" (the download's
one `form_preview.downloaded` event is S53's route, `form_pages_service.download_draft`).

A 1065 with an approved checkpoint and an engine diagnostics import carrying one error: its rule
links the open TXP-10 issue a person raised under the same reference, a second refresh adds
nothing, and a diagnostic with no open issue raises exactly one, which a third refresh links."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.modules.identity.api import member_context
from abacus.modules.review.api import create_issue
from abacus.modules.tax import form_diagnostics_run as fdr

from .support import Seeder

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def keys() -> Iterator[None]:
    configure_key_service(LocalKeyService(b"t06t50-form-diagnostics-master-key-012345"))
    yield
    reset_key_service()


async def _ridgeline(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, object]:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Ridgeline")
    await seed.member(site, partner, "engagement_partner")
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2025 Form 1065', $5) "
            "RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            partner.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year, engine) VALUES ($1, $2, $3, $4, '1065', 2025, 'cch_axcess')",
        tenant,
        item,
        site.engagement_id,
        site.entity_id,
    )
    await seed.run_untriggered(
        "INSERT INTO checkpoints (id, tenant_id, engagement_id, target_type, target_id, seq, "
        "author_kind, author_ref, cause, status, content_hash) VALUES ($1, $2, $3, 'tax_return', "
        "$4, 1, 'import', 'Imported from CCH Axcess 2025:Ridgeline:V3', 'engine_import', "
        "'approved', $5)",
        uuid.uuid4(),
        tenant,
        site.engagement_id,
        item,
        hashlib.sha256(b"ridgeline").hexdigest(),
    )
    event = await seed.value(
        "INSERT INTO engine_sync_events (tenant_id, return_id, kind, actor_kind) VALUES ($1, $2, "
        "'diagnostics', 'system') RETURNING id",
        tenant,
        item,
    )
    for code, severity in (("E1065-114", "error"), ("W1065-210", "warning")):
        await seed.run(
            "INSERT INTO engine_diagnostics (tenant_id, return_id, sync_event_id, code, severity, "
            "message_text) VALUES ($1, $2, $3, $4, $5, 'Engine message')",
            tenant,
            item,
            event,
            code,
            severity,
        )
    ctx = await member_context(tenant, partner.user_id)
    assert ctx is not None
    return tenant, site.engagement_id, item, replace(ctx, mfa_at=datetime.now(UTC))


async def test_t06t50_acceptance_a_matching_txp10_issue_is_linked_never_duplicated(
    seed: Seeder,
) -> None:
    _tenant, _engagement, item, ctx = await _ridgeline(seed)
    existing = await create_issue(
        ctx,  # type: ignore[arg-type] -- a person's AuthContext
        record_type="tax_return",
        record_id=item,
        kind="review_point",
        priority="high",
        title="Engine error E1065-114",
        internal_note=None,
        client_wording=None,
        client_contact_id=None,
        assignee_user_id=None,
        assignee_agent=False,
        blocks=["final_approval"],
        source_ref="engine_diagnostic:E1065-114",
        work_item_id=item,
    )
    before = cast(
        int, await seed.value("SELECT count(*) FROM issues WHERE work_item_id = $1", item)
    )
    checkpoint = await fdr.refresh(ctx.tenant, item)  # type: ignore[attr-defined] -- ctx is an AuthContext
    assert checkpoint is not None
    rows = {
        r["rule_key"]: r
        for r in await seed.rows(
            "SELECT rule_key, source, severity, status, issue_id FROM form_diagnostics "
            "WHERE work_item_id = $1",
            item,
        )
    }
    error = rows["engine.e1065-114"]
    assert (error["source"], error["severity"], error["status"], error["issue_id"]) == (
        "engine",
        "blocking",
        "open",
        existing,
    )
    warning = rows["engine.w1065-210"]
    assert warning["severity"] == "warning" and warning["issue_id"] is not None
    after = await seed.value("SELECT count(*) FROM issues WHERE work_item_id = $1", item)
    # The error linked the TXP-10 issue; only the two failures with none open raised one each:
    # the engine's warning and the missing partnership representative.
    assert after == before + 2
    assert rows["partnership_representative"]["status"] == "open"
    await fdr.refresh(ctx.tenant, item)  # type: ignore[attr-defined] -- ctx is an AuthContext
    assert await seed.value("SELECT count(*) FROM issues WHERE work_item_id = $1", item) == after
    assert {r for r in rows} >= {rule.key for rule in fdr.RULES}  # every code rule has its row


def test_t06t50_engine_rules_name_their_code_and_severity() -> None:
    import_id = uuid.uuid4()
    found = fdr.engine_rules(
        [
            ("E1065-114", "error", "1065.item_i", import_id),
            ("I9 Info", "informational", None, import_id),
        ]
    )
    assert [(r.rule_key, r.severity, r.issue_ref) for r in found] == [
        ("engine.e1065-114", "blocking", "engine_diagnostic:E1065-114"),
        ("engine.i9_info", "info", "engine_diagnostic:I9 Info"),
    ]
    assert all(r.failing and r.source == "engine" for r in found)


def test_t06t50_an_empty_1065_fails_only_the_partnership_representative() -> None:
    """With nothing on the return the tie-outs have nothing to compare (they read clear); the
    representative's designation is a datum the return must carry, so it fails."""
    from abacus.modules.tax.standards_checks import Facts

    found = fdr.evaluate(Facts(form="1065"))
    assert {r.rule_key for r in found} == {rule.key for rule in fdr.RULES}
    assert [r.rule_key for r in found if r.failing] == ["partnership_representative"]
