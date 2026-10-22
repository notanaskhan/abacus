"""Label-keyed deterministic draws, bit for bit the interim TS seed's (`apps/web/src/fixtures/
seed/prng.ts`: mulberry32 over an xmur3 string hash), so the scenario and the F-04-T05
fixtures agree until the fixtures are exported from here (F-04.21). No clock, no environment:
every value comes from a string label, and adding one record never reshuffles the others."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

_M: Final = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    """JavaScript's `Math.imul`, on unsigned 32-bit values."""
    return (a * b) & _M


def _hasher(text: str) -> Callable[[], int]:
    h = (1779033703 ^ len(text)) & _M
    for char in text:
        code = ord(char)
        if code > 0xFFFF:
            raise ValueError("labels are BMP text (JavaScript counts UTF-16 units)")
        h = _imul(h ^ code, 3432918353)
        h = ((h << 13) & _M) | (h >> 19)

    def draw() -> int:
        nonlocal h
        h = _imul(h ^ (h >> 16), 2246822507)
        h = _imul(h ^ (h >> 13), 3266489909)
        h ^= h >> 16
        return h

    return draw


def _mulberry32(seed: int) -> Callable[[], float]:
    a = seed & _M

    def draw() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & _M
        t = _imul(a ^ (a >> 15), 1 | a)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & _M) ^ t
        return ((t ^ (t >> 14)) & _M) / 4294967296

    return draw


class Rng:
    """A stream named by `namespace`."""

    def __init__(self, namespace: str) -> None:
        self._draw = _mulberry32(_hasher(namespace)())

    def next(self) -> float:
        return self._draw()

    def integer(self, low: int, high: int) -> int:
        """An integer in [low, high]."""
        return low + int(self._draw() * (high - low + 1))

    def pick[T](self, items: Sequence[T]) -> T:
        if not items:
            raise ValueError("pick from an empty list")
        return items[int(self._draw() * len(items))]

    def chance(self, probability: float) -> bool:
        return self._draw() < probability


def stable_id(label: str) -> str:
    """A UUID-shaped id (version 4 layout) derived from a label: the same label, the same id."""
    draw = _hasher(f"id:{label}")
    s = "".join(f"{draw():08x}" for _ in range(4))
    variant = "89ab"[int(s[16], 16) & 3]
    return f"{s[0:8]}-{s[8:12]}-4{s[13:16]}-{variant}{s[17:20]}-{s[20:32]}"
