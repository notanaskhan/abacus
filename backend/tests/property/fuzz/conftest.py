"""Hypothesis profiles for the parser fuzz suite (Q-03-T030).

`ci` (the default) is small and derandomised so the gate is deterministic; `nightly` is what
`fuzz-nightly.yml` runs inside its 15-minute budget. Pick one with ABACUS_FUZZ_PROFILE.
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci",
    max_examples=40,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.register_profile(
    "nightly",
    max_examples=20_000,
    deadline=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.load_profile(os.environ.get("ABACUS_FUZZ_PROFILE", "ci"))
