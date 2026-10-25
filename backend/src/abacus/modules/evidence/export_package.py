"""The export section slot (A-01-T17; SPEC-344 §6; A-01 §4.1).

Other modules add files to an engagement export without `evidence` importing them (P-05: no
`evidence -> assurance` edge): each registers a named section provider through
`evidence.api.register_export_section`. Four names are the core provenance files and land at
fixed paths (`provenance/<name>.csv`); `index` writes the index rows; every other name writes
under `sections/<name>/`. The package builder (A-01-T19) calls every registered provider at the
export's audit sequence and refuses to build while a core section has no provider
(`export_section_missing`): fail closed, never a package with a hole in its provenance.

Providers read; they never write and never call a model. What they return is client content
and is treated as hostile (file names are normalised by the builder, cells are neutralised).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.evidence.export_manifest import INDEX_CSV, PROVENANCE_FILES

# Core sections and where they land; the builder needs a provider for each.
CORE_SECTIONS: Final = {
    "index": INDEX_CSV,
    **{path.removeprefix("provenance/").removesuffix(".csv"): path for path in PROVENANCE_FILES},
}
# Written by the export service itself, never by a provider.
RESERVED: Final = frozenset({"readme", "manifest", "checksums", "evidence", "audit_trail"})
_NAME: Final = re.compile(r"[a-z][a-z0-9_]{1,39}")
_FILE: Final = re.compile(r"[a-z0-9][a-z0-9_.-]{0,79}")


@dataclass(frozen=True)
class SectionRequest:
    """What a provider is asked for: one export's selection at one audit sequence."""

    export_id: UUID
    engagement_id: UUID
    work_item_id: UUID
    binder_ids: tuple[UUID, ...]
    as_of_seq: int
    include_unaccepted: bool


@dataclass(frozen=True)
class SectionFile:
    """One file a section contributes. `name` is the file name inside the section's folder; a
    core section returns exactly one file, its CSV."""

    name: str
    content: bytes


SectionProvider = Callable[[TenantContext, SectionRequest], Awaitable[Sequence[SectionFile]]]


@dataclass(frozen=True)
class RegisteredSection:
    name: str
    section_version: str
    provider: SectionProvider


_SECTIONS: dict[str, RegisteredSection] = {}


class ExportSectionInvalid(ValueError):
    """A registration the slot refuses (a bad or reserved name, a second registration)."""


def register_export_section(
    name: str, provider: SectionProvider, *, section_version: str = "1.0"
) -> None:
    """Register `provider` for section `name`, once, at import time."""
    if not _NAME.fullmatch(name) or name in RESERVED:
        raise ExportSectionInvalid(f"{name!r} is not a section name")
    if not re.fullmatch(r"[0-9]+\.[0-9]+", section_version):
        raise ExportSectionInvalid(f"{name}: {section_version!r} is not a section version")
    if name in _SECTIONS:
        raise ExportSectionInvalid(f"{name} is registered twice")
    _SECTIONS[name] = RegisteredSection(name, section_version, provider)


def registered_sections() -> tuple[RegisteredSection, ...]:
    return tuple(_SECTIONS[n] for n in sorted(_SECTIONS))


def missing_core_sections() -> tuple[str, ...]:
    """The core sections nobody provides yet; the builder refuses while any is missing."""
    return tuple(sorted(set(CORE_SECTIONS) - set(_SECTIONS)))


def section_path(name: str, file_name: str) -> str:
    """Where a section's file lands in the package."""
    if name in CORE_SECTIONS:
        return CORE_SECTIONS[name]
    if not _FILE.fullmatch(file_name):
        raise ExportSectionInvalid(f"{name}: {file_name!r} is not a section file name")
    return f"sections/{name}/{file_name}"


__all__ = [
    "CORE_SECTIONS",
    "ExportSectionInvalid",
    "RegisteredSection",
    "SectionFile",
    "SectionProvider",
    "SectionRequest",
    "missing_core_sections",
    "register_export_section",
    "registered_sections",
    "section_path",
]
