"""The two-year comparison service (T-08-T11; S51 partials, TASK-8740; DEC-5731; SPEC-710 AC-21 to
AC-25; TAX-10). Dark behind `tax.two_year`.

- **Read**: the return's newest approved engine summary against the prior year's return of the
  same entity and form, over the CPA-reviewed line map (`compute/two_year_lines.py`), compared by
  code (`compute/two_year.py`). The threshold is the firm's `variance_thresholds` standard row
  `tax_two_year` in effect, its version pinned and named; with none in effect there is no
  comparison (409 `threshold_unavailable`, never an invented threshold). Each line carries its
  newest explanation version and whether that version is accepted, stale (the values moved since)
  or only proposed.
- **Edit**: a person's explanation is a new insert-only version ("Edited by <name>").
- **Accept**: a person accepts the newest version over the values they saw (409
  `explanation_stale` when the values hash moved; insert-only, human-only by the CHECK).
- **Export**: the comparison as an injection-safe workbook, audited.
Walls and visibility: every call authorises on the return's engagement (404 otherwise).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.tax.compute import two_year as calc
from abacus.modules.tax.compute.two_year_lines import AGI, LINE_MAPS, REFUND, TOTAL_TAX

KIND: Final = "tax_return"
CONTEXT: Final = "tax_two_year"


class ThresholdUnavailable(DomainConflict):
    code = "threshold_unavailable"


class ComparisonUnavailable(DomainConflict):
    code = "comparison_unavailable"


class ExplanationStale(DomainConflict):
    code = "explanation_stale"


@dataclass(frozen=True)
class Explanation:
    version_id: UUID
    text: str
    author_kind: str
    created_by: UUID
    accepted_by: UUID | None
    accepted_at: datetime | None
    accepted_hash: str | None


@dataclass(frozen=True)
class Line:
    line: calc.ComparisonLine
    values_hash: str
    explanation: Explanation | None

    @property
    def state(self) -> str | None:
        if self.explanation is None:
            return "unexplained" if self.line.flagged else None
        if self.explanation.accepted_by is None:
            return "proposed"
        return "accepted" if self.explanation.accepted_hash == self.values_hash else "stale"


@dataclass(frozen=True)
class Comparison:
    return_id: UUID
    engagement_id: UUID
    summary_version: str
    threshold: calc.Threshold
    threshold_version_id: UUID
    lines: tuple[Line, ...]
    agi: Decimal
    agi_prior: Decimal
    total_tax: Decimal
    total_tax_prior: Decimal
    refund: Decimal | None
    prior_refund: Decimal | None


_RETURN = text(
    "SELECT engagement_id, client_entity_id, form, tax_year FROM tax_returns "
    "WHERE work_item_id = :id"
)
_PRIOR = text(
    "SELECT work_item_id FROM tax_returns WHERE client_entity_id = :e AND form = :f "
    "AND tax_year = :y ORDER BY work_item_id LIMIT 1"
)
_SUMMARY = text(
    "SELECT engine_version, lines FROM return_engine_summaries WHERE work_item_id = :id "
    "AND kind <> 'pro_forma' ORDER BY approved_at DESC LIMIT 1"
)
_EXPLANATIONS = text(
    "SELECT DISTINCT ON (v.line_key) v.line_key, v.id, v.text, v.author_kind, v.created_by, "
    "a.accepted_by, a.accepted_at, a.values_hash FROM variance_explanation_versions v "
    "LEFT JOIN LATERAL (SELECT accepted_by, accepted_at, values_hash FROM "
    "variance_explanation_acceptances x WHERE x.version_id = v.id ORDER BY x.accepted_at DESC "
    "LIMIT 1) a ON true WHERE v.work_item_id = :id ORDER BY v.line_key, v.version_no DESC"
)


def _amounts(lines: object) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for raw in cast(list[object], lines or []):
        if not isinstance(raw, dict):
            continue
        line = cast(dict[str, object], raw)
        key, amount = line.get("line_key"), line.get("amount")
        if not isinstance(key, str) or amount is None:
            continue
        try:
            out[key] = Decimal(str(amount))
        except InvalidOperation:
            continue
    return out


async def _resource(ctx: AuthContext, return_id: UUID, action: str) -> tuple[UUID, str, int, UUID]:
    if ctx.client:
        raise NotFound(KIND)
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_RETURN, {"id": return_id})).first()
    if found is None or found[0] is None:
        raise NotFound(KIND)
    engagement = cast(UUID, found[0])
    resource = await engagement_resource_of(ctx.tenant, engagement)
    try:
        await authorise(ctx, action, replace(resource, work_item_id=return_id))
    except Forbidden:
        if action == "tax_return.read":
            raise NotFound(KIND) from None  # a walled return answers 404 (INV-3)
        raise
    return engagement, str(found[2]), int(cast(int, found[3])), cast(UUID, found[1])


async def _threshold(tenant: TenantContext) -> tuple[calc.Threshold, UUID]:
    from abacus.kernel.clock import today
    from abacus.modules.methodology.api import current_version_of_kind, policy_payload

    policy = await current_version_of_kind(
        tenant.tenant_id, "variance_thresholds", await today(tenant)
    )
    if policy is None:
        raise ThresholdUnavailable(facts={"standard": "variance_thresholds"})
    payload = await policy_payload(tenant.tenant_id, policy, "variance_thresholds")
    rows = cast("list[dict[str, object]]", (payload or {}).get("rows") or [])
    row = next((r for r in rows if r.get("context") == CONTEXT), None)
    if row is None:
        raise ThresholdUnavailable(facts={"standard": "variance_thresholds"})
    return (
        calc.Threshold(
            Decimal(str(row["pct"])), Decimal(str(row["amount_usd"])), str(policy.version_id)
        ),
        policy.version_id,
    )


async def comparison(ctx: AuthContext, return_id: UUID) -> Comparison:
    engagement, form, year, entity = await _resource(ctx, return_id, "tax_return.read")
    line_map = LINE_MAPS.get(form)
    if line_map is None:
        raise ComparisonUnavailable(facts={"form": form})
    async with tenant_session(ctx.tenant) as session:
        current = (await session.execute(_SUMMARY, {"id": return_id})).first()
        prior_id = await session.scalar(_PRIOR, {"e": entity, "f": form, "y": year - 1})
        prior = (
            None
            if prior_id is None
            else (await session.execute(_SUMMARY, {"id": prior_id})).first()
        )
        explained = {
            str(r[0]): Explanation(
                cast(UUID, r[1]), str(r[2]), str(r[3]), cast(UUID, r[4]),
                cast(UUID | None, r[5]), cast(datetime | None, r[6]), cast(str | None, r[7]),
            )
            for r in await session.execute(_EXPLANATIONS, {"id": return_id})
        }  # fmt: skip
    if current is None or prior is None:
        raise ComparisonUnavailable(facts={"return_id": str(return_id)})
    threshold, version_id = await _threshold(ctx.tenant)
    cy, py = _amounts(current[1]), _amounts(prior[1])
    compared = calc.compare(cy, py, line_map, threshold)
    lines = tuple(Line(ln, calc.values_hash([ln]), explained.get(ln.code)) for ln in compared)
    zero = Decimal(0)
    return Comparison(
        return_id, engagement, str(current[0]), threshold, version_id, lines,
        cy.get(AGI, zero), py.get(AGI, zero), cy.get(TOTAL_TAX, zero), py.get(TOTAL_TAX, zero),
        cy.get(REFUND), py.get(REFUND),
    )  # fmt: skip


def _line(found: Comparison, line_key: str) -> Line:
    line = next((ln for ln in found.lines if ln.line.code == line_key), None)
    if line is None:
        raise NotFound("two_year_line")
    return line


_NEXT_VERSION = text(
    "SELECT coalesce(max(version_no), 0) + 1 FROM variance_explanation_versions "
    "WHERE work_item_id = :w AND line_key = :k"
)
_NEW_VERSION = text(
    "INSERT INTO variance_explanation_versions (tenant_id, engagement_id, work_item_id, "
    "line_key, version_no, text, author_kind, created_by) VALUES (:t, :e, :w, :k, :n, :text, "
    "'human', :u) RETURNING id"
)


async def edit_explanation(
    ctx: AuthContext, return_id: UUID, line_key: str, body: str
) -> Comparison:
    """A person's explanation, a new insert-only version."""
    found = await comparison(ctx, return_id)
    await _resource(ctx, return_id, "variance_explanation.edit")
    _line(found, line_key)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"{return_id}:{line_key}"}
        )
        number = int(cast(int, await tx.session.scalar(
            _NEXT_VERSION, {"w": return_id, "k": line_key})))  # fmt: skip
        version = await tx.session.scalar(
            _NEW_VERSION,
            {"t": ctx.tenant_id, "e": found.engagement_id, "w": return_id, "k": line_key,
             "n": number, "text": body.strip(), "u": ctx.user_id},
        )  # fmt: skip
        tx.record(
            "variance_explanation.edited",
            target=Target("variance_explanation_version", cast(UUID, version)),
            after=Ref(version=number),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=return_id),
        )
    return await comparison(ctx, return_id)


_ACCEPT = text(
    "INSERT INTO variance_explanation_acceptances (tenant_id, version_id, values_hash, "
    "threshold_source, accepted_by) VALUES (:t, :v, :h, CAST(:src AS jsonb), :u)"
)


async def accept(
    ctx: AuthContext, return_id: UUID, line_key: str, version_id: UUID, values_hash: str
) -> Comparison:
    """AC-24, AC-25: the newest version over the values the reviewer saw."""
    found = await comparison(ctx, return_id)
    await _resource(ctx, return_id, "variance_explanation.accept")
    line = _line(found, line_key)
    if line.explanation is None or line.explanation.version_id != version_id:
        raise ExplanationStale(facts={"line_key": line_key})
    if values_hash != line.values_hash:
        raise ExplanationStale(facts={"line_key": line_key})
    source = {"source": "variance_policy", "version_id": str(found.threshold_version_id)}
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _ACCEPT,
            {"t": ctx.tenant_id, "v": version_id, "h": values_hash, "src": json.dumps(source),
             "u": ctx.user_id},
        )  # fmt: skip
        tx.record(
            "variance_explanation.accepted",
            target=Target("variance_explanation_version", version_id),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=return_id),
        )
    return await comparison(ctx, return_id)


async def export_xlsx(ctx: AuthContext, return_id: UUID) -> bytes:
    found = await comparison(ctx, return_id)
    await _resource(ctx, return_id, "export.create")
    rows: list[list[str | int | Decimal | bool | None]] = [
        ["Line", "Prior year", "Current year", "Change", "Change %", "Over threshold",
         "Explanation", "State"],
    ]  # fmt: skip
    for ln in found.lines:
        rows.append(
            [ln.line.label, ln.line.prior, ln.line.current, ln.line.delta, ln.line.delta_pct,
             ln.line.flagged, None if ln.explanation is None else ln.explanation.text,
             ln.state]
        )  # fmt: skip
    async with uow(ctx.tenant) as tx:
        tx.record(
            "two_year.exported",
            target=Target(KIND, return_id),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=return_id),
        )
    return workbook([Sheet("2-Year Comparison", rows)])


__all__ = [
    "Comparison",
    "ComparisonUnavailable",
    "ExplanationStale",
    "Line",
    "ThresholdUnavailable",
    "accept",
    "comparison",
    "edit_explanation",
    "export_xlsx",
]
