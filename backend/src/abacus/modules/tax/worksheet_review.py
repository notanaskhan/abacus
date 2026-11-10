"""The individual return workspace in the review grammar (T-04-T15; SPEC-649; T-04 §4.1; ADR-160,
ADR-161; DEC-3208).

Registrations the tax module makes through `review.api` and `agents.api` (it owns the tables of
0761; nothing else writes them):

- **Reviewables.** `return_worksheet` and `return_worksheet_section`, each with a content-hash
  provider: SHA-256 (`review.content_hash`) over its fields' keys and current values, so a field
  edit moves its section's and its worksheet's hash and the sign-offs on them read stale.
- **The field owner** `return_worksheet` (TAX-04/05 field paths `PUT /v1/fields/return_worksheet/
  <worksheet>/<field_key>/value`): the current value, the field's label, and a person's edit.
  Every return field is tax return information (TRI), so every key is TRI-tagged; an engine-
  sourced field is read-only (409 `engine_field_read_only`): its value comes from the engine
  import. The edit lands in `return_fields.current_value`, then the generic route records the
  `field_value_versions` row and the human checkpoint (`checkpoints=True`).
- **Suggestion targets** `return_field`, `pass_through_treatment` (a K-1 treatment: the slots'
  codes hold no digits) and `residency_determination`, each owned by its engagement; **proposal
  adapters** `return_field_changes`, `pass_through_treatments` and `residency`, which apply an
  approved proposal's rows through `review.api.record_value` (never a pending or rejected one;
  the agent proposes, a person approved).

An unregistered target type stays refused by the slots (fail closed).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.agents.api import (
    approved_proposal_rows,
    register_proposal_adapter,
    register_suggestion_target,
)
from abacus.modules.engagements.api import lock_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.review.api import (
    FieldOwner,
    Reviewable,
    ReviewableFacts,
    content_hash,
    record_value,
    register_field_owner,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.tax.worksheets import recompute_after_edit

WORKSHEET: Final = "return_worksheet"
SECTION: Final = "return_worksheet_section"
ALL_FIELDS_TRI: Final = frozenset({"*"})  # every return field is TRI (C19)


class EngineFieldReadOnly(DomainConflict):
    """An engine-sourced field takes its value from the engine import, never an edit."""

    code = "engine_field_read_only"


# --- hashes --------------------------------------------------------------------------------------

_FIELDS_OF: Final = text(
    "SELECT section_id, field_key, current_value FROM return_fields "
    "WHERE worksheet_id = :w ORDER BY field_key"
)


def _hash(rows: list[tuple[str, object]]) -> str:
    body = {"fields": [{"key": k, "value": v} for k, v in rows]}
    return content_hash(body)  # pyright: ignore[reportArgumentType] -- JSON column values


async def _rehash(tx: UnitOfWork, worksheet_id: UUID, section_id: UUID) -> str:
    """The section's and the worksheet's new hashes after a field moved; the worksheet's."""
    rows = (await tx.session.execute(_FIELDS_OF, {"w": worksheet_id})).all()
    section = _hash([(r.field_key, r.current_value) for r in rows if r.section_id == section_id])
    sheet = _hash([(r.field_key, r.current_value) for r in rows])
    await tx.session.execute(
        text(
            "UPDATE return_worksheet_sections SET content_hash = :h, version_no = version_no + 1, "
            "updated_at = clock_timestamp() WHERE id = :s"
        ),
        {"h": section, "s": section_id},
    )
    await tx.session.execute(
        text(
            "UPDATE return_worksheets SET content_hash = :h, version_no = version_no + 1, "
            "updated_at = clock_timestamp() WHERE id = :w"
        ),
        {"h": sheet, "w": worksheet_id},
    )
    return sheet


async def _rehash_all(tx: UnitOfWork, worksheet_id: UUID) -> str:
    """Every section's hash and the worksheet's, after a recompute moved fields anywhere."""
    sections = (
        await tx.session.execute(
            text("SELECT id FROM return_worksheet_sections WHERE worksheet_id = :w"),
            {"w": worksheet_id},
        )
    ).scalars()
    sheet = ""
    for section_id in list(sections):
        sheet = await _rehash(tx, worksheet_id, section_id)
    return sheet


# --- reviewables ---------------------------------------------------------------------------------


async def worksheet_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, key, title, content_hash FROM return_worksheets "
                    "WHERE engagement_id = :e AND active ORDER BY sort_order, key"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [Reviewable(WORKSHEET, r.id, r.key, r.title, r.content_hash, True) for r in rows]


async def section_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT s.id, w.key || ':' || s.key AS code, s.name, s.content_hash "
                    "FROM return_worksheet_sections s JOIN return_worksheets w "
                    "ON w.id = s.worksheet_id WHERE s.engagement_id = :e AND w.active "
                    "ORDER BY w.sort_order, s.sort_order, s.key"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [Reviewable(SECTION, r.id, r.code, r.name, r.content_hash, True) for r in rows]


async def _facts(tenant: TenantContext, table: str, target: str, row_id: UUID) -> ReviewableFacts:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    f"SELECT engagement_id, content_hash, version_no FROM {table} WHERE id = :i"  # noqa: S608 -- a fixed table of this module
                ),
                {"i": row_id},
            )
        ).first()
    if row is None:
        raise NotFound(target)
    return ReviewableFacts(
        target_type=target,
        target_id=row_id,
        engagement_id=row.engagement_id,
        content_hash=row.content_hash,
        version_no=row.version_no,
        preparer_user_ids=frozenset(),
    )


async def worksheet_facts(tenant: TenantContext, worksheet_id: UUID) -> ReviewableFacts:
    return await _facts(tenant, "return_worksheets", WORKSHEET, worksheet_id)


async def section_facts(tenant: TenantContext, section_id: UUID) -> ReviewableFacts:
    return await _facts(tenant, "return_worksheet_sections", SECTION, section_id)


# --- the field owner -----------------------------------------------------------------------------

_FIELD: Final = text(
    "SELECT id, section_id, engagement_id, tax_return_id, derivation, current_value, label "
    "FROM return_fields WHERE worksheet_id = :w AND field_key = :k"
)


async def field_value(
    tenant: TenantContext, worksheet_id: UUID, field_key: str
) -> dict[str, object] | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_FIELD, {"w": worksheet_id, "k": field_key})).first()
    return None if row is None else cast(dict[str, object] | None, row.current_value)


async def write_field(
    tx: UnitOfWork, worksheet_id: UUID, field_key: str, value: Mapping[str, object]
) -> tuple[UUID, UUID, UUID, str]:
    """The field's new current value and the hashes after it: (field, section, engagement, the
    worksheet's hash). An engine-sourced field refuses."""
    row = (await tx.session.execute(_FIELD, {"w": worksheet_id, "k": field_key})).first()
    if row is None:
        raise NotFound("return_field")
    if row.derivation == "engine":
        raise EngineFieldReadOnly(facts={"field": field_key})
    await tx.session.execute(
        text(
            "UPDATE return_fields SET current_value = CAST(:v AS jsonb), "
            "updated_at = clock_timestamp() WHERE id = :f"
        ),
        {"v": json.dumps(dict(value)), "f": row.id},
    )
    sheet = await _rehash(tx, worksheet_id, row.section_id)
    return row.id, row.section_id, row.engagement_id, sheet


async def apply_field_edit(
    tx: UnitOfWork, ctx: AuthContext, worksheet_id: UUID, field_key: str, value: dict[str, object]
) -> str | None:
    """A person's edit through the generic field route (which authorised `field.edit` and
    records the version and the checkpoint): the owner authorises its own write on the return."""
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_FIELD, {"w": worksheet_id, "k": field_key})).first()
    if found is None:
        raise NotFound("return_field")
    ref = await lock_ref(tx, found.engagement_id)
    await authorise(ctx, "field.edit", ref.resource())
    field_id, section_id, engagement_id, sheet = await write_field(
        tx, worksheet_id, field_key, value
    )
    # T-04-T16: the derived lines in code, in this unit of work, then every section's hash.
    if await recompute_after_edit(tx, engagement_id, worksheet_id):
        sheet = await _rehash_all(tx, worksheet_id)
    tx.record(
        "return_field.edited",
        target=Target("return_worksheet", worksheet_id),
        after=Ref(field=field_id, section=section_id),
        scope=Scope(engagement_id=engagement_id, work_item_id=found.tax_return_id),
    )
    return sheet


def label_of(field_key: str) -> str:
    """The tray's label when no row is at hand: the key's last segment, readable."""
    return field_key.rsplit(".", 1)[-1].replace("_", " ").capitalize()


# --- suggestion targets and proposal adapters ----------------------------------------------------


async def _engagement_of(table: str, tenant: TenantContext, row_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(f"SELECT engagement_id FROM {table} WHERE id = :i"),  # noqa: S608 -- a fixed table of this module
            {"i": row_id},
        )
    return cast(UUID | None, found)


async def field_engagement(tenant: TenantContext, field_id: UUID) -> UUID | None:
    return await _engagement_of("return_fields", tenant, field_id)


async def worksheet_engagement(tenant: TenantContext, worksheet_id: UUID) -> UUID | None:
    """T-04-T19: `tax.propose_field_changes` rows name the worksheet and the field key, as
    `apply_field_proposal` reads them."""
    return await _engagement_of("return_worksheets", tenant, worksheet_id)


async def k1_engagement(tenant: TenantContext, treatment_id: UUID) -> UUID | None:
    return await _engagement_of("k1_treatments", tenant, treatment_id)


async def residency_engagement(tenant: TenantContext, determination_id: UUID) -> UUID | None:
    return await _engagement_of("residency_determinations", tenant, determination_id)


async def apply_field_proposal(tenant: TenantContext, proposal_id: UUID) -> None:
    """An approved `return_field_changes` proposal: each row's value, as the adopted suggestion,
    through `record_value` (recompute of derived lines is T-04-T16's applier)."""
    async with tenant_session(tenant) as session:
        found = await approved_proposal_rows(session, proposal_id)
    if found is None:
        return
    engagement_id, rows = found
    async with uow(TenantContext(tenant.tenant_id, "system", f"proposal:{proposal_id}")) as tx:
        for row in rows:
            ref = row.field_ref
            if ref.get("target_type") != WORKSHEET or row.after is None:
                continue
            worksheet = UUID(str(ref["target_id"]))
            key = str(ref["field_key"])
            await write_field(tx, worksheet, key, row.after)
            await record_value(
                tx,
                engagement_id=engagement_id,
                target_type=WORKSHEET,
                target_id=worksheet,
                field_key=key,
                value=row.after,
                value_source="agent_suggested",
                cause="suggestion_adopted",
                suggestion_id=row.suggestion_id,
                citation_ids=list(row.citation_ids or []),
            )
        tx.record(
            "return_field.proposal_applied",
            target=Target("proposal", proposal_id),
            after=Ref(rows=len(rows)),
        )


async def _apply_status(table: str, tenant: TenantContext, proposal_id: UUID) -> None:
    """An approved K-1 treatment or residency proposal: its rows name the record and the option;
    the record moves to `proposed_approved` for the person's own confirm (never confirmed here)."""
    async with tenant_session(tenant) as session:
        found = await approved_proposal_rows(session, proposal_id)
    if found is None:
        return
    _, rows = found
    async with uow(TenantContext(tenant.tenant_id, "system", f"proposal:{proposal_id}")) as tx:
        for row in rows:
            target = row.field_ref.get("target_id")
            if target is None:
                continue
            await tx.session.execute(
                text(f"UPDATE {table} SET proposal_id = :p, updated_at = clock_timestamp(), "  # noqa: S608 -- a fixed table of this module
                     "version_no = version_no + 1 WHERE id = :i"),
                {"p": proposal_id, "i": UUID(str(target))},
            )  # fmt: skip
        tx.record(
            "tax_proposal.linked",
            target=Target("proposal", proposal_id),
            after=Ref(rows=len(rows)),
        )


async def apply_k1_proposal(tenant: TenantContext, proposal_id: UUID) -> None:
    await _apply_status("k1_treatments", tenant, proposal_id)


async def apply_residency_proposal(tenant: TenantContext, proposal_id: UUID) -> None:
    await _apply_status("residency_determinations", tenant, proposal_id)


def register() -> None:
    """At the tax api's import (P-39)."""
    register_reviewable(WORKSHEET, worksheet_reviewables)
    register_reviewable(SECTION, section_reviewables)
    register_reviewable_facts(WORKSHEET, worksheet_facts)
    register_reviewable_facts(SECTION, section_facts)
    register_field_owner(
        FieldOwner(
            WORKSHEET,
            field_value,
            ALL_FIELDS_TRI,
            label_of=label_of,
            apply_edit=apply_field_edit,
            checkpoints=True,
        )
    )
    register_suggestion_target("return_field", engagement_of=field_engagement)
    register_suggestion_target(WORKSHEET, engagement_of=worksheet_engagement)
    register_suggestion_target("pass_through_treatment", engagement_of=k1_engagement)
    register_suggestion_target("residency_determination", engagement_of=residency_engagement)
    register_proposal_adapter("return_field_changes", apply_field_proposal)
    register_proposal_adapter("pass_through_treatments", apply_k1_proposal)
    register_proposal_adapter("residency", apply_residency_proposal)
