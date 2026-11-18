"""The filing-deadline source slot (T-08-T07; SPEC-710 AC-20; FD-1, `filing-deadlines.md`).

`practice` builds the `filing_deadlines` read model but imports only identity, platform,
organisations, engagements and integrations (chapter 03 §2.3), so every other module (tax,
closes, notices, assurance, signatures, organisations) registers its due dates here, the I-01
`register_home_count` pattern: nothing imports `practice`.

Fail closed (AC-20): a source kind outside `SOURCE_KINDS` (the `filing_deadlines.source_kind`
CHECK of 0962) is refused at registration, so an unknown kind fails at startup; the recompute
asks only registered kinds. A provider answers metadata only: never TRI, never an amount.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID

# The 0962 CHECK, in one place; the migration test holds the two together.
SOURCE_KINDS: Final = frozenset(
    {
        "tax_return",
        "extension",
        "estimate_batch",
        "fiduciary_statement",
        "election_window",
        "notice_response",
        "envelope",
        "close",
        "assurance_report",
        "form_5500",
        "consent",
    }
)


@dataclass(frozen=True)
class FilingDeadlineWindow:
    start: date
    end: date


@dataclass(frozen=True)
class FilingDeadlineFact:
    """One due date a source owns, keyed by (source_kind, source_ref, filing_label)."""

    source_kind: str
    source_ref: str
    filing_label: str
    client_id: UUID | None
    office_id: UUID | None
    service_line: str
    original_due_on: date
    due_on: date
    stage_code: str
    owner_user_ids: tuple[UUID, ...] = ()
    signer_user_id: UUID | None = None
    rule_key: str | None = None
    reference_set_version_ids: tuple[UUID, ...] = ()
    extension_form: str | None = None
    extension_filed_on: date | None = None
    extended_due_on: date | None = None
    postponement_notice_id: UUID | None = None
    postponed_from: date | None = None
    done: bool = False
    work_item_id: UUID | None = None


# `provider(tenant, window)`: the tenant is the kernel's TenantContext, passed untyped because the
# slot sits below every source module (DEC-13 graph).
FilingDeadlineProvider = Callable[
    [object, FilingDeadlineWindow], Awaitable[Sequence[FilingDeadlineFact]]
]
_SOURCES: dict[str, FilingDeadlineProvider] = {}


class UnknownFilingDeadlineSource(ValueError):
    """A source kind the read model's CHECK does not know (AC-20)."""


def register_filing_deadline_source(kind: str, provider: FilingDeadlineProvider) -> None:
    """Registered once per kind at import; the same function again (a reloaded module) is a
    no-op, another function for a taken kind fails."""
    if kind not in SOURCE_KINDS:
        raise UnknownFilingDeadlineSource(f"filing deadline source {kind!r} is not a known kind")
    known = _SOURCES.get(kind)
    if known is not None and (known.__module__, known.__qualname__) != (
        provider.__module__,
        provider.__qualname__,
    ):
        raise ValueError(f"filing deadline source {kind!r} is already registered")
    _SOURCES[kind] = provider


def filing_deadline_source_kinds() -> tuple[str, ...]:
    return tuple(sorted(_SOURCES))


def filing_deadline_source(kind: str) -> FilingDeadlineProvider | None:
    """Fail closed: an unregistered kind yields nothing."""
    return _SOURCES.get(kind)
