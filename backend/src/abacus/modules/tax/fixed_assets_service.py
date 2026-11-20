"""The fixed-assets service (T-06-T33; TASK-8831; T-06 F1; SPEC-702 AC-1 to AC-6; TXP-03 a, a2, b,
d; ADR-050, ADR-005; DEC-77, DEC-84, DEC-5833). Amber.

- **Reads.** The register, by property and dispositions views and one asset's detail, computed by
  E3 (`compute.depreciation`) from the return's `fixed_assets` rows every time (ADR-050: code
  computes; the stored `current_year` is the last approved figure, the view is E3's). Tallies: Ties
  to TB (cost 1600, accumulated 1650, expense 5600 on sheet 01; `check` until the TB is in), Book
  = tax, Bonus eligibility (`check` while any asset's date is uncited, INV-2). Every row names its
  cell on 02 and its provenance (`engine_version`, `inputs_hash`).
- **Create** (`fixed_asset.create`): a person adds an asset; 409 `return_locked` once the return is
  filed or Accepted. Real property is straight line, mid-month; personal property 200DB (150DB for
  15- and 20-year), half-year.
- **Change** (`fixed_asset.propose_change`): a person's class, convention, bonus, §179 or date edit
  is a ghost value: an insert-only request naming the asset version it was made against. Nothing
  changes. C3's change sets are agent-authored (`agents.create_proposal`), so a person's request is
  this module's own, decided by a reviewer in the same grammar (DEC-5833).
- **Decide** (`fixed_asset.approve_change`): a reviewer other than the requester approves or
  rejects (a reason). Approval refuses a stale request (409 `proposal_changed`), writes the
  asset's next version image, re-runs E3 over the register, updates each asset whose figures
  moved, projects the changed rows' depreciation onto 02 (so the Fixed Assets section's sign-off
  goes stale) and saves a checkpoint of the workbook ("re-ties 733,500").
- **Sign-off** of the Fixed Assets section with an open flag (an asset flagged, or a request not
  yet decided) needs a note: 409 `open_flags_note_required` (`entity_sections.sign_section`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.tax.compute import depreciation as e3
from abacus.modules.tax.entity_depth_errors import ReturnLocked

TARGET: Final = "fixed_asset"
READ: Final = "fixed_asset.read"
CREATE: Final = "fixed_asset.create"
PROPOSE: Final = "fixed_asset.propose_change"
APPROVE: Final = "fixed_asset.approve_change"
LOCKED: Final = frozenset({"filed", "accepted"})
ENGINE: Final = "E3"
ZERO: Final = Decimal(0)
View = Literal["register", "by_property", "dispositions"]
Tally = Literal["tie", "off", "check"]

_CLASS_TO_DB: Final = {"27.5": "27_5"}
_CLASS_FROM_DB: Final = {"27_5": "27.5"}
_METHOD_TO_DB: Final = {"SL": "sl", "150DB": "db150", "200DB": "db200"}
_METHOD_FROM_DB: Final = {v: k for k, v in _METHOD_TO_DB.items()}
CHANGE_FIELDS: Final = (
    "recovery_class", "convention", "bonus_pct", "sec179", "acquired_on", "binding_contract_on",
)  # fmt: skip


class ProposalChanged(DomainConflict):
    """The asset moved since the request was made (or the request was already decided)."""

    code = "proposal_changed"


class ChangeAlreadyDecided(DomainConflict):
    code = "change_already_decided"


@dataclass(frozen=True)
class AssetRecord:
    id: UUID
    asset_no: int
    description: str
    property_id: UUID | None
    property_key: str
    placed_in_service_on: date
    acquired_on: date | None
    binding_contract_on: date | None
    date_citation_id: UUID | None
    cost: Decimal
    recovery_class: str  # contract spelling ("27.5"), or "land" / "nondepreciable"
    method: str  # "SL" | "150DB" | "200DB"
    convention: str  # "MM" | "HY" | "MQ"
    bonus_pct: Decimal
    sec179: Decimal
    book_equals_tax: bool
    status: str
    version: int
    disposed: bool

    def engine_asset(self) -> e3.Asset | None:
        if self.recovery_class in ("land", "nondepreciable"):
            return None
        return e3.Asset(
            asset_id=str(self.id),
            property_key=self.property_key,
            placed_in_service=self.placed_in_service_on,
            cost=self.cost,
            recovery_class=cast(e3.RecoveryClass, self.recovery_class),
            method=cast(e3.Method, self.method),
            convention=cast(e3.Convention, self.convention),
            bonus_pct=self.bonus_pct,
            section_179=self.sec179,
            acquired_on=self.acquired_on,
            binding_contract_on=self.binding_contract_on if self.date_citation_id else None,
        )

    def image(self) -> dict[str, object]:
        return {
            "asset_no": self.asset_no, "description": self.description,
            "property_id": None if self.property_id is None else str(self.property_id),
            "placed_in_service_on": self.placed_in_service_on.isoformat(),
            "acquired_on": None if self.acquired_on is None else self.acquired_on.isoformat(),
            "binding_contract_on": (
                None if self.binding_contract_on is None else self.binding_contract_on.isoformat()
            ),
            "cost": str(self.cost), "recovery_class": self.recovery_class, "method": self.method,
            "convention": self.convention, "bonus_pct": str(self.bonus_pct),
            "sec179": str(self.sec179), "version": self.version,
        }  # fmt: skip


@dataclass(frozen=True)
class Property:
    id: UUID
    code: str
    name: str
    land: Decimal


@dataclass(frozen=True)
class Facts:
    return_id: UUID
    engagement_id: UUID
    tax_year: int
    status: str
    assets: tuple[AssetRecord, ...]
    properties: tuple[Property, ...]
    tb: dict[str, int]
    cells: dict[int, str]  # asset_no -> "02!F<n>"


_ASSETS: Final = text(
    "SELECT a.id, a.asset_no, a.description, a.property_id, coalesce(p.code, 'none') AS pkey, "
    "a.placed_in_service_on, a.acquired_on, a.binding_contract_on, a.date_citation_id, a.cost, "
    "a.recovery_class, a.method, a.convention, a.bonus_pct, a.sec179, a.book_equals_tax, "
    "a.status, a.version, EXISTS (SELECT 1 FROM fixed_asset_dispositions d "
    "WHERE d.asset_id = a.id) AS disposed FROM fixed_assets a "
    "LEFT JOIN tax_properties p ON p.id = a.property_id "
    "WHERE a.work_item_id = :r ORDER BY a.asset_no"
)
_PROPERTIES: Final = text(
    "SELECT id, code, name, land_value FROM tax_properties WHERE work_item_id = :r ORDER BY code"
)
_RETURN: Final = text("SELECT tax_year, status FROM tax_returns WHERE work_item_id = :r")
_PENDING: Final = text(
    "SELECT count(*) FROM fixed_asset_change_requests q WHERE q.work_item_id = :r AND NOT EXISTS "
    "(SELECT 1 FROM fixed_asset_change_decisions d WHERE d.request_id = q.id)"
)


def _record(raw: object) -> AssetRecord:
    r = cast(Any, raw)
    return AssetRecord(
        UUID(str(r.id)), int(r.asset_no), str(r.description),
        None if r.property_id is None else UUID(str(r.property_id)), str(r.pkey),
        r.placed_in_service_on, r.acquired_on, r.binding_contract_on,
        None if r.date_citation_id is None else UUID(str(r.date_citation_id)),
        Decimal(r.cost), _CLASS_FROM_DB.get(str(r.recovery_class), str(r.recovery_class)),
        _METHOD_FROM_DB.get(str(r.method), "SL"), str(r.convention).upper(),
        Decimal(r.bonus_pct), Decimal(r.sec179), bool(r.book_equals_tax), str(r.status),
        int(r.version), bool(r.disposed),
    )  # fmt: skip


def _tb_and_cells(values: dict[str, dict[str, object]]) -> tuple[dict[str, int], dict[int, str]]:
    def v(key: str) -> object:
        cell = values.get(key)
        return None if cell is None else cell.get("v")

    tb: dict[str, int] = {}
    n = 2
    while f"01!A{n}" in values:
        code, amount = v(f"01!A{n}"), v(f"01!F{n}")
        if code is not None and amount not in (None, ""):
            tb[str(code)] = abs(int(Decimal(str(amount)).to_integral_value()))
        n += 1
    cells: dict[int, str] = {}
    n = 2
    while f"02!A{n}" in values:
        raw = v(f"02!A{n}")
        if raw is not None and str(raw).isdigit():
            cells[int(str(raw))] = f"02!F{n}"
        n += 1
    return tb, cells


async def facts_of(tenant: TenantContext, return_id: UUID, engagement_id: UUID) -> Facts:
    from abacus.modules.tax.entity_schedules import workbook_values

    async with tenant_session(tenant) as session:
        ret = (await session.execute(_RETURN, {"r": return_id})).first()
        if ret is None:
            raise NotFound("tax_return")
        assets = tuple(_record(r) for r in await session.execute(_ASSETS, {"r": return_id}))
        props = tuple(
            Property(UUID(str(p.id)), str(p.code), str(p.name), Decimal(p.land_value))
            for p in await session.execute(_PROPERTIES, {"r": return_id})
        )
    tb, cells = _tb_and_cells(await workbook_values(tenant, return_id))
    return Facts(return_id, engagement_id, int(ret.tax_year), str(ret.status), assets, props, tb,
                 cells)  # fmt: skip


def inputs_hash(assets: tuple[AssetRecord, ...], tax_year: int) -> str:
    body = {"tax_year": tax_year, "assets": [a.image() for a in assets]}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Computed:
    register: e3.Register
    by_asset: dict[str, e3.RoundedRow]
    bonus: dict[str, e3.BonusCheck]
    inputs_hash: str


def compute(facts: Facts) -> Computed:
    """E3 over the return's live (undisposed) depreciable assets (pure)."""
    live = [a for a in facts.assets if not a.disposed]
    engine = [x for a in live if (x := a.engine_asset()) is not None]
    reg = e3.register(engine, facts.tax_year)
    params = e3.parameters(facts.tax_year)
    return Computed(
        reg,
        {r.asset_id: r for r in reg.rows},
        {x.asset_id: e3.bonus_check(x, params) for x in engine},
        inputs_hash(tuple(live), facts.tax_year),
    )


def tallies(facts: Facts, c: Computed) -> tuple[Tally, Tally, Tally]:
    if not facts.tb:
        to_tb: Tally = "check"
    else:
        to_tb = "tie" if e3.ties(c.register, facts.tb).tie else "off"
    book: Tally = "tie" if all(a.book_equals_tax for a in facts.assets) else "check"
    bonus: Tally = "check" if any(v == "check" for v in c.bonus.values()) else "tie"
    return to_tb, book, bonus


async def _loaded(ctx: AuthContext, return_id: UUID) -> tuple[Facts, Resource]:
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    return await facts_of(ctx.tenant, return_id, loaded.facts.engagement_id), resource


async def read(ctx: AuthContext, return_id: UUID) -> tuple[Facts, Computed]:
    facts, resource = await _loaded(ctx, return_id)
    await authorise(ctx, READ, resource)
    return facts, compute(facts)


async def pending_count(tenant: TenantContext, return_id: UUID) -> int:
    async with tenant_session(tenant) as session:
        return int(await session.scalar(_PENDING, {"r": return_id}) or 0)


async def open_flags(tenant: TenantContext, return_id: UUID) -> int:
    """The Fixed Assets section's open flags: flagged assets and undecided change requests."""
    async with tenant_session(tenant) as session:
        flagged = int(
            await session.scalar(
                text(
                    "SELECT count(*) FROM fixed_assets WHERE work_item_id = :r AND status = 'flag'"
                ),
                {"r": return_id},
            )
            or 0
        )
    return flagged + await pending_count(tenant, return_id)


def _defaults(recovery_class: str) -> tuple[str, str]:
    if recovery_class in e3.REAL_PROPERTY:
        return "SL", "MM"
    return ("150DB" if recovery_class in ("15", "20") else "200DB"), "HY"


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.client or ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def create(
    ctx: AuthContext,
    return_id: UUID,
    *,
    description: str,
    property_key: str,
    placed_in_service: date,
    cost: Decimal,
    recovery_class: str,
) -> UUID:
    """A person adds an asset (module docstring)."""
    _human(ctx, CREATE)
    facts, resource = await _loaded(ctx, return_id)
    await authorise(ctx, CREATE, resource)
    if facts.status in LOCKED:
        raise ReturnLocked(facts={"work_item_id": str(return_id)})
    prop = next((p for p in facts.properties if p.code == property_key), None)
    if prop is None:
        raise NotFound("tax_property")
    method, convention = _defaults(recovery_class)
    asset_no = max((a.asset_no for a in facts.assets), default=0) + 1
    draft = AssetRecord(
        UUID(int=0), asset_no, description, prop.id, prop.code, placed_in_service, None, None,
        None, cost, recovery_class, method, convention, ZERO, ZERO, True, "ok", 1, False,
    )  # fmt: skip
    engine = draft.engine_asset()
    row = None if engine is None else e3.register([engine], facts.tax_year).rows[0]
    current = Decimal(row.current if row else 0)
    prior = Decimal(row.prior if row else 0)
    scope = Scope(engagement_id=facts.engagement_id, work_item_id=return_id)
    async with uow(ctx.tenant) as tx:
        asset_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO fixed_assets (tenant_id, engagement_id, work_item_id, "
                    "property_id, asset_no, description, placed_in_service_on, cost, "
                    "recovery_class, method, "
                    "convention, accum_bop, current_year, accum_eop, engine_name, engine_version, "
                    "inputs_hash) VALUES (:t, :e, :r, :p, :n, :d, :pis, :c, :cls, :m, :cv, :bop, "
                    ":cy, :eop, :en, :ev, :h) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": facts.engagement_id,
                    "r": return_id,
                    "p": prop.id,
                    "n": asset_no,
                    "d": description,
                    "pis": placed_in_service,
                    "c": cost,
                    "cls": _CLASS_TO_DB.get(recovery_class, recovery_class),
                    "m": _METHOD_TO_DB[method],
                    "cv": convention.lower(),
                    "bop": prior,
                    "cy": current,
                    "eop": prior + current,
                    "en": ENGINE,
                    "ev": e3.ENGINE_VERSION,
                    "h": inputs_hash((draft,), facts.tax_year),
                },
            )
        ).scalar_one()
        await _version(tx, ctx, UUID(str(asset_id)), replace(draft, id=UUID(str(asset_id))), None)
        tx.record("fixed_asset.created", target=Target(TARGET, UUID(str(asset_id))), scope=scope)
    return UUID(str(asset_id))


async def _version(
    tx: UnitOfWork, ctx: AuthContext, asset_id: UUID, record: AssetRecord, request_id: UUID | None
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO fixed_asset_versions (tenant_id, engagement_id, work_item_id, asset_id, "
            "version, image, proposal_id, changed_by) SELECT tenant_id, engagement_id, "
            "work_item_id, id, :v, CAST(:img AS jsonb), :q, :by FROM fixed_assets WHERE id = :a"
        ),
        {
            "a": asset_id,
            "v": record.version,
            "img": json.dumps(record.image()),
            "q": request_id,
            "by": ctx.user_id,
        },
    )


def _jsonable(change: dict[str, object]) -> dict[str, object]:
    return {
        k: (v.isoformat() if isinstance(v, date) else str(v) if isinstance(v, Decimal) else v)
        for k, v in change.items()
        if v is not None
    }


async def propose_change(
    ctx: AuthContext,
    return_id: UUID,
    asset_id: UUID,
    *,
    change: dict[str, object],
    expected_version: int,
    citation_ids: list[UUID],
) -> UUID:
    """A person's ghost value (module docstring): nothing changes until a reviewer decides."""
    _human(ctx, PROPOSE)
    facts, resource = await _loaded(ctx, return_id)
    await authorise(ctx, PROPOSE, resource)
    if facts.status in LOCKED:
        raise ReturnLocked(facts={"work_item_id": str(return_id)})
    asset = next((a for a in facts.assets if a.id == asset_id), None)
    if asset is None:
        raise NotFound(TARGET)
    if asset.version != expected_version:
        raise ProposalChanged(facts={"version": asset.version})
    body = _jsonable({k: change.get(k) for k in CHANGE_FIELDS})
    if not body:
        raise ProposalChanged(facts={"fields": 0})
    try:
        _apply(asset, body)  # E3's own rules (real property is SL/MM): an impossible ghost refuses
    except ValueError:
        raise ProposalChanged(facts={"fields": len(body), "valid": False}) from None
    async with uow(ctx.tenant) as tx:
        request_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO fixed_asset_change_requests (tenant_id, engagement_id, "
                    "work_item_id, asset_id, expected_version, change, citation_ids, "
                    "requested_by) "
                    "VALUES (:t, :e, :r, :a, :v, CAST(:c AS jsonb), CAST(:ids AS uuid[]), :by) "
                    "RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": facts.engagement_id,
                    "r": return_id,
                    "a": asset_id,
                    "v": expected_version,
                    "c": json.dumps(body),
                    "ids": [str(i) for i in citation_ids],
                    "by": ctx.user_id,
                },
            )
        ).scalar_one()
        tx.record(
            "fixed_asset.change_proposed",
            target=Target(TARGET, asset_id),
            after=Ref(request=UUID(str(request_id)), version=expected_version),
            scope=Scope(engagement_id=facts.engagement_id, work_item_id=return_id),
        )
    return UUID(str(request_id))


def _apply(asset: AssetRecord, change: dict[str, object]) -> AssetRecord:
    """The asset as the change would make it (validated by E3's own rules)."""
    cls = str(change.get("recovery_class", asset.recovery_class))
    convention = str(change.get("convention", asset.convention))
    method = asset.method
    if "recovery_class" in change:
        method, default_convention = _defaults(cls)
        if "convention" not in change:
            convention = default_convention

    def day(key: str, current: date | None) -> date | None:
        raw = change.get(key)
        return current if raw is None else date.fromisoformat(str(raw))

    out = replace(
        asset,
        recovery_class=cls,
        method=method,
        convention=convention,
        bonus_pct=Decimal(str(change.get("bonus_pct", asset.bonus_pct))),
        sec179=Decimal(str(change.get("sec179", asset.sec179))),
        acquired_on=day("acquired_on", asset.acquired_on),
        binding_contract_on=day("binding_contract_on", asset.binding_contract_on),
        version=asset.version + 1,
    )
    out.engine_asset()  # raises ValueError on an impossible combination (real property on HY)
    return out


@dataclass(frozen=True)
class Decided:
    request_id: UUID
    decision: Literal["approved", "rejected"]
    current: int  # the register's depreciation after the decision (733,500)
    checkpoint_id: UUID | None


async def decide(
    ctx: AuthContext,
    return_id: UUID,
    request_id: UUID,
    *,
    approve: bool,
    reason: str | None,
) -> Decided:
    """A reviewer's decision (module docstring)."""
    from abacus.modules.review.api import save_checkpoint
    from abacus.modules.tax.workbook_service import WORKBOOK, CellWrite, write_cells

    _human(ctx, APPROVE)
    facts, resource = await _loaded(ctx, return_id)
    await authorise(ctx, APPROVE, resource)
    async with tenant_session(ctx.tenant) as session:
        req = (
            await session.execute(
                text(
                    "SELECT q.id, q.asset_id, q.expected_version, q.change, q.requested_by, "
                    "d.id AS decided FROM fixed_asset_change_requests q LEFT JOIN "
                    "fixed_asset_change_decisions d ON d.request_id = q.id "
                    "WHERE q.id = :q AND q.work_item_id = :r"
                ),
                {"q": request_id, "r": return_id},
            )
        ).first()
    if req is None:
        raise NotFound("fixed_asset_change")
    if req.decided is not None:
        raise ChangeAlreadyDecided(facts={"request_id": str(request_id)})
    if UUID(str(req.requested_by)) == ctx.user_id:
        raise Forbidden(APPROVE, "segregation")  # the requester never decides their own change
    if not approve and not (reason or "").strip():
        raise ProposalChanged(facts={"reason": "required"})
    asset = next((a for a in facts.assets if a.id == UUID(str(req.asset_id))), None)
    if asset is None:
        raise NotFound(TARGET)
    if approve and asset.version != int(req.expected_version):
        raise ProposalChanged(facts={"version": asset.version})
    scope = Scope(engagement_id=facts.engagement_id, work_item_id=return_id)
    if not approve:
        async with uow(ctx.tenant) as tx:
            await _decision(tx, ctx, request_id, "rejected", reason)
            tx.record("fixed_asset.change_rejected", target=Target(TARGET, asset.id), scope=scope)
        return Decided(request_id, "rejected", compute(facts).register.current, None)
    changed = _apply(asset, dict(req.change))
    after = replace(facts, assets=tuple(changed if a.id == asset.id else a for a in facts.assets))
    computed = compute(after)
    writes: list[CellWrite] = []
    async with uow(ctx.tenant) as tx:
        await _decision(tx, ctx, request_id, "approved", None)
        await tx.session.execute(
            text(
                "UPDATE fixed_assets SET recovery_class = :cls, method = :m, convention = :cv, "
                "bonus_pct = :b, sec179 = :s, acquired_on = :acq, binding_contract_on = :bind, "
                "version = version + 1 WHERE id = :a AND version = :v"
            ),
            {
                "a": asset.id, "v": asset.version,
                "cls": _CLASS_TO_DB.get(changed.recovery_class, changed.recovery_class),
                "m": _METHOD_TO_DB[changed.method], "cv": changed.convention.lower(),
                "b": changed.bonus_pct, "s": changed.sec179, "acq": changed.acquired_on,
                "bind": changed.binding_contract_on,
            },
        )  # fmt: skip
        await _version(tx, ctx, asset.id, changed, request_id)
        for a in after.assets:
            row = computed.by_asset.get(str(a.id))
            if row is None:
                continue
            await tx.session.execute(
                text(
                    "UPDATE fixed_assets SET accum_bop = :bop, current_year = :cy, "
                    "accum_eop = :eop, engine_name = :en, engine_version = :ev, inputs_hash = :h, "
                    "computed_at = clock_timestamp() WHERE id = :a AND (current_year <> :cy OR "
                    "accum_bop <> :bop OR inputs_hash <> :h)"
                ),
                {"a": a.id, "bop": row.prior, "cy": row.current, "eop": row.accumulated,
                 "en": ENGINE, "ev": e3.ENGINE_VERSION, "h": computed.inputs_hash},
            )  # fmt: skip
            cell = facts.cells.get(a.asset_no)
            if cell is not None and a.id == asset.id:
                writes.append(CellWrite(cell, Decimal(row.current), "formula"))
        if writes:
            await write_cells(
                tx, engagement_id=facts.engagement_id, return_id=return_id, writes=writes
            )
        tx.record(
            "fixed_asset.change_approved",
            target=Target(TARGET, asset.id),
            after=Ref(request=request_id, version=changed.version),
            scope=scope,
        )
    checkpoint = await save_checkpoint(ctx, WORKBOOK, return_id, "Fixed asset change approved")
    return Decided(
        request_id, "approved", computed.register.current, getattr(checkpoint, "id", None)
    )


async def _decision(
    tx: UnitOfWork, ctx: AuthContext, request_id: UUID, decision: str, reason: str | None
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO fixed_asset_change_decisions (tenant_id, request_id, decision, reason, "
            "decided_by) VALUES (:t, :q, :d, :why, :by)"
        ),
        {"t": ctx.tenant_id, "q": request_id, "d": decision, "why": reason, "by": ctx.user_id},
    )


def register() -> None:
    """At the tax api's import: the Fixed Assets section's open flags join its sign-off."""
    from abacus.modules.tax.entity_sections import register_section_flags

    register_section_flags("fixed-assets", open_flags)


__all__ = [
    "APPROVE",
    "ChangeAlreadyDecided",
    "Computed",
    "Decided",
    "Facts",
    "ProposalChanged",
    "compute",
    "create",
    "decide",
    "facts_of",
    "open_flags",
    "propose_change",
    "read",
    "register",
    "tallies",
]
