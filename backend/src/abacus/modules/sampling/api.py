"""Public interface of the sampling module; other modules import only this (ADR-008).

Populations and selection by code (ADR-132; SPEC-037; TASK-083): pure functions over ledger
snapshots, with versioned rules, so another auditor can re-perform a selection.
"""

from abacus.modules.sampling.population import (
    RULE_VERSION,
    Entry,
    Population,
    build_population,
    tie_out,
)
from abacus.modules.sampling.selection import (
    CRITERIA_VERSION,
    DEFAULT_KEYWORDS,
    RANDOM_METHOD,
    RULES,
    Parameters,
    Selected,
    manual_kinds_for,
    seeded_v1,
    select,
)

__all__ = [
    "CRITERIA_VERSION",
    "DEFAULT_KEYWORDS",
    "RANDOM_METHOD",
    "RULES",
    "RULE_VERSION",
    "Entry",
    "Parameters",
    "Population",
    "Selected",
    "build_population",
    "manual_kinds_for",
    "seeded_v1",
    "select",
    "tie_out",
]
