"""Collaboration's fixed error codes (SPEC-650; `docs/contracts/collaboration.md` § Errors).
`facts` carry identifiers only."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainInvalid


class EmptyComment(DomainInvalid):
    code = "empty_comment"


class CommentTooLong(DomainInvalid):
    code = "comment_too_long"


class MentionNotAllowed(DomainInvalid):
    code = "mention_not_allowed"


class CorrectionNotAllowed(DomainInvalid):
    code = "correction_not_allowed"


class AlreadyRedacted(DomainConflict):
    code = "already_redacted"


class ThreadAlreadyResolved(DomainConflict):
    code = "thread_already_resolved"


class ThreadShared(DomainConflict):
    """SHL-18f: a shared thread is never converted to an internal review note (P-05-T09)."""

    code = "thread_shared"


class ThreadNotResolved(DomainConflict):
    """Reopen on an open thread: nothing to reopen."""

    code = "thread_not_resolved"


class AssigneeNotAllowed(DomainInvalid):
    code = "assignee_not_allowed"


class StaleVersion(DomainConflict):
    code = "stale_version"


class ChecklistFull(DomainInvalid):
    code = "checklist_full"


class TodoAlreadyDone(DomainConflict):
    code = "todo_already_done"


class TodoNotDone(DomainConflict):
    code = "todo_not_done"


class IfMatchRequired(DomainInvalid):
    """An autosave without `If-Match` (AC-20: every PATCH carries the version it edits)."""

    code = "if_match_required"
