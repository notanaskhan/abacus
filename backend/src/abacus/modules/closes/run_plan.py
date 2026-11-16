"""The close run's code plan, `closes.close_run` (C-01-T20; C-01 F3, §4.5; DEC-57, DEC-50;
ADR-050, ADR-005). Code plans, no model: the run is P-10's engagement run with this provider's
steps, one per procedure of the close's pinned plan version, in task groups by procedure type.

| Group (CLS-02 order) | Procedures | Run-step kind |
|---|---|---|
| Recategorize Revenue and Expenses | `recategorize` | `close_recategorize` |
| Reconcile to Statements | `reconciliation` | `close_reconcile_statement` |
| Reconcile Third Party Sales | `third_party_sales` | `close_clear_third_party_sales` |
| Identify and Amortize Prepaids | `amortization` | `close_amortize_prepaid` |
| Identify and Depreciate Fixed Assets | `depreciation` | `close_depreciate_fixed_assets` |
| Roll accruals | `accrual` | `close_roll_accruals` |
| Age and clear | `aging`, `clear_and_age`, `aging_cutoff` | `close_age_items` |
| Tie out | `rollforward`, `tie_to_return`, `tie_to_filings`, `flux` | `close_tie_out` |

Copperleaf's Run 2 is 2 + 3 + 2 + 1 + 1 = 9 procedures in 5 groups.

- **Scopes.** `all`, `group` (one group key), `failed_only` (the procedures whose last attempt
  failed) and `accounts` (the named accounts' procedures). A scoped run reruns just those rows;
  earlier results stand (no dependency chain between groups: each procedure reads the ledger).
- **Decisions.** A third-party group whose clearing account carries an unresolved unmatched
  transfer gets a `close_treatment` decision step first (CLS-02 d, the $6,412.40 Square
  transfer): the group's procedures wait on it; the other groups run. The card's options are code
  (record as an outstanding item, reclassify to the clearing account, ask the client) with a code
  recommendation; only the named person's click answers it (C3; DEC-50).
- **Concurrency** is the run's `max_parallel_steps` = 3 (CLS-02 "3 running at once").
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.modules.agents.api import (
    PlanRequest,
    PlanStep,
    register_plan_provider,
    run_step_rows,
    work_item_runs,
)
from abacus.modules.review.api import (
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    register_decision_kind,
)

PROVIDER: Final = "closes.close_run"
RUN_STEP: Final = "run_step."
TREATMENT_KIND: Final = "close_treatment"


@dataclass(frozen=True)
class Group:
    key: str
    label: str
    kind: str  # the run-step kind
    procedures: frozenset[str]


GROUPS: Final[tuple[Group, ...]] = (
    Group("recategorize", "Recategorize Revenue and Expenses", "close_recategorize", frozenset({"recategorize"})),
    Group("reconcile", "Reconcile to Statements", "close_reconcile_statement", frozenset({"reconciliation"})),
    Group("third_party", "Reconcile Third Party Sales", "close_clear_third_party_sales", frozenset({"third_party_sales"})),
    Group("prepaids", "Identify and Amortize Prepaids", "close_amortize_prepaid", frozenset({"amortization"})),
    Group("fixed_assets", "Identify and Depreciate Fixed Assets", "close_depreciate_fixed_assets", frozenset({"depreciation"})),
    Group("accruals", "Roll accruals", "close_roll_accruals", frozenset({"accrual"})),
    Group("aging", "Age and clear", "close_age_items", frozenset({"aging", "clear_and_age", "aging_cutoff"})),
    Group("tie_out", "Tie out", "close_tie_out", frozenset({"rollforward", "tie_to_return", "tie_to_filings", "flux"})),
)  # fmt: skip
GROUP_OF: Final = {p: g for g in GROUPS for p in g.procedures}
LEVEL: Final = {g.key: n for n, g in enumerate(GROUPS, start=1)}


class PlanNotPinned(DomainConflict):
    """The close has no published plan version for its month (CLS-09 first)."""

    code = "plan_not_pinned"


@dataclass(frozen=True)
class PlanRow:
    row_id: UUID
    position: int
    account_external_id: str | None
    account_name: str
    procedure: str
    method: str
    source: str
    review_level: str


_ROWS = text(
    "SELECT r.id, r.position, r.account_external_id, r.account_name, r.procedure, r.method, "
    "r.source, r.review_level FROM closes c JOIN close_plan_rows r "
    "ON r.version_id = c.close_plan_version_id WHERE c.work_item_id = :c "
    "AND r.frequency = 'monthly' ORDER BY r.position"
)
# An unmatched processor transfer on the close, not yet resolved by a person (CLS-02 d).
_PENDING = text(
    "SELECT i.id, i.ref, i.amount, x.account_external_id FROM reconciling_items i "
    "JOIN reconciliations x ON x.id = i.reconciliation_id "
    "WHERE x.close_id = :c AND i.kind = 'unmatched_transfer' AND i.issue_id IS NULL "
    "AND i.proposed_entry_id IS NULL AND NOT EXISTS (SELECT 1 FROM reconciling_item_resolutions r "
    "WHERE r.reconciling_item_id = i.id) ORDER BY i.created_at, i.id"
)


async def plan_rows(tenant: TenantContext, close_id: UUID) -> list[PlanRow]:
    async with tenant_session(tenant) as session:
        return [PlanRow(*r) for r in (await session.execute(_ROWS, {"c": close_id})).all()]  # pyright: ignore[reportArgumentType] -- column order


@dataclass(frozen=True)
class PendingTreatment:
    item_id: UUID
    ref: str
    amount: Decimal
    account_external_id: str


async def pending_treatments(tenant: TenantContext, close_id: UUID) -> list[PendingTreatment]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_PENDING, {"c": close_id})).all()
    return [PendingTreatment(r[0], r[1], Decimal(r[2]), r[3]) for r in rows]


def step_key(row: PlanRow) -> str:
    return f"p{row.position}_{row.procedure}"[:80]


def work_item_ref(close_id: UUID) -> str:
    return f"close:{close_id}"


def select_rows(
    rows: Sequence[PlanRow], scope: str, keys: Sequence[str], failed: frozenset[str] = frozenset()
) -> list[PlanRow]:
    if scope == "all":
        return list(rows)
    if scope == "group":
        wanted = set(keys)
        return [r for r in rows if GROUP_OF.get(r.procedure) and GROUP_OF[r.procedure].key in wanted]
    if scope == "accounts":
        wanted = set(keys)
        return [r for r in rows if r.account_external_id in wanted]
    if scope in ("failed_only", "task"):
        return [r for r in rows if step_key(r) in (failed if scope == "failed_only" else set(keys))]
    raise NotFound("run_scope")


def plan_steps(
    rows: Sequence[PlanRow], pending: Sequence[PendingTreatment], close_id: UUID
) -> list[PlanStep]:
    out: list[PlanStep] = []
    decided: dict[str, str] = {}
    for item in pending:
        key = f"treatment_{str(item.item_id)[:8]}"
        decided.setdefault("third_party", key)
        out.append(
            PlanStep(
                key=key,
                label="Decide the unmatched transfer",
                level=LEVEL["third_party"],
                kind="decision",
                arguments={
                    "decision_kind": TREATMENT_KIND,
                    "question_key": f"treatment:{item.item_id}",
                    "group": "third_party",
                },
            )
        )
    for row in rows:
        group = GROUP_OF.get(row.procedure)
        if group is None:
            continue
        gate = decided.get(group.key)
        out.append(
            PlanStep(
                key=step_key(row),
                label=f"{group.label}: {row.account_name}"[:200],
                level=LEVEL[group.key],
                kind="compute",
                tool=f"{RUN_STEP}{group.kind}",
                arguments={
                    "group": group.key,
                    "close_id": str(close_id),
                    "plan_row_id": str(row.row_id),
                    "procedure": row.procedure,
                    **({} if row.account_external_id is None else {"account": row.account_external_id}),
                },
                depends_on=(gate,) if gate else (),
            )
        )
    return out


async def failed_keys(tenant: TenantContext, close_id: UUID) -> frozenset[str]:
    """The procedures whose newest attempt failed, across the close's runs (agents' reads)."""
    latest: dict[str, str] = {}
    for run in await work_item_runs(tenant, work_item_ref(close_id)):
        for step in await run_step_rows(tenant, run.run_id):
            if step.key is not None and step.key not in latest:
                latest[step.key] = step.state
        # runs come newest first: a key seen in a newer run keeps that run's state
    return frozenset(k for k, state in latest.items() if state == "failed")


async def close_run_plan(
    tenant: TenantContext, engagement_id: UUID, request: PlanRequest
) -> list[PlanStep]:
    del engagement_id  # authorised by the start; the work item names the close
    rows = await plan_rows(tenant, request.work_item_id)
    if not rows:
        raise PlanNotPinned(facts={"close": "no_plan_rows"})
    failed = await failed_keys(tenant, request.work_item_id) if request.scope == "failed_only" else frozenset()
    chosen = select_rows(rows, request.scope, request.keys, failed)
    third_party = any(GROUP_OF.get(r.procedure) is GROUP_OF["third_party_sales"] for r in chosen)
    pending = await pending_treatments(tenant, request.work_item_id) if third_party else []
    return plan_steps(chosen, pending, request.work_item_id)


def groups_of(plan: Sequence[PlanStep]) -> list[tuple[str, int]]:
    """Procedures per group in CLS-02 order (decisions not counted): Run 2 = 2 + 3 + 2 + 1 + 1."""
    counts = {g.key: 0 for g in GROUPS}
    for step in plan:
        group = step.arguments.get("group")
        if step.kind == "compute" and isinstance(group, str):
            counts[group] += 1
    return [(k, n) for k, n in counts.items() if n]


# --- the close_treatment decision card (C3; code options, code recommendation) -------------------

_ITEM = text(
    "SELECT i.ref, i.amount, i.txn_date, x.account_external_id FROM reconciling_items i "
    "JOIN reconciliations x ON x.id = i.reconciliation_id WHERE i.id = :i AND x.close_id = :c"
)


async def treatment_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """Three code options over the transfer's own figures; the recommendation is code: a transfer
    older than the payout window is asked of the client, a recent one is carried as outstanding."""
    item_id = UUID(subject.question_key.removeprefix("treatment:"))
    if subject.work_item_id is None:
        raise NotFound("close")
    async with tenant_session(tenant) as session:
        found = (await session.execute(_ITEM, {"i": item_id, "c": subject.work_item_id})).first()
    if found is None:
        raise NotFound("reconciling_item")
    amount = f"{Decimal(found[1]):.2f}"
    figures = {"amount": amount, "ref": str(found[0]), "account": str(found[3])}
    proposed = "ask_client"
    return ComputedCard(
        options=(
            CardOption("record_outstanding", "Carry it as an outstanding item", figures),
            CardOption("reclassify", "Reclassify to the clearing account", figures),
            CardOption(
                "ask_client",
                "Ask the client what the transfer was",
                figures,
                "Proposed" if proposed == "ask_client" else None,
            ),
        )
    )


def register_treatment_kind() -> None:
    register_decision_kind(
        DecisionKind(
            code=TREATMENT_KIND,
            reserved_role="manager",
            options=treatment_card,
            questions={"treatment": "How should the unmatched transfer be treated?"},
        )
    )


register_plan_provider(PROVIDER, close_run_plan)
