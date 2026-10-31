"""The evidence package's hardening (N-02-T38; N-02 §3.3, §3.13; I-RETENTION-FLOOR; DEC-1567). RED.

- **Retention record types.** A §7216 consent's package is kept under `consent_evidence`
  (signature plus three years at least: the published floor), every other envelope's under
  `signature_evidence` (the firm's policy, never below its floor). An e-file authorization starts
  there and is extended, never shortened, to the IRS received date plus three years when T-01
  imports the accepted acknowledgement (`extend_retention`; Pub 1345). A type with no policy and
  no floor in this firm falls back to `signature_evidence`, so a package is never left unlocked.
- **Legible reproduction.** A PDF page that states, per signer, the five IRS items for a remote
  signature (the date and time, the masked IP and login, the identity result, the method, the
  signed image's and documents' SHA-256), drawn by C11's renderer in its isolated child from
  DocBlocks (no markup; values are the stored evidence). It is stored with the package, listed in
  each signer's documents and the manifest, so Download evidence carries it. The renderer being
  unavailable never blocks completion: the page is missing and `envelope.legible_copy_failed` is
  recorded for a person to see.
- **Nightly verification.** Every stored record an envelope's evidence names (documents,
  packages, signed images) is read back and hashed against its digest. A record that is missing
  or differs records `envelope.integrity_failed` once for that envelope, logs an error and
  increments `signatures_evidence_integrity_failures`, which the alarm watches (pages N).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import PlatformSchedule
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence.api import get_record, retain_until_for
from abacus.modules.identity.api import firm_tenant_ids
from abacus.modules.reporting.api import RenderingRefused, RenderInput, render_isolated
from abacus.modules.signatures.imports import RECORD_TYPE
from abacus.modules.signatures.workflows import INTEGRITY_ID, EvidenceIntegrityWorkflow

_log = get_logger(__name__)
_failures = meter(__name__).create_counter(
    "signatures_evidence_integrity_failures",
    description="Evidence records missing or not matching their digest (N-02-T38)",
)
CONSENT_PURPOSES: Final = frozenset({"consent_7216"})
CONSENT_TYPE: Final = "consent_evidence"
INTEGRITY_FAILED: Final = "envelope.integrity_failed"
LEGIBLE_FAILED: Final = "envelope.legible_copy_failed"
_EVENT = text(
    "INSERT INTO envelope_events (tenant_id, envelope_id, signer_id, kind, source, occurred_at) "
    "VALUES (:tenant, :envelope, NULL, :kind, 'system', :at)"
)


async def retain_until(
    tenant: TenantContext, purpose: str, service_line: str, anchor_at: datetime
) -> datetime | None:
    """The package's lock: its purpose's record type, else `signature_evidence`'s."""
    if purpose in CONSENT_PURPOSES:
        found = await retain_until_for(tenant, CONSENT_TYPE, service_line, anchor_at)
        if found is not None:
            return found
    return await retain_until_for(tenant, RECORD_TYPE, service_line, anchor_at)


def _text(value: str) -> dict[str, object]:
    return {"type": "text", "text": value}


def evidence_blocks(
    title: str, signers: Sequence[dict[str, str]], documents: Sequence[str]
) -> list[object]:
    """The legible page as DocBlocks: one key-value block per signer, then the documents."""
    blocks: list[object] = [
        {"type": "heading", "level": 1, "text": "Signature evidence"},
        {"type": "paragraph", "runs": [_text(title)]},
    ]
    for n, signer in enumerate(signers, start=1):
        blocks.append({"type": "heading", "level": 2, "text": f"Signer {n}"})
        blocks.append(
            {
                "type": "kv",
                "rows": [
                    {"key": label, "value": [_text(signer.get(key) or "—")]}
                    for label, key in (
                        ("Signed at", "signed_at"),
                        ("IP address (masked)", "ip_masked"),
                        ("Login", "login_ref"),
                        ("Identity verification", "identity_result"),
                        ("Signature method", "signature_method"),
                        ("Device", "device_label"),
                        ("Signed image SHA-256", "signed_image_sha256"),
                    )
                ],
            }
        )
    blocks.append({"type": "heading", "level": 2, "text": "Documents (SHA-256)"})
    blocks.append({"type": "list", "ordered": False, "items": [[_text(d)] for d in documents]})
    return blocks


def legible_page(
    title: str, signers: Sequence[dict[str, str]], documents: Sequence[str], at: datetime
) -> bytes | None:
    """The page's PDF from the renderer's isolated child, or None when it cannot render."""
    digest = hashlib.sha256(
        "|".join([title, *documents, *(s.get("signed_at", "") for s in signers)]).encode()
    ).hexdigest()
    try:
        out = render_isolated(
            RenderInput(
                layout_key="report",
                blocks=evidence_blocks(title, signers, documents),
                values={},
                title=f"Signature evidence · {title}"[:200],
                as_of=at,
                mode="final",
                content_hash=digest,
            )
        )
    except RenderingRefused:
        _log.warning("signatures.legible_copy_refused")
        return None
    except (OSError, ImportError):  # the renderer's libraries are missing on this host
        _log.warning("signatures.legible_copy_refused", reason="renderer_unavailable")
        return None
    return out.pdf


async def record_legible_failure(tenant: TenantContext, envelope_id: UUID) -> None:
    async with uow(tenant) as tx:
        await tx.session.execute(
            _EVENT,
            {
                "tenant": tenant.tenant_id,
                "envelope": envelope_id,
                "kind": LEGIBLE_FAILED,
                "at": system_now(),
            },
        )
        tx.record(LEGIBLE_FAILED, target=Target("envelope", envelope_id), after=Ref())


# --- the nightly verification ------------------------------------------------------------------


def _digest_of(key: str) -> str:
    """A records key ends in its body's SHA-256 (`evidence.records.record_key`)."""
    return key.rsplit("/", 1)[-1]


async def verify_firm(tenant_id: UUID) -> list[UUID]:
    """Each envelope's records read back against their digests; the envelopes that failed."""
    tenant = TenantContext(tenant_id, "system", "signatures:integrity")
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT v.envelope_id, v.document_sha256s, v.package_sha256, "
                    "v.signed_image_key, EXISTS (SELECT 1 FROM envelope_events x "
                    "WHERE x.envelope_id = v.envelope_id AND x.kind = :kind) AS flagged "
                    "FROM signature_evidence v ORDER BY v.envelope_id"
                ),
                {"kind": INTEGRITY_FAILED},
            )
        ).all()
    digests: dict[UUID, set[str]] = {}
    flagged: set[UUID] = set()
    for row in rows:
        wanted = digests.setdefault(row.envelope_id, set())
        wanted.update(str(d) for d in row.document_sha256s or ())
        if row.package_sha256:
            wanted.add(str(row.package_sha256))
        if row.signed_image_key:
            wanted.add(_digest_of(str(row.signed_image_key)))
        if row.flagged:
            flagged.add(row.envelope_id)
    failed: list[UUID] = []
    for envelope_id, wanted in digests.items():
        bad = False
        for digest in sorted(wanted):
            try:
                body = await get_record(tenant_id, RECORD_TYPE, digest)
            except ServiceUnavailable:  # the bytes differ from their digest (`RecordsUnavailable`)
                body = None
            if body is None:
                bad = True
                break
        if not bad:
            continue
        failed.append(envelope_id)
        _failures.add(1)
        _log.error("signatures.evidence_integrity_failed", envelope_id=str(envelope_id))
        if envelope_id in flagged:
            continue
        async with uow(tenant) as tx:
            await tx.session.execute(
                _EVENT,
                {
                    "tenant": tenant_id,
                    "envelope": envelope_id,
                    "kind": INTEGRITY_FAILED,
                    "at": system_now(),
                },
            )
            tx.record(INTEGRITY_FAILED, target=Target("envelope", envelope_id), after=Ref())
    return failed


@activity.defn(name="signatures.evidence_integrity_sweep")
async def evidence_integrity_sweep() -> int:
    """Every firm, one at a time; one firm's failure never stops the others."""
    failed = 0
    for tenant_id in await firm_tenant_ids():
        try:
            failed += len(await verify_firm(tenant_id))
        except Exception:
            _log.error(
                "signatures.evidence_integrity_sweep_failed",
                tenant_id=str(tenant_id),
                exc_info=True,
            )
    return failed


SCHEDULES: Final[tuple[PlatformSchedule, ...]] = (
    PlatformSchedule(
        id=INTEGRITY_ID,
        workflow=EvidenceIntegrityWorkflow,
        every=timedelta(days=1),
        note="N-02-T38: re-hash every envelope's evidence records; alarm on a mismatch",
    ),
)
ACTIVITIES: Final[tuple[object, ...]] = (evidence_integrity_sweep,)
