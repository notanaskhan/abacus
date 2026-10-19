"""Selecting journal entries for testing, by code (ADR-132; SPEC-037 AC-2; TASK-083).

Each criterion is a pure rule with an id; `CRITERIA_VERSION` changes when any rule's meaning does.
The random part draws from entries no criterion chose, with a recorded seed, by `seeded_v1`: a
partial Fisher-Yates shuffle that uses only `random.Random(seed).random()` (whose sequence Python
guarantees across versions; `sample` isn't). People's picks join with their reasons. Every
selected entry lists every rule that chose it, and the same inputs always give the same entries.
"""

from __future__ import annotations

import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from abacus.modules.ledger.api import JournalKey
from abacus.modules.sampling.population import Entry, Population

CRITERIA_VERSION: Final = 2  # v2 (founder, 2026-10-19): the trivial floor
RANDOM_METHOD: Final = "seeded_v1"
RULES: Final = (
    "large",
    "round",
    "near_year_end",
    "manual",
    "rare_account",
    "weekend",
    "keywords",
    "random",
    "picked",
)
# D2: manual transaction types per export format (the snapshot's source without `import_`).
MANUAL_KINDS: Final[dict[str, frozenset[str]]] = {
    "qbo_gl_csv": frozenset({"journal entry"}),
    "xero_gl_xlsx": frozenset({"manual journal"}),
    "qbd_gl_xlsx": frozenset({"general journal"}),
    "netsuite_gl_csv": frozenset({"journal"}),
    "intacct_gl_csv": frozenset({"gj"}),
}
DEFAULT_KEYWORDS: Final = ("adjust", "correction", "reverse", "plug", "per", "manual", "reclass")


@dataclass(frozen=True)
class Parameters:
    threshold: Decimal  # performance materiality x the firm's percentage
    trivial: Decimal
    year_end: date
    round_unit: Decimal = Decimal(1000)
    window_days: int = 3
    manual_kinds: frozenset[str] = frozenset()
    rare_count: int = 5
    keywords: tuple[str, ...] = DEFAULT_KEYWORDS
    random_count: int = 10
    seed: int = 0


@dataclass(frozen=True)
class Selected:
    entry: Entry
    rules: tuple[str, ...]
    reason: str | None = None  # a person's pick


def manual_kinds_for(source: str, extra: tuple[str, ...] = ()) -> frozenset[str]:
    found = MANUAL_KINDS.get(source.removeprefix("import_"), frozenset())
    return found | {k.casefold() for k in extra}


def _keywords(words: tuple[str, ...]) -> re.Pattern[str] | None:
    cleaned = [re.escape(w.strip()) for w in words if w.strip()]
    if not cleaned:
        return None
    return re.compile(rf"\b(?:{'|'.join(cleaned)})\b", re.IGNORECASE)


def rules_for(
    entry: Entry, p: Parameters, rare: frozenset[str], words: re.Pattern[str] | None
) -> tuple[str, ...]:
    """The criteria this entry meets, in `RULES` order. Every criterion but `large` applies only
    at or above the trivial threshold (founder, 2026-10-19): otherwise a noisy rule such as
    `weekend` selects more entries than anyone could test."""
    found: list[str] = []
    if entry.amount >= p.threshold:
        found.append("large")
    if entry.amount < p.trivial:
        return tuple(found)
    if p.round_unit > 0 and entry.amount % p.round_unit == 0:
        found.append("round")
    if p.year_end - timedelta(days=p.window_days) < entry.posted_on <= p.year_end:
        found.append("near_year_end")
    if (entry.kind or "").casefold() in p.manual_kinds:
        found.append("manual")
    if any(a in rare for a in entry.accounts):
        found.append("rare_account")
    if entry.posted_on.weekday() >= 5:
        found.append("weekend")
    if words is not None and any(words.search(d) for d in entry.descriptions):
        found.append("keywords")
    return tuple(found)


def seeded_v1[T](items: list[T], count: int, seed: int) -> list[int]:
    """Indices of `count` items drawn without replacement, re-performable from `seed`."""
    rng = random.Random(seed)
    order = list(range(len(items)))
    chosen: list[int] = []
    for i in range(min(count, len(order))):
        j = i + int(rng.random() * (len(order) - i))
        order[i], order[j] = order[j], order[i]
        chosen.append(order[i])
    return sorted(chosen)


def select(
    population: Population, p: Parameters, picks: Mapping[JournalKey, str] | None = None
) -> list[Selected]:
    """AC-2: the criteria, then the random draw from the rest, then people's picks."""
    rare = frozenset(a for a, n in population.postings_per_account.items() if n < p.rare_count)
    words = _keywords(p.keywords)
    chosen: dict[JournalKey, list[str]] = {}
    rest: list[Entry] = []
    for entry in population.entries:
        found = rules_for(entry, p, rare, words)
        if found:
            chosen[entry.key] = list(found)
        else:
            rest.append(entry)
    for index in seeded_v1(rest, p.random_count, p.seed):
        chosen[rest[index].key] = ["random"]
    reasons = dict(picks or {})
    by_key = {e.key: e for e in population.entries}
    for key in reasons:
        if key not in by_key:
            raise KeyError("a pick names an entry outside the population")
        chosen.setdefault(key, []).append("picked")
    return [
        Selected(by_key[key], tuple(rules), reasons.get(key))
        for key, rules in sorted(chosen.items())
    ]
