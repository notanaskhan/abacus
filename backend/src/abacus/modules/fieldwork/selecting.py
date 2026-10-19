"""The selection activity's work (SPEC-037 AC-1, AC-2; TASK-083; ADR-132).

The platform acts on the procedure's own row (the row is the proof, as runs are for retrievals):
it streams the engagement's newest reconciled general ledger snapshot, builds the population and
ties it out, then selects by the procedure's parameters and the engagement's materiality, and
records population, selection and entries in one transaction. An untied population is recorded
with its reason and selects nothing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import cast
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import check_facts, entity_of
from abacus.modules.fieldwork.repository import (
    get_procedure,
    insert_items,
    insert_population,
    insert_selection,
    lock_procedure,
    newest_materiality,
    set_procedure,
)
from abacus.modules.ledger.api import GlEntry, JournalKey, gl_entries, latest_gl_snapshot
from abacus.modules.sampling.api import (
    CRITERIA_VERSION,
    RANDOM_METHOD,
    RULE_VERSION,
    Parameters,
    build_population,
    manual_kinds_for,
    select,
    tie_out,
)

PAGE = 5000


def _reader(tenant_id: UUID, procedure_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"procedure:{procedure_id}")


async def _fail(tenant: TenantContext, procedure_id: UUID, code: str) -> str:
    async with uow(tenant) as tx:
        await set_procedure(tx.session, procedure_id, status="failed", failure_code=code)
        tx.record("procedure.failed", target=Target("procedure", procedure_id))
    return "failed"


async def fail_selection(tenant_id: UUID, procedure_id: UUID) -> None:
    """After the workflow's retries: `failed` with `selection_failed`, so it can be run again."""
    tenant = _reader(tenant_id, procedure_id)
    async with tenant_session(tenant) as session:
        found = await get_procedure(session, procedure_id)
    if found is not None and found.status == "selecting":
        await _fail(tenant, procedure_id, "selection_failed")


async def run_selection(tenant_id: UUID, procedure_id: UUID, requested_by: UUID) -> str:
    tenant = _reader(tenant_id, procedure_id)
    async with tenant_session(tenant) as session:
        procedure = await get_procedure(session, procedure_id)
        if procedure is None or procedure.status != "selecting":
            return procedure.status if procedure is not None else "missing"
        materiality = await newest_materiality(session, procedure.engagement_id)
    facts = await check_facts(tenant, procedure.engagement_id)
    entity = await entity_of(tenant, procedure.engagement_id)
    if materiality is None:
        return await _fail(tenant, procedure_id, "materiality_missing")
    snapshot = (
        await latest_gl_snapshot(tenant, entity, facts.fiscal_period_end)
        if facts is not None and entity is not None
        else None
    )
    if snapshot is None or facts is None:
        return await _fail(tenant, procedure_id, "no_ledger")
    postings: list[GlEntry] = []
    after = 0
    while True:
        page = await gl_entries(tenant, snapshot.id, after=after, limit=PAGE)
        if not page:
            break
        postings.extend(page)
        after = page[-1].line_no
    population = build_population(postings)
    del postings
    failure = tie_out(population, line_count=snapshot.line_count, total_debit=snapshot.total_debit)
    raw = procedure.parameters
    params = Parameters(
        threshold=(materiality.performance * int(cast(int, raw["threshold_percent"])) / 100),
        trivial=materiality.trivial,
        year_end=facts.fiscal_period_end,
        round_unit=Decimal(str(raw["round_unit"])),
        window_days=int(cast(int, raw["window_days"])),
        manual_kinds=manual_kinds_for(
            snapshot.source, tuple(str(k) for k in cast(list[object], raw["manual_kinds_extra"]))
        ),
        rare_count=int(cast(int, raw["rare_count"])),
        keywords=tuple(str(k) for k in cast(list[object], raw["keywords"])),
        random_count=int(cast(int, raw["random_count"])),
        seed=int(cast(int, raw["seed"])),
    )
    picks: dict[JournalKey, str] = {}
    for pick in cast(list[dict[str, object]], raw.get("picks") or []):
        key = cast(list[str], pick["key"])
        picks[(key[0], key[1], key[2], key[3])] = str(pick["reason"])
    known = {e.key for e in population.entries}
    picks = {k: r for k, r in picks.items() if k in known}  # a pick outside this ledger lapses
    chosen = select(population, params, picks) if failure is None else []
    async with uow(tenant) as tx:
        locked = await lock_procedure(tx.session, procedure_id)
        if locked is None or locked.status != "selecting":
            return locked.status if locked is not None else "missing"
        population_id = await insert_population(
            tx.session,
            tenant_id=tenant_id,
            procedure_id=procedure_id,
            gl_snapshot_id=snapshot.id,
            rule_version=RULE_VERSION,
            entry_count=len(population.entries),
            line_count=population.line_count,
            total_debit=population.total_debit,
            total_credit=population.total_credit,
            tied=failure is None,
            failure=failure,
        )
        if failure is not None:
            await set_procedure(
                tx.session, procedure_id, status="failed", failure_code="population_not_tied"
            )
            tx.record("procedure.failed", target=Target("procedure", procedure_id))
            return "failed"
        selection_id = await insert_selection(
            tx.session,
            tenant_id=tenant_id,
            procedure_id=procedure_id,
            population_id=population_id,
            parameters={**raw, "threshold": str(params.threshold)},
            criteria_version=CRITERIA_VERSION,
            random_method=RANDOM_METHOD,
            seed=params.seed,
            item_count=len(chosen),
            created_by=requested_by,
        )
        await insert_items(
            tx.session,
            [
                {
                    "tenant_id": tenant_id,
                    "selection_id": selection_id,
                    "position": i,
                    "posted_on": s.entry.posted_on,
                    "kind": s.entry.key[1],
                    "reference": s.entry.key[2],
                    "counterparty": s.entry.counterparty or s.entry.key[3],
                    "line_nos": list(s.entry.line_nos),
                    "accounts": list(s.entry.accounts),
                    "amount": s.entry.amount,
                    "descriptions": [d[:500] for d in s.entry.descriptions[:5]],
                    "rules": list(s.rules),
                    "reason": s.reason,
                }
                for i, s in enumerate(chosen)
            ],
        )
        await set_procedure(tx.session, procedure_id, status="selected", failure_code=None)
        tx.record(
            "procedure.selected",
            target=Target("procedure", procedure_id),
            after=Ref(selection_id=selection_id, items=len(chosen)),
        )
    return "selected"
