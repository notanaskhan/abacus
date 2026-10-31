"""C7 v1.1, additive, for T-01 and T-02 (N-02-T25; N-02 §4.4 "v1.1"; DEC-85; DEC-1285).
PROTECTED.

- **Source contracts.** `consent_set` (T-01's §7216 consents) and `tax_return` (T-01's e-file
  authorizations) are kinds with a contract: a source registering either must be able to draft,
  and its drafts carry the contract's purposes and policy family (`check_contract`), so an
  e-file envelope is never drafted under the consent floor or the other way round.
- **`supersede_for_amount_change(tenant, envelope_id, binding_id)`**, the system only (T-01's
  8879 binding after an import moved an amount): the envelope keeps its evidence and gains the
  marker "Amounts changed after signing · re-sign required"; every gate consumer treats it as
  unmet; nobody clears it (0432's trigger), a new envelope is the way back. A second call is a
  no-op.
- **`extend_retention(tenant, envelope_id, until)`**, forward only: every stored record of the
  envelope (signed document, certificate, packages, signature images) is locked until at least
  `until` and `envelopes.retain_until` moves forward; an earlier date than the envelope already
  holds is refused 409 `retention_not_extended` (0432's trigger refuses it below us too).
- **`envelope_summaries_for(ctx, work_item_ids)`**, TAX-01's signer chips (DV-17): per work item,
  each envelope's status, counts, superseded flag and per-signer chips (first name, status),
  without reading a document.
- **Gate facts for `efile_authorization`**: met by a completed, non-superseded `tax_return`
  envelope for the return.
- **Signer-level events** `envelope.signer_signed` and `envelope.signer_verification_failed`
  are emitted by the poll (`activities.envelope_poll`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence.api import extend_record
from abacus.modules.identity.api import AuthContext, names_of
from abacus.modules.organisations.api import contact_facts
from abacus.modules.signatures.events import EnvelopeSuperseded
from abacus.modules.signatures.imports import RECORD_TYPE

CONSENT_SET: Final = "consent_set"
TAX_RETURN: Final = "tax_return"
EFILE_GATE: Final = "efile_authorization"
AMOUNT_CHANGE: Final = "amount_change"
SUPERSEDED_LABEL: Final = "Amounts changed after signing · re-sign required"


@dataclass(frozen=True)
class SourceContract:
    purposes: frozenset[str]
    policy_family: str


SOURCE_CONTRACTS: Final[dict[str, SourceContract]] = {
    CONSENT_SET: SourceContract(frozenset({"consent_7216"}), "consent"),
    TAX_RETURN: SourceContract(
        frozenset({"form_8879", "form_8879_pe", "form_8879_f"}), "efile_authorization"
    ),
}


class SourceContractBroken(DomainInvalid):
    """A contracted source drafted outside its purposes or policy family."""

    code = "source_contract_broken"


class RetentionNotExtended(DomainConflict):
    """`extend_retention` only moves the date later."""

    code = "retention_not_extended"


class SystemOnly(PermissionError):
    """Only the system marks an envelope superseded (DEC-85): never a person or an agent."""


def check_contract(kind: str, purpose: str, policy_family: str) -> None:
    """A draft from a contracted source stays inside its contract; other kinds pass."""
    contract = SOURCE_CONTRACTS.get(kind)
    if contract is None:
        return
    if purpose not in contract.purposes or policy_family != contract.policy_family:
        raise SourceContractBroken(facts={"kind": kind, "purpose": purpose})


# --- Superseded for an amount change -----------------------------------------------------------


async def supersede_for_amount_change(
    tenant: TenantContext, envelope_id: UUID, binding_id: str
) -> bool:
    """The system-only marker; True when this call set it, False when it was already set."""
    if tenant.actor_kind != "system":
        raise SystemOnly(tenant.actor_kind)
    binding = binding_id.strip()
    if not 1 <= len(binding) <= 200:
        raise ValueError("binding_id")
    now = system_now()
    async with uow(tenant) as tx:
        found = (
            await tx.session.execute(
                text(
                    "UPDATE envelopes SET superseded_at = :now, superseded_reason = :reason, "
                    "superseded_binding_ref = :binding, version = version + 1, updated_at = :now "
                    "WHERE id = :id AND superseded_at IS NULL AND status <> 'draft' "
                    "RETURNING client_id, engagement_id"
                ),
                {"now": now, "reason": AMOUNT_CHANGE, "binding": binding, "id": envelope_id},
            )
        ).one_or_none()
        if found is None:
            exists = await tx.session.scalar(
                text("SELECT 1 FROM envelopes WHERE id = :id"), {"id": envelope_id}
            )
            if exists is None:
                raise NotFound("envelope")
            tx.record(
                "envelope.superseded",
                target=Target("envelope", envelope_id),
                after=Ref(repeat=1),
            )
            return False
        await tx.session.execute(
            text(
                "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, occurred_at) "
                "VALUES (:tenant, :id, 'envelope.superseded', 'system', :now)"
            ),
            {"tenant": tenant.tenant_id, "id": envelope_id, "now": now},
        )
        tx.record("envelope.superseded", target=Target("envelope", envelope_id))
        tx.emit(
            EnvelopeSuperseded(
                envelope_id=envelope_id,
                client_id=found.client_id,
                engagement_id=found.engagement_id,
                reason=AMOUNT_CHANGE,
            )
        )
    return True


# --- Retention, forward only -------------------------------------------------------------------


async def extend_retention(tenant: TenantContext, envelope_id: UUID, until: date) -> date:
    """Lock the envelope's records until at least `until`; the date it now holds."""
    async with tenant_session(tenant) as session:
        held = (
            await session.execute(
                text(
                    "SELECT e.retain_until AS extended, (SELECT max(v.retain_until) FROM "
                    "signature_evidence v WHERE v.envelope_id = e.id) AS floor "
                    "FROM envelopes e WHERE e.id = :id"
                ),
                {"id": envelope_id},
            )
        ).one_or_none()
        if held is None:
            raise NotFound("envelope")
        proofs = (
            await session.execute(
                text(
                    "SELECT document_sha256s, package_sha256, signed_image_key "
                    "FROM signature_evidence WHERE envelope_id = :id"
                ),
                {"id": envelope_id},
            )
        ).all()
    current: date | None = max(
        (d for d in (held.extended, held.floor) if d is not None), default=None
    )
    if current is not None and until < current:
        raise RetentionNotExtended(facts={"retain_until": current.isoformat()})
    if current is not None and until == current:
        return current
    digests: set[str] = set()
    for p in proofs:
        digests.update(str(d) for d in p.document_sha256s)
        if p.package_sha256 is not None:
            digests.add(str(p.package_sha256))
        if p.signed_image_key is not None:
            digests.add(str(p.signed_image_key).rsplit("/", 1)[-1])
    lock = datetime.combine(until, time(23, 59, 59), tzinfo=UTC)
    for digest in sorted(digests):
        await extend_record(tenant.tenant_id, RECORD_TYPE, digest, lock)
    now = system_now()
    async with uow(tenant) as tx:
        await tx.session.execute(
            text("UPDATE envelopes SET retain_until = :until, updated_at = :now WHERE id = :id"),
            {"until": until, "now": now, "id": envelope_id},
        )
        await tx.session.execute(
            text(
                "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, occurred_at) "
                "VALUES (:tenant, :id, 'envelope.retention_extended', 'system', :now)"
            ),
            {"tenant": tenant.tenant_id, "id": envelope_id, "now": now},
        )
        tx.record(
            "envelope.retention_extended",
            target=Target("envelope", envelope_id),
            after=Ref(records=len(digests), days=(until - (current or now.date())).days),
        )
    return until


# --- TAX-01's signer chips ---------------------------------------------------------------------


@dataclass(frozen=True)
class SignerChip:
    signer_id: UUID
    first_name: str
    role: str
    status: str


@dataclass(frozen=True)
class WorkItemEnvelope:
    envelope_id: UUID
    work_item_id: UUID
    purpose: str
    status: str
    superseded: bool
    signed: int
    total: int
    chips: tuple[SignerChip, ...]


def _first(name: str | None) -> str:
    return name.split()[0] if name else "Signer"


async def envelope_summaries_for(
    ctx: AuthContext, work_item_ids: Sequence[UUID]
) -> dict[UUID, list[WorkItemEnvelope]]:
    """Per work item, its envelopes newest first (drafts and voided ones left out), for a caller
    that authorised reading those work items. Identifiers, codes and first names only."""
    if not work_item_ids:
        return {}
    async with tenant_session(ctx.tenant) as session:
        heads = (
            await session.execute(
                text(
                    "SELECT id, work_item_id, purpose, status, superseded_at IS NOT NULL AS "
                    "superseded FROM envelopes WHERE work_item_id = ANY(:items) "
                    "AND status NOT IN ('draft', 'voided') ORDER BY created_at DESC"
                ),
                {"items": list(work_item_ids)},
            )
        ).all()
        people = (
            await session.execute(
                text(
                    "SELECT id, envelope_id, contact_id, user_id, role, status FROM "
                    'envelope_signers WHERE envelope_id = ANY(:ids) ORDER BY "order"'
                ),
                {"ids": [h.id for h in heads]},
            )
        ).all()
        contacts = await contact_facts(
            session, [p.contact_id for p in people if p.contact_id is not None]
        )
    users = await names_of(list({p.user_id for p in people if p.user_id is not None}))
    chips: dict[UUID, list[SignerChip]] = {}
    for p in people:
        name = (
            contacts[p.contact_id].display_name
            if p.contact_id is not None and p.contact_id in contacts
            else users.get(p.user_id)
            if p.user_id is not None
            else None
        )
        chips.setdefault(p.envelope_id, []).append(
            SignerChip(p.id, _first(name), str(p.role), str(p.status))
        )
    out: dict[UUID, list[WorkItemEnvelope]] = {}
    for h in heads:
        mine = chips.get(h.id, [])
        out.setdefault(h.work_item_id, []).append(
            WorkItemEnvelope(
                envelope_id=h.id,
                work_item_id=h.work_item_id,
                purpose=str(h.purpose),
                status=str(h.status),
                superseded=bool(h.superseded),
                signed=sum(1 for c in mine if c.status == "signed"),
                total=len(mine),
                chips=tuple(mine),
            )
        )
    return out


# --- The e-file authorization gate -------------------------------------------------------------

_EFILE = text(
    "SELECT id, completed_at::date AS completed_on FROM envelopes WHERE source_kind = :kind "
    "AND source_id = :source AND status = 'completed' AND superseded_at IS NULL "
    "ORDER BY completed_at DESC LIMIT 1"
)


async def efile_gate(tenant: TenantContext, tax_return_id: UUID) -> tuple[UUID, date] | None:
    """The newest completed, non-superseded `tax_return` envelope for the return, or None."""
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(_EFILE, {"kind": TAX_RETURN, "source": tax_return_id})
        ).one_or_none()
    return None if found is None else (found.id, found.completed_on)
