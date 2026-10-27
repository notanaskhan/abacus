"""The write path for field values (ADR-160 clause 10; P-04-T24's appliers, DEC-602).

`record_value` appends one `field_value_versions` row inside the caller's unit of work: the next
`seq` for the field (under a transaction lock on the field, so two writers never take the same
number), the typed value `{t, v}` (decimals as strings), its source and cause, the citations, and a
human edit's citation note sealed to its own (target, field, seq). The row's actor is the
transaction's (a CHECK binds it), the `policy` source and actor stay refused
(`fvv_policy_dormant`), and a human edit without a note is refused by `fvv_human_edits_cite`. The
provenance read, field ticks and the `FIELD-001` rule are P-04-T35's.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import transaction_context
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import UnitOfWork
from abacus.modules.review.events import FieldValueRecorded
from abacus.modules.review.sealing import seal_text

ValueSource = Literal["agent_suggested", "human", "formula", "tb_linked", "engine_import"]
Cause = Literal[
    "edit", "suggestion_adopted", "recompute", "import", "restore", "template_update", "relink"
]
VALUE_TYPES: Final = frozenset({"decimal", "text", "date", "bool"})
_TARGET: Final = re.compile(r"[a-z][a-z_]{0,39}")
_FIELD: Final = re.compile(r"[A-Za-z0-9_.!:-]{1,80}")
_NOTE_LIMIT: Final = 2000
_VALUE_LIMIT: Final = 200


class FieldValueInvalid(DomainInvalid):
    """A value, field key or citation note the field history can't take."""

    code = "field_value_invalid"


def typed_value(value: Mapping[str, object]) -> dict[str, object]:
    """`{t, v}` checked: `t` one of the four types, `v` a string (a decimal string for
    `decimal`), a bool for `bool`, or null (an empty cell)."""
    kind, raw = value.get("t"), value.get("v")
    if kind not in VALUE_TYPES or set(value) - {"t", "v"}:
        raise FieldValueInvalid(facts={"field": "value"})
    if raw is None:
        return {"t": kind, "v": None}
    if kind == "bool":
        if not isinstance(raw, bool):
            raise FieldValueInvalid(facts={"field": "value"})
        return {"t": kind, "v": raw}
    if not isinstance(raw, str) or len(raw) > _VALUE_LIMIT:
        raise FieldValueInvalid(facts={"field": "value"})
    if kind == "decimal":
        try:
            number = Decimal(raw)
        except InvalidOperation:
            raise FieldValueInvalid(facts={"field": "value"}) from None
        if not number.is_finite():
            raise FieldValueInvalid(facts={"field": "value"})
    return {"t": kind, "v": raw}


async def record_value(
    tx: UnitOfWork,
    *,
    engagement_id: UUID | None,
    target_type: str,
    target_id: UUID,
    field_key: str,
    value: Mapping[str, object],
    value_source: ValueSource,
    cause: Cause,
    value_kind: Literal["exact", "estimate"] = "exact",
    on_behalf_of_user_id: UUID | None = None,
    suggestion_id: UUID | None = None,
    checkpoint_id: UUID | None = None,
    citation_ids: Sequence[UUID] = (),
    citation_note: str | None = None,
    issue_id: UUID | None = None,
) -> int:
    """`review.api.record_value`: the field's next version, in the caller's unit of work, by the
    transaction's actor. Returns its `seq`. The caller has authorised the write on its own
    target; the owner's applier is the only caller (ADR-161 clause 1)."""
    if not _TARGET.fullmatch(target_type) or not _FIELD.fullmatch(field_key):
        raise FieldValueInvalid(facts={"field": "field_key"})
    checked = typed_value(value)
    note = (citation_note or "").strip()
    if value_source == "human" and not note:
        raise FieldValueInvalid(facts={"field": "citation_note"})
    if len(note) > _NOTE_LIMIT:
        raise FieldValueInvalid(facts={"field": "citation_note"})
    session = tx.session
    tenant = await transaction_context(session)  # the tenant row-level security enforces
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": f"fvv:{target_type}:{target_id}:{field_key}"},
    )
    seq = int(
        (
            await session.execute(
                text(
                    "SELECT coalesce(max(seq), 0) + 1 FROM field_value_versions "
                    "WHERE target_type = :t AND target_id = :i AND field_key = :f"
                ),
                {"t": target_type, "i": target_id, "f": field_key},
            )
        ).scalar_one()
    )
    sealed = (
        await seal_text(
            tenant, note, "field_value_version", target_type, target_id, field_key, seq
        )
        if note
        else None
    )
    await session.execute(
        text(
            "INSERT INTO field_value_versions (tenant_id, engagement_id, target_type, target_id, "
            "field_key, seq, value, value_kind, value_source, cause, on_behalf_of_user_id, "
            "suggestion_id, checkpoint_id, citation_ids, citation_note_sealed, issue_id) VALUES "
            "(:tenant, :engagement, :t, :i, :f, :seq, CAST(:value AS jsonb), :kind, :source, "
            ":cause, :obo, :suggestion, :checkpoint, CAST(:citations AS uuid[]), :note, :issue)"
        ),
        {
            "tenant": tenant.tenant_id,
            "engagement": engagement_id,
            "t": target_type,
            "i": target_id,
            "f": field_key,
            "seq": seq,
            "value": json.dumps(checked),
            "kind": value_kind,
            "source": value_source,
            "cause": cause,
            "obo": on_behalf_of_user_id,
            "suggestion": suggestion_id,
            "checkpoint": checkpoint_id,
            "citations": list(citation_ids),
            "note": sealed,
            "issue": issue_id,
        },
    )
    tx.emit(
        FieldValueRecorded(
            engagement_id=engagement_id,
            target_type=target_type,
            target_id=target_id,
            field_key=field_key,
            seq=seq,
            cause=cause,
        )
    )
    return seq
