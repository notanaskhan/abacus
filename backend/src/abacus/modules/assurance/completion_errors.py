"""A-07's refusal codes (A-07 §4.3; A-07-T06; DEC-2233; docs/contracts/audit-completion.md).

Declared with the contract so the error catalogue, the generated client and the screens' refusal
words know them before the services raise them (A-07-T18 onward). Facts beside a code are
identifiers only (DEC-60).
"""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid


class Archived(DomainConflict):
    """The work item is locked: nothing changes outside an `archived_write` kind."""

    code = "archived"


class GatesNotMet(DomainConflict):
    """A gate the act needs is not met at the server (`facts.gates`)."""

    code = "gates_not_met"


class ChecklistIncomplete(DomainConflict):
    """An item or an EQR note is still open (EQR concurrence, archive lock)."""

    code = "checklist_incomplete"


class EqrOnly(DomainForbidden):
    """Only the assigned engagement quality reviewer may do this."""

    code = "eqr_only"


class EqrIneligible(DomainConflict):
    """The assignee fails P-07's eligibility re-check (on the team, the EP, or cooling-off)."""

    code = "eqr_ineligible"


class EpOnly(DomainForbidden):
    """Only the engagement partner may do this."""

    code = "ep_only"


class ApprovalRequired(DomainConflict):
    """The version has no engagement partner approval yet: nothing is sent."""

    code = "approval_required"


class DecisionRequired(DomainConflict):
    """A reserved decision (opinion, going concern) is not decided on its card yet."""

    code = "decision_required"


class ItemDerived(DomainConflict):
    """A projected checklist item follows its events and cannot be marked by hand."""

    code = "item_derived"


class InternalAmountInText(DomainInvalid):
    """Client-facing letter text may not carry a materiality amount."""

    code = "internal_amount_in_text"


class DateMismatch(DomainConflict):
    """The letter's signature date is not the report date."""

    code = "date_mismatch"


class LetterContentChanged(DomainConflict):
    """The version changed since the person saw it: nothing is written."""

    code = "content_changed"


class StaleVersion(DomainConflict):
    """The record moved on since `seen_version`: reload and try again."""

    code = "stale_version"


class SealMismatch(DomainConflict):
    """The recomputed seal differs from the locked manifest's (RB-29)."""

    code = "seal_mismatch"


class ReleaseModeExternal(DomainConflict):
    """The firm releases and archives in its own tool (`assurance_release_mode = external`)."""

    code = "release_mode_external"


class ParagraphLocked(DomainConflict):
    """A general paragraph is always included and is not firm-editable."""

    code = "paragraph_locked"
