"""JE score selection, v1 (A-08-T12; SPEC-657 AC-1.4; ADR P-57; ADR-340 §2, §5).

A frozen sampler version over a scored JE population (`je_scoring`): the selection's first part
is every entry at or above `score_min` (score order, then reference), cut to `top_n` where the
person set one; the second part is `unpredictable_n` entries drawn uniformly, with the one random
primitive (`draw.Stream` and the partial Fisher-Yates walk), from the entries the first part left
out, in reference order. The same scores, parameters and seed give the same items, and
`inputs_hash` proves which they were, so a re-performer reaches the same 34 + 6 = 40.

Imports only the standard library and this package (the compute contract, A-03-T21).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from abacus.modules.sampling.compute.draw import SEED_MAX, Stream, partial_fisher_yates

VERSION: Final = "je_select/1.0"
METHOD: Final = "je_score_selection"
Reason = Literal["risk_score", "unpredictable"]


@dataclass(frozen=True)
class Scored:
    """One scored entry as the selection reads it."""

    entry_ref: str
    score: int


@dataclass(frozen=True)
class Pick:
    position: int  # 1-based: the by-score part first, then the unpredictable picks
    entry_ref: str
    reason: Reason
    score: int


@dataclass(frozen=True)
class ScoreDraw:
    picks: tuple[Pick, ...]
    by_score: int
    unpredictable: int
    inputs_hash: str
    items_hash: str
    sampler_version: str = VERSION


class SelectionInvalid(ValueError):
    """Parameters the version cannot draw with (no rule, a bad seed, more picks than entries)."""


def _scores_hash(scores: Sequence[Scored]) -> str:
    raw = json.dumps(sorted((s.entry_ref, s.score) for s in scores), separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def inputs_hash(
    scores: Sequence[Scored],
    *,
    score_min: int | None,
    top_n: int | None,
    unpredictable_n: int,
    seed: int,
) -> str:
    document = {
        "engine_version": VERSION,
        "method": METHOD,
        "seed": seed,
        "score_min": score_min,
        "top_n": top_n,
        "unpredictable_n": unpredictable_n,
        "scores_hash": _scores_hash(scores),
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()


def items_hash(picks: Sequence[Pick]) -> str:
    raw = json.dumps([[p.position, p.entry_ref, p.reason] for p in picks], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def select(
    scores: Sequence[Scored],
    *,
    score_min: int | None,
    top_n: int | None,
    unpredictable_n: int,
    seed: int,
) -> ScoreDraw:
    """The by-score part, then the seeded unpredictable picks from what it left out."""
    if score_min is None and top_n is None:
        raise SelectionInvalid("score_min_or_top_n")
    if not 0 <= seed <= SEED_MAX or unpredictable_n < 0:
        raise SelectionInvalid("parameters")
    if len({s.entry_ref for s in scores}) != len(scores):
        raise SelectionInvalid("duplicate_entry")
    ranked = sorted(scores, key=lambda s: (-s.score, s.entry_ref))
    floor = 1 if score_min is None else max(score_min, 1)  # a zero score is never "by score"
    first = [s for s in ranked if s.score >= floor]
    if top_n is not None:
        first = first[:top_n]
    taken = {s.entry_ref for s in first}
    rest = sorted((s for s in scores if s.entry_ref not in taken), key=lambda s: s.entry_ref)
    if unpredictable_n > len(rest):
        raise SelectionInvalid("unpredictable_exceeds_population")
    drawn = partial_fisher_yates(Stream(seed), len(rest), unpredictable_n)
    picks = [Pick(i + 1, s.entry_ref, "risk_score", s.score) for i, s in enumerate(first)]
    picks += [
        Pick(len(first) + i + 1, rest[j].entry_ref, "unpredictable", rest[j].score)
        for i, j in enumerate(drawn)
    ]
    return ScoreDraw(
        picks=tuple(picks),
        by_score=len(first),
        unpredictable=len(drawn),
        inputs_hash=inputs_hash(
            scores, score_min=score_min, top_n=top_n, unpredictable_n=unpredictable_n, seed=seed
        ),
        items_hash=items_hash(picks),
    )
