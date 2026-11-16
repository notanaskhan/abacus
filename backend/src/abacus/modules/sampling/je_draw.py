"""The `je_score_selection` draw inside `SampleDrawWorkflow` (A-08-T12; SPEC-657 AC-1.4; ADR P-57).

`draw.run_draw` hands a `je_score_selection` version here: the frozen JE selection re-runs over
the scores of the run the version names, with the version's own seed and parameters, and the
result must hash to the inputs recorded when the selection was requested; any difference refuses
the draw (`inputs_changed`), so the items are always the ones the person asked for.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.sampling import je_repository as repo
from abacus.modules.sampling.compute import je_selection

METHOD: Final = je_selection.METHOD


class JeDrawRefused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class JeItem:
    position: int
    ordinal: int
    record_key: str
    reason: str
    stratum_position: int | None = None


@dataclass(frozen=True)
class JeDrawn:
    items: tuple[JeItem, ...]
    items_hash: str


def parameters_of(version: Mapping[str, Any]) -> dict[str, Any]:  # Any: stored JSON
    raw = version["parameters"]
    if isinstance(raw, dict):
        return cast(dict[str, Any], raw)  # Any: stored JSON
    return cast(dict[str, Any], json.loads(str(raw)))  # Any: stored JSON


async def je_items(
    session: AsyncSession,
    version: Mapping[str, Any],  # Any: a database row
    records: Sequence[Mapping[str, Any]],  # Any: database rows
) -> JeDrawn:
    p = parameters_of(version)
    if str(version["sampler_version"]) != je_selection.VERSION:
        raise JeDrawRefused("unknown_sampler_version")
    run_id = UUID(str(p["run_id"]))
    scores = [
        je_selection.Scored(ref, score) for ref, score, _ in await repo.all_scores(session, run_id)
    ]
    if isinstance(p.get("expansion"), dict):
        return await _expanded_items(session, version, records, scores, p["expansion"])
    try:
        selection = je_selection.select(
            scores,
            score_min=p.get("score_min"),
            top_n=p.get("top_n"),
            unpredictable_n=int(p.get("unpredictable_n") or 0),
            seed=int(version["seed"]),
        )
    except je_selection.SelectionInvalid:
        raise JeDrawRefused("parameters_invalid") from None
    if selection.inputs_hash != version["inputs_hash"]:
        raise JeDrawRefused("inputs_changed")
    if len(selection.picks) != int(version["final_size"]):
        raise JeDrawRefused("size_mismatch")
    ordinals = {str(r["record_key"]): int(r["ordinal"]) for r in records}
    try:
        items = tuple(
            JeItem(pick.position, ordinals[pick.entry_ref], pick.entry_ref, pick.reason)
            for pick in selection.picks
        )
    except KeyError:
        raise JeDrawRefused("population_changed") from None
    return JeDrawn(items, selection.items_hash)


async def _expanded_items(
    session: AsyncSession,
    version: Mapping[str, Any],  # Any: a database row
    records: Sequence[Mapping[str, Any]],  # Any: database rows
    scores: Sequence[je_selection.Scored],
    expansion: Mapping[str, Any],  # Any: the version's parameters
) -> JeDrawn:
    """A-08-T17: an approved expansion's version. The base version's items keep their positions;
    the additions follow, recomputed from the version's seed; any drift refuses the draw."""
    from abacus.modules.sampling import sample_set_repository as set_repo
    from abacus.modules.sampling.expansions import expand

    base = await set_repo.items(session, UUID(str(expansion["base_version_id"])))
    by_ref = {s.entry_ref: s.score for s in scores}
    prefix = [
        je_selection.Pick(
            int(i["position"]),
            str(i["record_key"]),
            i["selection_reason"],
            by_ref.get(str(i["record_key"]), 0),
        )
        for i in sorted(base, key=lambda i: int(i["position"]))
    ]
    try:
        expanded = expand(
            prefix,
            scores,
            add_by_score=int(expansion["add_by_score"]),
            add_unpredictable=int(expansion["add_unpredictable"]),
            add_keys=[str(k) for k in cast("list[object]", expansion.get("add_item_keys") or [])],
            seed=int(version["seed"]),
        )
    except Exception:
        raise JeDrawRefused("parameters_invalid") from None
    if expanded.prefix_hash != expansion["prefix_hash"]:
        raise JeDrawRefused("inputs_changed")
    if expanded.items_hash != version["inputs_hash"]:
        raise JeDrawRefused("inputs_changed")
    ordinals = {str(r["record_key"]): int(r["ordinal"]) for r in records}
    try:
        items = tuple(
            JeItem(pick.position, ordinals[pick.entry_ref], pick.entry_ref, pick.reason)
            for pick in expanded.picks
        )
    except KeyError:
        raise JeDrawRefused("population_changed") from None
    return JeDrawn(items, expanded.items_hash)
