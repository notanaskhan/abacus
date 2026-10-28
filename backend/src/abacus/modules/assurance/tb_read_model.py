"""AUD-06's read model on C9 v1: the view by layer and the leadsheet by area (A-02-T10;
TASK-1336; SPEC-333 AC-5, AC-17, AC-18; A-02 §4.1 `trial_balance_view.py`).

Every route authorises its one action on the engagement first (another firm's or a walled
engagement answers 404 with no count, a member without an independence confirmation 403
`independence_pending`), then the flag `ledger.tb_workpaper` (404 off), then reads.

Binding from the #417 security review (DEC-440):
- **Area rules** come from the engagement's *own* applied methodology version, read inside the
  caller's tenant session (`engagements.api.version_detail(ctx.tenant, …)`), on every call:
  there is no cache, so nothing keyed only by a version id can carry one firm's rules into
  another firm's trial balance. Row-level security answers NotFound for a version that is not
  this firm's; an engagement with no methodology applied has no rules (every account is then
  "Unassigned" unless annotated, never dropped).
- The view by layer calls `ledger.require_balanced`: a layer whose debits and credits differ
  answers 409 `layer_unbalanced` with the difference, never a view that does not foot.
- **Code computes, models judge** (ADR-050): every amount, subtotal, balance, Δ and Δ% is
  computed here or in `ledger` in exact `Decimal`; no model is involved and the browser sums
  nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from decimal import Decimal
from types import MappingProxyType
from typing import Annotated, Final, cast, get_args
from uuid import UUID

from fastapi import Depends, Header, Query
from fastapi.responses import Response

from abacus.kernel._flags import LEDGER_TB_WORKPAPER
from abacus.kernel._statuses import (
    TieOutTallyStatus,
    TrialBalanceLabelStatus,
    TrialBalanceLayerStatus,
)
from abacus.kernel.errors import DomainForbidden, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.assurance.tb_contract import (
    XLSX,
    AreaKey,
    DisplayUnit,
    SourceKind,
    TbAction,
    TbChecksSummaryOut,
    TbGroupOut,
    TbLayerBalanceOut,
    TbLayerLineOut,
    TbLayerViewOut,
    TbLeadsheetAreaOut,
    TbLeadsheetRowOut,
    TbLineFlagOut,
    TbProvenanceOut,
    TieIssueLinkIn,
    TieIssueLinkOut,
    tb_router,
)
from abacus.modules.engagements.api import EngagementRef, get_ref, version_detail
from abacus.modules.evidence.api import LayerExport, LayerLine, render_trial_balance_layers
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    allowed_actions,
    authorise,
    current_context,
    engagement_team,
)
from abacus.modules.ledger.api import (
    AreaRule,
    Candidate,
    TbLine,
    TrialBalanceView,
    candidates,
    leadsheets,
    require_balanced,
    trial_balance_view,
)
from abacus.modules.workpapers.api import checks_for, link_issue

UNASSIGNED: Final = "Unassigned"
_ZERO: Final = Decimal("0.00")
_SOURCE_KINDS: Final = frozenset(get_args(SourceKind))
_ACTIONS: Final = tuple(get_args(TbAction))


class IndependencePending(DomainForbidden):
    """C9 §6: a member of the engagement team with no current independence confirmation. Only
    a person on the team gets this far (walls and other firms answer 404 first)."""

    code = "independence_pending"


async def _gate(ctx: AuthContext, engagement_id: UUID) -> EngagementRef:
    """Authorise first (404 for walls and other firms, 403 by role, 403 `independence_pending`
    without an independence confirmation), then the flag (404 off)."""
    ref = await get_ref(ctx, engagement_id)
    try:
        await authorise(ctx, "trial_balance.read", ref.resource())
    except Forbidden as exc:
        if exc.layer == "independence":
            raise IndependencePending(str(engagement_id)) from exc
        raise
    if not await flag_enabled(ctx.tenant, LEDGER_TB_WORKPAPER):
        raise NotFound(LEDGER_TB_WORKPAPER.name)
    return ref


async def area_rules(ctx: AuthContext, ref: EngagementRef) -> tuple[AreaRule, ...]:
    """The engagement's own methodology account rules, as ledger `AreaRule`s named by the
    area's name. Read inside `tenant_session(ctx.tenant)` on every call; never cached."""
    if ref.methodology_version_id is None:
        return ()
    detail = await version_detail(ctx.tenant, ref.methodology_version_id)
    if detail.summary.version_id != ref.methodology_version_id:  # defence in depth
        raise NotFound("methodology_version")
    names = {a.code: a.name for a in detail.areas}
    return tuple(
        AreaRule(names.get(r.area_code, r.area_code), r.account_from, r.account_to)
        for r in detail.rules
    )


def _layer_value(line: TbLine, layer: str) -> Decimal:
    if layer == "aje":
        return line.aje or _ZERO
    if layer == "rje":
        return line.rje or _ZERO
    if layer == "final" and line.final is not None:
        return line.final
    return line.eoy


def _groups(
    lines: Sequence[TbLine], layer: str, flags: dict[str, list[TbLineFlagOut]]
) -> list[TbGroupOut]:
    """One group per audit area, alphabetical, Unassigned last; subtotals by code."""
    has_prior = any(line.boy is not None for line in lines)
    by_area: dict[str, list[TbLine]] = {}
    for line in lines:
        by_area.setdefault(line.area or UNASSIGNED, []).append(line)
    order = sorted((a for a in by_area if a != UNASSIGNED), key=str.lower)
    if UNASSIGNED in by_area:
        order.append(UNASSIGNED)
    adjusted = layer != "unadjusted"
    out: list[TbGroupOut] = []
    for area in order:
        members = by_area[area]
        out.append(
            TbGroupOut(
                key=area[:120],
                label=area,
                lines=[
                    TbLayerLineOut(
                        account_code=line.account_code,
                        account_name=line.account_name,
                        area=line.area,
                        wp_ref=line.wp_ref,
                        boy=line.boy,
                        eoy=line.eoy,
                        aje=line.aje if adjusted else None,
                        rje=line.rje if adjusted else None,
                        final=line.final if adjusted else None,
                        adjustment_refs=list(line.refs) if adjusted else [],
                        flags=flags.get(line.account_code, []),
                    )
                    for line in members
                ],
                boy=sum((x.boy or _ZERO for x in members), _ZERO) if has_prior else None,
                eoy=sum((_layer_value(x, layer) for x in members), _ZERO),
            )
        )
    return out


def _newer(found: TrialBalanceView, snapshots: Sequence[Candidate]) -> int:
    """Snapshots of the same period, pulled after the shown version's, that differ from it."""
    return sum(
        1
        for c in snapshots
        if c.lines_changed
        and c.snapshot.pulled_at > found.version.pulled_at
        and c.snapshot.id != found.version.snapshot_id
    )


async def layer_view(
    ctx: AuthContext,
    engagement_id: UUID,
    tb_id: UUID,
    layer: TrialBalanceLayerStatus,
    version_no: int | None,
) -> TbLayerViewOut:
    """AUD-06 a, c, d, g: the trial balance at one layer and version."""
    return (await _layer_view(ctx, engagement_id, tb_id, layer, version_no))[0]


async def _layer_view(
    ctx: AuthContext,
    engagement_id: UUID,
    tb_id: UUID,
    layer: TrialBalanceLayerStatus,
    version_no: int | None,
) -> tuple[TbLayerViewOut, TrialBalanceView]:
    ref = await _gate(ctx, engagement_id)
    rules = await area_rules(ctx, ref)
    found = await trial_balance_view(
        ctx.tenant, engagement_id, tb_id, version_no, layer.value, rules
    )
    balance = require_balanced(found.lines, layer.value)
    checks = await checks_for(ctx, engagement_id, tb_id)
    flags: dict[str, list[TbLineFlagOut]] = {}
    for check in checks:
        if check.result.status == "off":
            for code in check.accounts:
                flags.setdefault(code, []).append(
                    TbLineFlagOut(kind="does_not_tie", check_id=check.id, issue_id=check.issue_id)
                )
    statuses = [c.result.status for c in checks]
    worst = next((TieOutTallyStatus(s) for s in ("off", "pending", "tie") if s in statuses), None)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    snapshots = await candidates(ctx.tenant, engagement_id, ref.client_entity_id, tb_id)
    allowed = await allowed_actions(ctx, ref.resource(), _ACTIONS)
    version = found.version
    kind = version.source_kind if version.source_kind in _SOURCE_KINDS else "other"
    out = TbLayerViewOut(
        trial_balance_id=found.summary.id,
        engagement_id=engagement_id,
        label=TrialBalanceLabelStatus(found.summary.label),
        layer=layer,
        layers_available=[m for m in TrialBalanceLayerStatus if m.value in found.layer_balances],
        display_unit=cast(DisplayUnit, found.summary.display_unit),
        period_start=found.summary.period_start,
        period_end=found.summary.period_end,
        prior_period_end=version.prior_period_end,
        version_no=version.version_no,
        current_version_no=found.summary.current_version_no,
        provenance=TbProvenanceOut(
            source_kind=cast(SourceKind, kind),
            source=version.source,
            pulled_at=version.pulled_at,
            adopted_by_user_id=version.adopted_by,
            adopted_by_name=names.get(version.adopted_by, "Former member"),
            adopted_at=version.adopted_at,
        ),
        groups=_groups(found.lines, layer.value, flags),
        totals=[],  # named totals arrive with A-03's grouping sets (DEC-395 D1)
        balance=TbLayerBalanceOut(
            layer=layer,
            debit=balance.debit,
            credit=balance.credit,
            difference=balance.difference,
            balanced=balance.balanced,
        ),
        checks=TbChecksSummaryOut(
            tie=statuses.count("tie"),
            off=statuses.count("off"),
            pending=statuses.count("pending"),
            worst=worst,
        ),
        newer_snapshots=_newer(found, snapshots),
        allowed_actions=[cast(TbAction, a) for a in _ACTIONS if a in allowed],
    )
    return out, found


async def leadsheet_area(
    ctx: AuthContext,
    engagement_id: UUID,
    tb_id: UUID,
    area: str,
    layer: TrialBalanceLayerStatus,
    version_no: int | None,
) -> TbLeadsheetAreaOut:
    """AUD-06 e: one audit area's leadsheet, PY · CY · Δ · Δ% (half-even to 0.1 by code)."""
    ref = await _gate(ctx, engagement_id)
    rules = await area_rules(ctx, ref)
    found = await trial_balance_view(
        ctx.tenant, engagement_id, tb_id, version_no, layer.value, rules
    )
    sheet = next((s for s in leadsheets(found.lines, layer.value) if s.area == area), None)
    if sheet is None:
        raise NotFound("leadsheet")
    return TbLeadsheetAreaOut(
        trial_balance_id=found.summary.id,
        version_no=found.version.version_no,
        area=sheet.area,
        unassigned=sheet.area == UNASSIGNED,
        layer=layer,
        display_unit=cast(DisplayUnit, found.summary.display_unit),
        rows=[
            TbLeadsheetRowOut(
                account_code=r.account_code,
                account_name=r.account_name,
                py=r.py,
                cy=r.cy,
                change=r.change,
                change_pct=r.change_pct,
            )
            for r in sheet.rows
        ],
        py=sheet.py,
        cy=sheet.cy,
        change=sheet.change,
        change_pct=sheet.change_pct,
    )


# --- routes (declared on C9's router; `assurance.api` mounts it from here) ---------------------

Ctx = Annotated[AuthContext, Depends(current_context)]


@tb_router.get(
    "/{tb_id}/layers/{layer}",
    action="trial_balance.read",
    response_model=TbLayerViewOut,
    errors=(409,),
)
async def tb_layer_view_route(
    engagement_id: UUID,
    tb_id: UUID,
    layer: TrialBalanceLayerStatus,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> TbLayerViewOut:
    """AUD-06's view at one layer (A-02-T10); AJE, RJE and Final answer 409 `layer_unavailable`
    until an adjustment source is registered, and an unbalanced layer 409 `layer_unbalanced`."""
    return await layer_view(ctx, engagement_id, tb_id, layer, version)


@tb_router.get(
    "/{tb_id}/leadsheets/{area}",
    action="trial_balance.read",
    response_model=TbLeadsheetAreaOut,
    errors=(409,),
)
async def tb_leadsheet_area_route(
    engagement_id: UUID,
    tb_id: UUID,
    area: AreaKey,
    ctx: Ctx,
    layer: TrialBalanceLayerStatus = TrialBalanceLayerStatus.UNADJUSTED,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> TbLeadsheetAreaOut:
    """AUD-06 e: one audit area's leadsheet, PY · CY · Δ · Δ% (A-02-T10); "Unassigned" holds the
    accounts no rule or annotation places."""
    return await leadsheet_area(ctx, engagement_id, tb_id, area, layer, version)


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]


async def _define_gate(ctx: AuthContext, engagement_id: UUID) -> None:
    """Authorise `tie_out_check.define` first (walls 404, a role 403), then the flag (404 off)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "tie_out_check.define", ref.resource())
    if not await flag_enabled(ctx.tenant, LEDGER_TB_WORKPAPER):
        raise NotFound(LEDGER_TB_WORKPAPER.name)


@tb_router.post(
    "/{tb_id}/checks/{check_id}/issue-link",
    action="tie_out_check.define",
    response_model=TieIssueLinkOut,
    status_code=201,
    errors=(409,),
)
async def tie_issue_link_route(
    engagement_id: UUID,
    tb_id: UUID,
    check_id: UUID,
    body: TieIssueLinkIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> TieIssueLinkOut:
    """AUD-06 c (A-02-T17): link an issue raised through C3 on this engagement to a check, once;
    409 `tie_out_check_stale` on a stale `seen_version`, 409 `tie_out_check_issue_linked` for a
    second issue; audited `tie_out_check.issue_linked`. Authorised first (walls 404), then the
    flag (404 off)."""
    await _define_gate(ctx, engagement_id)

    async def run() -> tuple[int, dict[str, object]]:
        link = await link_issue(
            ctx, engagement_id, tb_id, check_id, body.issue_id, body.seen_version
        )
        out = TieIssueLinkOut(
            check_id=link.check_id,
            issue_id=link.issue_id,
            version_no=link.version_no,
            linked_by_user_id=link.linked_by_user_id,
            linked_at=link.linked_at,
        )
        return 201, out.model_dump(mode="json")

    # ED-177 (P-36): the key replays its first answer; reused for another request it is 422
    # `idempotency_key_reused`, before the set-once rule is consulted.
    stored = await idempotent(
        ctx.tenant,
        route="tie_out_check.issue_link",
        key=idempotency_key,
        body={
            "engagement_id": str(engagement_id),
            "tb_id": str(tb_id),
            "check_id": str(check_id),
            "issue_id": str(body.issue_id),
            "seen_version": body.seen_version,
        },
        run=run,
    )
    return TieIssueLinkOut.model_validate(stored.body)


# --- Open in Excel (A-02-T22; AC-8.1) -----------------------------------------------------------

_LAYER_WORDS: Final = MappingProxyType(
    {"unadjusted": "Unadjusted", "aje": "AJE", "rje": "RJE", "final": "Final"}
)  # read-only: the module keeps nothing between calls
_LAYER_NO: Final = MappingProxyType({"unadjusted": 0, "aje": 1, "rje": 2, "final": 3})


def _ticks_text(line: TbLayerLineOut) -> str:
    """ "L1 agreed Marcus Delaney 2026-09-14T15:02:00+00:00; …": an agent's tick names the person
    it acted for, "via Agent" (INV-5)."""
    out: list[str] = []
    for t in line.ticks:
        who = f"{t.by_name} via Agent" if t.actor_kind == "agent" else t.by_name
        out.append(f"L{t.level} {t.kind} {who} {t.at.isoformat()}")
    return "; ".join(out)


def export_of(view: TbLayerViewOut, found: TrialBalanceView) -> LayerExport:
    """The export's content from the view the screen shows (the same figures, by code)."""
    adjusted = view.layer.value != "unadjusted"
    lines = tuple(
        LayerLine(
            account_code=line.account_code,
            account_name=line.account_name,
            area=group.label,
            wp_ref=line.wp_ref or "",
            boy=line.boy,
            eoy=line.eoy,
            aje=line.aje,
            rje=line.rje,
            final=line.final,
            ticks=_ticks_text(line),
            citations="; ".join(str(c) for c in line.citation_ids),
        )
        for group in view.groups
        for line in group.lines
    )
    has_prior = any(line.boy is not None for line in lines)
    p = view.provenance
    footer = (
        ("Trial balance", str(view.trial_balance_id)),
        ("Label", view.label.value),
        ("Version", str(view.version_no)),
        ("Layer", _LAYER_WORDS[view.layer.value]),
        ("Period", f"{view.period_start.isoformat()} to {view.period_end.isoformat()}"),
        ("Source", p.source),
        ("Source kind", p.source_kind),
        ("Pulled at", p.pulled_at.isoformat()),
        ("Snapshot ID", str(found.version.snapshot_id)),
        ("Prior snapshot ID", str(found.version.prior_snapshot_id or "")),
        ("Adopted by", p.adopted_by_name),
        ("Adopted at", p.adopted_at.isoformat()),
        ("Amounts", "computed by Accrued from the snapshot; not edited"),
    )
    return LayerExport(
        title=f"Trial balance {view.period_end.isoformat()}",
        layer=_LAYER_WORDS[view.layer.value],
        adjusted=adjusted,
        lines=lines,
        total_boy=sum((g.boy or _ZERO for g in view.groups), _ZERO) if has_prior else None,
        total_eoy=sum((g.eoy for g in view.groups), _ZERO),
        debit=view.balance.debit,
        credit=view.balance.credit,
        difference=view.balance.difference,
        pulled_at=p.pulled_at,
        footer=footer,
    )


async def export_layer(
    ctx: AuthContext,
    engagement_id: UUID,
    tb_id: UUID,
    layer: TrialBalanceLayerStatus,
    version_no: int | None,
) -> tuple[bytes, int]:
    """AC-8.1: authorise `trial_balance.export` first (walls 404), then the flag (404 off), then
    the layer exactly as AUD-06 shows it; the bytes and the version. Audited
    `trial_balance.exported` with the file's SHA-256."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.export", ref.resource())
    if not await flag_enabled(ctx.tenant, LEDGER_TB_WORKPAPER):
        raise NotFound(LEDGER_TB_WORKPAPER.name)
    view, found = await _layer_view(ctx, engagement_id, tb_id, layer, version_no)
    content = render_trial_balance_layers(export_of(view, found))
    async with uow(ctx.tenant) as tx:
        tx.record(
            "trial_balance.exported",
            target=Target("trial_balance", view.trial_balance_id),
            after=Ref(
                version_no=view.version_no,
                layer_no=_LAYER_NO[view.layer.value],
                file_sha256=hashlib.sha256(content).hexdigest(),
            ),
        )
    return content, view.version_no


@tb_router.get(
    "/{tb_id}/export.xlsx",
    action="trial_balance.export",
    response_model=bytes,
    errors=(409,),
)
async def tb_export_route(
    engagement_id: UUID,
    tb_id: UUID,
    ctx: Ctx,
    layer: TrialBalanceLayerStatus = TrialBalanceLayerStatus.UNADJUSTED,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> Response:
    """Open in Excel (A-02-T22): a deterministic XLSX of the layer with ticks, citations and a
    provenance footer, audited `trial_balance.exported`; formula-like text is neutralised.
    409 `layer_unavailable` or `layer_unbalanced`, as the view."""
    content, version_no = await export_layer(ctx, engagement_id, tb_id, layer, version)
    name = f"trial-balance-v{version_no}-{layer.value}.xlsx"
    return Response(
        content=content,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
