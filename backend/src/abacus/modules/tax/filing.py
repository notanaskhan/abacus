"""The 8879 amount binding and the drift relock (T-01-T36; T-01 §3.12; I-8879-DRIFT; DEC-85;
DEC-1566). RED: what a taxpayer authorised, and the only path that voids it.

- **The `tax_return` envelope source** (C7 v1.1): Form 8879 with NY TR-579-IT from the engine
  PDFs the bridge filed, and the filing unit's signers (taxpayer and spouse each their own
  signer) under the `efile_authorization` policy with KBA, in parallel.
- **Draft** (`delivery_packet.prepare`, a person, after the packet is approved): C7 drafts the
  envelope, then the figures it authorises are bound to it: total income, AGI, tax, withholding,
  refund and balance due per jurisdiction, from the return's values at the approved checkpoint,
  with their SHA-256 and the Pub 1345 tolerances' reference-set version.
- **Recheck** on `checkpoint.approved` for a return (an engine import's approval included) and on
  `reference_set.published` (corrected tolerances): every open binding is compared with the
  return's values now under the tolerances in effect today (`platform.api.pub1345_tolerances`,
  never a constant). A figure moving by more than its tolerance, or appearing or disappearing,
  supersedes the binding and C7 marks the envelope `superseded_by_change`: the gate relocks.
  The system only relocks: nothing here clears a supersession or signs anything (0524's trigger
  refuses it too).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import DomainEvent, OutboxEvent, Ref, Scope, Target, uow
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    engagement_resource,
)
from abacus.modules.organisations.api import filing_unit
from abacus.modules.platform.api import form_8879_for, pub1345_tolerances
from abacus.modules.review.api import current_checkpoint, current_values
from abacus.modules.signatures.api import (
    EnvelopeSource,
    SourceDocument,
    SourceDraft,
    SourceSigner,
    create_draft,
    register_envelope_source,
    supersede_for_amount_change,
)

TARGET: Final = "tax_return"
SOURCE: Final = "tax_return"
PREPARE: Final = "delivery_packet.prepare"
RECORD_TYPE: Final = "efile_authorization"
ACTOR: Final = "tax:filing"
_log = get_logger(__name__)
# Figures that move under the first tolerance (total income, AGI) and under the second (tax,
# withholding, refund, balance due); Pub 1345 (DEC-85).
INCOME: Final = frozenset({"total_income", "agi"})
AMOUNTS: Final = frozenset({"tax", "withholding", "refund", "balance_due"})
# The engine's field keys for each figure, by jurisdiction (the bridge's values file).
FIELDS: Final[dict[str, dict[str, str]]] = {
    "US": {
        "total_income": "f1040.total_income",
        "agi": "f1040.agi",
        "tax": "f1040.total_tax",
        "withholding": "f1040.withholding",
        "refund": "f1040.refund",
        "balance_due": "f1040.balance_due",
    },
    "NY": {
        "agi": "it201.agi",
        "tax": "it201.tax",
        "withholding": "it201.withholding",
        "refund": "it201.refund",
        "balance_due": "it201.balance_due",
    },
    "IL": {"agi": "il1040.agi", "tax": "il1040.tax", "balance_due": "il1040.balance_due"},
    "CO": {
        "agi": "co_dr0104pn.agi",
        "tax": "co_dr0104pn.tax",
        "balance_due": "co_dr0104pn.balance_due",
    },
}
# The engine PDFs that make the envelope's documents, in order.
DOCUMENTS: Final = ("form_8879", "tr_579_it")

Figures = dict[str, dict[str, str]]


class PacketNotApproved(DomainConflict):
    code = "packet_not_approved"


class NoFigures(DomainConflict):
    code = "no_figures"


class NoAuthorizationForm(DomainConflict):
    code = "no_authorization_form"


class EnvelopeExists(DomainConflict):
    code = "envelope_exists"


class EfileRelocked(DomainEvent):
    """A binding was superseded: the 8879 must be signed again (identifiers only)."""

    event_type = "efile.relocked"
    return_id: Annotated[UUID, classified("internal")]
    binding_id: Annotated[UUID, classified("internal")]
    envelope_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class Binding:
    id: UUID
    envelope_id: UUID
    authorization_form: str
    tolerances_ref: UUID


def _decimal(raw: object) -> Decimal | None:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError):
        return None


def figures_of(values: Mapping[str, Mapping[str, object]]) -> Figures:
    """The authorised figures present on the return, as decimal strings (code reads them; no
    sum is made)."""
    out: Figures = {}
    for jurisdiction, keys in FIELDS.items():
        for figure, key in keys.items():
            found = values.get(key)
            amount = None if found is None else _decimal(found.get("v"))
            if amount is not None:
                out.setdefault(jurisdiction, {})[figure] = str(amount)
    return out


def figures_sha256(figures: Figures) -> bytes:
    canonical = json.dumps(figures, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).digest()


def drift(bound: Figures, now: Figures, income_usd: int, amounts_usd: int) -> list[str]:
    """The figures that moved beyond their tolerance (strictly more: a move of exactly the
    tolerance holds), or that appeared or disappeared."""
    moved: list[str] = []
    for jurisdiction in sorted(set(bound) | set(now)):
        was, is_ = bound.get(jurisdiction, {}), now.get(jurisdiction, {})
        for figure in sorted(set(was) | set(is_)):
            a, b = was.get(figure), is_.get(figure)
            if a is None or b is None:
                moved.append(f"{jurisdiction}.{figure}")
                continue
            limit = income_usd if figure in INCOME else amounts_usd
            if abs(Decimal(b) - Decimal(a)) > limit:
                moved.append(f"{jurisdiction}.{figure}")
    return moved


@dataclass(frozen=True)
class _Return:
    engagement_id: UUID
    client_id: UUID
    client_name: str
    entity_id: UUID
    tax_year: int
    form: str


async def _return(ctx: AuthContext, return_id: UUID) -> _Return:
    item = next(
        (
            i
            for i in await work_item_facts(ctx, TARGET, "tax_return.read_metadata")
            if i.work_item_id == return_id
        ),
        None,
    )
    if item is None:
        raise NotFound(TARGET)
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT client_entity_id, tax_year, form FROM tax_returns "
                    "WHERE work_item_id = :r"
                ),
                {"r": return_id},
            )
        ).first()
    if row is None:
        raise NotFound(TARGET)
    return _Return(
        item.engagement_id, item.client_id, item.client_name, row[0], int(row[1]), str(row[2])
    )


async def _documents(tenant: TenantContext, return_id: UUID) -> tuple[SourceDocument, ...]:
    """The newest engine PDF of each authorization kind, by the bytes' SHA-256 (the bridge kept
    it on the sync event: the evidence fingerprint)."""
    out: list[SourceDocument] = []
    async with tenant_session(tenant) as session:
        for kind in DOCUMENTS:
            row = (
                await session.execute(
                    text(
                        "SELECT summary ->> 'evidence_version_id', payload_sha256 "
                        "FROM engine_sync_events WHERE return_id = :r AND kind = 'pdfs' "
                        "AND summary ->> 'pdf_kind' = :k ORDER BY at DESC LIMIT 1"
                    ),
                    {"r": return_id, "k": kind},
                )
            ).first()
            if row is not None and row[0] and row[1]:
                out.append(
                    SourceDocument(
                        sha256=str(row[1]),
                        evidence_version_id=UUID(str(row[0])),
                        source_ref=f"engine_pdf:{kind}",
                        tri=True,
                    )
                )
    return tuple(out)


async def _draft_source(ctx: AuthContext, return_id: UUID) -> SourceDraft:
    """C7's prefill for a return: the authorization forms and each filer as a signer (KBA)."""
    facts = await _return(ctx, return_id)
    documents = await _documents(ctx.tenant, return_id)
    if len(documents) == 0:
        raise NoFigures(facts={"work_item_id": str(return_id)})
    unit = await filing_unit(ctx, facts.entity_id)
    return SourceDraft(
        purpose="form_8879",
        policy_family="efile_authorization",
        client_id=facts.client_id,
        title=f"Form 8879 + TR-579-IT · TY{facts.tax_year} · {facts.client_name}",
        documents=documents,
        signers=tuple(
            SourceSigner(identity_method="kba", contact_id=s.contact_id) for s in unit.signers
        ),
        form_code="8879",
        engagement_id=facts.engagement_id,
        work_item_id=return_id,
        signer_order="parallel",
    )


async def _none(ctx: AuthContext, return_id: UUID) -> list[object]:
    return []


def register() -> None:
    """At import (tax/api.py): the `tax_return` envelope source (C7 v1.1 contract)."""
    register_envelope_source(
        EnvelopeSource(
            kind=SOURCE,
            documents=_none,
            signers=_none,
            retention_record_type=RECORD_TYPE,
            gate="efile_authorization",
            completed_label="Signed",
            draft=_draft_source,
        )
    )


async def _packet_approved(tenant: TenantContext, return_id: UUID) -> bool:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(
                "SELECT 1 FROM delivery_packets WHERE return_id = :r AND status = 'approved' "
                "LIMIT 1"
            ),
            {"r": return_id},
        )
    return found is not None


async def _open_binding(tenant: TenantContext, return_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(
                "SELECT id FROM efile_amount_bindings WHERE return_id = :r "
                "AND superseded_at IS NULL LIMIT 1"
            ),
            {"r": return_id},
        )
    return None if found is None else cast(UUID, found)


async def draft_envelope(ctx: AuthContext, return_id: UUID) -> Binding:
    """The 8879 envelope through C7, and its amount binding (§3.12)."""
    if ctx.client:
        raise NotFound(TARGET)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(PREPARE, "role")
    facts = await _return(ctx, return_id)
    resource = replace(
        await engagement_resource(ctx.tenant, facts.engagement_id),
        client_id=facts.client_id,
        work_item_id=return_id,
    )
    await authorise(ctx, PREPARE, resource)
    if not await _packet_approved(ctx.tenant, return_id):
        raise PacketNotApproved(facts={"work_item_id": str(return_id)})
    if await _open_binding(ctx.tenant, return_id) is not None:
        raise EnvelopeExists(facts={"work_item_id": str(return_id)})
    checkpoint = await current_checkpoint(ctx.tenant, TARGET, return_id)
    figures = figures_of(await current_values(ctx.tenant, TARGET, return_id))
    if checkpoint is None or not figures:
        raise NoFigures(facts={"work_item_id": str(return_id)})
    on = await today(ctx.tenant)
    try:
        form = await form_8879_for(facts.form, facts.tax_year, "US", as_of=on)
        tolerances = await pub1345_tolerances(facts.tax_year, as_of=on)
    except LookupError:
        raise NoAuthorizationForm(facts={"work_item_id": str(return_id)}) from None
    envelope_id = await create_draft(ctx, SOURCE, return_id)
    binding_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO efile_amount_bindings (id, tenant_id, return_id, envelope_id, "
                "checkpoint_id, figures, figures_sha256, tolerances_ref) VALUES (:id, :t, :r, "
                ":e, :c, CAST(:f AS jsonb), :h, :tol)"
            ),
            {
                "id": binding_id,
                "t": ctx.tenant_id,
                "r": return_id,
                "e": envelope_id,
                "c": checkpoint[0],
                "f": json.dumps(figures, sort_keys=True),
                "h": figures_sha256(figures),
                "tol": tolerances.reference_set_version_id,
            },
        )
        tx.record(
            "efile_binding.created",
            target=Target(TARGET, return_id),
            after=Ref(
                binding=binding_id,
                envelope=envelope_id,
                figures_sha256=figures_sha256(figures).hex(),
            ),
            scope=Scope(engagement_id=facts.engagement_id, client_id=facts.client_id),
        )
    return Binding(
        binding_id, envelope_id, form.authorization_form, tolerances.reference_set_version_id
    )


# --- the relock (system only) -----------------------------------------------------------------


async def recheck(tenant_id: UUID, return_id: UUID | None = None) -> list[UUID]:
    """Every open binding (of one return, or the firm's) against the values and tolerances now;
    the ones superseded. The system may only relock (DEC-85)."""
    system = TenantContext(tenant_id, "system", ACTOR)
    async with tenant_session(system) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT b.id, b.return_id, b.envelope_id, b.figures, r.tax_year, "
                        "r.engagement_id, w.client_id FROM efile_amount_bindings b "
                        "JOIN tax_returns r ON r.work_item_id = b.return_id "
                        "JOIN work_items w ON w.id = b.return_id "
                        "WHERE b.superseded_at IS NULL AND (CAST(:r AS uuid) IS NULL "
                        "OR b.return_id = :r)"
                    ),
                    {"r": return_id},
                )
            )
            .mappings()
            .all()
        )
    on = await today(system)
    superseded: list[UUID] = []
    for row in rows:
        try:
            tolerances = await pub1345_tolerances(int(row["tax_year"]), as_of=on)
        except LookupError:
            _log.warning("efile.recheck_no_tolerances", tax_year=int(row["tax_year"]))
            continue
        now = figures_of(await current_values(system, TARGET, cast(UUID, row["return_id"])))
        moved = drift(
            cast(Figures, row["figures"]),
            now,
            tolerances.total_income_or_agi_usd,
            tolerances.tax_withholding_refund_balance_usd,
        )
        if not moved:
            continue
        binding_id = cast(UUID, row["id"])
        reason = "amount_change: " + ", ".join(moved)
        async with uow(system) as tx:
            await tx.session.execute(
                text(
                    "UPDATE efile_amount_bindings SET superseded_at = abacus_now(), "
                    "superseded_reason = :why WHERE id = :id AND superseded_at IS NULL"
                ),
                {"id": binding_id, "why": reason[:500]},
            )
            tx.record(
                "efile_binding.superseded",
                target=Target(TARGET, cast(UUID, row["return_id"])),
                after=Ref(binding=binding_id, tolerances=tolerances.reference_set_version_id),
                scope=Scope(
                    engagement_id=cast(UUID | None, row["engagement_id"]),
                    client_id=cast(UUID, row["client_id"]),
                ),
            )
            tx.emit(
                EfileRelocked(
                    return_id=cast(UUID, row["return_id"]),
                    binding_id=binding_id,
                    envelope_id=cast(UUID, row["envelope_id"]),
                )
            )
        await supersede_for_amount_change(system, cast(UUID, row["envelope_id"]), str(binding_id))
        superseded.append(binding_id)
    return superseded


async def on_checkpoint_approved(event: OutboxEvent) -> None:
    """A return's checkpoint moved (an engine import approved included): recheck its bindings."""
    if event.payload.get("target_type") != TARGET:
        return
    await recheck(event.tenant_id, UUID(str(event.payload["target_id"])))


async def on_tolerances_published(event: OutboxEvent) -> None:
    """Corrected Pub 1345 tolerances: recheck every open binding of the firm."""
    if event.payload.get("set_key") not in (None, "form_8879_set"):
        return
    await recheck(event.tenant_id)


async def binding_state(tenant: TenantContext, return_id: UUID) -> tuple[UUID | None, bool]:
    """The return's newest binding and whether it is superseded (TAX-12's read model)."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, superseded_at IS NOT NULL FROM efile_amount_bindings "
                    "WHERE return_id = :r ORDER BY bound_at DESC LIMIT 1"
                ),
                {"r": return_id},
            )
        ).first()
    return (None, False) if row is None else (cast(UUID, row[0]), bool(row[1]))


async def envelope_of(tenant: TenantContext, binding_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT envelope_id FROM efile_amount_bindings WHERE id = :b"), {"b": binding_id}
        )
    return None if found is None else cast(UUID, found)


__all__ = [
    "Binding",
    "binding_state",
    "draft_envelope",
    "drift",
    "envelope_of",
    "figures_of",
    "on_checkpoint_approved",
    "on_tolerances_published",
    "recheck",
    "register",
]
