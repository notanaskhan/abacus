"""Slices: the subsets of content a screen family needs (SPEC-307 AC-2; F-04 §2.1). F-04 ships
`audit_core` (the firm, offices, people, 184 clients and the 27 audits) and `portal_minimum`
(Northwind's and Granite Peak's portal users and the Feld binder). Later epics register theirs
(`tax` T-02, `cas` C-01, Harlow & Pike A-09, Tessellate X-02) with `@register_slice`, so adding
one never edits this file. A slice yields timeline events; an unregistered slice is an error."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SliceBuilder = Callable[[], Iterable[Event]]
_SLICES: dict[str, SliceBuilder] = {}
F04_SLICES: Final = ("audit_core", "portal_minimum")


def register_slice(name: str) -> Callable[[SliceBuilder], SliceBuilder]:
    def register(builder: SliceBuilder) -> SliceBuilder:
        if name in _SLICES and _SLICES[name] is not builder:
            raise ValueError(f"slice {name!r} is already registered")
        _SLICES[name] = builder
        return builder

    return register


def slice_events(name: str) -> list[Event]:
    builder = _SLICES.get(name)
    if builder is None:
        raise KeyError(f"no slice {name!r}; registered: {', '.join(sorted(_SLICES)) or 'none'}")
    return list(builder())


def registered() -> tuple[str, ...]:
    return tuple(sorted(_SLICES))
