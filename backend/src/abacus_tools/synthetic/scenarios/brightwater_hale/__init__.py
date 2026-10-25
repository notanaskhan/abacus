"""The Brightwater Hale scenario (F-04-T10; SPEC-307; DEC-27, DEC-47): one synthetic firm on
one timeline, built deterministically and replayed through the service APIs by the loader
(F-04-T13). Everything here is synthetic; nothing reads a clock, the environment or a file."""

from abacus_tools.synthetic.scenarios.brightwater_hale import (
    binders,  # registers "binders" (P-06-T08)
    compliance,  # registers "compliance" (Q-02-T39)
    firm_people,  # registers "people" (G-01-T06)
    portal,  # registers "portal" (P-08-T14)
    shell,  # registers "shell" (P-01-T07)
)
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import (
    SCENARIO_HASH,
    SCENARIO_VERSION,
    Scenario,
    build,
)

__all__ = [
    "SCENARIO_HASH",
    "SCENARIO_VERSION",
    "Scenario",
    "binders",
    "build",
    "compliance",
    "firm_people",
    "portal",
    "shell",
]
