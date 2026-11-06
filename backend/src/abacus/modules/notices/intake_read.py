"""What `NoticeIntakeWorkflow` does (N-04-T07; N-04 US-2.2, US-2.3; DEC-2326).

Code reads a mapped notice's fields from P-11's form extraction; nothing is guessed, and a value
below 0.90 stays `low_confidence` for a person. With no map the responder proposes over masked text
(N-04-T19), each value naming its run for a person to confirm; with the responder off, refused or
empty, and on a refusal by the OCR gate, manual entry opens with the reason in words. The client is
matched by the taxpayer's last four and, where the map reads a name, the name (`name_tin`, else
`tin`): one candidate is matched, several are the person's pick, none is the client picker. The
return is matched on entity, year and (when read) form; the authorization comes from CLI-05's
register; a notice with the same entity, code and date, or the same file bytes, is a possible
duplicate. A person still decides all of it at Create notice.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch, signal_workflow
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, uow
from abacus.modules.evidence.api import (
    EvidenceTextReady,
    OcrRunRefused,
    ReadField,
    engagement_of_version,
    extract_version,
    extracted_fields_of,
    masked_pages,
    ocr_refusal_of,
    versions_with_same_bytes,
)
from abacus.modules.notices.events import NoticeIntakeReady, NoticeIntakeStarted
from abacus.modules.notices.intake import FIELD_KINDS
from abacus.modules.notices.intake_workflow import NoticeIntakeWorkflow
from abacus.modules.notices.intake_workflow_types import NoticeIntakeInput
from abacus.modules.organisations.api import entities_with_tin_last4

# P-11's form-map keys (`evidence/forms/*/*.yaml`) in the notice's field keys.
_FROM_MAP: Final[dict[str, str]] = {
    "notice.number": "notice.code",
    "notice.tax_year": "notice.tax_year",
    "notice.date": "notice.date",
    "notice.respond_by": "notice.respond_by",
    "notice.amount_due": "notice.amount_total",
    "notice.tax_due": "notice.amount_tax",
    "notice.proposed_tax": "notice.amount_tax",
    "notice.penalties": "notice.amount_penalty",
    "notice.interest": "notice.amount_interest",
    "notice.taxpayer_last4": "taxpayer.tin",
    "notice.taxpayer_name": "taxpayer.name",
}
_VALUE_TYPE: Final[dict[str, str]] = {
    "notice.code": "code",
    "notice.tax_year": "int",
    "notice.date": "date",
    "notice.respond_by": "date",
    "notice.amount_total": "money",
    "notice.amount_tax": "money",
    "notice.amount_penalty": "money",
    "notice.amount_interest": "money",
    "taxpayer.tin": "tin",
    "taxpayer.name": "text",
}
_AGENT_KEYS: Final = tuple(k for k, kind in FIELD_KINDS.items() if kind != "tin")
_LOW_CONFIDENCE: Final = 0.90
NO_MAP: Final = "no_map"
NO_FILE: Final = "no_file"


def workflow_id(tenant_id: UUID, intake_id: UUID) -> str:
    return f"notice_intake:{tenant_id}:{intake_id}"


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "notices:intake")


class _Moved(Exception):
    """The intake left `extracting` under the read: leave it as a person has it."""


@dataclass(frozen=True)
class ClientMatch:
    client_entity_id: UUID | None
    method: str | None
    candidates: tuple[UUID, ...]


def match_client(last4: str | None, name: str | None, on_file: Mapping[UUID, str]) -> ClientMatch:
    """`on_file`: the entities with these last four. A name narrows them, never widens: one left
    is matched, several are the person's pick, none (or no last four) is the client picker."""
    if last4 is None or not on_file:
        return ClientMatch(None, None, ())
    if name is not None:
        wanted = name.casefold().strip()
        named = sorted(e for e, found in on_file.items() if found.casefold().strip() == wanted)
        if len(named) == 1:
            return ClientMatch(named[0], "name_tin", ())
    entities = tuple(sorted(on_file))
    if len(entities) == 1:
        return ClientMatch(entities[0], "tin", ())
    return ClientMatch(None, None, entities)


async def _status_and_version(
    session: AsyncSession, intake_id: UUID
) -> tuple[str, UUID | None] | None:
    row = (
        await session.execute(
            text("SELECT status, evidence_version_id FROM notice_intakes WHERE id = :id"),
            {"id": intake_id},
        )
    ).first()
    return None if row is None else (row.status, row.evidence_version_id)


async def _insert_code_value(
    session: AsyncSession, tenant_id: UUID, intake_id: UUID, key: str, field: ReadField
) -> None:
    is_tin = key == "taxpayer.tin"
    if is_tin and field.last4 is None and field.value_text is None:
        return
    last4 = (field.last4 or (field.value_text or "")[-4:]) if is_tin else None
    await session.execute(
        text(
            "INSERT INTO notice_field_values (tenant_id, owner_type, owner_id, field_key, "
            "value_type, value_text, value_sealed, last4, confidence, low_confidence, origin, "
            "extracted_field_id, recorded_actor_kind) VALUES (:t, 'intake', :id, :k, :vt, :v, "
            ":sealed, :last4, :conf, :low, 'code_map', :ef, 'system')"
        ),
        {
            "t": tenant_id,
            "id": intake_id,
            "k": key,
            "vt": _VALUE_TYPE[key],
            "v": None if is_tin else field.value_text,
            "sealed": (
                await seal(
                    tenant_id,
                    (last4 or "").encode(),
                    f"notice_field_values.value_sealed:{intake_id}:{key}",
                )
                if is_tin
                else None
            ),
            "last4": last4,
            "conf": field.confidence,
            "low": field.low_confidence,
            "ef": field.id,
        },
    )


def _facts_of(fields: tuple[ReadField, ...]) -> dict[str, ReadField]:
    return {_FROM_MAP[f.field_key]: f for f in fields if f.field_key in _FROM_MAP}


async def _return_match(
    tenant: TenantContext, entity: UUID | None, year: int | None, form: str | None
) -> UUID | None:
    if entity is None or year is None:
        return None
    from abacus.modules.tax.api import return_for_entity

    return await return_for_entity(tenant, entity, year, form)


async def authorization_of(
    tenant: TenantContext, entity: UUID | None, year: int | None
) -> dict[str, object]:
    """CLI-05's register for the entity and year: the kind, its label and its id."""
    if entity is None or year is None:
        return {"kind": "none", "label": "None · blocked"}
    from abacus.modules.tax.api import authorization_on_file

    found = await authorization_on_file(tenant, entity, year)
    if found is None:
        return {"kind": "none", "label": "None · blocked"}
    kind, label, authorization_id = found
    return {"kind": kind, "label": label, "id": str(authorization_id)}


async def duplicate_of(
    session: AsyncSession,
    tenant: TenantContext,
    entity: UUID | None,
    code: str | None,
    notice_date: date | None,
    version_id: UUID | None,
) -> UUID | None:
    """US-2.3: the same entity, code and date, or the same file's bytes, on a notice."""
    if entity is not None and code is not None and notice_date is not None:
        same = await session.scalar(
            text(
                "SELECT work_item_id FROM notices WHERE client_entity_id = :e "
                "AND notice_code = :c AND notice_date = :d "
                "ORDER BY received_on, work_item_id LIMIT 1"
            ),
            {"e": entity, "c": code[:20], "d": notice_date},
        )
        if same is not None:
            return same
    if version_id is None:
        return None
    versions = await versions_with_same_bytes(tenant, version_id)
    if not versions:
        return None
    return await session.scalar(
        text(
            "SELECT work_item_id FROM notices WHERE source_evidence_version_id = ANY(:vs) "
            "ORDER BY received_on, work_item_id LIMIT 1"
        ),
        {"vs": list(versions)},
    )


def iso_date(value: str | None) -> date | None:
    try:
        return None if value is None else date.fromisoformat(value)
    except ValueError:
        return None


def year_of(value: str | None) -> int | None:
    return int(value) if value is not None and value.isdecimal() else None


async def read_intake(tenant_id: UUID, intake_id: UUID, refusal: str | None) -> str:
    """Idempotent: an intake past `extracting` is left as a person may already have it."""
    tenant = _system(tenant_id)
    async with tenant_session(tenant) as session:
        state = await _status_and_version(session, intake_id)
    if state is None or state[0] != "extracting":
        return "gone" if state is None else state[0]
    version = state[1]
    if version is None:
        return await _manual(tenant, intake_id, NO_FILE)
    if refusal is not None:
        return await _manual(tenant, intake_id, refusal)
    await extract_version(tenant_id, version)
    fields = await extracted_fields_of(tenant, version)
    facts = _facts_of(fields)
    if not facts:
        return await _proposed(tenant, intake_id, version) or await _manual(
            tenant, intake_id, NO_MAP
        )
    tin = facts.get("taxpayer.tin")
    last4 = (tin.last4 or (tin.value_text or "")[-4:] or None) if tin else None
    name = facts["taxpayer.name"].value_text if "taxpayer.name" in facts else None
    code = facts["notice.code"].value_text if "notice.code" in facts else None
    year = year_of(facts["notice.tax_year"].value_text) if "notice.tax_year" in facts else None
    on = iso_date(facts["notice.date"].value_text) if "notice.date" in facts else None
    found = await entities_with_tin_last4(tenant, last4) if last4 else {}
    client = match_client(last4, name, found)
    return_id = await _return_match(tenant, client.client_entity_id, year, None)
    authorization = await authorization_of(tenant, client.client_entity_id, year)
    client_id = None
    if client.client_entity_id is not None:
        from abacus.modules.organisations.api import client_of_entity

        client_id = await client_of_entity(tenant, client.client_entity_id)
    try:
        return await _store(
            tenant, intake_id, version, facts, fields, client, client_id, return_id,
            authorization, code, on,
        )  # fmt: skip
    except _Moved:
        async with tenant_session(tenant) as session:
            now = await _status_and_version(session, intake_id)
        return "gone" if now is None else now[0]


async def _proposed(tenant: TenantContext, intake_id: UUID, version: UUID) -> str | None:
    """A form code has no map for: the responder's reading of the masked text, as a proposal. None
    leaves the intake for manual entry."""
    from abacus.ai_gateway.context import DataSubject
    from abacus.modules.agents.api import extract_notice_fields

    pages = await masked_pages(tenant, evidence_version_id=version)
    engagement = await engagement_of_version(tenant, version)
    async with tenant_session(tenant) as session:
        initiator = await session.scalar(
            text("SELECT created_by FROM notice_intakes WHERE id = :id"), {"id": intake_id}
        )
    if not pages or engagement is None or initiator is None:
        return None
    found = await extract_notice_fields(
        tenant,
        engagement_id=engagement,
        initiator=initiator,
        keys=_AGENT_KEYS,
        lines=[(f"p{page}", body) for page, body in sorted(pages.items())],
        # No entity until the client is matched: the §7216 gate then refuses (fail closed).
        subjects=(DataSubject(None, None),),
    )
    kept = [] if found is None else [f for f in found.output.fields if f.field_key in FIELD_KINDS]
    if found is None or not kept:
        return None
    tenant_id = tenant.tenant_id
    try:
        async with uow(tenant) as tx:
            again = await _status_and_version(tx.session, intake_id)
            if again is None or again[0] != "extracting":
                raise _Moved
            for field in kept:
                await tx.session.execute(
                    text(
                        "INSERT INTO notice_field_values (tenant_id, owner_type, owner_id, "
                        "field_key, value_type, value_text, confidence, low_confidence, origin, "
                        "agent_run_id, recorded_actor_kind) VALUES (:t, 'intake', :id, :k, :vt, "
                        ":v, :conf, :low, 'agent', :run, 'agent')"
                    ),
                    {
                        "t": tenant_id,
                        "id": intake_id,
                        "k": field.field_key,
                        "vt": FIELD_KINDS[field.field_key],
                        "v": field.value,
                        "conf": round(field.confidence, 3),
                        "low": field.confidence < _LOW_CONFIDENCE,
                        "run": found.run_id,
                    },
                )
            await tx.session.execute(
                text(
                    "UPDATE notice_intakes SET status = 'ready', extraction_mode = 'agent', "
                    "row_version = row_version + 1 WHERE id = :id"
                ),
                {"id": intake_id},
            )
            tx.emit(NoticeIntakeReady(intake_id=intake_id, owner_id=initiator))
            tx.record(
                "notice_intake.extracted",
                target=Target("notice_intake", intake_id),
                after=Ref(fields=len(kept)),
            )
    except _Moved:
        return "gone"
    return "ready"


async def _store(
    tenant: TenantContext,
    intake_id: UUID,
    version: UUID,
    facts: Mapping[str, ReadField],
    fields: tuple[ReadField, ...],
    client: ClientMatch,
    client_id: UUID | None,
    return_id: UUID | None,
    authorization_facts: Mapping[str, object],
    code: str | None,
    on: date | None,
) -> str:
    tenant_id = tenant.tenant_id
    async with uow(tenant) as tx:
        again = await _status_and_version(tx.session, intake_id)
        if again is None or again[0] != "extracting":
            raise _Moved
        for key, field in sorted(facts.items()):
            await _insert_code_value(tx.session, tenant_id, intake_id, key, field)
        owner = await tx.session.scalar(
            text(
                "UPDATE notice_intakes SET status = 'ready', extraction_mode = 'code_map', "
                "client_id = :client, match = CAST(:match AS jsonb), "
                "authorization_facts = CAST(:facts AS jsonb), duplicate_of_work_item_id = :dup, "
                "row_version = row_version + 1 WHERE id = :id RETURNING created_by"
            ),
            {
                "client": client_id,
                "match": json.dumps(
                    {
                        "client_entity_id": _text(client.client_entity_id),
                        "method": client.method,
                        "candidates": [str(c) for c in client.candidates],
                        "return_id": _text(return_id),
                    }
                ),
                "facts": json.dumps(authorization_facts),
                "dup": await duplicate_of(
                    tx.session, tenant, client.client_entity_id, code, on, version
                ),
                "id": intake_id,
            },
        )
        tx.emit(NoticeIntakeReady(intake_id=intake_id, owner_id=owner))
        tx.record(
            "notice_intake.extracted",
            target=Target("notice_intake", intake_id),
            after=Ref(fields=len(facts), low_confidence=sum(f.low_confidence for f in fields)),
        )
    return "ready"


def _text(value: UUID | None) -> str | None:
    return None if value is None else str(value)


async def _manual(tenant: TenantContext, intake_id: UUID, reason: str) -> str:
    try:
        async with uow(tenant) as tx:
            owner = await tx.session.scalar(
                text(
                    "UPDATE notice_intakes SET status = 'manual_entry', "
                    "extraction_mode = 'manual', match = match || CAST(:match AS jsonb), "
                    "row_version = row_version + 1 "
                    "WHERE id = :id AND status = 'extracting' RETURNING created_by"
                ),
                {"match": json.dumps({"manual_reason_code": reason}), "id": intake_id},
            )
            if owner is None:
                raise _Moved
            tx.emit(NoticeIntakeReady(intake_id=intake_id, owner_id=owner))
            tx.record("notice_intake.extracted", target=Target("notice_intake", intake_id))
    except _Moved:
        return "gone"
    return "manual_entry"


async def read_if_ready(tenant_id: UUID, intake_id: UUID) -> str:
    """The workflow's first question: a file read before the intake existed publishes no more
    events, so read what is already there; otherwise wait for the signal."""
    tenant = _system(tenant_id)
    async with tenant_session(tenant) as session:
        state = await _status_and_version(session, intake_id)
    if state is None or state[0] != "extracting":
        return "gone" if state is None else state[0]
    if state[1] is None:
        return await _manual(tenant, intake_id, NO_FILE)
    refusal = await ocr_refusal_of(tenant, state[1])
    if refusal is not None:
        return await _manual(tenant, intake_id, refusal)
    if await extract_version(tenant_id, state[1]) > 0:
        return await read_intake(tenant_id, intake_id, None)
    return "extracting"


async def mark_failed(tenant_id: UUID, intake_id: UUID) -> str:
    """Ten minutes without text: "Couldn't read this file — enter the fields"."""
    try:
        async with uow(_system(tenant_id)) as tx:
            moved = await tx.session.scalar(
                text(
                    "UPDATE notice_intakes SET status = 'failed', extraction_mode = 'manual', "
                    "row_version = row_version + 1 WHERE id = :id AND status = 'extracting' "
                    "RETURNING created_by"
                ),
                {"id": intake_id},
            )
            if moved is None:
                raise _Moved
            tx.emit(NoticeIntakeReady(intake_id=intake_id, owner_id=moved))
            tx.record("notice_intake.extracted", target=Target("notice_intake", intake_id))
    except _Moved:
        return "gone"
    return "failed"


# --- the consumers ----------------------------------------------------------------------------


async def on_intake_started(event: OutboxEvent) -> None:
    await dispatch(
        NoticeIntakeWorkflow,
        NoticeIntakeInput(str(event.tenant_id), str(event.payload["intake_id"])),
        id=workflow_id(event.tenant_id, UUID(str(event.payload["intake_id"]))),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def _waiting_on(tenant_id: UUID, version_id: UUID) -> list[UUID]:
    async with tenant_session(_system(tenant_id)) as session:
        rows = await session.scalars(
            text(
                "SELECT id FROM notice_intakes WHERE evidence_version_id = :v "
                "AND status = 'extracting'"
            ),
            {"v": version_id},
        )
        return list(rows)


async def on_text_ready(event: OutboxEvent) -> None:
    version = UUID(str(event.payload["evidence_version_id"]))
    for intake_id in await _waiting_on(event.tenant_id, version):
        await signal_workflow(workflow_id(event.tenant_id, intake_id), "text_ready")


async def on_ocr_refused(event: OutboxEvent) -> None:
    version = UUID(str(event.payload["evidence_version_id"]))
    for intake_id in await _waiting_on(event.tenant_id, version):
        await signal_workflow(
            workflow_id(event.tenant_id, intake_id), "refused", str(event.payload["reason"])
        )


SUBSCRIPTIONS: Final[dict[str, Handler]] = {
    NoticeIntakeStarted.event_type: on_intake_started,
    EvidenceTextReady.event_type: on_text_ready,
    OcrRunRefused.event_type: on_ocr_refused,
}
