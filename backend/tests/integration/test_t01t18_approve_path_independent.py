# ac-test-author: ayushkbhatia
"""T-01-T18 (ADR-078; TASK-2433; DEC-1474's owed approve path): the independent suite for final
approval with a published BH-TAX-02, written from the row and
`docs/contracts/tax-engine-bridge.md`, not from the builder's tests. Q-03-T121 wrote the refusals;
this is the path a person takes.

The row's acceptance: "Only Daniel Reyes can approve the Feld return: a shared Ridgeline draft or
an import awaiting approval blocks him with its reason, Samuel Ito's approve control is never
enabled, the agent principal is refused at the database, and approval issues exactly one export
grant." Here BH-TAX-02 goes in as a firm imports it (the standard's workbook, then its owner's
publish) and names Daniel for the Feld client; L1 to L3 are signed on the approved import's
checkpoint through `POST /v1/sign-offs`. Then: Samuel's read names Daniel as the approver and his
approve is refused; a shared Ridgeline draft K-1 or a second import awaiting approval blocks
Daniel with its code and record, and the refusal changes nothing; with neither, Daniel's approval
records one L4 sign-off on the checkpoint's hash, moves the return to Approved and issues exactly
one export grant, opening after the 10-second Undo window. The agent and policy principals'
refusal at the database is Q-03-T121's (`test_t01t18_final_approval_independent.py`).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

from abacus.kernel.clock import today
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology.api import (
    create_standard,
    import_standard_workbook,
    publish_standard,
    standard_workbook,
)
from abacus.modules.review.api import STATEMENTS

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import (
    HEAD,
    Feld,
    Json,
    _person,  # pyright: ignore[reportPrivateUsage] -- T-01-T25's harness
    call_as,
    engines,
    feld_return,
    switched_on,
)

__all__ = ["engines", "switched_on"]

UNDO = timedelta(seconds=10)
LEVELS = ("L1_preparer", "L2_reviewer", "L3_manager")
V4 = (HEAD + "2025I:FeldJ,V4,f1040.direct_deposit_last4,1040,35b,6620\n").encode()


async def _staff(feld: Feld, name: str, role: str, *, level: str = "manager") -> AuthContext:
    """A member of the Feld engagement in `role`, independence confirmed."""
    who = await _person(feld.seed, feld.tenant, name)
    await feld.seed.run(
        "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
        feld.tenant,
        who.user_id,
        level,
    )
    await feld.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
        feld.tenant,
        feld.engagement,
        who.user_id,
        role,
    )
    await _confirm(feld, who)
    return who


async def _confirm(feld: Feld, who: AuthContext) -> None:
    await feld.seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
        "clock_timestamp()) ON CONFLICT DO NOTHING",
        feld.tenant,
        feld.engagement,
        who.user_id,
    )


async def _bh_tax_02(feld: Feld, daniel: AuthContext) -> None:
    """BH-TAX-02 as the firm loads it: the workbook imported to a draft, published by its owner,
    naming Daniel Reyes for the Feld client."""
    client = cast(
        uuid.UUID,
        await feld.seed.value("SELECT client_id FROM work_items WHERE id = $1", feld.item),
    )
    standard = await create_standard(
        daniel,
        kind="return_approval_policy",
        key="bh-tax-02",
        name="Return final approval",
        owner_id=daniel.user_id,
    )
    payload: dict[str, object] = {
        "kind": "return_approval_policy",
        "code": "BH-TAX-02",
        "rule": "signing_partner_final_approval",
        "applies_to": [{"client_id": str(client), "approver_user_id": str(daniel.user_id)}],
        "export_condition": "after_final_approval",
    }
    await import_standard_workbook(
        daniel, standard.id, standard_workbook(standard.kind, standard.name, payload)
    )
    await publish_standard(
        daniel, standard.id, effective_from=await today(daniel.tenant), change_summary="Version 1"
    )


async def _ready(feld: Feld, *, upto: int = 3) -> tuple[AuthContext, str]:
    """Daniel named by BH-TAX-02, the return In review, and L1 to `upto` signed on its
    checkpoint; Daniel and the checkpoint's content hash."""
    await feld.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'review.grammar_api', 'true', 'test-seed', 'T-01-T18')",
        feld.tenant,
    )
    await feld.seed.open_engagement(feld.tenant, feld.engagement)  # pyright: ignore[reportArgumentType] -- the harness keeps the id untyped
    daniel = await _staff(feld, "Daniel Reyes", "engagement_partner", level="partner")
    await feld.seed.run(
        "UPDATE memberships SET firm_role = 'practice_leader' "
        "WHERE tenant_id = $1 AND user_id = $2",
        feld.tenant,
        daniel.user_id,
    )
    daniel = replace(daniel, firm_role="practice_leader")
    await feld.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'signer', $4)",
        feld.tenant,
        feld.item,
        feld.engagement,
        daniel.user_id,
    )
    await _bh_tax_02(feld, daniel)
    await feld.seed.run(
        "UPDATE tax_returns SET status = 'in_review' WHERE work_item_id = $1", feld.item
    )
    digest = cast(
        str,
        await feld.seed.value(
            "SELECT content_hash FROM checkpoints WHERE id = $1", feld.checkpoint
        ),
    )
    seen = f"sha256:{digest.removeprefix('sha256:')}"
    await _confirm(feld, feld.samuel)
    kevin = await _staff(feld, "Kevin Osei", "staff", level="staff")
    priya = await _staff(feld, "Priya Nair", "senior", level="senior")
    for who, level in ((kevin, 1), (priya, 2), (feld.samuel, 3))[:upto]:
        signed = await call_as(who)(
            "POST",
            "/v1/sign-offs",
            json={
                "target_type": "tax_return",
                "target_id": str(feld.item),
                "level": LEVELS[level - 1],
                "seen_hash": seen,
                "statement_version": STATEMENTS[level].version,
            },
        )
        assert signed.status_code == 201, (level, signed.text)
    return daniel, seen


async def _approve(feld: Feld, who: AuthContext, seen: str) -> tuple[int, Json]:
    answered = await call_as(who)(
        "POST",
        f"/v1/tax-returns/{feld.item}/final-approval",
        json={"seen_checkpoint_id": str(feld.checkpoint), "content_hash": seen},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    return answered.status_code, cast(Json, answered.json())


async def _read(feld: Feld, who: AuthContext) -> Json:
    read = await call_as(who)("GET", f"/v1/tax-returns/{feld.item}/final-approval")
    assert read.status_code == 200, read.text
    return cast(Json, read.json())


async def _unchanged(feld: Feld) -> None:
    assert (
        await feld.seed.value("SELECT status FROM tax_returns WHERE work_item_id = $1", feld.item)
        == "in_review"
    )
    for query in (
        "SELECT count(*) FROM sign_offs WHERE target_id = $1 AND level = 4",
        "SELECT count(*) FROM approval_grants WHERE subject_id = $1",
    ):
        assert await feld.seed.value(query, feld.item) == 0, query


async def test_ac_only_daniel_approves_and_exactly_one_export_grant_is_issued(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    daniel, seen = await _ready(feld)
    # Samuel's control is never enabled: the read names Daniel, and his approve is refused.
    samuels = await _read(feld, feld.samuel)
    assert samuels["approver_user_id"] == str(daniel.user_id)
    status, _ = await _approve(feld, feld.samuel, seen)
    assert status == 403
    await _unchanged(feld)

    daniels = await _read(feld, daniel)
    assert daniels["eligible"] is True, daniels["blockers"]
    assert daniels["checkpoint_id"] == str(feld.checkpoint)
    before = datetime.now(UTC)
    status, body = await _approve(feld, daniel, seen)
    assert status == 200, body
    assert (
        await feld.seed.value("SELECT status FROM tax_returns WHERE work_item_id = $1", feld.item)
        == "approved"
    )
    final = await feld.seed.rows(
        "SELECT signed_by, content_hash FROM sign_offs WHERE target_id = $1 AND level = 4",
        feld.item,
    )
    bare = seen.removeprefix("sha256:")
    assert [(r["signed_by"], str(r["content_hash"]).removeprefix("sha256:")) for r in final] == [
        (daniel.user_id, bare)
    ]
    grants = await feld.seed.rows(
        "SELECT action, approver_user_id, payload_sha256, not_before FROM approval_grants "
        "WHERE subject_id = $1",
        feld.item,
    )
    assert len(grants) == 1
    (grant,) = grants
    assert (grant["action"], grant["approver_user_id"]) == ("tax_return.approve", daniel.user_id)
    assert grant["payload_sha256"] == seen.removeprefix("sha256:")
    assert grant["not_before"] >= before + UNDO - timedelta(seconds=1)
    events = await feld.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'tax_return.approved'",
        feld.tenant,
    )
    assert events == 1
    again, _ = await _approve(feld, daniel, seen)  # approved once; a second approval is refused
    assert again in (403, 409)
    assert (
        await feld.seed.value(
            "SELECT count(*) FROM approval_grants WHERE subject_id = $1", feld.item
        )
        == 1
    )


async def test_ac_a_shared_ridgeline_draft_blocks_daniel_with_its_reason(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    daniel, seen = await _ready(feld)
    ridgeline = await feld.seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, created_by) SELECT tenant_id, engagement_id, client_id, client_entity_id, "
        "'tax_return', 'Ridgeline Partners 1065', $2 FROM work_items WHERE id = $1 RETURNING id",
        feld.item,
        feld.samuel.user_id,
    )
    recipient = await feld.seed.value(
        "INSERT INTO k1_recipients (tenant_id, work_item_id, engine_ref, display_name, "
        "recipient_kind) VALUES ($1, $2, 'P01', 'Jonah Feld', 'lp') RETURNING id",
        feld.tenant,
        ridgeline,
    )
    package = await feld.seed.value(
        "INSERT INTO k1_packages (tenant_id, recipient_id, work_item_id, form, tax_year, "
        "version_no) VALUES ($1, $2, $3, '1065', 2025, 1) RETURNING id",
        feld.tenant,
        recipient,
        ridgeline,
    )
    await feld.seed.run(
        "INSERT INTO k1_handoffs (tenant_id, package_id, target_work_item_id, shared_by) "
        "VALUES ($1, $2, $3, $4)",
        feld.tenant,
        package,
        feld.item,
        feld.samuel.user_id,
    )
    read = await _read(feld, daniel)
    assert read["eligible"] is False
    blockers = cast(list[Json], read["blockers"])
    assert [(b["kind"], b.get("ref_id")) for b in blockers] == [("draft_k1", str(package))]
    status, body = await _approve(feld, daniel, seen)
    assert status == 409 and body["detail"] == "final_approval_blocked", body
    await _unchanged(feld)


async def test_ac_an_import_awaiting_approval_blocks_daniel_with_its_reason(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    daniel, seen = await _ready(feld)
    uploaded = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-imports",
        params={"kind": "values"},
        headers={"X-File-Name": "2025I_FeldJ_V4.csv", "Content-Type": "text/csv"},
        content=V4,
    )
    assert uploaded.status_code == 201, uploaded.text
    assert cast(Json, uploaded.json())["status"] == "pending_approval"
    read = await _read(feld, daniel)
    kinds = [b["kind"] for b in cast(list[Json], read["blockers"])]
    assert kinds == ["import_pending_approval"], read["blockers"]
    status, body = await _approve(feld, daniel, seen)
    assert status == 409 and body["detail"] == "final_approval_blocked", body
    await _unchanged(feld)


async def test_ac_a_missing_manager_sign_off_blocks_by_its_level(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    daniel, seen = await _ready(feld, upto=2)
    read = await _read(feld, daniel)
    kinds = [b["kind"] for b in cast(list[Json], read["blockers"])]
    assert kinds == ["sign_off_missing_l3"], read["blockers"]
    status, _ = await _approve(feld, daniel, seen)
    assert status == 409
    await _unchanged(feld)
