"""AttachmentTriage's classify-and-flag step (N-01-T17; N-01 §3.4, §4.4 step 5; DEC-1177).

`communications.attachment_classified` runs after evidence's upload steps (the word layer and the
PII scan are in place): evidence classifies the attachment by rule and records it
(`document_classifications`), then code flags it from what it and the other modules know, as one
new run (`run_no` one past the last) of `inbox_attachment_flags`. The attachment points at its
classification. An attachment of an unmatched thread is classified, but the client-scoped checks
(duplicate of a filed version, wrong year, TIN, replacement) wait for a client: a later run
(after Match client) adds them.

Destination candidates come from the matcher (N-01-T22): a classified attachment of a known client
emits `inbox_attachment.matchable`, which starts its intake mode. Until it proposes there are none
and `ambiguous_candidates` never fires.
"""

from __future__ import annotations

import json
from typing import Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.communications.events import InboxAttachmentMatchable
from abacus.modules.communications.triage_flags import (
    CHECKER_VERSION,
    FlagFacts,
    code_flags,
)
from abacus.modules.communications.triage_workflow import TriageInput
from abacus.modules.engagements.api import client_tax_years
from abacus.modules.evidence.api import (
    classifier_rules,
    classify_intake,
    filed_classification_match,
    version_with_fingerprint,
)
from abacus.modules.organisations.api import entity_tin_last4s

_ACTOR: Final = "communications.attachment_triage"
_ATTACHMENT = text(
    "SELECT a.id, a.file_name, a.media_type, a.fingerprint, a.client_id, a.created_at, "
    "t.client_entity_id FROM inbox_attachments a JOIN inbox_threads t ON t.id = a.thread_id "
    "WHERE a.id = :id AND a.status <> 'withdrawn'"
)
# The same client's earlier copy only: a flag never names another client's attachment (INV-3).
_EARLIER_COPY = text(
    "SELECT id FROM inbox_attachments WHERE fingerprint = :fp AND id <> :id "
    "AND created_at <= :at AND client_id = :client ORDER BY created_at, id LIMIT 1"
)


@activity.defn(name="communications.attachment_classified")
async def attachment_classified(given: TriageInput) -> int:
    """Classify and flag one attachment; returns the number of flags raised (0 when gone)."""
    tenant = TenantContext(UUID(given.tenant_id), "system", _ACTOR)
    attachment_id = UUID(given.attachment_id)
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ATTACHMENT, {"id": attachment_id})).one_or_none()
        if row is None:
            return 0
        earlier = (
            await session.scalar(
                _EARLIER_COPY,
                {
                    "fp": row.fingerprint,
                    "id": attachment_id,
                    "at": row.created_at,
                    "client": row.client_id,
                },
            )
            if row.client_id is not None
            else None
        )
    classified = await classify_intake(
        tenant, attachment_id, file_name=row.file_name, media_type=row.media_type
    )
    found = classified.classification
    duplicate_version = replacement = None
    expected: frozenset[int] = frozenset()
    last4s: frozenset[str] = frozenset()
    if row.client_id is not None:
        duplicate_version = await version_with_fingerprint(tenant, row.client_id, row.fingerprint)
        expected = await client_tax_years(tenant, row.client_id)
        last4s = await entity_tin_last4s(tenant, row.client_id, row.client_entity_id)
        if found.tax_year is not None and found.kind == "tax_form":
            replacement = await filed_classification_match(
                tenant,
                row.client_id,
                form_family=found.form_family,
                tax_year=found.tax_year,
                issuer_name=None,
            )
            # The identical file is a duplicate, not a replacement.
            replacement = None if replacement == duplicate_version else replacement
    flags = code_flags(
        FlagFacts(
            media_type=row.media_type,
            has_text_layer=classified.has_text_layer,
            tax_year=found.tax_year,
            tin_last4=found.taxpayer_tin_last4,
            corrected=found.corrected,
            confidence=found.overall,
            low_confidence_below=classifier_rules().low_confidence_below,
            duplicate_version_id=duplicate_version,
            duplicate_attachment_id=earlier,
            expected_years=expected,
            entity_last4s=last4s,
            replacement_version_id=replacement,
        )
    )
    async with uow(tenant) as tx:
        run_no = int(
            await tx.session.scalar(
                text(
                    "SELECT coalesce(max(run_no), 0) + 1 FROM inbox_attachment_flags "
                    "WHERE attachment_id = :id"
                ),
                {"id": attachment_id},
            )
            or 1
        )
        for flag in flags:
            await tx.session.execute(
                text(
                    "INSERT INTO inbox_attachment_flags (tenant_id, attachment_id, run_no, kind, "
                    "severity, ref_evidence_version_id, facts, checker_version) VALUES (:tenant, "
                    ":attachment, :run, :kind, :severity, :ref, CAST(:facts AS jsonb), :checker)"
                ),
                {
                    "tenant": tenant.tenant_id,
                    "attachment": attachment_id,
                    "run": run_no,
                    "kind": flag.kind,
                    "severity": flag.severity,
                    "ref": flag.ref_evidence_version_id,
                    "facts": _json(flag.facts),
                    "checker": CHECKER_VERSION,
                },
            )
        await tx.session.execute(
            text("UPDATE inbox_attachments SET classification_id = :c WHERE id = :id"),
            {"c": classified.classification_id, "id": attachment_id},
        )
        tx.record(
            "inbox_attachment.flagged",
            target=Target("inbox_attachment", attachment_id),
            after=Ref(
                run_no=run_no, classification_id=classified.classification_id, flags=len(flags)
            ),
        )
        # N-01-T22: a classified attachment of a known client may be matched to a destination.
        if row.client_id is not None:
            tx.emit(InboxAttachmentMatchable(attachment_id=attachment_id, client_id=row.client_id))
    return len(flags)


def _json(facts: dict[str, object]) -> str:
    return json.dumps(facts, sort_keys=True, separators=(",", ":"))


ACTIVITIES: Final = (attachment_classified,)
