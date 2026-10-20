"""Gate policy per engagement type family (F-03-T12; chapter 03 §3.1.3; DEC-39).

The platform default says which of the gates G1 to G9 each family requires. A firm override may add
a gate or make one strict; it can never remove a platform gate.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

FAMILY: Final[dict[str, str]] = {
    "fs_audit": "attest",
    "ebp_audit": "attest",
    "review": "attest",
    "agreed_upon_procedures": "attest",
    "soc1": "attest",
    "soc2": "attest",
    "readiness": "attest",
    "internal_audit": "attest",
    "compilation": "compilation_preparation",
    "preparation": "compilation_preparation",
    "tax_compliance": "tax",
    "cas_monthly_close": "cas",
    "notice_response": "notice",
    "advisory": "advisory",
}
ALL_GATES: Final = tuple(f"G{n}" for n in range(1, 10))
PLATFORM: Final[dict[str, frozenset[str]]] = {
    "attest": frozenset(ALL_GATES),
    "compilation_preparation": frozenset({"G1", "G3", "G5", "G8", "G9"}),
    "tax": frozenset({"G1", "G3"}),
    "cas": frozenset({"G1", "G3"}),
    "notice": frozenset({"G3"}),
    "advisory": frozenset({"G1", "G3"}),
}


def required_gates(engagement_type: str, overrides: Iterable[tuple[str, str]] = ()) -> list[str]:
    """The gates an engagement must pass: the platform's for its family, plus any the firm added.
    `overrides` are (gate, requirement) rows; a firm can only add or tighten (DEC-39)."""
    family = FAMILY[engagement_type]
    gates = set(PLATFORM[family]) | {gate for gate, _ in overrides if gate in ALL_GATES}
    return sorted(gates, key=lambda g: int(g[1:]))
