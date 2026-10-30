"""C21 part A, the service: platform reference sets (K-02-T05; K-02 §4.3, §4.5; SPEC-500 AC-15+).

Reference sets are global (no tenant): the app reads them only through migration 0400's
SECURITY DEFINER readers, inside `platform_transaction`, and never sees a draft. Resolution on a
date is the reader's: the latest `effective_from` on or before `as_of`, ties to the highest
version, so a re-published correction wins from its own effective date and the prior set answers
before it.

The kind registry and validators here are what the operator CLI (K-02-T06) runs before it calls
`reference_set_draft`: a payload must parse as its kind's model, and a `standards_sets` draft may
hold no PCAOB or issuer set (X-07, DEC-19) and may neither drop a published code nor move one to
another family. Publishing re-checks the last two in the database (`standards_sets_apply`).

Every typed reader returns the id of the version its answer came from (INV-2). Nothing here holds
a rule's value (AGENTS 16).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Final, cast

from pydantic import BaseModel, ValidationError
from sqlalchemy import RowMapping, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncConnection

from abacus.kernel.clock import today
from abacus.kernel.db import platform_transaction
from abacus.kernel.errors import DomainInvalid
from abacus.modules.platform.reference_sets_contract import (
    DisasterPostponementsPayload,
    DueDateRulesPayload,
    Form8879For,
    Form8879SetPayload,
    InformationReturnThresholdsPayload,
    LegalHolidaysPayload,
    ReferenceSetKind,
    ReferenceSetOut,
    ReferenceSetResolvedOut,
    ReferenceSetVersionOut,
    ResolvedReference,
    RetentionFloor,
    RetentionMinimumsPayload,
    StandardsSetRow,
    StandardsSetsPayload,
    ThresholdFor,
    TolerancesFor,
)

# The readers run as this platform principal: the audit of who read public law is not needed,
# but the transaction still names its actor (P-01-T05).
_ACTOR: Final = "system:reference_sets"

Payload = (
    DueDateRulesPayload
    | LegalHolidaysPayload
    | DisasterPostponementsPayload
    | Form8879SetPayload
    | InformationReturnThresholdsPayload
    | RetentionMinimumsPayload
    | StandardsSetsPayload
)

# --- the kind registry ---------------------------------------------------------------------------

KINDS: Final[Mapping[ReferenceSetKind, type[BaseModel]]] = {
    "due_date_rules": DueDateRulesPayload,
    "legal_holidays": LegalHolidaysPayload,
    "disaster_postponements": DisasterPostponementsPayload,
    "form_8879_set": Form8879SetPayload,
    "information_return_thresholds": InformationReturnThresholdsPayload,
    "retention_minimums": RetentionMinimumsPayload,
    "standards_sets": StandardsSetsPayload,
}


class ReferenceKindUnknown(DomainInvalid):
    """The kind is not one of the seven reference kinds (`state_*` kinds are Q-05's)."""

    code = "reference_kind_unknown"


class ReferencePayloadInvalid(DomainInvalid):
    """The payload does not parse as its kind's model (`facts.kind`, `facts.problems`)."""

    code = "reference_payload_invalid"


class StandardsSetRefused(DomainInvalid):
    """A `standards_sets` draft holds a PCAOB or issuer set, drops a published code or moves one
    to another family (`facts.reason`, `facts.code`; X-07)."""

    code = "standards_set_refused"


def validate_payload(kind: str, payload: Mapping[str, object]) -> Payload:
    """The payload parsed as its kind's model. The payload names its own kind, and it must be
    this one (the database checks the same on draft)."""
    model = KINDS.get(cast(ReferenceSetKind, kind))
    if model is None:
        raise ReferenceKindUnknown
    if payload.get("kind") != kind:
        raise ReferencePayloadInvalid(facts={"kind": kind, "problems": 1})
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise ReferencePayloadInvalid(
            facts={"kind": kind, "problems": error.error_count()}
        ) from None


# PCAOB auditing standards are numbered "AS 2201" (also written "AS-2201" in codes); AICPA's are
# "AU-C", "AR-C", "QM". "Issuer" stands alone in an issuer set's name, never inside "nonissuer"
# or "non-issuer".
_PCAOB: Final = re.compile(r"pcaob|\bAS[\s_-]?\d{4}\b", re.IGNORECASE)
_ISSUER_WORD: Final = re.compile(r"(?<![a-z])(?<!non)(?<!non-)(?<!non )issuers?\b", re.IGNORECASE)


def _names_pcaob_or_issuer(row: StandardsSetRow) -> bool:
    texts = (row.code, row.label, *row.standard_refs)
    return any(_PCAOB.search(t) or _ISSUER_WORD.search(t.replace("_", " ")) for t in texts)


def validate_standards_sets(
    draft: StandardsSetsPayload, published: Mapping[str, str]
) -> StandardsSetsPayload:
    """`draft`, if it holds no PCAOB or issuer set and keeps every published code (`published`
    maps each code ever published to its family) in its family. The first problem is refused."""
    for row in draft.rows:
        if _names_pcaob_or_issuer(row):
            raise StandardsSetRefused(facts={"reason": "pcaob_or_issuer", "code": row.code})
    families = {row.code: row.family for row in draft.rows}
    for code in sorted(published):
        if code not in families:
            raise StandardsSetRefused(facts={"reason": "code_removed", "code": code})
        if families[code] != published[code]:
            raise StandardsSetRefused(facts={"reason": "family_changed", "code": code})
    return draft


async def check_draft(kind: str, payload: Mapping[str, object]) -> Payload:
    """What the operator CLI runs before `reference_set_draft`: the payload valid for its kind,
    and a `standards_sets` payload checked against every code published so far."""
    parsed = validate_payload(kind, payload)
    if isinstance(parsed, StandardsSetsPayload):
        validate_standards_sets(parsed, await published_standards_codes())
    return parsed


# --- the readers (migration 0400's definer functions) --------------------------------------------

_VERSION_TYPES: Final = {"payload": JSONB, "source_citations": JSONB}


async def _resolve_row(conn: AsyncConnection, key: str, as_of: date) -> RowMapping | None:
    statement = text("SELECT * FROM reference_set_resolve(:key, :as_of)").columns(**_VERSION_TYPES)
    return (await conn.execute(statement, {"key": key, "as_of": as_of})).mappings().first()


async def _list_rows(conn: AsyncConnection, kind: str | None) -> Sequence[RowMapping]:
    statement = text("SELECT * FROM reference_set_list(:kind)")
    return (await conn.execute(statement, {"kind": kind})).mappings().all()


async def _history_rows(conn: AsyncConnection, key: str) -> Sequence[RowMapping]:
    statement = text("SELECT * FROM reference_set_history(:key)").columns(**_VERSION_TYPES)
    return (await conn.execute(statement, {"key": key})).mappings().all()


def _set_out(row: RowMapping) -> ReferenceSetOut:
    return ReferenceSetOut(
        key=row["key"],
        kind=row["kind"],
        jurisdiction=row["jurisdiction"],
        title=row["title"],
        content_owner=row["content_owner"],
        description=row["description"],
        current_version=row["current_version"],
        current_effective_from=row["current_effective_from"],
    )


def _version_out(row: RowMapping, status: str = "published") -> ReferenceSetVersionOut:
    return ReferenceSetVersionOut.model_validate(
        {
            "id": row["version_id"],
            "set_key": row["set_key"],
            "version": row["version"],
            "status": row.get("status", status),
            "tax_year": row["tax_year"],
            "effective_from": row["effective_from"],
            "payload_schema_version": row["payload_schema_version"],
            "payload_hash": row["payload_hash"],
            "source_citations": row["source_citations"] or [],
            "drafted_by": row["drafted_by"],
            "approved_by": row["approved_by"],
            "change_reason": row["change_reason"],
            "published_at": cast(datetime | None, row["published_at"]),
            "payload": row["payload"],
        }
    )


async def list_sets(kind: ReferenceSetKind | None = None) -> list[ReferenceSetOut]:
    """Every set with a published or withdrawn version, by kind then key, with the version in
    effect today (none before its first effective date)."""
    async with platform_transaction(_ACTOR) as conn:
        return [_set_out(row) for row in await _list_rows(conn, kind)]


async def resolve(key: str, as_of: date) -> ReferenceSetResolvedOut | None:
    """The set and the version in effect on `as_of`; None for an unknown key or nothing in
    effect by then."""
    async with platform_transaction(_ACTOR) as conn:
        found = await _resolve_row(conn, key, as_of)
        if found is None:
            return None
        sets = {row["key"]: row for row in await _list_rows(conn, found["kind"])}
    return ReferenceSetResolvedOut(
        set=_set_out(sets[key]), as_of=as_of, version=_version_out(found)
    )


async def versions(key: str) -> list[ReferenceSetVersionOut] | None:
    """The published and withdrawn versions, newest first; None for a key with neither."""
    async with platform_transaction(_ACTOR) as conn:
        rows = await _history_rows(conn, key)
    return [_version_out(row) for row in rows] or None


async def published_standards_codes() -> dict[str, str]:
    """Every code any `standards_sets` version has published, with its family (a withdrawn
    version cannot exist for this kind: 0400 refuses it)."""
    codes: dict[str, str] = {}
    async with platform_transaction(_ACTOR) as conn:
        for found in await _list_rows(conn, "standards_sets"):
            for row in await _history_rows(conn, found["key"]):
                payload = StandardsSetsPayload.model_validate(row["payload"])
                for standard in payload.rows:
                    codes.setdefault(standard.code, standard.family)
    return codes


# --- the C21 part A module API -------------------------------------------------------------------


def _resolved(key: str, as_of: date, row: RowMapping) -> ResolvedReference:
    kind = cast(ReferenceSetKind, row["kind"])
    return ResolvedReference(
        key=key,
        kind=kind,
        as_of=as_of,
        version_id=row["version_id"],
        version=row["version"],
        effective_from=row["effective_from"],
        payload=KINDS[kind].model_validate(row["payload"]),
        tax_year=row["tax_year"],
    )


async def references_in_effect(kind: ReferenceSetKind, as_of: date) -> list[ResolvedReference]:
    """Every set of `kind` resolved on `as_of`, latest effective first, then highest version
    (sets with nothing in effect by then are left out)."""
    found: list[ResolvedReference] = []
    async with platform_transaction(_ACTOR) as conn:
        for listed in await _list_rows(conn, kind):
            row = await _resolve_row(conn, listed["key"], as_of)
            if row is not None:
                found.append(_resolved(listed["key"], as_of, row))
    return sorted(found, key=lambda f: (f.effective_from, f.version), reverse=True)


async def reference_value(key: str, as_of: date) -> ResolvedReference:
    """The version of set `key` in effect on `as_of`. Unknown key or nothing published by then:
    `LookupError`."""
    async with platform_transaction(_ACTOR) as conn:
        row = await _resolve_row(conn, key, as_of)
    if row is None:
        raise LookupError(key)
    return _resolved(key, as_of, row)


async def form_8879_for(
    return_type: str, tax_year: int, jurisdiction: str, *, as_of: date
) -> Form8879For:
    """The 8879-family form for a return type and tax year, from the form set in effect on
    `as_of`. No set in effect lists it: `LookupError`."""
    for found in await references_in_effect("form_8879_set", as_of):
        payload = cast(Form8879SetPayload, found.payload)
        for row in payload.rows:
            if (row.return_type, row.tax_year, row.jurisdiction) == (
                return_type,
                tax_year,
                jurisdiction,
            ):
                return Form8879For(
                    return_type=row.return_type,
                    tax_year=row.tax_year,
                    jurisdiction=row.jurisdiction,
                    authorization_form=row.authorization_form,
                    revision=row.revision,
                    reference_set_version_id=found.version_id,
                )
    raise LookupError(f"form_8879_set:{return_type}:{tax_year}:{jurisdiction}")


async def pub1345_tolerances(tax_year: int, *, as_of: date) -> TolerancesFor:
    """The Pub 1345 relock tolerances for a tax year, from the form set in effect on `as_of`
    whose rows cover that year. None does: `LookupError` (never a default; DEC-85)."""
    for found in await references_in_effect("form_8879_set", as_of):
        payload = cast(Form8879SetPayload, found.payload)
        if any(row.tax_year == tax_year for row in payload.rows):
            return TolerancesFor(
                tax_year=tax_year,
                total_income_or_agi_usd=payload.tolerances.total_income_or_agi_usd,
                tax_withholding_refund_balance_usd=(
                    payload.tolerances.tax_withholding_refund_balance_usd
                ),
                reference_set_version_id=found.version_id,
            )
    raise LookupError(f"form_8879_set:tolerances:{tax_year}")


async def information_return_threshold(form: str, payment_year: int) -> ThresholdFor:
    """The 1099-family reporting threshold for a payment year, from the sets in effect today."""
    for found in await references_in_effect("information_return_thresholds", await today()):
        payload = cast(InformationReturnThresholdsPayload, found.payload)
        for row in payload.rows:
            if (row.form, row.payment_year) == (form, payment_year):
                return ThresholdFor(
                    form=row.form,
                    payment_year=row.payment_year,
                    threshold_usd=row.threshold_usd,
                    min_transactions=row.min_transactions,
                    reference_set_version_id=found.version_id,
                )
    raise LookupError(f"information_return_thresholds:{form}:{payment_year}")


async def retention_minimum(record_type: str, service_line: str) -> RetentionFloor:
    """The counsel-approved retention floor for a record type and service line, from the sets
    in effect today (never a default; DEC-71)."""
    for found in await references_in_effect("retention_minimums", await today()):
        payload = cast(RetentionMinimumsPayload, found.payload)
        for row in payload.rows:
            if (row.record_type, row.service_line) == (record_type, service_line):
                return RetentionFloor(
                    record_type=row.record_type,
                    service_line=row.service_line,
                    floor_years=row.floor_years,
                    anchor=row.anchor,
                    reference_set_version_id=found.version_id,
                )
    raise LookupError(f"retention_minimums:{record_type}:{service_line}")
