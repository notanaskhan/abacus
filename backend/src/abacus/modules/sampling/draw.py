"""One version's draw, as the system for its firm (A-03-T10; A-03 §4.4; ADR-340 §3 to §5).

`SampleDrawWorkflow`'s activity runs `run_draw`: it reads the `drawing` version, re-checks that its
population still has a completeness tie and still hashes to what it was built as, selects with the
sampler version the version names (frozen, `compute`), checks the selection's inputs hash against
the one recorded when the draw started, and in one transaction writes the strata and items and
moves the version to `draft` with its items and content hashes. The approvers are told
(`sample_set.approval_requested`). Anything else marks the version `failed` with a code, so no
partial item list is ever visible. A redelivered run on a version that is no longer drawing is a
no-op.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Final, cast
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.sampling import sample_set_repository as repo
from abacus.modules.sampling.compute import (
    Record,
    SampleDraw,
    StratumRule,
    canonical,
    sampler,
)
from abacus.modules.sampling.sample_sets import TARGET, version_content_hash

ACTOR: Final = "sample_draw"
Row = Mapping[str, Any]  # Any: database rows and stored JSON of mixed column types


class SampleSetApprovalRequested(DomainEvent):
    """A drawn version waits for a manager's or the partner's approval (C16
    `sample_set_approval_requested`; identifiers only)."""

    event_type: ClassVar[str] = "sample_set.approval_requested"

    sample_set_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class DrawRefused(Exception):
    """The draw cannot go on; `code` is the version's failure code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _reader(tenant_id: UUID, version_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"{ACTOR}:{version_id}")


def _strata(parameters: Mapping[str, object]) -> list[StratumRule]:
    raw = cast(list[dict[str, Any]], parameters.get("strata") or [])  # Any: stored JSON
    return [
        StratumRule(
            None if s.get("min_amount") is None else Decimal(str(s["min_amount"])),
            None if s.get("max_amount") is None else Decimal(str(s["max_amount"])),
            s["test_rule"],
            s.get("random_count"),
        )
        for s in raw
    ]


async def fail_draw(tenant_id: UUID, version_id: UUID, code: str = "draw_failed") -> str:
    tenant = _reader(tenant_id, version_id)
    async with uow(tenant) as tx:
        if await repo.mark_failed(tx.session, version_id, code):
            tx.record("sample_set.draw_failed", target=Target(TARGET, version_id))
    return "failed"


async def run_draw(tenant_id: UUID, version_id: UUID) -> str:
    """Draw the version; its status afterwards (`draft`, `failed`, or what it already was)."""
    tenant = _reader(tenant_id, version_id)
    async with tenant_session(tenant) as session:
        version = await repo.version_by_id(session, version_id)
        if version is None or version["status"] != "drawing":
            return "missing" if version is None else str(version["status"])
        sample_set = await repo.sample_set(session, cast(UUID, version["sample_set_id"]))
        population_id = cast(UUID, version["population_id"])
        population = next(iter(await repo.populations(session, [population_id])), None)
        ties = await repo.tie_results(session, [population_id])
        records = await repo.records(session, population_id)
    if sample_set is None or population is None:
        return await fail_draw(tenant_id, version_id, "population_missing")
    if not ties:
        return await fail_draw(tenant_id, version_id, "completeness_tie_required")
    try:
        drawn = _select(version, str(population["sha256"]), records)
    except DrawRefused as refused:
        return await fail_draw(tenant_id, version_id, refused.code)
    by_ordinal = {int(r["ordinal"]): r for r in records}
    rules = _strata(_parameters(version))
    async with uow(tenant) as tx:
        await repo.insert_strata(
            tx.session,
            [
                {
                    "tenant_id": tenant_id,
                    "sample_set_version_id": version_id,
                    "position": s.position,
                    "min_amount": s.min_amount,
                    "max_amount": s.max_amount,
                    "population_count": s.population_count,
                    "population_amount": s.population_amount,
                    "test_rule": s.test_rule,
                    "random_count": rules[s.position - 1].random_count,
                    "selected_count": s.selected_count,
                }
                for s in drawn.strata
            ],
        )
        await repo.insert_items(
            tx.session,
            [
                {
                    "tenant_id": tenant_id,
                    "sample_set_version_id": version_id,
                    "position": item.position,
                    "population_record_ordinal": item.ordinal,
                    "record_key": item.record_key,
                    "stratum_position": item.stratum_position,
                    "selection_reason": item.reason,
                    "display": _display(by_ordinal[item.ordinal]),
                }
                for item in drawn.items
            ],
        )
        hashed = version_content_hash(version, str(population["sha256"]), drawn.items_hash)
        if not await repo.mark_draft(
            tx.session, {"id": version_id, "items_hash": drawn.items_hash, "content_hash": hashed}
        ):
            return "superseded"
        tx.record(
            "sample_set.draw_completed",
            target=Target(TARGET, version_id),
            after=Ref(items=len(drawn.items), items_hash=drawn.items_hash),
        )
        tx.emit(
            SampleSetApprovalRequested(
                sample_set_id=cast(UUID, sample_set["id"]),
                version_id=version_id,
                engagement_id=cast(UUID, sample_set["engagement_id"]),
                by_user=cast(UUID, version["created_by"]),
            )
        )
    return "draft"


def _parameters(version: Row) -> Mapping[str, object]:
    raw = version["parameters"]
    return cast(Mapping[str, object], raw if isinstance(raw, dict) else json.loads(str(raw)))


def _display(record: Row) -> str:
    raw = record["display"]
    return raw if isinstance(raw, str) else json.dumps(raw or {})


def _select(version: Row, population_hash: str, records: list[dict[str, Any]]) -> SampleDraw:
    """The frozen sampler's selection, checked against what the draw started with."""
    try:
        engine = sampler(str(version["sampler_version"]))
    except KeyError:
        raise DrawRefused("unknown_sampler_version") from None
    try:
        population = canonical(
            Record(str(r["record_key"]), r["amount"] if isinstance(r["amount"], Decimal) else None)
            for r in records
        )
    except ValueError:
        raise DrawRefused("population_unreadable") from None
    if population.population_hash != population_hash:
        raise DrawRefused("population_changed")
    stratified = version["method"] == "threshold_random_stratified"
    try:
        drawn = engine.select(
            population,
            str(version["method"]),
            seed=int(version["seed"]),
            size=None if stratified else int(version["final_size"]),
            strata=_strata(_parameters(version)) if stratified else (),
        )
    except ValueError:
        raise DrawRefused("parameters_invalid") from None
    if drawn.inputs_hash != version["inputs_hash"]:
        raise DrawRefused("inputs_changed")
    if not stratified and len(drawn.items) != int(version["final_size"]):
        raise DrawRefused("size_mismatch")
    return drawn
