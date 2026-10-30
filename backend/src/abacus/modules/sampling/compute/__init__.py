"""The sampler library (ADR-340; A-03-T04): pure, versioned, frozen once registered.

Red, protected path (A-03-T01). Imports only the standard library, `abacus.kernel.numeric` and
`abacus.kernel.calendar` (the import-linter compute contract, A-03-T21).

- `canonical`: canonical population order and the population hash.
- `draw`: the one random primitive (`getrandbits(32)`), rejection sampling, partial Fisher-Yates.
- `v2_3`: sampler version 2.3 (`select`), frozen.
- `stats`: `attribute_size`, `udl`, `udl_percent`, `project`, `project_ratio`.
- `versions`: `SAMPLER_VERSIONS`, `CURRENT`, `sampler(identifier)`.
"""

from abacus.modules.sampling.compute.canonical import (
    CanonicalPopulation,
    Record,
    canonical,
    normalise_key,
)
from abacus.modules.sampling.compute.stats import (
    attribute_size,
    binomial_cdf,
    project,
    project_ratio,
    udl,
    udl_percent,
)
from abacus.modules.sampling.compute.v2_3 import Item, Selection, StratumResult, StratumRule
from abacus.modules.sampling.compute.versions import CURRENT, SAMPLER_VERSIONS, sampler

__all__ = [
    "CURRENT",
    "SAMPLER_VERSIONS",
    "CanonicalPopulation",
    "Item",
    "Record",
    "Selection",
    "StratumResult",
    "StratumRule",
    "attribute_size",
    "binomial_cdf",
    "canonical",
    "normalise_key",
    "project",
    "project_ratio",
    "sampler",
    "udl",
    "udl_percent",
]
