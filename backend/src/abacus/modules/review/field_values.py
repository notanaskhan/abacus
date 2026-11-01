"""The write path for field values (ADR-160 clause 10; P-04-T24's appliers, DEC-602).

`record_value` appends one `field_value_versions` row inside the caller's unit of work: the next
`seq` for the field (under a transaction lock on the field, so two writers never take the same
number), the typed value `{t, v}` (decimals as strings), its source and cause, the citations, and a
human edit's citation note sealed to its own (target, field, seq). The row's actor is the
transaction's (a CHECK binds it), the `policy` source and actor stay refused
(`fvv_policy_dormant`), and a human edit without a note is refused by `fvv_human_edits_cite`.

P-04-T35 (DEC-1050): a field's identity for its ticks (`field_target_id`, the `field` target of a
`field_tick` sign-off) and its content hash (`field_hash`, what a tick signs); the `FIELD-001`
rule keeps every write of `field_value_versions` in this file.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.review.events import FieldValueRecorded
from abacus.modules.review.hashing import Json, content_hash
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


# P-04-T35: a field's ticks are `field_tick` sign-offs on a `field` target whose id is derived
# from the field (one id per target and key, in every firm: the row's tenant scopes it).
FIELD_TARGET: Final = "field"
_FIELD_NAMESPACE: Final = uuid.UUID("0c8f6a3e-2d6b-4f0e-9b7a-35a1d1c5e7f2")


def field_target_id(target_type: str, target_id: UUID, field_key: str) -> UUID:
    """The `field` target id a tick on this field is recorded against."""
    return uuid.uuid5(_FIELD_NAMESPACE, f"{target_type}:{target_id}:{field_key}")


def field_hash(
    target_type: str,
    target_id: UUID,
    field_key: str,
    value: Mapping[str, object] | None,
    value_kind: str,
) -> str:
    """What a tick signs (bare hex, `review.hashing`): the field and its current typed value and
    kind. A changed value is a changed hash, so an earlier tick reads stale (ADR-160 clause 3)."""
    return content_hash(
        cast(
            Json,
            {
                "target_type": target_type,
                "target_id": str(target_id),
                "field_key": field_key,
                "value": dict(value) if value is not None else None,
                "value_kind": value_kind,
            },
        )
    )


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
    found = await session.execute(
        text(
            "INSERT INTO field_value_versions (tenant_id, engagement_id, target_type, target_id, "
            "field_key, seq, value, value_kind, value_source, cause, on_behalf_of_user_id, "
            "suggestion_id, checkpoint_id, citation_ids, citation_note_sealed, issue_id) VALUES "
            "(:tenant, :engagement, :t, :i, :f, :seq, CAST(:value AS jsonb), :kind, :source, "
            ":cause, :obo, :suggestion, :checkpoint, CAST(:citations AS uuid[]), :note, :issue) "
            "RETURNING id"
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
    # Review low (DEC-609): every field write is its own audit event, by the transaction's actor.
    tx.record(
        "field.value_recorded",
        target=Target("field_value_version", found.scalar_one()),
        after=Ref(seq=seq, citations=len(citation_ids)),
        scope=Scope(engagement_id=engagement_id),
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


@dataclass(frozen=True)
class PreviousValue:
    """A field's latest version time and the value before it (P-04-T29's Undo)."""

    latest_at: datetime
    value: dict[str, object]
    value_kind: Literal["exact", "estimate"]


async def previous_value(
    tx: UnitOfWork, target_type: str, target_id: UUID, field_key: str
) -> PreviousValue | None:
    """The value before the field's latest version, or None when it has only one."""
    rows = (
        await tx.session.execute(
            text(
                "SELECT value, value_kind, created_at FROM field_value_versions "
                "WHERE target_type = :t AND target_id = :i AND field_key = :f "
                "ORDER BY seq DESC LIMIT 2"
            ),
            {"t": target_type, "i": target_id, "f": field_key},
        )
    ).all()
    if len(rows) < 2:
        return None
    return PreviousValue(
        rows[0].created_at,
        cast(dict[str, object], rows[1].value),
        cast(Literal["exact", "estimate"], rows[1].value_kind),
    )


# --- T-01-T19: what an engine import diffs against, and what changed after a sync ------------


async def current_values(
    tenant: TenantContext, target_type: str, target_id: UUID
) -> dict[str, dict[str, object]]:
    """Each field's latest value on the target (`{t, v}`), for an owner diffing an engine file
    against what Accrued holds. The caller has authorised a read of the target."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT DISTINCT ON (field_key) field_key, value FROM field_value_versions "
                    "WHERE target_type = :t AND target_id = :i ORDER BY field_key, seq DESC"
                ),
                {"t": target_type, "i": target_id},
            )
        ).all()
    return {str(r.field_key): cast(dict[str, object], r.value) for r in rows}


@dataclass(frozen=True)
class FieldVersionFact:
    """One version of a field, as an owner's history shows it (A-04-T13: AUD-08 b's versions)."""

    seq: int
    value: dict[str, object]
    value_source: str
    actor_kind: str
    actor_id: str
    on_behalf_of_user_id: UUID | None
    suggestion_id: UUID | None
    citation_ids: tuple[UUID, ...]
    created_at: datetime


async def field_timeline(
    tenant: TenantContext, target_type: str, target_id: UUID, field_key: str
) -> list[FieldVersionFact]:
    """A field's versions, oldest first. The caller has authorised a read of the target; the
    sealed citation note stays sealed."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT seq, value, value_source, actor_kind, actor_id, on_behalf_of_user_id, "
                    "suggestion_id, citation_ids, created_at FROM field_value_versions "
                    "WHERE target_type = :t AND target_id = :i AND field_key = :f ORDER BY seq"
                ),
                {"t": target_type, "i": target_id, "f": field_key},
            )
        ).all()
    return [
        FieldVersionFact(
            int(r.seq),
            cast(dict[str, object], r.value),
            str(r.value_source),
            str(r.actor_kind),
            str(r.actor_id),
            r.on_behalf_of_user_id,
            r.suggestion_id,
            tuple(r.citation_ids or ()),
            r.created_at,
        )
        for r in rows
    ]


async def changed_since(
    tenant: TenantContext, target_type: str, target_id: UUID, since: datetime
) -> list[str]:
    """Fields Accrued changed after `since` other than by an engine import (TAX-09c's out of sync),
    in key order."""
    async with tenant_session(tenant) as session:
        return list(
            (
                await session.execute(
                    text(
                        "SELECT DISTINCT field_key FROM field_value_versions WHERE "
                        "target_type = :t AND target_id = :i AND created_at > :since "
                        "AND value_source <> 'engine_import' ORDER BY field_key"
                    ),
                    {"t": target_type, "i": target_id, "since": since},
                )
            ).scalars()
        )
