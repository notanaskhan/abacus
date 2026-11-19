"""CLS-08's package read and structure edit (C-02-T21; TASK-8706; SPEC-701; DEC-5703).

`get_package` reads the close's deliverable (or, before the first edit or generate, the package it
would hold) and computes its figures from the posted TB through `compute/package.py`: C8's final
layer (posted or recorded entries only) mapped through C9's FS lines, the SSARS route from K-02's
`ssars_cas_settings` in effect at the period end with the package's CAS answer, and the release
preconditions from the close's own facts (accounts reconciled, open exceptions, entries not
posted). Nothing is stored by a read.

`edit_package` writes a new insert-only version (sections, CAS answer, route, legend key, the
posted TB reference and its content hash) at the version the person saw (409 `stale_version`
otherwise), creating the deliverable on the first edit; a released package is not edited (409
`package_released`). A live human only (the route checks), audited as `close_package.edited`.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Row, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.closes.compute import package as pkg
from abacus.modules.closes.delivery_contract import (
    DeliveryPackageEditIn,
    DeliveryPackageOut,
    DeliveryPreconditionOut,
    DeliveryStatementLineOut,
)
from abacus.modules.closes.delivery_errors import PackageReleased
from abacus.modules.closes.service import StaleClose as StaleVersion
from abacus.modules.closes.service import close_summary, visible_close
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, authorise

DEFAULT_SECTIONS: Final = ["balance_sheet", "income_statement", "commentary"]
NET_INCOME_LABEL: Final = "Net income, year to date"
LEGENDS: Final = {pkg.NO_ASSURANCE: "No assurance is provided."}


_DELIVERABLE = text(
    "SELECT d.id, d.status, d.current_version_no, d.released_at, d.client_approved_at, "
    "v.sections, v.cas_answer, v.content_hash, v.route, v.legend_key, v.posted_tb_ref, "
    "v.commentary FROM close_deliverables d "
    "LEFT JOIN close_deliverable_versions v ON v.deliverable_id = d.id "
    "AND v.version_no = d.current_version_no WHERE d.close_id = :c"
)
_NEW_DELIVERABLE = text(
    "INSERT INTO close_deliverables (tenant_id, close_id, work_item_id, status) "
    "VALUES (:t, :c, :c, 'draft') ON CONFLICT (tenant_id, close_id) DO NOTHING RETURNING id"
)
_NEW_VERSION = text(
    "INSERT INTO close_deliverable_versions (tenant_id, deliverable_id, version_no, sections, "
    "cas_answer, route, legend_key, posted_tb_ref, content_hash, commentary) VALUES (:t, :d, :n, "
    "CAST(:sections AS jsonb), :cas, :route, :legend, CAST(:tb AS jsonb), :hash, "
    "CAST(:commentary AS jsonb))"
)
_BUMP = text(
    "UPDATE close_deliverables SET current_version_no = :n, status = 'draft' "
    "WHERE id = :d AND current_version_no = :seen RETURNING id"
)


def _period_end(period: str) -> date:
    year, month = (int(p) for p in period.split("-"))
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    return date.fromordinal(first_next.toordinal() - 1)


async def _framework(tenant_id: UUID, period_end: date) -> str:
    """K-02's `ssars_framework_for` on the firm's settings in effect at the period end; a firm
    with no settings published reads the standard's own boundary (no early adoption)."""
    from abacus.modules.methodology.api import (
        PolicyRef,
        SsarsCasSettingsPayload,
        current_version_of_kind,
        policy_payload,
        ssars_framework_for,
    )

    policy = await current_version_of_kind(tenant_id, "ssars_cas_settings", period_end)
    if policy is None:
        payload = SsarsCasSettingsPayload(kind="ssars_cas_settings", early_adopt_ssars27=False)
        policy = PolicyRef("ssars_cas_settings", UUID(int=0), 0, "SSARS 27 boundary")
    else:
        raw = await policy_payload(tenant_id, policy, "ssars_cas_settings")
        payload = SsarsCasSettingsPayload.model_validate(raw)
    return str(ssars_framework_for(payload, policy, period_end=period_end).framework)


async def _figures(
    ctx: AuthContext, close_id: UUID
) -> tuple[list[pkg.StatementLine], list[pkg.StatementLine], dict[str, object]]:
    """Balance sheet and income statement lines from C8's final layer mapped through C9; the
    posted TB reference the version stores. No TB or mapping yet: no lines."""
    from abacus.modules.adjustments.api import adjusted_tb
    from abacus.modules.ledger.api import engagement_trial_balances, mapping_view

    close = await visible_close(ctx, close_id)
    tbs = await engagement_trial_balances(ctx.tenant, close.engagement_id)
    if not tbs:
        return [], [], {}
    current = max(tbs, key=lambda t: t.period_end)
    view = await mapping_view(ctx.tenant, close.engagement_id, current.id)
    if view is None:
        return [], [], {"trial_balance_id": str(current.id)}
    final = cast(Any, await adjusted_tb(ctx, close_id, "final"))  # Any: the ledger's view type
    fs: dict[UUID, pkg.FsLine] = {}
    for g_order, g in enumerate(view.groupings):
        for l_order, line in enumerate(g.lines):
            fs[line.id] = pkg.FsLine(
                line.key,
                line.label,
                g.key,
                g.label,
                cast(pkg.GroupingClass, g.class_),
                g_order * 1000 + l_order,
            )
    mapping = {
        a.account_code: fs[a.fs_line_id]
        for a in view.accounts
        if a.fs_line_id is not None and a.fs_line_id in fs
    }
    accounts = [
        pkg.LedgerAccount(ln.account_code, ln.account_name, Decimal(ln.final or 0))
        for ln in final.lines
    ]
    month = [a for a in accounts if a.ref in mapping and mapping[a.ref].grouping_class in (
        "revenue", "expenses")]  # fmt: skip
    bs = pkg.balance_sheet(
        accounts, mapping, net_income_label=NET_INCOME_LABEL, equity_grouping_key="equity"
    )
    inc = pkg.income_statement(month, mapping)
    ref: dict[str, object] = {
        "trial_balance_id": str(current.id),
        "mapping_set_id": str(view.mapping_set_id),
        "mapping_hash": view.content_hash,
        "pending_entries": int(final.pending_entries),
    }
    return list(bs.lines), list(inc.lines), ref


def _line_out(ln: pkg.StatementLine) -> DeliveryStatementLineOut:
    return DeliveryStatementLineOut(
        key=ln.key,
        label=ln.label,
        amount=ln.amount,
        account_refs=list(ln.account_refs),
        prior=ln.prior,
    )


async def _row(tenant: TenantContext, close_id: UUID) -> Row[Any] | None:  # Any: a SQL row
    async with tenant_session(tenant) as session:
        return (await session.execute(_DELIVERABLE, {"c": close_id})).first()


async def get_package(ctx: AuthContext, close_id: UUID) -> DeliveryPackageOut:
    close = await visible_close(ctx, close_id)
    ref = await get_ref(ctx, close.engagement_id)
    await authorise(ctx, "close_package.read", ref.resource())
    row = await _row(ctx.tenant, close_id)
    sections = list(row.sections) if row is not None and row.sections is not None else (
        list(DEFAULT_SECTIONS))  # fmt: skip
    cas_answer = bool(row.cas_answer) if row is not None and row.cas_answer is not None else True
    framework = await _framework(ctx.tenant_id, _period_end(close.period))
    routed = pkg.route(framework, cas_answer=cas_answer)
    bs, inc, tb_ref = await _figures(ctx, close_id)
    summary = await close_summary(ctx, close_id)
    reasons = pkg.preconditions(
        reconciled=summary.accounts_reconciled,
        accounts=summary.accounts_total,
        open_issues=summary.open_issues,
        unposted_entries=int(cast(int, tb_ref.get("pending_entries", 0))),
    )
    version_no = int(row.current_version_no) if row is not None and row.current_version_no else 1
    stored = dict(row.commentary or {}) if row is not None else {}
    commentary = (
        str(stored["doc"]) if "doc" in stored else await drafted_commentary(ctx.tenant, close_id)
    )
    return DeliveryPackageOut(
        close_id=close_id,
        status=row.status if row is not None else "drafting",
        version_no=version_no,
        route=routed.route,
        legend=LEGENDS.get(routed.legend_key or ""),
        sections=sections,  # type: ignore[arg-type]  # stored as the Section literals
        cas_answer=cas_answer,
        balance_sheet=[_line_out(ln) for ln in bs] if "balance_sheet" in sections else [],
        income_statement=[_line_out(ln) for ln in inc] if "income_statement" in sections else [],
        preconditions=[
            DeliveryPreconditionOut(blocker=p.blocker, done=p.done, of=p.of) for p in reasons
        ],
        released_at=row.released_at if row is not None else None,
        client_approved_at=row.client_approved_at if row is not None else None,
        content_hash=pkg.content_hash(bs, inc, routed, sections),
        version=version_no,
        commentary=commentary if "commentary" in sections else None,
    )


COMMENTARY_TEMPLATE: Final = "{flux}"


async def drafted_commentary(tenant: TenantContext, close_id: UUID) -> str:
    """C-02-T21 (S51 partials): the commentary before anyone writes it, filled by code from the
    close's accepted flux explanations (drafts never appear). The firm's own commentary template
    is content (an admin import, C-02-T28); until one is loaded the lines stand alone."""
    from abacus.modules.closes.flux import accepted_flux

    accepted = [
        pkg.AcceptedFlux(label, change, pct, explanation)
        for label, change, pct, explanation in await accepted_flux(tenant, close_id)
    ]
    return pkg.commentary(COMMENTARY_TEMPLATE, accepted)


async def edit_commentary(
    ctx: AuthContext, close_id: UUID, doc: str, expected_version: int
) -> DeliveryPackageOut:
    """CLS-08's commentary edit: a new version with the person's text and everything else as the
    current version holds it (figures stay locked to the ledger), at the version they saw (409
    `stale_version`); a released package is not edited (409 `package_released`). Before any
    version exists the structure defaults apply."""
    close = await visible_close(ctx, close_id)
    ref = await get_ref(ctx, close.engagement_id)
    await authorise(ctx, "close_package.edit", ref.resource())
    framework = await _framework(ctx.tenant_id, _period_end(close.period))
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_DELIVERABLE, {"c": close_id})).first()
        if row is not None and row.status in ("released", "approved_by_client"):
            raise PackageReleased(facts={"close_id": str(close_id)})
        seen = int(row.current_version_no) if row is not None else 0
        if (seen or 1) != expected_version:
            raise StaleVersion(facts={"close_id": str(close_id)})
        if row is not None and row.sections is not None:
            sections = list(row.sections)
            cas, route, legend = bool(row.cas_answer), str(row.route), row.legend_key
            tb_ref, content = dict(row.posted_tb_ref), str(row.content_hash)
        else:
            sections, cas = list(DEFAULT_SECTIONS), True
            routed = pkg.route(framework, cas_answer=cas)
            bs, inc, tb_ref = await _figures(ctx, close_id)
            route, legend = routed.route, routed.legend_key
            content = pkg.content_hash(bs, inc, routed, sections)
        deliverable = row.id if row is not None else await tx.session.scalar(
            _NEW_DELIVERABLE, {"t": ctx.tenant_id, "c": close_id})  # fmt: skip
        if deliverable is None:
            raise StaleVersion(facts={"close_id": str(close_id)})
        number = seen + 1
        await tx.session.execute(
            _NEW_VERSION,
            {
                "t": ctx.tenant_id, "d": deliverable, "n": number,
                "sections": json.dumps(sections), "cas": cas, "route": route, "legend": legend,
                "tb": json.dumps(tb_ref), "hash": content,
                "commentary": json.dumps({"doc": doc.strip()}),
            },
        )  # fmt: skip
        if await tx.session.scalar(_BUMP, {"d": deliverable, "n": number, "seen": seen}) is None:
            raise StaleVersion(facts={"close_id": str(close_id)})
        tx.record(
            "close_package.commentary_edited",
            target=Target("close", close_id),
            after=Ref(version=number),
        )
    return await get_package(ctx, close_id)


async def edit_package(
    ctx: AuthContext, close_id: UUID, body: DeliveryPackageEditIn
) -> DeliveryPackageOut:
    """A new version with the person's structure (toggles and the CAS answer), at the version
    they saw."""
    close = await visible_close(ctx, close_id)
    ref = await get_ref(ctx, close.engagement_id)
    await authorise(ctx, "close_package.edit", ref.resource())
    framework = await _framework(ctx.tenant_id, _period_end(close.period))
    routed = pkg.route(framework, cas_answer=body.cas_answer)
    bs, inc, tb_ref = await _figures(ctx, close_id)
    sections = list(dict.fromkeys(body.sections))
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_DELIVERABLE, {"c": close_id})).first()
        if row is not None and row.status in ("released", "approved_by_client"):
            raise PackageReleased(facts={"close_id": str(close_id)})
        seen = int(row.current_version_no) if row is not None else 0
        if (seen or 1) != body.expected_version:
            raise StaleVersion(facts={"close_id": str(close_id)})
        deliverable = row.id if row is not None else await tx.session.scalar(
            _NEW_DELIVERABLE, {"t": ctx.tenant_id, "c": close_id})  # fmt: skip
        if deliverable is None:
            raise StaleVersion(facts={"close_id": str(close_id)})  # created meanwhile
        number = seen + 1
        await tx.session.execute(
            _NEW_VERSION,
            {
                "t": ctx.tenant_id,
                "d": deliverable,
                "n": number,
                "sections": json.dumps(sections),
                "cas": body.cas_answer,
                "route": routed.route,
                "legend": routed.legend_key,
                "tb": json.dumps(tb_ref),
                "hash": pkg.content_hash(bs, inc, routed, sections),
                # a structure edit keeps the person's commentary (regenerate keeps edits)
                "commentary": json.dumps(dict(row.commentary or {}) if row is not None else {}),
            },
        )
        if await tx.session.scalar(_BUMP, {"d": deliverable, "n": number, "seen": seen}) is None:
            raise StaleVersion(facts={"close_id": str(close_id)})
        tx.record(
            "close_package.edited",
            target=Target("close", close_id),
            after=Ref(version=number),
        )
    return await get_package(ctx, close_id)


__all__ = ["drafted_commentary", "edit_commentary", "edit_package", "get_package"]
