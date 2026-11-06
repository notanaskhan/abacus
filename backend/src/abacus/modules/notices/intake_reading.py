"""How an intake leaves `extracting` (N-04 US-2.2; N-04-T19; DEC-2334). Subscribers, as the system.

- `extracted_fields.recorded`: code read a mapped notice, so its fields are copied in with their
  confidence, and the intake is `ready` (`code_map`). The source row stays the evidence.
- `upload_checks.recorded`: the PII scan finished. A form code has no map for goes to the responder
  in `extract` mode over masked text; what comes back is a proposal a person confirms. With the
  responder off, refused or empty, the intake opens in `manual_entry`. Nothing is guessed.
- `ocr_run.refused`: the page has no words, so `manual_entry`.

A taxpayer ID isn't copied: `extracted_fields` holds its own sealed value and last four, and a
person enters it on the intake.
"""

from __future__ import annotations

from typing import Any, Final
from uuid import UUID

from sqlalchemy import text

from abacus.ai_gateway.context import DataSubject
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import OutboxEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.agents.api import extract_notice_fields
from abacus.modules.evidence.api import form_is_known, masked_pages, recorded_form_fields
from abacus.modules.notices.intake import FIELD_KINDS

# A form map's key to the intake's field (P-11's maps name what the page prints).
FROM_FORM: Final[dict[str, str]] = {
    "notice.number": "notice.code",
    "notice.tax_year": "notice.tax_year",
    "notice.date": "notice.date",
    "notice.respond_by": "notice.respond_by",
    "notice.amount_due": "notice.amount_total",
    "notice.proposed_tax": "notice.amount_tax",
    "notice.interest": "notice.amount_interest",
    "notice.penalty": "notice.amount_penalty",
}
AGENT_KEYS: Final = tuple(k for k, kind in FIELD_KINDS.items() if kind != "tin")
Row = dict[str, Any]  # Any: a result row or a recorded field


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "notices:intake_reading")


async def _extracting(tenant: TenantContext, version_id: UUID) -> list[Row]:
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, created_by, client_id FROM notice_intakes "
                        "WHERE evidence_version_id = :v AND status = 'extracting'"
                    ),
                    {"v": version_id},
                )
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


async def _insert_value(
    tx: UnitOfWork,
    tenant_id: UUID,
    intake_id: UUID,
    key: str,
    value: str,
    confidence: object,
    *,
    low_confidence: bool,
    origin: str,
    agent_run_id: UUID | None,
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO notice_field_values (tenant_id, owner_type, owner_id, field_key, "
            "value_type, value_text, confidence, low_confidence, origin, agent_run_id, "
            "recorded_actor_kind) VALUES (:t, 'intake', :id, :k, :vt, :v, :conf, :low, :origin, "
            ":run, :actor)"
        ),
        {
            "t": tenant_id,
            "id": intake_id,
            "k": key,
            "vt": FIELD_KINDS[key],
            "v": value,
            "conf": confidence,
            "low": low_confidence,
            "origin": origin,
            "run": agent_run_id,
            "actor": "agent" if origin == "agent" else "system",
        },
    )


async def _settle(tx: UnitOfWork, intake_id: UUID, status: str, mode: str, fields: int) -> None:
    await tx.session.execute(
        text(
            "UPDATE notice_intakes SET status = :s, extraction_mode = :m, "
            "row_version = row_version + 1 WHERE id = :id AND status = 'extracting'"
        ),
        {"s": status, "m": mode, "id": intake_id},
    )
    tx.record(
        "notice_intake.read",
        target=Target("notice_intake", intake_id),
        after=Ref(fields=fields),
    )


async def on_fields_recorded(event: OutboxEvent) -> None:
    tenant = _system(event.tenant_id)
    version_id = UUID(str(event.payload["evidence_version_id"]))
    intakes = await _extracting(tenant, version_id)
    if not intakes:
        return
    found = [
        f for f in await recorded_form_fields(tenant, version_id) if f["field_key"] in FROM_FORM
    ]
    for row in intakes:
        async with uow(tenant) as tx:
            for field in found:
                if field["value_text"] is None:
                    continue
                await _insert_value(
                    tx,
                    event.tenant_id,
                    row["id"],
                    FROM_FORM[field["field_key"]],
                    str(field["value_text"]),
                    field["confidence"],
                    low_confidence=bool(field["low_confidence"]),
                    origin="code_map",
                    agent_run_id=None,
                )
            await _settle(tx, row["id"], "ready", "code_map", len(found))


async def _manual(tenant: TenantContext, intake_id: UUID) -> None:
    async with uow(tenant) as tx:
        await _settle(tx, intake_id, "manual_entry", "manual", 0)


async def on_scanned(event: OutboxEvent) -> None:
    """A version's masked text exists now. A mapped form waits for its own event."""
    tenant = _system(event.tenant_id)
    version_id = UUID(str(event.payload["evidence_version_id"]))
    intakes = await _extracting(tenant, version_id)
    if not intakes or await form_is_known(tenant, version_id):
        return
    pages = await masked_pages(tenant, evidence_version_id=version_id)
    lines = [(f"p{page}", body) for page, body in sorted((pages or {}).items())]
    for row in intakes:
        proposed = (
            await extract_notice_fields(
                tenant,
                engagement_id=UUID(str(event.payload["engagement_id"])),
                initiator=row["created_by"],
                keys=AGENT_KEYS,
                lines=lines,
                # No entity until the client is matched: the §7216 gate then refuses (fail closed).
                subjects=(DataSubject(None, None),),
            )
            if lines
            else None
        )
        if proposed is None or not proposed.output.fields:
            await _manual(tenant, row["id"])
            continue
        kept = [f for f in proposed.output.fields if f.field_key in FIELD_KINDS]
        async with uow(tenant) as tx:
            for field in kept:
                await _insert_value(
                    tx,
                    event.tenant_id,
                    row["id"],
                    field.field_key,
                    field.value,
                    round(field.confidence, 3),
                    low_confidence=field.confidence < LOW_CONFIDENCE,
                    origin="agent",
                    agent_run_id=proposed.run_id,
                )
            await _settle(tx, row["id"], "ready", "agent", len(kept))


async def on_ocr_refused(event: OutboxEvent) -> None:
    tenant = _system(event.tenant_id)
    for row in await _extracting(tenant, UUID(str(event.payload["evidence_version_id"]))):
        await _manual(tenant, row["id"])


LOW_CONFIDENCE: Final = 0.90  # N-04 US-2.2: a person confirms it before Create notice

SUBSCRIPTIONS: Final = {
    "extracted_fields.recorded": on_fields_recorded,
    "upload_checks.recorded": on_scanned,
    "ocr_run.refused": on_ocr_refused,
}

__all__ = ["FROM_FORM", "SUBSCRIPTIONS", "on_fields_recorded", "on_ocr_refused", "on_scanned"]
