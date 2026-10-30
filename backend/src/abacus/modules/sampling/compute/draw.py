"""The one random primitive and the walks built on it (ADR-340 §2; A-03-T04; SPEC-580 AC-9).

Selection calls `random.Random(seed).getrandbits(32)` and nothing else from `random`: MT19937's
output for a seed is stable across Python versions, while `sample`, `shuffle`, `randrange` and
`random()` are not promised to be. Rejection sampling to a uniform index and the partial
Fisher-Yates walk are Accrued code, frozen with the version that uses them. A unit test fails if
any other `random` member is referenced under `sampling/compute/`.
"""

from __future__ import annotations

import random
from typing import Final

SEED_MAX: Final = 2**24 - 1  # 24-bit seeds, 0 to 16,777,215 (ADR-340 §5)
_BITS: Final = 32
_SPAN: Final = 2**_BITS


class Stream:
    """Uniform indices from one seed, by rejection sampling over 32-bit words."""

    def __init__(self, seed: int) -> None:
        if not 0 <= seed <= SEED_MAX:
            raise ValueError("a seed is a 24-bit value")
        self._rng = random.Random(seed)  # noqa: S311 - re-performable selection, not secrecy (ADR-340)

    def below(self, bound: int) -> int:
        """A uniform integer in [0, bound): words at or above the largest multiple are redrawn."""
        if bound <= 0:
            raise ValueError("bound must be positive")
        limit = (_SPAN // bound) * bound
        word = self._rng.getrandbits(_BITS)
        while word >= limit:
            word = self._rng.getrandbits(_BITS)
        return word % bound


def partial_fisher_yates(stream: Stream, population: int, count: int) -> list[int]:
    """`count` distinct indices from range(population), in draw order.

    Step i swaps slot i with a uniform slot in [i, population) and takes slot i; only the touched
    slots are stored, so a draw of 25 from 1,912 never builds the whole list.
    """
    if not 0 <= count <= population:
        raise ValueError("count must lie between 0 and the population")
    swapped: dict[int, int] = {}
    chosen: list[int] = []
    for i in range(count):
        j = i + stream.below(population - i)
        value_j = swapped.get(j, j)
        swapped[j] = swapped.get(i, i)
        chosen.append(value_j)
    return chosen
