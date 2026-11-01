"""The firm's template library as pack validation reads it (A-04-T07; OQ-15, DEC-1758, DEC-1867).

A step's `template_refs` (`request:<key>`, `workpaper:<kind>`) resolve against the pinned version
and the firm's template library: request and workpaper templates are database content with their
own lifecycle (K-03). The owners register what their libraries hold; with nothing registered a
reference resolves only through the version (fail closed). Workpaper kinds are workpapers' own.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

from abacus.kernel.db import TenantContext

# (tenant, references) -> the references the firm's library holds.
TemplateLibrary = Callable[[TenantContext, frozenset[str]], Awaitable[frozenset[str]]]
_LIBRARIES: list[TemplateLibrary] = []


def register_template_library(library: TemplateLibrary) -> None:
    """A template owner's lookup (K-03's request templates; workpapers' kinds). Once each."""
    if library not in _LIBRARIES:
        _LIBRARIES.append(library)


async def templates_held(tenant: TenantContext, refs: Iterable[str]) -> frozenset[str]:
    """The references some registered library holds for this firm."""
    wanted = frozenset(refs)
    held: set[str] = set()
    for library in _LIBRARIES:
        if not wanted - held:
            break
        held |= await library(tenant, wanted - held)
    return frozenset(held & wanted)
