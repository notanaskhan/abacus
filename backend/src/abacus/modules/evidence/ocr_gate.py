"""P-11-T23: the OCR gate and its usage record (P-11 AC7.2; DEC-2251). Red (evidence).

Before any page reaches a provider the gate runs, in order, and the **first** failing condition is
the refusal reason: the platform kill switch (`model_route_block` on route `textract`, ADR-140)
→ the firm flag `evidence.ocr` → a provider-terms entry covering `textract` today (P-11-T21) →
the boundary basis (a synthetic firm, or a real firm whose entry carries the AI-services opt-out
evidence) → the §7216 rule (evidence in a tax-return-information scope needs the C19 consent the
caller found, unless counsel's `tri_basis` is recorded on the entry). Every run, refused or not,
writes one insert-only `ocr_runs` row (0666) and an audit event with identifiers and counts
only, never document text. A refusal is never retried automatically and never rerouted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import EVIDENCE_OCR
from abacus.kernel.clock import today
from abacus.kernel.controls import control_active
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import flag_enabled
from abacus.kernel.ocr import Api
from abacus.kernel.provider_terms import covering
from abacus.kernel.uow import Ref, Target, uow

Refusal = Literal[
    "kill_switch", "flag_off", "terms_not_covering", "boundary_basis", "consent_missing",
    "quota_exceeded",
]  # fmt: skip
ROUTE: Final = "textract"
DAILY_PAGE_CAP: Final = 5000  # per firm, P-11 §cost; a refusal, never a queue


@dataclass(frozen=True)
class GateFacts:
    """What the caller knows about the source: whether the firm is synthetic, whether the
    evidence is in a TRI scope, and whether its subjects hold both §7216 consents (C19)."""

    synthetic_firm: bool
    tri_scope: bool
    tri_consented: bool


async def first_refusal(tenant: TenantContext, facts: GateFacts) -> Refusal | None:
    if await control_active("model_route_block", tenant.tenant_id, route=ROUTE):
        return "kill_switch"
    if not await flag_enabled(tenant, EVIDENCE_OCR):
        return "flag_off"
    entry = covering(ROUTE, await today(tenant))
    if entry is None:
        return "terms_not_covering"
    if not facts.synthetic_firm and not entry.ai_services_opt_out:
        return "boundary_basis"
    if facts.tri_scope and not facts.tri_consented and not entry.tri_basis:
        return "consent_missing"
    return None


async def over_daily_cap(tenant: TenantContext, pages: int) -> bool:
    """Whether reading `pages` more would pass the firm's daily cap (P-11-T25; DEC-2375)."""
    async with tenant_session(tenant) as session:
        used = await session.scalar(
            text(
                "SELECT coalesce(sum(page_units), 0) FROM ocr_runs "
                "WHERE created_at >= date_trunc('day', clock_timestamp())"
            )
        )
    return int(used or 0) + pages > DAILY_PAGE_CAP


async def record_run(
    tenant: TenantContext,
    *,
    evidence_version_id: UUID | None,
    inbox_file_id: UUID | None,
    provider: str,
    api: Api,
    pages: list[int],
    refused: Refusal | None,
    synthetic_firm: bool,
    request_ids: list[str],
) -> UUID:
    """One `ocr_runs` row and its audit event: the cost and gate record (no text)."""
    status = "refused" if refused else "completed"
    async with uow(tenant) as tx:
        run_id = await tx.session.scalar(
            text(
                "INSERT INTO ocr_runs (tenant_id, evidence_version_id, inbox_file_id, provider, "
                "api, pages, status, refused_reason, basis, page_units, provider_request_ids) "
                "VALUES (:t, :ev, :inbox, :provider, :api, :pages, :status, :refused, :basis, "
                ":units, :ids) RETURNING id"
            ),
            {
                "t": tenant.tenant_id,
                "ev": evidence_version_id,
                "inbox": inbox_file_id,
                "provider": provider,
                "api": api,
                "pages": pages,
                "status": status,
                "refused": refused,
                "basis": "synthetic" if synthetic_firm else "client_data",
                "units": 0 if refused else len(pages),
                "ids": request_ids,
            },
        )
        tx.record(
            "ocr.run_recorded",
            target=Target("ocr_run", UUID(str(run_id))),
            after=Ref(pages=len(pages), refused=int(refused is not None)),
        )
    return UUID(str(run_id))
