"""Holdouts: content left out so a journey can create it (SPEC-307 AC-3; F-04.11). With
`fairhaven_ebp`, the Fairhaven Foods 401(k) Plan client and its EBP engagement are absent, so
J02-audit-core creates them (CLI-01 derives 183 before, 184 after); with `copperleaf`, the CAS
path starts without Copperleaf; with `thornbury_estate` (P-07-T50, CLI-06 and J19), the estate is
not yet added: the Thornbury client is Walter Thornbury with his own entity only, so CLI-06 b's
intake adds the estate under him ("96% match"). A replaced client keeps its place and its
partner, office and services; events about the estate client are left out, and events that need
the holdout (`data["holdout"]`) load only with it."""

from __future__ import annotations

from typing import Final

HOLDOUTS: Final[dict[str, frozenset[str]]] = {
    "fairhaven_ebp": frozenset({"Fairhaven Foods 401(k) Plan"}),
    "copperleaf": frozenset({"Copperleaf Coffee Roasters, Inc."}),
    "thornbury_estate": frozenset({"Estate of Walter Thornbury"}),
}
# Holdouts that keep a held-out client in an earlier form: name -> (name then, entities then).
REPLACEMENTS: Final[dict[str, dict[str, tuple[str, tuple[str, ...]]]]] = {
    "thornbury_estate": {
        "Estate of Walter Thornbury": ("Walter Thornbury", ("Walter Thornbury",))
    },
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


def replacements(
    names: frozenset[str] | set[str] | tuple[str, ...],
) -> dict[str, tuple[str, tuple[str, ...]]]:
    """The clients the given holdouts keep in an earlier form, by their full-scenario name."""
    held_out(names)  # an unknown holdout is an error
    out: dict[str, tuple[str, tuple[str, ...]]] = {}
    for name in names:
        out |= REPLACEMENTS.get(name, {})
    return out


def replaced_name(holdout: str, name: str) -> str | None:
    """What `holdout` calls the client named `name` in the full scenario, if it renames it."""
    found = REPLACEMENTS.get(holdout, {}).get(name)
    return found[0] if found is not None else None
