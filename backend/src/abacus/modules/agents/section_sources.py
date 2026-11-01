"""The section drafter's source slot (A-04-T11; DEC-1868).

Agents may not import workpapers (BOUND-002, ADR-008: workpapers depends on agents), so the paper
a draft reads comes through this slot. Workpapers registers one `SectionSource` at import:
- `paper`: the paper and section as the drafter reads it (404 for one it can't), in the shapes
  below;
- `bound`: the version's steps the paper is bound to;
- `pack_problem`: the first template reference the pinned version and the firm's library can't
  resolve, with AUD-09 d's sentence, or None.
With none registered, a draft is refused before anything is written (fail closed).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainUnavailable
from abacus.modules.methodology.api import VersionStep

CELL_TARGET: Final = "workpaper_cell"


@dataclass(frozen=True)
class SourceCell:
    sheet_key: str
    cell_key: str
    row_key: str | None
    col_key: str | None
    value: dict[str, object] | None  # `{t, v}`; None for an empty cell


@dataclass(frozen=True)
class SourcePaper:
    workpaper_id: UUID
    engagement_id: UUID
    work_item_id: UUID
    code: str
    title: str
    kind: str
    version_no: int
    step_keys: tuple[str, ...]
    section_key: str | None
    cells: tuple[SourceCell, ...]


@dataclass(frozen=True)
class PackProblem:
    message: str  # AUD-09 d's sentence
    program_code: str
    number: int
    ref: str


@dataclass(frozen=True)
class SectionSource:
    paper: Callable[[TenantContext, UUID, UUID, str | None], Awaitable[SourcePaper]]
    bound: Callable[[Sequence[VersionStep], SourcePaper], list[VersionStep]]
    pack_problem: Callable[[TenantContext, UUID, SourcePaper], Awaitable[PackProblem | None]]


class SourceMissing(DomainUnavailable):
    """No workpaper source is registered here."""

    code = "drafter_unavailable"


class PackRefused(DomainConflict):
    """The pinned version points at a template neither it nor the firm's library holds (AC6.1).
    `message` is AUD-09 d's sentence; the facts name the step and the reference."""

    code = "pack_configuration_error"

    def __init__(self, problem: PackProblem) -> None:
        super().__init__(
            facts={
                "program_code": problem.program_code,
                "number": problem.number,
                "ref": problem.ref,
            }
        )
        self.message = problem.message


_SOURCE: list[SectionSource] = []


def register_section_source(source: SectionSource) -> None:
    if _SOURCE and _SOURCE[0] is not source:
        raise ValueError("a section source is already registered")
    _SOURCE[:] = [source]


def section_source() -> SectionSource:
    if not _SOURCE:
        raise SourceMissing
    return _SOURCE[0]


# A-05-T12 (DEC-1956): which paper kinds each owner's mode drafts. A mode with a registered plan
# runs only on those kinds (a mode's owner registers it; the planning modes have none and run on
# any paper the source returns). An empty plan runs on nothing yet (`related_parties` before
# AUD-27's records exist).
_MODE_PLANS: dict[str, frozenset[str]] = {}


def register_mode_plan(mode: str, kinds: frozenset[str]) -> None:
    known = _MODE_PLANS.get(mode)
    if known is not None and known != kinds:
        raise ValueError(f"section draft mode {mode!r} already has a plan")
    _MODE_PLANS[mode] = kinds


def mode_kinds(mode: str) -> frozenset[str] | None:
    return _MODE_PLANS.get(mode)


__all__ = [
    "CELL_TARGET",
    "PackProblem",
    "PackRefused",
    "SectionSource",
    "SourceCell",
    "SourceMissing",
    "SourcePaper",
    "mode_kinds",
    "register_mode_plan",
    "register_section_source",
    "section_source",
]
