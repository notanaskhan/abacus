"""Tie-out checks on a trial balance (SPEC-310; TASK-321; A-02 §3.3).

People define a check (balanced, tie or rollforward); every expected value cites the evidence
it came from (`citation_required`, and a database CHECK agrees). An edit is a new version with a
reason. Results are computed on read by the tie engine from the trial balance's current version,
so a new version of the trial balance re-evaluates every check without writing anything.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.api import version_view
from abacus.modules.identity.api import AuthContext, authorise, engagement_team
from abacus.modules.ledger.api import TrialBalanceView, trial_balance_view
from abacus.modules.workpapers.tie_models import TieOutCheck, TieOutCheckVersion
from abacus.modules.workpapers.tie_repository import (
    checks_of,
    current_versions,
    insert_check,
    insert_check_version,
    key_taken,
    lock_check,
    set_check_version,
)
from abacus.modules.workpapers.ties import (
    Balances,
    Column,
    Component,
    Definition,
    Kind,
    Result,
    evaluate,
)

_KEY: Final = re.compile(r"[^a-z0-9]+")
_CENTS: Final = Decimal("0.01")
MAX_COMPONENTS: Final = 12
MAX_ACCOUNTS: Final = 200


class CitationRequired(DomainInvalid):
    code = "citation_required"


class CheckInvalid(DomainInvalid):
    code = "tie_out_check_invalid"


class CheckStale(DomainInvalid):
    code = "tie_out_check_stale"


class KeyTaken(DomainInvalid):
    code = "tie_out_check_key_taken"


@dataclass(frozen=True)
class CheckInput:
    label: str
    kind: Kind
    accounts: tuple[str, ...]
    column: Column
    negate: bool
    expected: Decimal | None
    components: tuple[Component, ...]
    citation_ids: tuple[UUID, ...]
    tolerance: Decimal


@dataclass(frozen=True)
class CheckView:
    id: UUID
    key: str
    label: str
    kind: Kind
    accounts: list[str]
    column: Column
    negate: bool
    expected: Decimal | None
    components: list[Component]
    citation_ids: list[UUID]
    tolerance: Decimal
    version_no: int
    defined_by_name: str
    defined_at: datetime
    result: Result


def _money(value: Decimal) -> Decimal:
    try:
        return value.quantize(_CENTS)
    except InvalidOperation as exc:
        raise CheckInvalid("amount") from exc


def clean(body: CheckInput) -> CheckInput:
    """Shapes per kind: balanced has no expected value; tie has one; rollforward has signed
    components. Any expected figure needs at least one citation."""
    label = body.label.strip()
    if not 1 <= len(label) <= 120:
        raise CheckInvalid("label")
    accounts = tuple(dict.fromkeys(a.strip() for a in body.accounts if a.strip()))
    if len(accounts) > MAX_ACCOUNTS or any(len(a) > 64 for a in accounts):
        raise CheckInvalid("accounts")
    tolerance = _money(body.tolerance)
    if tolerance < 0:
        raise CheckInvalid("tolerance")
    if body.kind == "balanced":
        if body.expected is not None or body.components or accounts:
            raise CheckInvalid("balanced")
        return CheckInput(label, "balanced", (), body.column, False, None, (), (), tolerance)
    if not accounts:
        raise CheckInvalid("accounts")
    if body.kind == "tie":
        if body.expected is None or body.components:
            raise CheckInvalid("tie")
        expected, components = _money(body.expected), ()
    else:
        if body.expected is not None or not 1 <= len(body.components) <= MAX_COMPONENTS:
            raise CheckInvalid("rollforward")
        components = tuple(
            Component(c.label.strip(), 1 if c.sign > 0 else -1, _money(c.value))
            for c in body.components
        )
        if any(not 1 <= len(c.label) <= 80 for c in components):
            raise CheckInvalid("component")
        expected = None
    citations = tuple(dict.fromkeys(body.citation_ids))
    if not citations:
        raise CitationRequired(body.kind)
    return CheckInput(
        label,
        body.kind,
        accounts,
        body.column,
        body.negate,
        expected,
        components,
        citations,
        tolerance,
    )


def balances_of(view: TrialBalanceView) -> Balances:
    eoy = {line.account_code: line.eoy for line in view.lines}
    has_prior = view.boy is not None
    boy = (
        {line.account_code: line.boy or Decimal("0.00") for line in view.lines}
        if has_prior
        else None
    )
    totals: dict[str, tuple[Decimal, Decimal] | None] = {
        "eoy": (view.eoy.debit, view.eoy.credit),
        "boy": (view.boy.debit, view.boy.credit) if view.boy is not None else None,
    }
    return Balances(eoy, boy, totals)


def _definition(check: TieOutCheck, v: TieOutCheckVersion) -> Definition:
    selector = v.actual_selector
    expected = v.expected or {}
    raw_value = expected.get("value")
    return Definition(
        kind=check.kind,  # type: ignore[arg-type]  # the CHECK constraint holds it to Kind
        accounts=tuple(str(a) for a in selector.get("accounts", [])),
        column="boy" if selector.get("column") == "boy" else "eoy",
        negate=bool(selector.get("negate", False)),
        expected=Decimal(str(raw_value)) if raw_value is not None else None,
        components=tuple(
            Component(str(c["label"]), int(c["sign"]), Decimal(str(c["value"])))
            for c in expected.get("components", [])
        ),
        tolerance=v.tolerance,
    )


def _payload(body: CheckInput) -> tuple[dict[str, object], dict[str, object] | None]:
    selector: dict[str, object] = {
        "accounts": list(body.accounts),
        "column": body.column,
        "negate": body.negate,
    }
    if body.kind == "tie":
        return selector, {"value": str(body.expected)}
    if body.kind == "rollforward":
        return selector, {
            "components": [
                {"label": c.label, "sign": c.sign, "value": str(c.value)} for c in body.components
            ]
        }
    return selector, None


async def _check_citations(ctx: AuthContext, engagement_id: UUID, ids: Sequence[UUID]) -> None:
    for vid in ids:
        if (await version_view(ctx.tenant, vid)).engagement_id != engagement_id:
            raise NotFound("evidence_version")


def _key(label: str, taken: set[str]) -> str:
    base = _KEY.sub("-", label.lower()).strip("-")[:32] or "check"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    return key


async def checks_for(ctx: AuthContext, engagement_id: UUID, tb_id: UUID) -> list[CheckView]:
    """AC-1: each check with its result on the trial balance's current version."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "trial_balance.read", ref.resource())
    view = await trial_balance_view(ctx.tenant, engagement_id, tb_id)
    async with tenant_session(ctx.tenant) as session:
        checks = await checks_of(session, tb_id)
        versions = await current_versions(session, checks)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    balances = balances_of(view)
    out: list[CheckView] = []
    for c in checks:
        v = versions.get(c.id)
        if v is None:
            continue
        d = _definition(c, v)
        out.append(
            CheckView(
                c.id,
                c.key,
                v.label,
                d.kind,
                list(d.accounts),
                d.column,
                d.negate,
                d.expected,
                list(d.components),
                list(v.citation_ids),
                v.tolerance,
                v.version_no,
                names.get(v.created_by, "Former member"),
                v.created_at,
                evaluate(d, balances),
            )
        )
    return out


async def define_check(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID, body: CheckInput
) -> UUID:
    """AC-2: a new check (version 1)."""
    clean_body = clean(body)
    await _check_citations(ctx, engagement_id, clean_body.citation_ids)
    await trial_balance_view(ctx.tenant, engagement_id, tb_id)  # NotFound off the engagement
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "tie_out_check.define", ref.resource())
        taken = {c.key for c in await checks_of(tx.session, tb_id)}
        key = _key(clean_body.label, taken)
        if await key_taken(tx.session, tb_id, key):
            raise KeyTaken(key)
        check_id = await insert_check(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            target_type="trial_balance",
            target_id=tb_id,
            key=key,
            kind=clean_body.kind,
            created_by=ctx.user_id,
        )
        selector, expected = _payload(clean_body)
        await insert_check_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            check_id=check_id,
            version_no=1,
            label=clean_body.label,
            actual_selector=selector,
            expected=expected,
            citation_ids=list(clean_body.citation_ids),
            tolerance=clean_body.tolerance,
            reason=None,
            created_by=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )
        tx.record(
            "tie_out_check.defined",
            target=Target("tie_out_check", check_id),
            after=Ref(kind=("balanced", "tie", "rollforward").index(clean_body.kind)),
        )
    return check_id


async def edit_check(
    ctx: AuthContext,
    engagement_id: UUID,
    tb_id: UUID,
    check_id: UUID,
    body: CheckInput,
    reason: str,
    seen_version: int,
) -> int:
    """AC-3: a new version of a check, with a reason; the kind stays."""
    reason = reason.strip()
    if not 1 <= len(reason) <= 500:
        raise CheckInvalid("reason")
    clean_body = clean(body)
    await _check_citations(ctx, engagement_id, clean_body.citation_ids)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "tie_out_check.define", ref.resource())
        check = await lock_check(tx.session, check_id)
        if check is None or check.target_id != tb_id or check.engagement_id != engagement_id:
            raise NotFound("tie_out_check")
        if check.kind != clean_body.kind:
            raise CheckInvalid("kind")
        if check.current_version_no != seen_version:
            raise CheckStale(str(check_id))
        version_no = check.current_version_no + 1
        selector, expected = _payload(clean_body)
        await insert_check_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            check_id=check.id,
            version_no=version_no,
            label=clean_body.label,
            actual_selector=selector,
            expected=expected,
            citation_ids=list(clean_body.citation_ids),
            tolerance=clean_body.tolerance,
            reason=reason,
            created_by=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )
        await set_check_version(tx.session, check.id, version_no)
        tx.record(
            "tie_out_check.changed",
            target=Target("tie_out_check", check.id),
            before=Ref(version_no=check.current_version_no),
            after=Ref(version_no=version_no),
        )
    return version_no
