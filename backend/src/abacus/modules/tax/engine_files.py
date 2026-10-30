"""The engine's diagnostics as issues, its PDFs as evidence and its e-file status report
(T-01-T26; T-01 §3.10; tax-engine-bridge §6; P-04-T30; DEC-78; DEC-1464). RED: client-system
content comes in here.

- **Diagnostics** (after T-01-T19 stored the run): each `error` becomes one `engine_diagnostic`
  issue (Action required, blocking final approval) through `review.api.record_engine_issue`,
  deduplicated on `engine:<code>:<field>` per return, so a file re-imported any number of times
  raises one issue; the diagnostic rows name it (`issue_id`). An error already reads Failed on
  the chip (`engine_sync.chip_state`). The engine's message is never the issue's title: the
  title is the code and field (client-system text stays on the row, ADR-052).
- **PDFs** (`kind=pdfs`, one file per upload, named `<engine id>_V<n>_<kind>.pdf`): scanned and
  staged, then filed as an imported evidence version (channel `import`, source `engine_import`)
  on the return: the client copy, vouchers and K-1s in Deliverables, the 8879 and state
  authorization forms in Signed authorizations. K-1s are T-02's (DEC-78): `engine_documents`
  answers a return's engine PDFs of a kind, for its package.
- **E-file status report** (`kind=acks`): one `engine_acks` row per jurisdiction, pending for the
  e-file record (T-02); a rejection announces `engine_ack.rejected` (C16 `ack_rejected`).

Every file belongs to the return's engine return (409 `engine_return_mismatch` otherwise).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Annotated, ClassVar, Final
from uuid import UUID

from pydantic import Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.evidence.api import file_engine_copy, screen_and_stage
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import record_engine_issue
from abacus.modules.tax import engine_repository as repo
from abacus.modules.tax.engine_adapter import (
    AcksFile,
    EngineFileInvalid,
    EnginePdf,
    parse_acks,
    parse_pdf,
)

TARGET: Final = "tax_return"
FOLDERS: Final = {
    "client_copy": "deliverables",
    "form_8879": "signed_authorizations",
    "tr_579_it": "signed_authorizations",
    "voucher_1040es_q4": "deliverables",
    "voucher_it2105_q4": "deliverables",
    "k1": "deliverables",
}
TITLES: Final = {
    "client_copy": "Client copy",
    "form_8879": "Form 8879",
    "tr_579_it": "NY TR-579-IT",
    "voucher_1040es_q4": "Form 1040-ES voucher",
    "voucher_it2105_q4": "IT-2105 voucher",
    "k1": "Schedule K-1",
}


class AckRejected(DomainEvent):
    """The engine's e-file status report carries a rejection (identifiers and codes only)."""

    event_type: ClassVar[str] = "engine_ack.rejected"

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    jurisdiction: Annotated[str, classified("internal")]
    by_user: Annotated[UUID | None, classified("internal")] = None
    recipient_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


def _pdf(file: tuple[str, bytes]) -> EnginePdf:
    return parse_pdf(*file)


async def _parsed[A, T](parser: Callable[[A], T], given: A) -> T:
    """Parse in the isolated child (the file is hostile); a bad file is 422 with its reason."""
    from abacus.modules.tax.engine_import import EngineFileRefused

    try:
        return await asyncio.to_thread(run_isolated, parser, given)
    except EngineFileInvalid as bad:
        raise EngineFileRefused(facts={"reason": bad.code}) from None
    except IsolationFailed:
        raise EngineFileRefused(facts={"reason": "unreadable"}) from None


async def _client_of(ctx: AuthContext, return_id: UUID) -> UUID:
    for item in await work_item_facts(ctx, TARGET):
        if item.work_item_id == return_id:
            return item.client_id
    raise NotFound(TARGET)


async def import_other(
    ctx: AuthContext,
    return_id: UUID,
    engagement_id: UUID,
    kind: str,
    file_name: str,
    content: bytes,
) -> UUID:
    """A PDF or an e-file status report; answers the sync event's id. The caller authorised
    `engine_import.create` on the return."""
    from abacus.modules.tax.engine_import import EngineReturnMismatch

    pdf: EnginePdf | None = None
    acks: AcksFile | None = None
    if kind == "pdfs":
        pdf = await _parsed(_pdf, (file_name, content))
        engine_id = pdf.engine_return_id
    else:
        acks = await _parsed(parse_acks, content)
        engine_id = acks.engine_return_id
    screened = await screen_and_stage(ctx.tenant_id, content, file_name, None)
    client_id = await _client_of(ctx, return_id)
    async with uow(ctx.tenant) as tx:
        link = await repo.link_of(tx.session, return_id)
        if link is not None and link.engine_return_id != engine_id:
            raise EngineReturnMismatch(facts={"work_item_id": str(return_id)})
        file = {
            "file_name": screened.file_name,
            "file_key": screened.stored.key,
            "file_version": screened.stored.version_id,
            "file_size": screened.stored.size,
            "payload_sha256": screened.sha256,
        }
        base = {
            "tenant_id": ctx.tenant_id,
            "return_id": return_id,
            "engine_return_id": engine_id,
            "actor_user_id": ctx.user_id,
        }
        if pdf is not None:
            version_id = await file_engine_copy(
                tx,
                tenant_id=ctx.tenant_id,
                client_id=client_id,
                engagement_id=engagement_id,
                work_item_id=return_id,
                folder_kind=FOLDERS[pdf.kind],
                title=f"{TITLES[pdf.kind]} · {engine_id}:V{pdf.version}",
                stored_key=screened.stored.key,
                stored_version_id=screened.stored.version_id,
                sha256=screened.sha256,
                size_bytes=screened.stored.size,
                actor_id=str(ctx.user_id),
            )
            event_id = await repo.insert_event(
                tx.session,
                {
                    **base,
                    **file,
                    "kind": "pdfs",
                    "version": pdf.version,
                    "summary": {"pdf_kind": pdf.kind, "evidence_version_id": str(version_id)},
                },
            )
            tx.record(
                "engine_sync.pdf_filed",
                target=Target(TARGET, return_id),
                after=Ref(event=event_id, evidence_version=version_id),
            )
            return event_id
        if acks is None:  # unreachable: a kind is a PDF or a status report
            raise NotFound(TARGET)
        rejected = [a for a in acks.acks if a.status == "rejected"]
        event_id = await repo.insert_event(
            tx.session,
            {
                **base,
                **file,
                "kind": "acks",
                "summary": {
                    "accepted": len(acks.acks) - len(rejected),
                    "rejected": len(rejected),
                },
            },
        )
        await tx.session.execute(
            text(
                "INSERT INTO engine_acks (tenant_id, return_id, sync_event_id, jurisdiction, "
                "submission_last4, status, status_at, reject_code, reject_text) VALUES (:t, :r, "
                ":e, :j, :l, :s, :at, :rc, :rt)"
            ),
            [
                {
                    "t": ctx.tenant_id,
                    "r": return_id,
                    "e": event_id,
                    "j": a.jurisdiction,
                    "l": a.submission_last4,
                    "s": a.status,
                    "at": a.status_at,
                    "rc": a.reject_code,
                    "rt": a.reject_text,
                }
                for a in acks.acks
            ],
        )
        tx.record(
            "engine_sync.acks_received",
            target=Target(TARGET, return_id),
            after=Ref(event=event_id, rejected=len(rejected), rows=len(acks.acks)),
        )
        for a in rejected:
            tx.emit(
                AckRejected(
                    work_item_id=return_id,
                    engagement_id=engagement_id,
                    jurisdiction=a.jurisdiction,
                    recipient_user_ids=[ctx.user_id],
                )
            )
        return event_id


async def diagnostic_issues(ctx: AuthContext, return_id: UUID, sync_event_id: UUID) -> int:
    """One issue per error code and field, raised once per return however often the file comes
    back; the run's rows name their issue. Answers how many errors named an issue."""
    async with tenant_session(ctx.tenant) as session:
        rows = list(await repo.diagnostics_of(session, sync_event_id))
    named = 0
    for d in rows:
        if d.severity != "error":
            continue
        field = d.field_key or ""
        issue_id = await record_engine_issue(
            ctx,
            record_type=TARGET,
            record_id=return_id,
            work_item_id=return_id,
            source_ref=f"engine:{d.code}:{field}",
            title=f"Engine diagnostic {d.code}" + (f" · {field}" if field else ""),
        )
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                text(
                    "UPDATE engine_diagnostics SET issue_id = :i WHERE sync_event_id = :e "
                    "AND code = :c AND coalesce(field_key, '') = :f AND issue_id IS NULL"
                ),
                {"i": issue_id, "e": sync_event_id, "c": d.code, "f": field},
            )
            tx.record(
                "engine.diagnostic_received",
                target=Target(TARGET, return_id),
                after=Ref(event=sync_event_id, issue=issue_id),
            )
        named += 1
    return named


async def engine_documents(tenant: TenantContext, return_id: UUID, kind: str) -> list[UUID]:
    """The evidence versions of a return's engine PDFs of `kind`, newest first (T-02's K-1
    package reads `k1`). For a caller that authorised a read of the return."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT summary ->> 'evidence_version_id' FROM engine_sync_events "
                    "WHERE return_id = :r AND kind = 'pdfs' AND summary ->> 'pdf_kind' = :k "
                    "ORDER BY at DESC"
                ),
                {"r": return_id, "k": kind},
            )
        ).scalars()
        return [UUID(str(v)) for v in rows if v]


__all__ = ["AckRejected", "diagnostic_issues", "engine_documents", "import_other"]
