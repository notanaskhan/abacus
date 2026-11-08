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

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainUnavailable
from abacus.modules.identity.api import AgentContext, AuthContext
from abacus.modules.methodology.api import VersionStep

if TYPE_CHECKING:
    from abacus.kernel.uow import UnitOfWork

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


# A-04-T23 (DEC-2059): the paper's owner raises a PBC GAP attention flag the agent drafted, in
# the run's unit of work, as the agent with its run (0581: an agent's flag names its run).
# (unit of work, the agent, the paper, its section, the row, the flag's text) -> the flag's id
FlagRaiser = Callable[
    ["UnitOfWork", AgentContext, SourcePaper, str | None, str | None, str], Awaitable[UUID]
]


@dataclass(frozen=True)
class SectionSource:
    paper: Callable[[TenantContext, UUID, UUID, str | None], Awaitable[SourcePaper]]
    bound: Callable[[Sequence[VersionStep], SourcePaper], list[VersionStep]]
    pack_problem: Callable[[TenantContext, UUID, SourcePaper], Awaitable[PackProblem | None]]
    raise_flag: FlagRaiser | None = None


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


# A-04-T22 (DEC-2058): a mode's mapping adds its documents and its waiting inputs to the context
# code builds. The documents are evidence versions the engagement holds, page by page (D<n>, in
# the mapping's order); a citation to one is a C4 `document_text` claim on its page. Waiting
# inputs are what the section still needs from the client (a request item not yet received),
# recorded on the run, never guessed at. A mode with no mapping drafts from steps and cells only.


@dataclass(frozen=True)
class ModePage:
    number: int
    text: str


@dataclass(frozen=True)
class ModeDocument:
    evidence_version_id: UUID
    title: str
    pages: tuple[ModePage, ...]


@dataclass(frozen=True)
class ModeTarget:
    """A-04-T24 (DEC-2060): where an adopted value on a mode's own cell lands (a risk's field,
    through its owner's suggestion applier), instead of the paper's cell."""

    target_type: str
    target_id: UUID
    field_key: str
    choices: tuple[str, ...] = ()  # when set, the cell's text must be one of these (DEC-2480)


@dataclass(frozen=True)
class ModeInputs:
    documents: tuple[ModeDocument, ...] = ()
    waiting_on: tuple[str, ...] = ()
    # A-04-T24: the mode's own cells (A1 keys on its own sheet, as a grid of its records), each
    # with the target its value lands on, and code facts ("risks_total = 10") for numbers by
    # reference.
    cells: tuple[SourceCell, ...] = ()
    targets: Mapping[str, ModeTarget] = field(default_factory=dict[str, ModeTarget])
    facts: tuple[tuple[str, dict[str, object]], ...] = ()
    # Names to pick from ("EBP-03, EBP-04"): shown as facts, but support no number (DEC-2480).
    identifiers: tuple[tuple[str, dict[str, object]], ...] = ()


# (the run's agent, as the actor the reads are authorised for; the paper as the source read it)
ModeMapping = Callable[[AgentContext, SourcePaper], Awaitable[ModeInputs]]
_MODE_MAPPINGS: dict[str, ModeMapping] = {}


def register_mode_mapping(mode: str, mapping: ModeMapping) -> None:
    known = _MODE_MAPPINGS.get(mode)
    if known is not None and (known.__module__, known.__qualname__) != (
        mapping.__module__,
        mapping.__qualname__,
    ):
        raise ValueError(f"section draft mode {mode!r} already has a mapping")
    _MODE_MAPPINGS[mode] = mapping


def mode_mapping(mode: str) -> ModeMapping | None:
    return _MODE_MAPPINGS.get(mode)


# A-04-T23 (DEC-2059): what code does when a person starts a mode, before the run exists, as that
# person (risk_narrative inserts the presumed fraud risks the methodology prepopulates). It runs
# in the starter's own context; the agent never writes the register.
ModePreparer = Callable[[AuthContext, UUID, SourcePaper], Awaitable[None]]
_MODE_PREPARERS: dict[str, ModePreparer] = {}
# The modes whose drafts may raise PBC GAP flags (A-04 §6: risk_narrative only).
FLAG_MODES: Final = frozenset({"risk_narrative"})


def register_mode_preparer(mode: str, preparer: ModePreparer) -> None:
    known = _MODE_PREPARERS.get(mode)
    if known is not None and (known.__module__, known.__qualname__) != (
        preparer.__module__,
        preparer.__qualname__,
    ):
        raise ValueError(f"section draft mode {mode!r} already has a preparer")
    _MODE_PREPARERS[mode] = preparer


def mode_preparer(mode: str) -> ModePreparer | None:
    return _MODE_PREPARERS.get(mode)


__all__ = [
    "CELL_TARGET",
    "FLAG_MODES",
    "FlagRaiser",
    "ModeDocument",
    "ModeInputs",
    "ModeMapping",
    "ModePage",
    "ModePreparer",
    "ModeTarget",
    "PackProblem",
    "PackRefused",
    "SectionSource",
    "SourceCell",
    "SourceMissing",
    "SourcePaper",
    "mode_kinds",
    "mode_mapping",
    "mode_preparer",
    "register_mode_mapping",
    "register_mode_plan",
    "register_mode_preparer",
    "register_section_source",
    "section_source",
]
