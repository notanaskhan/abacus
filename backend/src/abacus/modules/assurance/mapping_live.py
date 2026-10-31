"""C9 v2 mapping, live (A-03-T08; A-03 §3 F6 US-6.1, US-6.2, US-6.4; ADR-341 §5; DEC-1661).

The contract stub's routes (`tb_mapping_contract.py`) over the v0 service (`assurance/mapping.py`)
and ledger's compute-on-read mapping: a mapping set per trial balance of record, its rows and
code's tallies and subtotals, one account's edit (insert-only, the newest wins, `seen_version`
is the account's edit count), confirm (the preparer's L1 sign-off through `review.api` with the
`content_hash` the person saw; 409 `unmapped_accounts` while any account is unmapped) and the
mapped trial balance.

"Run" is computing: ADR-341 §5 maps on read, so starting the rules creates the set and the run is
ready at once (`run_done = run_total` = the accounts). No row is ever `suggested`: that state and
the adopt route are A-09's TB mapper's (ADR-005).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.listing import ListPage
from abacus.modules.assurance.mapping import (
    edit,
    mapping_with_prior,
    prior_keys_for,
    sign_mapping,
    start,
)
from abacus.modules.assurance.tb_mapping_contract import (
    AccountMappingEditIn,
    AccountMappingOut,
    GroupSubtotalOut,
    MappedFsLineOut,
    MappedTrialBalanceOut,
    MappingConfirmIn,
    MappingRunIn,
    MappingRunOut,
    MappingSetOut,
    MappingSetSummaryOut,
    MappingTalliesOut,
    SignOffChipOut,
)
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, allowed_actions, authorise, names_of
from abacus.modules.ledger.api import (
    CONFIDENCE,
    MappingView,
    account_edits,
    engagement_trial_balances,
    mapped_trial_balance,
    mapping_set_by_id,
    published_versions,
    subtotals,
    trial_balance_view,
)
from abacus.modules.review.api import sign_off_states

TARGET: Final = "mapping_set"
_METHOD: Final = {
    "prior_year": "prior_year_match",
    "number_range": "number_range",
    "manual": "manual",
}
_ACTIONS: Final = ("account_mapping.edit", "mapping_set.confirm", "mapping_set.run")


class StaleVersion(DomainConflict):
    """The account was edited since the person read it (`seen_version` is its edit count)."""

    code = "stale_version"


class ContentChanged(DomainConflict):
    """The mapping changed since the person read it: confirm names the hash they saw."""

    code = "content_changed"


class MappingExistsForTb(DomainConflict):
    """The rules already ran on this trial balance of record: one set per TB (ADR-341 §4)."""

    code = "mapping_run_in_progress"


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


async def _set(ctx: AuthContext, mapping_set_id: UUID, action: str) -> tuple[UUID, UUID]:
    """The set's engagement and trial balance, after the action on its engagement."""
    found = await mapping_set_by_id(ctx.tenant, mapping_set_id)
    if found is None:
        raise NotFound("mapping_set")
    ref = await get_ref(ctx, found.engagement_id)
    await authorise(ctx, action, ref.resource())
    return found.engagement_id, found.trial_balance_id


async def _summary(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID, view: MappingView
) -> MappingSetSummaryOut:
    tb = await trial_balance_view(ctx.tenant, engagement_id, tb_id)
    ref = await get_ref(ctx, engagement_id)
    hashes = {view.mapping_set_id: view.content_hash}
    states = (await sign_off_states(ctx.tenant, TARGET, [view.mapping_set_id], hashes))[
        view.mapping_set_id
    ]
    signed = [
        (s.level, s.signed_by, s.signed_at, s.stale)
        for s in states
        if s.signed_by is not None and s.signed_at is not None
    ]
    names = await names_of([by for _, by, _, _ in signed])
    chips = [
        SignOffChipOut(
            level=level,
            initials=_initials(names.get(by, "")),
            name=names.get(by, ""),
            at=at,
            stale=stale,
        )
        for level, by, at, stale in signed
    ]
    if any(c.stale for c in chips):
        status = "changed_after_sign_off"
    elif any(c.level >= 2 for c in chips):
        status = "reviewed"
    elif any(c.level == 1 for c in chips):
        status = "prepared"
    else:
        status = "in_progress"
    balanced = sum((a.eoy for a in view.accounts), Decimal(0)) == 0
    return MappingSetSummaryOut.model_validate(
        {
            "id": view.mapping_set_id,
            "engagement_id": engagement_id,
            "trial_balance_id": tb_id,
            "trial_balance_version_no": tb.version.version_no,
            "client_entity_id": ref.client_entity_id,
            "entity_name": tb.summary.label,
            "period_end": tb.summary.period_end,
            "grouping_set_version_id": view.version.id,
            "grouping_set_label": f"{view.version.set_name} v{view.version.version}",
            "prior_source": "prior_engagement",
            "run_status": "ready",
            "status": status,
            "tallies": MappingTalliesOut(
                accounts=len(view.accounts),
                mapped=view.mapped,
                need_review=view.unmapped,
                prior_year_match=view.prior_year,
                number_range=view.number_range,
                edited=view.manual,
                tb_balanced=1 if balanced else 0,
                tb_count=1,
            ),
            "sign_offs": chips,
            "content_hash": view.content_hash,
        }
    )


async def mapping_sets(ctx: AuthContext, engagement_id: UUID) -> ListPage[MappingSetSummaryOut]:
    """One mapping set per trial balance of record (the route authorised the engagement)."""
    items: list[MappingSetSummaryOut] = []
    for tb in await engagement_trial_balances(ctx.tenant, engagement_id):
        view = await mapping_with_prior(ctx.tenant, engagement_id, tb.id)
        if view is not None:
            items.append(await _summary(ctx, engagement_id, tb.id, view))
    return ListPage[MappingSetSummaryOut](items=items, total=len(items))


async def run_start(ctx: AuthContext, engagement_id: UUID, body: MappingRunIn) -> MappingRunOut:
    """Start the rules on a TB of record, on the firm's newest published grouping set. Computing
    on read, the run is ready at once (DEC-1661)."""
    # The TB must be this engagement's before anything about it is said (no 409 oracle).
    tbs = {t.id for t in await engagement_trial_balances(ctx.tenant, engagement_id)}
    if body.trial_balance_id not in tbs:
        raise NotFound("trial_balance")
    if await mapping_with_prior(ctx.tenant, engagement_id, body.trial_balance_id) is not None:
        raise MappingExistsForTb
    versions = await published_versions(ctx.tenant)
    if not versions:
        raise NotFound("grouping_set_version")
    newest = max(versions, key=lambda v: (v.published_at or v.created_at, v.version))
    await start(ctx, engagement_id, body.trial_balance_id, newest.id)
    view = await mapping_with_prior(ctx.tenant, engagement_id, body.trial_balance_id)
    if view is None:
        raise NotFound("mapping_set")
    return _run(view)


def _run(view: MappingView) -> MappingRunOut:
    total = len(view.accounts)
    return MappingRunOut(
        mapping_set_id=view.mapping_set_id,
        run_status="ready",
        run_done=total,
        run_total=total,
        failure_code=None,
    )


async def run(ctx: AuthContext, mapping_set_id: UUID) -> MappingRunOut:
    engagement_id, tb_id = await _set(ctx, mapping_set_id, "mapping_set.read")
    view = await mapping_with_prior(ctx.tenant, engagement_id, tb_id)
    if view is None:
        raise NotFound("mapping_set")
    return _run(view)


def _rows(
    view: MappingView, snapshot_id: UUID, edits: dict[str, object], names: dict[UUID, str]
) -> list[AccountMappingOut]:
    lines = {line.id: (g, line) for g in view.groupings for line in g.lines}
    out: list[AccountMappingOut] = []
    for a in view.accounts:
        found = lines.get(a.fs_line_id) if a.fs_line_id is not None else None
        history = edits.get(a.account_code)
        was = getattr(history, "was_fs_line_id", None)
        if history is not None and getattr(history, "rule_before", False):
            was = None
        was_line = lines.get(was) if was is not None else None
        method = None if a.method is None else _METHOD[a.method]
        out.append(
            AccountMappingOut.model_validate(
                {
                    "account_code": a.account_code,
                    "account_name": a.account_name,
                    "citation_match_id": f"led:{snapshot_id}:{a.account_code}",
                    "balance": a.eoy,
                    "fs_line_id": a.fs_line_id,
                    "fs_line_label": None if found is None else found[1].label,
                    "grouping_label": None if found is None else found[0].label,
                    "state": "unmapped"
                    if a.fs_line_id is None
                    else ("edited" if a.method == "manual" else "rule"),
                    "method": method,
                    "confidence": None if a.method is None else CONFIDENCE[a.method],
                    "was_fs_line_label": None if was_line is None else was_line[1].label,
                    "edited_by_initials": None
                    if a.edited_by is None
                    else _initials(names.get(a.edited_by, "")),
                    "edited_at": a.edited_at,
                    "seen_version": getattr(history, "count", 0),
                }
            )
        )
    return out


async def mapping_set(
    ctx: AuthContext,
    mapping_set_id: UUID,
    filter_: Literal["needs_review", "unmatched"] | None = None,
    group_by: Literal["fs_line"] | None = None,
) -> MappingSetOut:
    """AUD-31's rows, tallies and subtotals (US-6.1); balances only from the snapshot."""
    engagement_id, tb_id = await _set(ctx, mapping_set_id, "mapping_set.read")
    view = await mapping_with_prior(ctx.tenant, engagement_id, tb_id)
    if view is None:
        raise NotFound("mapping_set")
    tb = await trial_balance_view(ctx.tenant, engagement_id, tb_id)
    edits = cast(dict[str, object], await account_edits(ctx.tenant, mapping_set_id))
    editors = {a.edited_by for a in view.accounts if a.edited_by is not None}
    names = await names_of(list(editors))
    rows = _rows(view, tb.version.snapshot_id, edits, names)
    if filter_ is not None:
        rows = [r for r in rows if r.fs_line_id is None]
    if group_by == "fs_line":
        order = {line.id: n for n, line in enumerate(x for g in view.groupings for x in g.lines)}
        rows.sort(
            key=lambda r: order.get(r.fs_line_id, len(order)) if r.fs_line_id else len(order)
        )
    key_of = {line.id: g.key for g in view.groupings for line in g.lines}
    sums = subtotals(
        [g.key for g in view.groupings],
        [
            (key_of[a.fs_line_id], a.eoy)
            for a in view.accounts
            if a.fs_line_id is not None and a.fs_line_id in key_of
        ],
    )
    labels = {g.key: g.label for g in view.groupings}
    ref = await get_ref(ctx, engagement_id)
    allowed = sorted(await allowed_actions(ctx, ref.resource(), _ACTIONS))
    return MappingSetOut.model_validate(
        {
            "summary": await _summary(ctx, engagement_id, tb_id, view),
            "rows": rows,
            "subtotals": [
                GroupSubtotalOut(
                    grouping_key=s.grouping_key,
                    grouping_label=labels[s.grouping_key],
                    subtotal=s.subtotal,
                    source_total=s.source_total,
                    off=s.off,
                )
                for s in sums
            ],
            "allowed_actions": allowed,
        }
    )


async def edit_account(
    ctx: AuthContext, mapping_set_id: UUID, account_code: str, body: AccountMappingEditIn
) -> AccountMappingOut:
    """US-6.2: one account's FS line (null returns it to the rules); 409 `stale_version`."""
    engagement_id, tb_id = await _set(ctx, mapping_set_id, "account_mapping.edit")
    current = (await account_edits(ctx.tenant, mapping_set_id)).get(account_code)
    if (0 if current is None else current.count) != body.seen_version:
        raise StaleVersion
    await edit(ctx, engagement_id, tb_id, [(account_code, body.fs_line_id)])
    out = await mapping_set(ctx, mapping_set_id)
    row = next((r for r in out.rows if r.account_code == account_code), None)
    if row is None:
        raise NotFound("account")
    return row


async def confirm(
    ctx: AuthContext, mapping_set_id: UUID, body: MappingConfirmIn
) -> MappingSetSummaryOut:
    """US-6.2: the preparer's L1 sign-off on the hash the person saw, `mapping_set.confirmed` in
    the same unit; 409 `unmapped_accounts` while any remains, `content_changed` on a stale hash."""
    engagement_id, tb_id = await _set(ctx, mapping_set_id, "mapping_set.confirm")
    view = await mapping_with_prior(ctx.tenant, engagement_id, tb_id)
    if view is None:
        raise NotFound("mapping_set")
    if view.content_hash != body.seen_hash:
        raise ContentChanged
    await sign_mapping(ctx, engagement_id, tb_id, 1)
    after = await mapping_with_prior(ctx.tenant, engagement_id, tb_id)
    if after is None:
        raise NotFound("mapping_set")
    return await _summary(ctx, engagement_id, tb_id, after)


async def mapped(ctx: AuthContext, mapping_set_id: UUID) -> MappedTrialBalanceOut:
    """US-6.4: debits, credits and net per FS line, computed by code."""
    engagement_id, tb_id = await _set(ctx, mapping_set_id, "mapping_set.read")
    prior = await prior_keys_for(ctx.tenant, engagement_id)
    found = await mapped_trial_balance(ctx.tenant, engagement_id, tb_id, prior)
    if found is None:
        raise NotFound("mapping_set")
    return MappedTrialBalanceOut(
        mapping_set_id=found.mapping_set_id,
        trial_balance_id=found.trial_balance_id,
        trial_balance_version_no=found.trial_balance_version_no,
        grouping_set_version_id=found.grouping_set_version_id,
        content_hash=found.content_hash,
        lines=[
            MappedFsLineOut.model_validate(
                {
                    "class_": x.grouping_class,
                    "grouping_key": x.grouping_key,
                    "grouping_label": x.grouping_label,
                    "fs_line_key": x.fs_line_key,
                    "fs_line_label": x.fs_line_label,
                    "normal_balance": x.normal_balance,
                    "debit": x.debit,
                    "credit": x.credit,
                    "net": x.net,
                }
            )
            for x in found.lines
        ],
        debit=found.debit,
        credit=found.credit,
        unmapped=found.unmapped,
    )


__all__: Sequence[str] = (
    "confirm",
    "edit_account",
    "mapped",
    "mapping_set",
    "mapping_sets",
    "run",
    "run_start",
)
