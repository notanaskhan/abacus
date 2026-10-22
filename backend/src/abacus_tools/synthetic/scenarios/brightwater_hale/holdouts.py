"""Holdouts: content left out so a journey can create it (SPEC-307 AC-3; F-04.11). With
`fairhaven_ebp`, the Fairhaven Foods 401(k) Plan client and its EBP engagement are absent, so
J02-audit-core creates them (CLI-01 derives 183 before, 184 after); with `copperleaf`, the CAS
path starts without Copperleaf."""

from __future__ import annotations

from typing import Final

HOLDOUTS: Final[dict[str, frozenset[str]]] = {
    "fairhaven_ebp": frozenset({"Fairhaven Foods 401(k) Plan"}),
    "copperleaf": frozenset({"Copperleaf Coffee Roasters, Inc."}),
}


def held_out(names: frozenset[str] | set[str] | tuple[str, ...]) -> frozenset[str]:
    """The client names the given holdouts leave out; an unknown holdout is an error."""
    unknown = set(names) - HOLDOUTS.keys()
    if unknown:
        raise KeyError(f"unknown holdout(s): {', '.join(sorted(unknown))}")
    out: set[str] = set()
    for name in names:
        out |= HOLDOUTS[name]
    return frozenset(out)
