"""The estate workpaper service (T-07-T22; T-07 §4, F12–F14; SPEC-656 AC-12.1 to AC-14.2; amber).

TXT-04's sections over the estate engine (`compute/estate.py`): the inventory (six schedules and
their basis to the estate's 1041), the deductions (with the §642(g) election a person records),
the computation (every figure labelled "Accrued tie-out (shadow)", DEC-77), the gift history and
the derivation tiles. Inputs are insert-only versions set by a person with a reason; an asset is
`valued` only with a citation (the migration's CHECK as well). Each read recomputes when the
inputs changed and stores the new version (idempotent by `inputs_hash`). The due chip is the
practice due-date engine's (Form 706: date of death + 9 months; Form 4768: + 6 months, rolled
under §7503), with the same rule computed here when the firm's published rules hold no 706 row.
Approve values is P-04's L4 on the `estate_values` reviewable (DF-08; partner only, the matrix's).
Request appraisal… links an asset to a C5 request item; the request is a person's send (SHL-14).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, names_of
from abacus.modules.organisations.api import entity_name
from abacus.modules.practice.api import due_dates_for
from abacus.modules.review.api import (
    Reviewable,
    ReviewableFacts,
    register_reviewable,
    register_reviewable_facts,
    sign_off_states,
)
from abacus.modules.tax.compute import estate as engine
from abacus.modules.tax.estate_contract import (
    EstateAssetEditIn,
    EstateAssetIn,
    EstateAssetOut,
    EstateComputationLineOut,
    EstateComputationOut,
    EstateDeductionEditIn,
    EstateDeductionIn,
    EstateDeductionOut,
    EstateDeductionsOut,
    EstateDerivationOut,
    EstateDerivationRowOut,
    EstateDueChipOut,
    EstateGiftsOut,
    EstateHeaderOut,
    EstateInventoryOut,
    EstateInventoryTotalsOut,
    EstateStateCardOut,
    EstateTallyOut,
    EstateWithoutDsueOut,
    GiftHistoryEditIn,
    GiftHistoryIn,
    GiftHistoryRowOut,
)
from abacus.modules.tax.instruments.service import _authorised, _return

TARGET: Final = "estate_values"
READ: Final = "estate_workpaper.read"
EDIT: Final = "estate_workpaper.edit"
_AAD_REASON: Final = "tax.estate.reason"
_AAD_DONEE: Final = "tax.estate.donee"


class EstateProfileMissing(DomainConflict):
    code = "estate_profile_missing"


class ValuedNeedsCitation(DomainInvalid):
    code = "uncited_change"


class VersionConflict(DomainConflict):
    code = "version_conflict"


def _person(ctx: AuthContext) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(EDIT, "role")


async def _scope(ctx: AuthContext, return_id: UUID, action: str) -> tuple[UUID, UUID, int]:
    r = await _return(ctx.tenant, return_id)
    if r.form != "706":
        raise NotFound("tax_return")
    await _authorised(ctx, r.engagement_id, action)
    return r.engagement_id, r.client_entity_id, r.tax_year


_PROFILE: Final = text(
    "SELECT date_of_death, dsue_amount, residence_state FROM estate_profiles WHERE client_entity_id = :e"
)
_ASSETS: Final = text(
    "SELECT i.id, i.schedule, i.description, i.basis_rule, v.seq, v.dod_value, v.avd_value, v.status, "
    "v.support_text, v.request_item_id, v.citation_ids FROM estate_inventory_items i JOIN LATERAL "
    "(SELECT * FROM estate_inventory_item_versions x WHERE x.item_id = i.id ORDER BY x.seq DESC "
    "LIMIT 1) v ON true WHERE i.work_item_id = :r ORDER BY i.schedule, i.created_at, i.id"
)
_DEDUCTIONS: Final = text(
    "SELECT d.id, d.schedule, d.description, v.seq, v.amount, v.estimated, v.election, "
    "v.citation_ids FROM estate_deductions d JOIN LATERAL (SELECT * FROM estate_deduction_versions x "
    "WHERE x.deduction_id = d.id ORDER BY x.seq DESC LIMIT 1) v ON true WHERE d.work_item_id = :r "
    "ORDER BY d.schedule, d.created_at, d.id"
)
_GIFTS: Final = text(
    "SELECT g.id, g.year, g.donee_name_sealed, g.asset, v.seq, v.gift_amount, v.form_709_status, "
    "v.filed_on, v.evidence_version_id FROM gift_history_items g JOIN LATERAL (SELECT * FROM "
    "gift_history_item_versions x WHERE x.gift_id = g.id ORDER BY x.seq DESC LIMIT 1) v ON true "
    "WHERE g.client_entity_id = :e ORDER BY g.year, g.created_at, g.id"
)
_CURRENT: Final = text(
    "SELECT id, version_no, inputs_hash, outputs, content_hash, engine_version, parameter_set, label "
    "FROM estate_computations WHERE work_item_id = :r ORDER BY version_no DESC LIMIT 1"
)


async def _profile(session: AsyncSession, entity: UUID) -> tuple[date, Decimal, str | None]:
    row = (await session.execute(_PROFILE, {"e": entity})).first()
    if row is None:
        raise EstateProfileMissing(facts={"client_entity": "no_profile"})
    return row[0], Decimal(row[1]), row[2]


def _add_months(day: date, months: int) -> date:
    year, month = divmod(day.month - 1 + months, 12)
    year, month = day.year + year, month + 1
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def _roll(day: date) -> date:
    while day.weekday() >= 5:  # §7503: Saturday or Sunday to Monday
        day += timedelta(days=1)
    return day


async def due_chip(tax_year: int, date_of_death: date, extended: bool = False) -> EstateDueChipOut:
    """Form 706: DOD + 9 months; Form 4768: + 6 months; both rolled (AC-14.1). The firm's
    published due-date rules win; without a 706 rule the statutory rule is computed here."""
    try:
        found = await due_dates_for("706", tax_year, date_of_death, event_date=date_of_death)
        due, ext = found.original_due_on, found.extended_due_on or found.original_due_on
    except LookupError:
        params = engine.parameters(tax_year)
        original = _add_months(date_of_death, params.filing_months)
        due = _roll(original)
        ext = _roll(_add_months(original, params.extension_months))
    form_8971 = due + timedelta(days=30)
    return EstateDueChipOut(due_on=due, extension_to=ext, extended=extended, form_8971_due_on=form_8971)


async def _inputs(session: AsyncSession, tenant: TenantContext, return_id: UUID, entity: UUID, tax_year: int) -> tuple[engine.EstateInputs, list[object], list[object], list[object]]:
    _, dsue, state = await _profile(session, entity)
    assets = list((await session.execute(_ASSETS, {"r": return_id})).all())
    deductions = list((await session.execute(_DEDUCTIONS, {"r": return_id})).all())
    gifts = list((await session.execute(_GIFTS, {"e": entity})).all())
    inputs = engine.EstateInputs(
        tax_year,
        tuple(engine.Asset(str(a[0]), a[1], Decimal(a[5]), None if a[6] is None else Decimal(a[6]), a[3]) for a in assets),
        tuple(engine.Deduction(str(d[0]), d[1], Decimal(d[4])) for d in deductions),
        tuple(engine.Gift(str(g[0]), int(g[1]), Decimal(g[5])) for g in gifts),
        dsue=dsue,
        residence_state=state,
    )
    del tenant
    return inputs, assets, deductions, gifts


def _content(outputs: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _computed(ctx: AuthContext, return_id: UUID) -> tuple[engine.EstateResult, dict[str, object], tuple[UUID, int, str, str, str], list[object], list[object], list[object]]:
    """The current computation, recomputed and stored when the inputs moved."""
    engagement, entity, tax_year = await _scope(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        inputs, assets, deductions, gifts = await _inputs(session, ctx.tenant, return_id, entity, tax_year)
        current = (await session.execute(_CURRENT, {"r": return_id})).first()
    result = engine.compute(inputs)
    outputs = engine.outputs_of(result)
    if current is not None and current[2] == result.inputs_hash:
        meta = (current[0], int(current[1]), str(current[5]), str(current[6]), str(current[4]))
        return result, outputs, meta, assets, deductions, gifts
    content = _content(outputs)
    version = 1 if current is None else int(current[1]) + 1
    async with uow(ctx.tenant) as tx:
        cid = await tx.session.scalar(
            text(
                "INSERT INTO estate_computations (tenant_id, engagement_id, work_item_id, version_no, "
                "inputs_hash, content_hash, engine_name, engine_version, parameter_set, outputs, "
                "prior_computation_id) VALUES (:t, :e, :w, :v, :ih, :ch, :en, :ev, :ps, "
                "CAST(:o AS jsonb), :prior) ON CONFLICT (work_item_id, version_no) DO NOTHING RETURNING id"
            ),
            {"t": ctx.tenant_id, "e": engagement, "w": return_id, "v": version, "ih": result.inputs_hash,
             "ch": content, "en": result.engine_name, "ev": result.engine_version, "ps": result.parameter_set,
             "o": json.dumps(outputs, sort_keys=True), "prior": None if current is None else current[0]},
        )  # fmt: skip
        tx.record(
            "estate_computation.computed", target=Target("tax_return", return_id),
            after=Ref(version=version, inputs_hash=result.inputs_hash),
            scope=Scope(engagement_id=engagement, work_item_id=return_id),
        )  # fmt: skip
    meta = (cast(UUID, cid), version, result.engine_version, result.parameter_set, content)
    return result, outputs, meta, assets, deductions, gifts


async def _header(ctx: AuthContext, return_id: UUID, result: engine.EstateResult, content_hash: str) -> EstateHeaderOut:
    r = await _return(ctx.tenant, return_id)
    async with tenant_session(ctx.tenant) as session:
        dod, _, _ = await _profile(session, r.client_entity_id)
    name = await entity_name(ctx.tenant, r.client_entity_id) or ""
    states = await sign_off_states(ctx.tenant, TARGET, [return_id], {return_id: content_hash})
    l4 = next((s for s in states.get(return_id, []) if s.level == 4), None)
    signer = None if l4 is None or l4.signed_by is None else (await names_of([l4.signed_by])).get(l4.signed_by)
    return EstateHeaderOut(
        return_id=return_id, client_entity_id=r.client_entity_id, decedent_name=name.removeprefix("Estate of ").strip() or name,
        date_of_death=dod, due=await due_chip(r.tax_year, dod),
        tallies=[
            EstateTallyOut(key="gross_estate", label="Gross estate", value=result.gross_estate_dod, state=None),
            EstateTallyOut(key="deductions", label="Deductions", value=result.deductions, state=None),
            EstateTallyOut(key="taxable_estate", label="Taxable estate", value=result.taxable_estate, state=None),
            EstateTallyOut(key="applicable_exclusion", label="Applicable exclusion", value=result.applicable_exclusion, state=None),
            EstateTallyOut(key="net_tax", label="Net estate tax", value=result.net_tax, state=None),
        ],
        values_signed_by_initials=None if signer is None else "".join(w[0] for w in signer.split()[:2]).upper(),
        values_sign_off_stale=l4 is not None and l4.stale,
        allowed_actions=["estate_workpaper.edit", "sign_off.l4", "request_item.send"],
    )  # fmt: skip


async def inventory(ctx: AuthContext, return_id: UUID) -> EstateInventoryOut:
    result, _, meta, assets, _, _ = await _computed(ctx, return_id)
    out = [
        EstateAssetOut(
            id=a[0], schedule=a[1], description=a[2], dod_value=Decimal(a[5]),
            avd_value=None if a[6] is None else Decimal(a[6]),
            basis_to_1041=result.basis_by_asset.get(str(a[0])), basis_rule=a[3], support_text=a[8],
            status=a[7], request_item_id=a[9], citation_ids=list(a[10] or ()), version=int(a[4]),
        )  # fmt: skip
        for a in cast(Sequence[Sequence[object]], assets)  # pyright: ignore[reportArgumentType,reportUnknownArgumentType]
    ]
    return EstateInventoryOut(
        header=await _header(ctx, return_id, result, meta[4]),
        assets=out,
        totals=EstateInventoryTotalsOut(dod_value=result.gross_estate_dod, avd_value=result.gross_estate_avd, basis_to_1041=result.basis_to_1041),
    )


async def deductions(ctx: AuthContext, return_id: UUID) -> EstateDeductionsOut:
    result, _, meta, _, rows, _ = await _computed(ctx, return_id)
    return EstateDeductionsOut(
        header=await _header(ctx, return_id, result, meta[4]),
        deductions=[
            EstateDeductionOut(
                id=d[0], schedule=d[1], description=d[2], amount=Decimal(d[4]), estimated=bool(d[5]),
                election=d[6], citation_ids=list(d[7] or ()), version=int(d[3]),
            )  # fmt: skip
            for d in cast(Sequence[Sequence[object]], rows)  # pyright: ignore[reportArgumentType,reportUnknownArgumentType]
        ],
        total=result.deductions,
    )


async def computation(ctx: AuthContext, return_id: UUID) -> EstateComputationOut:
    result, _, meta, _, _, _ = await _computed(ctx, return_id)
    lines = [
        ("taxable_estate", "Taxable estate", result.taxable_estate, None),
        ("adjusted_taxable_gifts", "Adjusted taxable gifts", result.adjusted_taxable_gifts, None),
        ("tentative_tax_base", "Tentative tax base", result.tentative_tax_base, None),
        ("tentative_tax", "Tentative tax", result.tentative_tax, "tentative_tax"),
        ("bea", "Basic exclusion amount (2026)", result.bea, None),
        ("dsue", "DSUE", result.dsue, None),
        ("applicable_exclusion", "Applicable exclusion", result.applicable_exclusion, "applicable_exclusion"),
        ("credit", "Applicable credit", result.credit, "credit"),
        ("net_tax", "Net estate tax", None if result.net_tax == 0 else result.net_tax, None),
    ]
    banner = (
        f"Form 706 required: gross estate plus adjusted taxable gifts ({result.filing_threshold_amount:,.0f}) "
        f"exceeds the {result.bea:,.0f} basic exclusion amount"
        if result.filing_required else None
    )  # fmt: skip
    return EstateComputationOut(
        header=await _header(ctx, return_id, result, meta[4]),
        computation_id=meta[0], version_no=meta[1], engine_version=meta[2], inputs_hash=result.inputs_hash,
        parameter_set=meta[3], label="accrued_tie_out_shadow",
        lines=[EstateComputationLineOut(key=k, label=lbl, value=v, derivation_tile=t) for k, lbl, v, t in lines],
        without_dsue=EstateWithoutDsueOut(credit=result.credit_without_dsue, tax=result.tax_without_dsue),
        state_card=EstateStateCardOut(jurisdiction=result.state or "", required=bool(result.state_required), status="pending", issue_id=None),
        filing_required=result.filing_required, filing_banner=banner, avd_available=result.avd_available,
    )  # fmt: skip


async def gifts(ctx: AuthContext, return_id: UUID) -> EstateGiftsOut:
    result, _, meta, _, _, rows = await _computed(ctx, return_id)
    by_key = {g.key: g for g in result.gifts}
    out: list[GiftHistoryRowOut] = []
    for g in cast(Sequence[Sequence[object]], rows):  # pyright: ignore[reportArgumentType,reportUnknownArgumentType]
        line = by_key[str(g[0])]
        donee = (await open_sealed(ctx.tenant_id, cast(bytes, g[2]), _AAD_DONEE)).decode()
        out.append(
            GiftHistoryRowOut(
                id=cast(UUID, g[0]), year=int(cast(int, g[1])), donee_name=donee, asset=str(g[3]),
                gift_amount=line.amount, annual_exclusion=line.exclusion, taxable_gift=line.taxable,
                form_709_status=g[6],  # pyright: ignore[reportArgumentType] -- a registry word
                filed_on=cast(date | None, g[7]), evidence_version_id=cast(UUID | None, g[8]), version=int(cast(int, g[4])),
            )  # fmt: skip
        )
    return EstateGiftsOut(
        header=await _header(ctx, return_id, result, meta[4]), gifts=out,
        adjusted_taxable_gifts=result.adjusted_taxable_gifts, tie="tie",
    )  # fmt: skip


async def derivation(ctx: AuthContext, return_id: UUID, tile: str) -> EstateDerivationOut:
    result, _, _, _, _, _ = await _computed(ctx, return_id)
    rows: dict[str, list[tuple[str, Decimal | None]]] = {
        "applicable_exclusion": [("Basic exclusion amount (2026)", result.bea), ("DSUE (Helen's portability election)", result.dsue), ("Applicable exclusion", result.applicable_exclusion)],
        "tentative_tax": [("Tentative tax base", result.tentative_tax_base), ("Tentative tax (§2001(c))", result.tentative_tax)],
        "credit": [("Tax on the applicable exclusion", result.credit), ("Without DSUE", result.credit_without_dsue)],
    }
    if tile not in rows:
        raise NotFound("derivation")
    note = "Computed by the Accrued estate engine; the engine of record is CCH Axcess (Accrued tie-out, shadow)."
    return EstateDerivationOut(tile=tile, rows=[EstateDerivationRowOut(label=lbl, value=v) for lbl, v in rows[tile]], note=note, provenance_id=None)


# --- edits ---------------------------------------------------------------------------------------


async def _sealed(ctx: AuthContext, value: str | None, aad: str) -> bytes | None:
    return None if value is None else await seal(ctx.tenant_id, value.encode(), aad)


async def add_asset(ctx: AuthContext, return_id: UUID, body: EstateAssetIn) -> EstateAssetOut:
    _person(ctx)
    engagement, _, _ = await _scope(ctx, return_id, EDIT)
    async with uow(ctx.tenant) as tx:
        item = await tx.session.scalar(
            text("INSERT INTO estate_inventory_items (tenant_id, engagement_id, work_item_id, schedule, description, basis_rule, created_by) VALUES (:t, :e, :w, :s, :d, :b, :u) RETURNING id"),
            {"t": ctx.tenant_id, "e": engagement, "w": return_id, "s": body.schedule, "d": body.description, "b": body.basis_rule, "u": ctx.user_id},
        )  # fmt: skip
        status = "valued" if body.citation_ids else "gathering_support"
        await tx.session.execute(
            text("INSERT INTO estate_inventory_item_versions (tenant_id, item_id, seq, dod_value, avd_value, status, support_text, citation_ids, set_by_kind, set_by_id) VALUES (:t, :i, 1, :dod, :avd, :st, :sup, :c, 'human', :u)"),
            {"t": ctx.tenant_id, "i": item, "dod": body.dod_value, "avd": body.avd_value, "st": status, "sup": body.support_text, "c": list(body.citation_ids), "u": ctx.user_id},
        )  # fmt: skip
        tx.record("estate_asset.created", target=Target("estate_asset", cast(UUID, item)), scope=Scope(engagement_id=engagement, work_item_id=return_id))
    return next(a for a in (await inventory(ctx, return_id)).assets if a.id == item)


async def edit_asset(ctx: AuthContext, asset_id: UUID, body: EstateAssetEditIn) -> EstateAssetOut:
    _person(ctx)
    if body.status == "valued" and not body.citation_ids:
        raise ValuedNeedsCitation(facts={"field": "citation_ids"})
    async with tenant_session(ctx.tenant) as session:
        head = (await session.execute(text("SELECT work_item_id, engagement_id FROM estate_inventory_items WHERE id = :i"), {"i": asset_id})).first()
    if head is None:
        raise NotFound("estate_asset")
    await _scope(ctx, head[0], EDIT)
    async with uow(ctx.tenant) as tx:
        current = await tx.session.scalar(text("SELECT max(seq) FROM estate_inventory_item_versions WHERE item_id = :i"), {"i": asset_id})
        if int(current or 0) != body.expected_version:
            raise VersionConflict(facts={"current_version": int(current or 0)})
        await tx.session.execute(
            text("INSERT INTO estate_inventory_item_versions (tenant_id, item_id, seq, dod_value, avd_value, status, support_text, citation_ids, set_by_kind, set_by_id, reason_sealed) VALUES (:t, :i, :s, :dod, :avd, :st, :sup, :c, 'human', :u, :r)"),
            {"t": ctx.tenant_id, "i": asset_id, "s": body.expected_version + 1, "dod": body.dod_value, "avd": body.avd_value, "st": body.status, "sup": body.support_text, "c": list(body.citation_ids), "u": ctx.user_id, "r": await _sealed(ctx, body.reason, _AAD_REASON)},
        )  # fmt: skip
        tx.record("estate_asset.changed", target=Target("estate_asset", asset_id), after=Ref(version=body.expected_version + 1), scope=Scope(engagement_id=head[1], work_item_id=head[0]))
    return next(a for a in (await inventory(ctx, head[0])).assets if a.id == asset_id)


async def add_deduction(ctx: AuthContext, return_id: UUID, body: EstateDeductionIn) -> EstateDeductionOut:
    _person(ctx)
    engagement, _, _ = await _scope(ctx, return_id, EDIT)
    async with uow(ctx.tenant) as tx:
        did = await tx.session.scalar(
            text("INSERT INTO estate_deductions (tenant_id, engagement_id, work_item_id, schedule, description, created_by) VALUES (:t, :e, :w, :s, :d, :u) RETURNING id"),
            {"t": ctx.tenant_id, "e": engagement, "w": return_id, "s": body.schedule, "d": body.description, "u": ctx.user_id},
        )  # fmt: skip
        await tx.session.execute(
            text("INSERT INTO estate_deduction_versions (tenant_id, deduction_id, seq, amount, estimated, election, citation_ids, set_by_kind, set_by_id) VALUES (:t, :d, 1, :a, :est, :el, :c, 'human', :u)"),
            {"t": ctx.tenant_id, "d": did, "a": body.amount, "est": body.estimated, "el": str(body.election), "c": list(body.citation_ids), "u": ctx.user_id},
        )  # fmt: skip
        tx.record("estate_deduction.created", target=Target("estate_deduction", cast(UUID, did)), scope=Scope(engagement_id=engagement, work_item_id=return_id))
    return next(d for d in (await deductions(ctx, return_id)).deductions if d.id == did)


async def edit_deduction(ctx: AuthContext, deduction_id: UUID, body: EstateDeductionEditIn) -> EstateDeductionOut:
    """The §642(g) election is a person's choice with a reason (AC-12.4)."""
    _person(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = (await session.execute(text("SELECT work_item_id, engagement_id FROM estate_deductions WHERE id = :d"), {"d": deduction_id})).first()
    if head is None:
        raise NotFound("estate_deduction")
    await _scope(ctx, head[0], EDIT)
    async with uow(ctx.tenant) as tx:
        current = await tx.session.scalar(text("SELECT max(seq) FROM estate_deduction_versions WHERE deduction_id = :d"), {"d": deduction_id})
        if int(current or 0) != body.expected_version:
            raise VersionConflict(facts={"current_version": int(current or 0)})
        await tx.session.execute(
            text("INSERT INTO estate_deduction_versions (tenant_id, deduction_id, seq, amount, estimated, election, citation_ids, set_by_kind, set_by_id, reason_sealed) VALUES (:t, :d, :s, :a, :est, :el, :c, 'human', :u, :r)"),
            {"t": ctx.tenant_id, "d": deduction_id, "s": body.expected_version + 1, "a": body.amount, "est": body.estimated, "el": str(body.election), "c": list(body.citation_ids), "u": ctx.user_id, "r": await _sealed(ctx, body.reason, _AAD_REASON)},
        )  # fmt: skip
        tx.record("estate_deduction.changed", target=Target("estate_deduction", deduction_id), after=Ref(version=body.expected_version + 1), scope=Scope(engagement_id=head[1], work_item_id=head[0]))
    return next(d for d in (await deductions(ctx, head[0])).deductions if d.id == deduction_id)


async def _entity_return(ctx: AuthContext, client_entity_id: UUID) -> UUID:
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text("SELECT work_item_id FROM tax_returns WHERE client_entity_id = :e AND form = '706' ORDER BY tax_year DESC LIMIT 1"),
            {"e": client_entity_id},
        )
    if found is None:
        raise NotFound("tax_return")
    return cast(UUID, found)


async def add_gift(ctx: AuthContext, client_entity_id: UUID, body: GiftHistoryIn) -> GiftHistoryRowOut:
    _person(ctx)
    return_id = await _entity_return(ctx, client_entity_id)
    engagement, _, _ = await _scope(ctx, return_id, EDIT)
    async with uow(ctx.tenant) as tx:
        gid = await tx.session.scalar(
            text("INSERT INTO gift_history_items (tenant_id, client_entity_id, year, donee_name_sealed, asset, created_by) VALUES (:t, :e, :y, :d, :a, :u) RETURNING id"),
            {"t": ctx.tenant_id, "e": client_entity_id, "y": body.year, "d": await _sealed(ctx, body.donee_name, _AAD_DONEE), "a": body.asset, "u": ctx.user_id},
        )  # fmt: skip
        await tx.session.execute(
            text("INSERT INTO gift_history_item_versions (tenant_id, gift_id, seq, gift_amount, form_709_status, filed_on, evidence_version_id, set_by_kind, set_by_id) VALUES (:t, :g, 1, :a, :s, :f, :ev, 'human', :u)"),
            {"t": ctx.tenant_id, "g": gid, "a": body.gift_amount, "s": str(body.form_709_status), "f": body.filed_on, "ev": body.evidence_version_id, "u": ctx.user_id},
        )  # fmt: skip
        tx.record("gift_history.created", target=Target("gift_history_item", cast(UUID, gid)), scope=Scope(engagement_id=engagement, work_item_id=return_id))
    return next(g for g in (await gifts(ctx, return_id)).gifts if g.id == gid)


async def edit_gift(ctx: AuthContext, gift_id: UUID, body: GiftHistoryEditIn) -> GiftHistoryRowOut:
    _person(ctx)
    async with tenant_session(ctx.tenant) as session:
        entity = await session.scalar(text("SELECT client_entity_id FROM gift_history_items WHERE id = :g"), {"g": gift_id})
    if entity is None:
        raise NotFound("gift_history_item")
    return_id = await _entity_return(ctx, cast(UUID, entity))
    engagement, _, _ = await _scope(ctx, return_id, EDIT)
    async with uow(ctx.tenant) as tx:
        current = await tx.session.scalar(text("SELECT max(seq) FROM gift_history_item_versions WHERE gift_id = :g"), {"g": gift_id})
        if int(current or 0) != body.expected_version:
            raise VersionConflict(facts={"current_version": int(current or 0)})
        await tx.session.execute(
            text("INSERT INTO gift_history_item_versions (tenant_id, gift_id, seq, gift_amount, form_709_status, filed_on, evidence_version_id, set_by_kind, set_by_id, reason_sealed) VALUES (:t, :g, :s, :a, :st, :f, :ev, 'human', :u, :r)"),
            {"t": ctx.tenant_id, "g": gift_id, "s": body.expected_version + 1, "a": body.gift_amount, "st": str(body.form_709_status), "f": body.filed_on, "ev": body.evidence_version_id, "u": ctx.user_id, "r": await _sealed(ctx, body.reason, _AAD_REASON)},
        )  # fmt: skip
        tx.record("gift_history.changed", target=Target("gift_history_item", gift_id), after=Ref(version=body.expected_version + 1), scope=Scope(engagement_id=engagement, work_item_id=return_id))
    return next(g for g in (await gifts(ctx, return_id)).gifts if g.id == gift_id)


# --- the L4 reviewable (DF-08) --------------------------------------------------------------------


async def reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(text("SELECT DISTINCT ON (work_item_id) work_item_id, content_hash FROM estate_computations WHERE engagement_id = :e ORDER BY work_item_id, version_no DESC"), {"e": engagement_id})).all()
    return [Reviewable(TARGET, r[0], f"estate:{r[0]}", "Estate values", r[1], True) for r in rows]


async def facts(tenant: TenantContext, target_id: UUID) -> ReviewableFacts | None:
    async with tenant_session(tenant) as session:
        r = (await session.execute(text("SELECT engagement_id, content_hash, version_no FROM estate_computations WHERE work_item_id = :r ORDER BY version_no DESC LIMIT 1"), {"r": target_id})).first()
    if r is None:
        return None
    return ReviewableFacts(
        target_type=TARGET, target_id=target_id, engagement_id=r[0], content_hash=r[1], version_no=int(r[2]),
        preparer_user_ids=frozenset(), required_levels=(4,), label="Estate values", work_item_id=target_id,
    )  # fmt: skip


def register() -> None:
    register_reviewable(TARGET, reviewables)
    register_reviewable_facts(TARGET, facts)
