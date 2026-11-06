"""The sampler library (ADR-340; A-03-T04): pure, versioned, frozen once registered.

Red, protected path (A-03-T01). Imports only the standard library, `abacus.kernel.numeric` and
`abacus.kernel.calendar` (the import-linter compute contract, A-03-T21).

- `canonical`: canonical population order and the population hash.
- `draw`: the one random primitive (`getrandbits(32)`), rejection sampling, partial Fisher-Yates.
- `v2_3`: sampler version 2.3 (`select`), frozen.
- `stats`: `attribute_size`, `udl`, `udl_percent`, `projected_misstatement`,
  `projected_misstatement_ratio`.
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
    misstatement_per_item,
    projected_misstatement,
    projected_misstatement_ratio,
    projection_carried,
    udl,
    udl_percent,
)
from abacus.modules.sampling.compute.v2_3 import Item, SampleDraw, StratumResult, StratumRule
from abacus.modules.sampling.compute.versions import CURRENT, SAMPLER_VERSIONS, sampler

__all__ = [
    "CURRENT",
    "SAMPLER_VERSIONS",
    "CanonicalPopulation",
    "Item",
    "Record",
    "SampleDraw",
    "StratumResult",
    "StratumRule",
    "attribute_size",
    "binomial_cdf",
    "canonical",
    "misstatement_per_item",
    "normalise_key",
    "projected_misstatement",
    "projected_misstatement_ratio",
    "projection_carried",
    "sampler",
    "udl",
    "udl_percent",
]
