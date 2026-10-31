"""Public interface of the sampling module; other modules import only this (ADR-008).

Populations and selection by code (ADR-132; SPEC-037; TASK-083): pure functions over ledger
snapshots, with versioned rules, so another auditor can re-perform a selection.
"""

from abacus.modules.sampling.compute import (
    CURRENT as SAMPLER_CURRENT,
)
from abacus.modules.sampling.compute import (
    SAMPLER_VERSIONS,
    attribute_size,
    projected_misstatement,
    udl,
    udl_percent,
)

# The routers the API mounts, in order (P-39; F-03-T07). A-03-T02: the sampling contract stub.
from abacus.modules.sampling.contract import ROUTERS
from abacus.modules.sampling.payments import (
    PAYMENTS_RULE_VERSION,
    Band,
    Bill,
    bills_by_party,
    build_payments,
    recorded_bill,
    select_payments,
    ties,
)
from abacus.modules.sampling.population import (
    RULE_VERSION,
    Entry,
    Population,
    build_population,
    tie_out,
)

# A-03-T07: populations and completeness ties (the routes call the service; T10 reads them).
from abacus.modules.sampling.populations import TIE_VERSION, population_view
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
    "PAYMENTS_RULE_VERSION",
    "RANDOM_METHOD",
    "ROUTERS",
    "RULES",
    "RULE_VERSION",
    "SAMPLER_CURRENT",
    "SAMPLER_VERSIONS",
    "TIE_VERSION",
    "Band",
    "Bill",
    "Entry",
    "Parameters",
    "Population",
    "Selected",
    "attribute_size",
    "bills_by_party",
    "build_payments",
    "build_population",
    "manual_kinds_for",
    "population_view",
    "projected_misstatement",
    "recorded_bill",
    "seeded_v1",
    "select",
    "select_payments",
    "tie_out",
    "ties",
    "udl",
    "udl_percent",
]
