"""The engine field profile for the W2 file bridge (T-04-T30; T-04 §3.10 AC-10.1 to AC-10.3;
ADR-150 W2, ADR P-18; DEC-49, DEC-3405). RED.

What the bridge's workbook may carry, per engine: the `Fields` sheet's columns and the shape of an
`engine_field_key` the partner's engine admin validated (TR-06: only validated keys are mapped; a
key outside the profile blocks the export with its name). The tax module maps a worksheet field
to its key (`return_fields.engine_field_key`); this module only says what the engine reads. It
never transmits anything (DEC-49, R-04).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class EngineFieldProfile:
    engine: str
    columns: tuple[str, ...]
    key_pattern: re.Pattern[str]

    def valid_key(self, key: str) -> bool:
        return self.key_pattern.fullmatch(key) is not None


CCH_AXCESS: Final = EngineFieldProfile(
    engine="cch_axcess",
    columns=("field_key", "form", "line", "value"),
    # `<form>.<line>` keys, lower case: `it201.line20`, `f1040.l2a`, `nyc.tax`,
    # `it360_1.recompute`.
    key_pattern=re.compile(r"[a-z0-9][a-z0-9_]{0,39}(\.[a-z0-9][a-z0-9_]{0,39}){1,3}"),
)
PROFILES: Final = {CCH_AXCESS.engine: CCH_AXCESS}


def engine_field_profile(engine: str = "cch_axcess") -> EngineFieldProfile:
    found = PROFILES.get(engine)
    if found is None:
        raise LookupError(f"no engine field profile for {engine!r}")
    return found


__all__ = ["CCH_AXCESS", "EngineFieldProfile", "engine_field_profile"]
