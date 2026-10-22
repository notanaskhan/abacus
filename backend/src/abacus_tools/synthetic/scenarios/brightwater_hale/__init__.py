"""The Brightwater Hale scenario (F-04-T10; SPEC-307; DEC-27, DEC-47): one synthetic firm on
one timeline, built deterministically and replayed through the service APIs by the loader
(F-04-T13). Everything here is synthetic; nothing reads a clock, the environment or a file."""

from abacus_tools.synthetic.scenarios.brightwater_hale import shell  # registers "shell" (P-01-T07)
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import (
    SCENARIO_HASH,
    SCENARIO_VERSION,
    Scenario,
    build,
)

__all__ = ["SCENARIO_HASH", "SCENARIO_VERSION", "Scenario", "build", "shell"]
