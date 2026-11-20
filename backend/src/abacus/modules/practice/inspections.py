"""Monitoring: inspections, QM findings and the annual evaluation (Q-05-T18; SPEC-711 AC-6 to
AC-11; ADM-12 a-g; DEC-5827). Amber.

- **Cycles** list the year's inspections and open findings by code.
- **Candidates** carry a deterministic risk score from the firm's published selection rule
  (`inspection_selection_rules`: weights x facts, ties broken by the rule's seed), with the people
  who may not inspect each one (the EP or signer, the team, the EQR).
- **Planning** refuses a person who is not objective (422 `inspector_not_objective`), writes the
  inspection and issues the inspector's read-only grants (identity, OQ-6) to the due date + 30
  days. **Start** and **Conclude** move it forward; conclusion revokes the grants.
- **Findings** record a deficiency (sealed title), its root cause, remediation, owner and due date;
  the **evaluation** is reserved to the QM owner (`qm_finding.evaluate`, insert-only, human-only);
  **Mark remediated** closes it with a note; remediation to-dos go through P-05.
- **The annual evaluation**: a checklist, then Request conclusion raises the firm-scope
  `qm_annual_evaluation` card for the QM owner (`qm_ultimate`) once every inspection of the cycle
  has concluded (409 `inspections_open`). The agent never evaluates, concludes or decides.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import today as clock_today
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise

_FINGERPRINT: Final = "practice.qm_finding"
EVALUATION_KIND: Final = "qm_annual_evaluation"
EVALUATION_OPTIONS: Final = (
    {"key": "reasonable_assurance", "label": "The SQMS provides reasonable assurance"},
    {
        "key": "except_for",
        "label": "Except for the matters described, it provides reasonable assurance",
    },
    {"key": "does_not", "label": "The SQMS does not provide reasonable assurance"},
)


class NotObjective(DomainInvalid):
    code = "inspector_not_objective"
    message = "The inspector worked on this engagement."


class InspectionsOpen(DomainConflict):
    code = "inspections_open"
    message = "Every inspection of the cycle must conclude first."


class InspectionState(DomainConflict):
    code = "inspection_state"
    message = "The inspection has moved on."


# --- facts ---------------------------------------------------------------------------------------


async def _engagement_of(tenant: TenantContext, work_item_id: UUID) -> UUID:
    from abacus.modules.engagements.api import work_item_engagement

    found = await work_item_engagement(tenant, work_item_id)
    if found is None:
        raise NotFound("work_item")
    return found


async def not_objective(tenant: TenantContext, engagement_id: UUID) -> set[UUID]:
    """The EP or signer, every team member and the EQR: none of them may inspect it."""
    from abacus.modules.identity.api import team_of

    return {user for user, _role in await team_of(tenant.tenant_id, engagement_id)}


def score(weights: dict[str, object], facts: dict[str, bool], seed: int, key: str) -> Decimal:
    """Deterministic: the sum of the weights whose facts hold, plus a tie-break below 0.01 from
    the rule's seed and the candidate (the same rule and facts always give the same order)."""
    total = sum(
        (Decimal(str(weights[f])) for f, on in facts.items() if on and f in weights), Decimal(0)
    )
    tie = int(hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()[:4], 16) / Decimal(10_000_000)
    return (total + tie).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class Candidate:
    work_item_id: UUID
    engagement_name: str
    risk_score: Decimal
    selected_because: str
    not_objective_user_ids: list[UUID]


_RULE = text(
    "SELECT version, weights, seed FROM inspection_selection_rules ORDER BY version DESC LIMIT 1"
)


async def candidates(ctx: AuthContext, cycle_id: UUID) -> tuple[int, list[Candidate]]:
    """The cycle's candidate engagements, scored (code only). The pool is the cycle's archived or
    pre-lock work items the engagements module lists for practice."""
    from abacus.modules.engagements.api import attest_of, engagement_label, inspectable_work_items

    await authorise(ctx, "inspection.plan", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        rule = (await session.execute(_RULE)).first()
        year = await session.scalar(
            text("SELECT year FROM qm_cycles WHERE id = :c"), {"c": cycle_id}
        )
    if rule is None or year is None:
        raise NotFound("inspection_selection_rule")
    weights = cast(dict[str, object], rule.weights)
    out: list[Candidate] = []
    for work_item_id, engagement_id, facts in await inspectable_work_items(ctx.tenant, int(year)):
        facts = {**facts, "attest": bool(await attest_of(ctx.tenant, engagement_id))}
        label = await engagement_label(ctx.tenant, engagement_id)
        because = (
            ", ".join(sorted(f for f, on in facts.items() if on and f in weights)) or "rotation"
        )
        out.append(
            Candidate(
                work_item_id,
                "" if label is None else (label.client_entity_name or label.client_name),
                score(weights, facts, int(rule.seed), str(work_item_id)),
                because[:300],
                sorted(await not_objective(ctx.tenant, engagement_id)),
            )
        )
    out.sort(key=lambda c: (-c.risk_score, str(c.work_item_id)))
    return int(rule.version), out


# --- inspections ---------------------------------------------------------------------------------


async def plan(
    ctx: AuthContext,
    *,
    cycle_id: UUID,
    work_item_id: UUID,
    kind: str,
    inspector_user_id: UUID,
    due_on: date | None,
) -> UUID:
    from abacus.modules.identity.api import inspection_grant_expiry, issue_inspection_grants

    await authorise(ctx, "inspection.plan", Resource.firm(ctx.tenant_id))
    engagement_id = await _engagement_of(ctx.tenant, work_item_id)
    excluded = await not_objective(ctx.tenant, engagement_id)
    if inspector_user_id in excluded:
        raise NotObjective(facts={"user_id": str(inspector_user_id)})
    signer = min(excluded) if excluded else ctx.user_id
    async with tenant_session(ctx.tenant) as session:
        rule = (await session.execute(_RULE)).first()
    today = await clock_today(ctx.tenant)
    due = due_on or (today + timedelta(days=60))
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('inspection_ref:' || :t))"),
            {"t": str(ctx.tenant_id)},
        )
        number = int(
            cast(int, await tx.session.scalar(text("SELECT count(*) + 1 FROM inspections")))
        )
        inspection_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO inspections (tenant_id, cycle_id, ref, work_item_id, "
                    "inspected_engagement_id, kind, basis, ep_signer_user_id, inspector_user_id, "
                    "rule_version, due_on) VALUES (:t, :c, :ref, :w, :e, :k, 'sqms1', :ep, :i, "
                    ":rv, "
                    ":due) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "c": cycle_id,
                    "ref": f"INS-{today:%y}-{number:02d}",
                    "w": work_item_id,
                    "e": engagement_id,
                    "k": kind,
                    "ep": signer,
                    "i": inspector_user_id,
                    "rv": None if rule is None else int(rule.version),
                    "due": due,
                },
            ),
        )
        await issue_inspection_grants(
            tx, tenant_id=ctx.tenant_id, inspection_id=inspection_id,
            inspector_user_id=inspector_user_id, engagement_ids=[engagement_id],
            granted_by=ctx.user_id,
            expires_at=inspection_grant_expiry(None, datetime.combine(due, time(23, 59), UTC)),
        )  # fmt: skip
        tx.record("inspection.planned", target=Target("inspection", inspection_id))
    return inspection_id


async def _move(ctx: AuthContext, inspection_id: UUID, *, to: str) -> str:
    from abacus.modules.identity.api import revoke_inspection_grants

    await authorise(ctx, "inspection.update", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text("SELECT status, inspector_user_id FROM inspections WHERE id = :i FOR UPDATE"),
                {"i": inspection_id},
            )
        ).first()
        if row is None:
            raise NotFound("inspection")
        if (to, row.status) not in (("in_progress", "planned"), ("concluded", "in_progress")):
            raise InspectionState(facts={"status": str(row.status)})
        await tx.session.execute(
            text(
                "UPDATE inspections SET status = :s, concluded_on = CASE WHEN :s = 'concluded' "
                "THEN current_date END, version = version + 1 WHERE id = :i"
            ),
            {"s": to, "i": inspection_id},
        )
        if to == "concluded":
            await revoke_inspection_grants(tx, inspection_id, f"user:{ctx.user_id}")
        tx.record(
            f"inspection.{'started' if to == 'in_progress' else 'concluded'}",
            target=Target("inspection", inspection_id),
        )
    return to


async def start(ctx: AuthContext, inspection_id: UUID) -> str:
    return await _move(ctx, inspection_id, to="in_progress")


async def conclude(ctx: AuthContext, inspection_id: UUID) -> str:
    return await _move(ctx, inspection_id, to="concluded")


async def cycles(tenant: TenantContext) -> list[dict[str, object]]:
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT c.id, c.year, c.as_of, "
                        "(SELECT count(*) FROM inspections i WHERE i.cycle_id = c.id AND i.status "
                        "= 'planned') AS planned, "
                        "(SELECT count(*) FROM inspections i WHERE i.cycle_id = c.id AND i.status "
                        "= 'in_progress') AS in_progress, "
                        "(SELECT count(*) FROM inspections i WHERE i.cycle_id = c.id AND i.status "
                        "= 'concluded') AS concluded, "
                        "(SELECT count(*) FROM qm_findings f WHERE f.cycle_id = c.id AND f.status "
                        "<> 'remediated') AS findings_open "
                        "FROM qm_cycles c ORDER BY c.year DESC"
                    )
                )
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


async def inspections(tenant: TenantContext, cycle_id: UUID | None) -> list[dict[str, object]]:
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, ref, work_item_id, inspected_engagement_id, kind, basis, "
                        "inspector_user_id, "
                        "status, due_on FROM inspections WHERE CAST(:c AS uuid) IS NULL OR "
                        "cycle_id = :c ORDER BY ref"
                    ),
                    {"c": cycle_id},
                )
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


# --- findings ------------------------------------------------------------------------------------


async def record_finding(
    ctx: AuthContext,
    *,
    cycle_id: UUID,
    inspection_id: UUID | None,
    title: str,
    owner_user_id: UUID | None,
    due_on: date | None,
) -> UUID:
    await authorise(ctx, "qm_finding.record", Resource.firm(ctx.tenant_id))
    sealed = await seal(ctx.tenant_id, title.encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('qm_finding_ref:' || :t))"),
            {"t": str(ctx.tenant_id)},
        )
        number = int(
            cast(int, await tx.session.scalar(text("SELECT count(*) + 1 FROM qm_findings")))
        )
        finding_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO qm_findings (tenant_id, cycle_id, ref, inspection_id, source, "
                    "title_sealed, owner_user_id, due_on, raised_by_kind) VALUES (:t, :c, :ref, "
                    ":i, "
                    ":src, :title, :o, :due, 'human') RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "c": cycle_id,
                    "ref": f"QM-F-{number:02d}",
                    "i": inspection_id,
                    "src": "inspection" if inspection_id else "other",
                    "title": sealed,
                    "o": owner_user_id,
                    "due": due_on,
                },
            ),
        )
        tx.record(
            "qm_finding.recorded",
            target=Target("qm_finding", finding_id),
            after=Ref(number=number),
        )
    return finding_id


async def update_finding(
    ctx: AuthContext,
    finding_id: UUID,
    *,
    root_cause_category: str | None,
    root_cause: str | None,
    remediation: str | None,
    owner_user_id: UUID | None,
    due_on: date | None,
    version: int,
) -> None:
    await authorise(ctx, "qm_finding.update", Resource.firm(ctx.tenant_id))
    rc = (
        None
        if root_cause is None
        else await seal(ctx.tenant_id, root_cause.encode(), _FINGERPRINT)
    )
    rm = (
        None
        if remediation is None
        else await seal(ctx.tenant_id, remediation.encode(), _FINGERPRINT)
    )
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(
            text(
                "UPDATE qm_findings SET root_cause_category = coalesce(:cat, "
                "root_cause_category), "
                ""
                "root_cause_sealed = coalesce(:rc, root_cause_sealed), remediation_sealed = "
                "coalesce(:rm, remediation_sealed), owner_user_id = coalesce(:o, owner_user_id), "
                "due_on = coalesce(:due, due_on), status = CASE WHEN status = 'open' THEN "
                "'in_progress' ELSE status END, version = version + 1 WHERE id = :f AND version = "
                ":v "
                "AND status <> 'remediated' RETURNING id"
            ),
            {
                "cat": root_cause_category,
                "rc": rc,
                "rm": rm,
                "o": owner_user_id,
                "due": due_on,
                "f": finding_id,
                "v": version,
            },
        )
        if done is None:
            raise DomainConflict(facts={"reason": "stale_finding"})
        tx.record("qm_finding.updated", target=Target("qm_finding", finding_id))


async def evaluate_finding(
    ctx: AuthContext, finding_id: UUID, *, evaluation: str, rationale: str
) -> None:
    """The QM owner's evaluation (matrix `qm_finding.evaluate`; the table is human-only)."""
    await authorise(ctx, "qm_finding.evaluate", Resource.firm(ctx.tenant_id))
    sealed = await seal(ctx.tenant_id, rationale.encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO qm_finding_evaluations (tenant_id, finding_id, evaluation, "
                "rationale_sealed, evaluated_by) VALUES (:t, :f, :e, :r, :u)"
            ),
            {"t": ctx.tenant_id, "f": finding_id, "e": evaluation, "r": sealed, "u": ctx.user_id},
        )
        tx.record("qm_finding.evaluated", target=Target("qm_finding", finding_id))


async def remediate(ctx: AuthContext, finding_id: UUID, note: str) -> None:
    await authorise(ctx, "qm_finding.remediate", Resource.firm(ctx.tenant_id))
    sealed = await seal(ctx.tenant_id, note.encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(
            text(
                "UPDATE qm_findings SET status = 'remediated', remediated_at = clock_timestamp(), "
                "remediation_note_sealed = :n, version = version + 1 WHERE id = :f AND status <> "
                "'remediated' RETURNING id"
            ),
            {"n": sealed, "f": finding_id},
        )
        if done is None:
            raise DomainConflict(facts={"reason": "already_remediated"})
        tx.record("qm_finding.remediated", target=Target("qm_finding", finding_id))


async def remediation_todo(
    ctx: AuthContext, finding_id: UUID, *, title: str, assignee_user_id: UUID, due_on: date | None
) -> UUID:
    from abacus.modules.collaboration.api import create_todo

    todo_id = await create_todo(
        ctx, scope_kind="firm", engagement_id=None, title=title,
        assignee_user_id=assignee_user_id, due_on=due_on, anchor=None, checklist=(),
        source_thread_id=None,
    )  # fmt: skip
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO qm_finding_links (tenant_id, finding_id, link_kind, ref, created_by) "
                "VALUES (:t, :f, 'todo', CAST(:r AS jsonb), :u)"
            ),
            {
                "t": ctx.tenant_id,
                "f": finding_id,
                "r": json.dumps({"todo_id": str(todo_id)}),
                "u": ctx.user_id,
            },
        )
        tx.record("qm_finding.linked", target=Target("qm_finding", finding_id))
    return todo_id


async def findings(
    tenant: TenantContext, cycle_year: int | None, status: str | None
) -> list[dict[str, object]]:
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT f.id, f.ref, f.source, f.agent_key, f.title_sealed, f.status, "
                        "f.root_cause_category, "
                        "f.owner_user_id, f.due_on, f.raised_by_kind, f.version, i.ref AS "
                        "inspection_ref, "
                        "(SELECT e.evaluation FROM qm_finding_evaluations e WHERE e.finding_id = "
                        "f.id ORDER BY e.at DESC LIMIT 1) AS evaluation "
                        "FROM qm_findings f LEFT JOIN inspections i ON i.id = f.inspection_id "
                        "JOIN "
                        "qm_cycles c ON c.id = f.cycle_id "
                        "WHERE (CAST(:y AS int) IS NULL OR c.year = :y) AND (CAST(:s AS text) IS "
                        "NULL OR f.status = :s) ORDER BY f.ref"
                    ),
                    {"y": cycle_year, "s": status},
                )
            )
            .mappings()
            .all()
        )
    out: list[dict[str, object]] = []
    for r in rows:
        row = dict(r)
        row["title"] = (
            await open_sealed(tenant.tenant_id, bytes(r["title_sealed"]), _FINGERPRINT)
        ).decode()
        out.append(row)
    return out


# --- the annual evaluation -----------------------------------------------------------------------


async def annual_evaluation(tenant: TenantContext, year: int) -> dict[str, object]:
    async with tenant_session(tenant) as session:
        cycle = (
            await session.execute(text("SELECT id FROM qm_cycles WHERE year = :y"), {"y": year})
        ).first()
        if cycle is None:
            raise NotFound("qm_cycle")
        row = (
            await session.execute(
                text(
                    "SELECT responsible_user_id, decision_card_id, checklist FROM "
                    "annual_evaluations WHERE cycle_id = :c"
                ),
                {"c": cycle.id},
            )
        ).first()
        settings = (
            await session.execute(text("SELECT ultimate_responsible_user_id FROM qm_settings"))
        ).first()
        open_n = int(cast(int, await session.scalar(text(
            "SELECT count(*) FROM inspections WHERE cycle_id = :c AND status <> 'concluded'"
        ), {"c": cycle.id})))  # fmt: skip
    decided = None
    if row is not None and row.decision_card_id is not None:
        from abacus.modules.review.api import card_decided_at

        decided = await card_decided_at(tenant, UUID(str(row.decision_card_id)))
    responsible = (
        row.responsible_user_id if row is not None else (settings[0] if settings else None)
    )
    return {
        "cycle_id": cycle.id, "year": year, "responsible_user_id": responsible,
        "decision_card_id": None if row is None else row.decision_card_id,
        "checklist": {} if row is None else dict(row.checklist), "inspections_open": open_n,
        "status": "concluded" if decided is not None else "not_started", "concluded_at": decided,
    }  # fmt: skip


async def save_checklist(ctx: AuthContext, year: int, checklist: dict[str, bool]) -> None:
    await authorise(ctx, "quality.manage", Resource.firm(ctx.tenant_id))
    found = await annual_evaluation(ctx.tenant, year)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO annual_evaluations (tenant_id, cycle_id, responsible_user_id) VALUES "
                "(:t, :c, :u) ON CONFLICT (cycle_id) DO NOTHING"
            ),
            {
                "t": ctx.tenant_id,
                "c": found["cycle_id"],
                "u": found["responsible_user_id"] or ctx.user_id,
            },
        )
        await tx.session.execute(
            text(
                "UPDATE annual_evaluations SET checklist = CAST(:k AS jsonb) WHERE cycle_id = :c"
            ),
            {"k": json.dumps(checklist, sort_keys=True), "c": found["cycle_id"]},
        )
        tx.record(
            "qm_evaluation.checklist_saved",
            target=Target("qm_cycle", cast(UUID, found["cycle_id"])),
        )


async def request_conclusion(ctx: AuthContext, year: int) -> UUID:
    """409 `inspections_open` until every inspection concluded; then the firm-scope card for the
    QM owner (`qm_ultimate`)."""
    from abacus.modules.review.api import raise_firm_card

    found = await annual_evaluation(ctx.tenant, year)
    if int(cast(int, found["inspections_open"])) > 0:
        raise InspectionsOpen(facts={"open": str(found["inspections_open"])})
    if found["decision_card_id"] is not None:
        return cast(UUID, found["decision_card_id"])
    responsible = cast(UUID | None, found["responsible_user_id"])
    if responsible is None:
        raise NotFound("qm_owner")
    card_id = await raise_firm_card(
        ctx, kind=EVALUATION_KIND, question_key=f"sqms.annual_evaluation.{year}",
        reserved_user_id=responsible, options=[dict(o) for o in EVALUATION_OPTIONS],
    )  # fmt: skip
    await save_checklist(ctx, year, cast(dict[str, bool], found["checklist"]))
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("UPDATE annual_evaluations SET decision_card_id = :k WHERE cycle_id = :c"),
            {"k": card_id, "c": found["cycle_id"]},
        )
        tx.record(
            "qm_evaluation.conclusion_requested",
            target=Target("qm_cycle", cast(UUID, found["cycle_id"])),
        )
    return card_id


__all__ = [
    "EVALUATION_KIND",
    "EVALUATION_OPTIONS",
    "InspectionsOpen",
    "NotObjective",
    "annual_evaluation",
    "candidates",
    "conclude",
    "cycles",
    "evaluate_finding",
    "findings",
    "inspections",
    "not_objective",
    "plan",
    "record_finding",
    "remediate",
    "remediation_todo",
    "request_conclusion",
    "save_checklist",
    "score",
    "start",
    "update_finding",
]
