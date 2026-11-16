"""The CCH Axcess file bridge, 1041 mode (T-07-T19; T-07 §4, F10;
`docs/contracts/tax-engine-bridge.md`
§6; ADR-150 W2 `tax_engine_file_bridge`; DEC-77, DEC-78; red): what leaves the firm for the engine
for a trust or estate income tax return, and how the engine's 1041 figures come back.

**Export.** A Form 1041 exports through T-01's file bridge (`export.export_return`: a person's,
after the signer's final approval, consuming that approval's grant) with one more sheet set built
by code from the signed fiduciary computation (T-07-T16's version the L2 sign-off covers; refused
with 409 `fiduciary_not_signed` while the sign-off is missing or stale):

- `Fiduciary`: `engine_field_key`, `label`, `value` for page 1 (type of entity, lines 1 interest,
  2a ordinary dividends, 2b(2) qualified dividends, 18 income distribution deduction), Schedule B
  (lines 1 adjusted total income through 15 IDD) and the exemption;
- `K1_1041`: `beneficiary_ref`, `beneficiary`, `box`, `amount` (boxes 1, 2a and 2b).

**Import.** A CCH 1041 import is P-04's engine import checkpoint, approved by a person; once it is
approved, each engine figure under these keys is compared with the computation by code, and each
difference raises one `engine_diagnostic` issue (`source_ref = recon:<key>`, deduplicated, the
title naming the line, never the figure). A one-dollar difference on line 18 raises exactly one.

**Never transmit** (R-04): nothing here sends, files or calls the engine. Values are TRI.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import current_values, record_engine_issue, sign_off_states

FIDUCIARY_FORMS: Final = frozenset({"1041"})
FIELDS_HEADER: Final = ("engine_field_key", "label", "value")
K1_HEADER: Final = ("beneficiary_ref", "beneficiary", "box", "amount")
RETURN_TARGET: Final = "tax_return"
COMPUTATION_TARGET: Final = "fiduciary_computation"
RECON_PREFIX: Final = "recon:"
_PREFIXES: Final = ("f1041.", "sch_b.", "k1_1041.")
_ENTITY_TYPE: Final = {
    "complex_trust": "complex",
    "simple_trust": "simple",
    "estate": "decedent_estate",
}


class FiduciaryNotSigned(DomainConflict):
    """The fiduciary computation has no current L2 sign-off: nothing leaves (T-07-T19)."""

    code = "fiduciary_not_signed"


@dataclass(frozen=True)
class FieldRow:
    engine_field_key: str
    label: str
    value: str


@dataclass(frozen=True)
class K1Row:
    beneficiary_ref: str
    beneficiary: str
    box: str
    amount: Decimal


@dataclass(frozen=True)
class FiduciarySection:
    fields: tuple[FieldRow, ...]
    k1: tuple[K1Row, ...]


def _d(value: object) -> Decimal:
    return Decimal(str(value))


def field_rows(outputs: Mapping[str, object], entity_type: str) -> list[FieldRow]:
    """The engine_field_key map (page 1, Schedule B, exemption), from a computation's outputs."""
    dni_by = cast(Mapping[str, str], outputs.get("dni_by_character", {}))
    rows = [
        FieldRow(
            "f1041.type_of_entity", "Type of entity", _ENTITY_TYPE.get(entity_type, entity_type)
        ),
        FieldRow("f1041.line_1", "Interest income", f"{_d(dni_by.get('interest', '0')):.2f}"),
        FieldRow(
            "f1041.line_2a",
            "Total ordinary dividends",
            f"{_d(dni_by.get('ordinary_dividends', '0')):.2f}",
        ),
        FieldRow(
            "f1041.line_2b2",
            "Qualified dividends allocable to beneficiaries",
            f"{_d(outputs.get('dni_qualified', '0')):.2f}",
        ),
        FieldRow("f1041.line_18", "Income distribution deduction", f"{_d(outputs['idd']):.2f}"),
        FieldRow("f1041.line_21", "Exemption", f"{_d(outputs.get('exemption', '0')):.2f}"),
        FieldRow("f1041.line_23", "Taxable income", f"{_d(outputs['taxable_income']):.2f}"),
        FieldRow("sch_b.line_7", "Distributable net income", f"{_d(outputs['dni']):.2f}"),
        FieldRow("sch_b.line_11", "Total distributions", f"{_d(outputs['distributions']):.2f}"),
        FieldRow("sch_b.line_15", "Income distribution deduction", f"{_d(outputs['idd']):.2f}"),
    ]
    return rows


def k1_rows(outputs: Mapping[str, object]) -> list[K1Row]:
    out: list[K1Row] = []
    for a in cast(Sequence[Mapping[str, object]], outputs.get("allocations", [])):
        for box, key in (("1", "box_1"), ("2a", "box_2a"), ("2b", "box_2b")):
            out.append(K1Row(str(a["beneficiary"]), str(a["name"]), box, _d(a[key])))
    return out


_LATEST: Final = text(
    "SELECT c.outputs, c.content_hash, coalesce(t.fiduciary_kind, 'trust') FROM "
    "fai_dni_computations c "
    "JOIN tax_returns r ON r.work_item_id = c.work_item_id LEFT JOIN trust_profiles t "
    "ON t.client_entity_id = r.client_entity_id WHERE c.work_item_id = :r "
    "ORDER BY c.version_no DESC LIMIT 1"
)
_DETERMINED_TYPE: Final = text(
    "SELECT v.value_code FROM instrument_interpretations i JOIN instrument_determinations d "
    "ON d.interpretation_id = i.id AND d.key = 'trust_type' JOIN LATERAL (SELECT value_code FROM "
    "instrument_determination_versions x WHERE x.determination_id = d.id ORDER BY seq DESC LIMIT "
    "1) v "
    "ON true WHERE i.work_item_id = :r AND i.superseded_at IS NULL"
)


async def _signed(tenant: TenantContext, return_id: UUID) -> tuple[Mapping[str, object], str]:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_LATEST, {"r": return_id})).first()
        determined = await session.scalar(_DETERMINED_TYPE, {"r": return_id})
    if row is None:
        raise FiduciaryNotSigned(facts={"computation": "missing"})
    states = await sign_off_states(
        tenant, COMPUTATION_TARGET, [return_id], {return_id: str(row[1])}
    )
    l2 = next((s for s in states.get(return_id, []) if s.level == 2), None)
    if l2 is None or l2.signed_by is None or l2.stale:
        raise FiduciaryNotSigned(facts={"computation": "not_signed"})
    kind = (
        "estate"
        if str(row[2]) == "estate"
        else ("simple_trust" if determined == "simple" else "complex_trust")
    )
    return cast(Mapping[str, object], row[0]), kind


async def fiduciary_section(tenant: TenantContext, return_id: UUID) -> FiduciarySection:
    """The 1041 sheets from the signed computation (409 `fiduciary_not_signed` otherwise)."""
    outputs, kind = await _signed(tenant, return_id)
    return FiduciarySection(tuple(field_rows(outputs, kind)), tuple(k1_rows(outputs)))


# --- reconciliation to the engine of record
# ---------------------------------------------------------


@dataclass(frozen=True)
class ReconRow:
    key: str
    label: str
    accrued: Decimal | None
    engine: Decimal | None

    @property
    def differs(self) -> bool:
        return (self.accrued != self.engine) and (self.engine is not None)


def _amount(cell: Mapping[str, object] | None) -> Decimal | None:
    if cell is None or cell.get("v") in (None, ""):
        return None
    try:
        return Decimal(str(cell.get("v")))
    except InvalidOperation:
        return None


def compare(
    section: FiduciarySection, engine: Mapping[str, Mapping[str, object]]
) -> list[ReconRow]:
    ours: dict[str, tuple[str, Decimal | None]] = {}
    for f in section.fields:
        try:
            ours[f.engine_field_key] = (f.label, Decimal(f.value))
        except InvalidOperation:
            continue  # the type of entity is a code, compared by the engine import itself
    for k in section.k1:
        ours[f"k1_1041.{k.beneficiary_ref}.box_{k.box}"] = (
            f"K-1 (1041) {k.beneficiary} box {k.box}",
            k.amount,
        )
    rows = [
        ReconRow(key, label, value, _amount(engine.get(key)))
        for key, (label, value) in ours.items()
        if key in engine
    ]
    rows += [
        ReconRow(key, key, None, _amount(engine.get(key)))
        for key in sorted(engine)
        if key.startswith(_PREFIXES) and key not in ours
    ]
    return rows


async def reconcile(tenant: TenantContext, return_id: UUID) -> list[ReconRow]:
    outputs, kind = await _latest_unsigned_ok(tenant, return_id)
    section = FiduciarySection(tuple(field_rows(outputs, kind)), tuple(k1_rows(outputs)))
    engine = {
        k: v
        for k, v in (await current_values(tenant, RETURN_TARGET, return_id)).items()
        if k.startswith(_PREFIXES)
    }
    return compare(section, engine)


async def _latest_unsigned_ok(
    tenant: TenantContext, return_id: UUID
) -> tuple[Mapping[str, object], str]:
    """The newest computation, signed or not: the engine's figures are compared with what Accrued
    shows now (a stale sign-off is the reviewer's to redo, not a reason to skip the check)."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_LATEST, {"r": return_id})).first()
        determined = await session.scalar(_DETERMINED_TYPE, {"r": return_id})
    if row is None:
        return {
            "idd": "0",
            "taxable_income": "0",
            "dni": "0",
            "distributions": "0",
        }, "complex_trust"
    kind = (
        "estate"
        if str(row[2]) == "estate"
        else ("simple_trust" if determined == "simple" else "complex_trust")
    )
    return cast(Mapping[str, object], row[0]), kind


async def raise_differences(ctx: AuthContext, return_id: UUID) -> int:
    """After an approved CCH 1041 import: one `engine_diagnostic` issue per difference."""
    raised = 0
    for row in (r for r in await reconcile(ctx.tenant, return_id) if r.differs):
        await record_engine_issue(
            ctx,
            record_type=RETURN_TARGET,
            record_id=return_id,
            work_item_id=return_id,
            source_ref=f"{RECON_PREFIX}{row.key}",
            title=f"CCH reconciliation · {row.label}"[:200],
        )
        raised += 1
    return raised
