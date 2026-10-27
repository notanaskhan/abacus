"""The AI policy's stricter-only validator (G-02-T23; ADR-186 item 4, ADR-187; SPEC-349 AC-38).

A draft's sections may only be as strict as the platform's compiled defaults, or stricter:

- **Locked cells** (`LOCKS`): the policy principal and every gate's policy acceptance stay off
  (ADR-187, P-08 dormant), and the §7216 consent stays required (ADR-167). Any other value is
  refused.
- **Tunable cells** (`STRICTER`): moving a number or a switch the loose way past the platform
  default is refused (`lower`: the draft's value may not exceed the default; `higher`: it may not
  fall below it). Auto mode may be turned off for any type; it may never be turned on for a type
  whose default is off.
- **Gates** must be the catalogue's keys; a firm stores only what it may change.

A refusal is 422 `policy_loosening_refused` with `facts.field`, the first offending cell's path.
Code computes; nothing here reads a model (ADR-050).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from abacus.modules.agents._ai_policy_defaults import GATES, LOCKS, SECTIONS, STRICTER
from abacus.modules.agents.ai_policy_errors import AiPolicyLoosened

GATE_KEYS: frozenset[str] = frozenset(str(g["gate_key"]) for g in GATES)
_GATE_LOCK = "gates.*.policy_acceptance_on"


def _cell(sections: Mapping[str, object], path: str) -> object:
    head, _, rest = path.partition(".")
    return cast(Mapping[str, object], sections.get(head, {})).get(rest)


def _refuse(field: str) -> AiPolicyLoosened:
    return AiPolicyLoosened(field, facts={"field": field})


def check_stricter_only(draft: Mapping[str, object]) -> None:
    """Raise `AiPolicyLoosened` for the first cell the draft loosens; return None otherwise."""
    for path in LOCKS:
        if path == _GATE_LOCK:
            continue
        if _cell(draft, path) != _cell(SECTIONS, path):
            raise _refuse(path)
    for gate in cast(list[Mapping[str, object]], draft.get("gates", [])):
        key = str(gate.get("action_key", ""))
        if gate.get("policy_acceptance_on", False) is not False:
            raise _refuse(f"gates.{key}.policy_acceptance_on")
        if key not in GATE_KEYS:
            raise _refuse(f"gates.{key}")
    for path, way in STRICTER.items():
        value, floor = _cell(draft, path), _cell(SECTIONS, path)
        if value is None:
            continue
        if isinstance(floor, bool):
            if not isinstance(value, bool):
                raise _refuse(path)
            loose = (value and not floor) if way == "lower" else (floor and not value)
        else:
            number, base = cast(float, value), cast(float, floor)
            loose = number > base if way == "lower" else number < base
        if loose:
            raise _refuse(path)
