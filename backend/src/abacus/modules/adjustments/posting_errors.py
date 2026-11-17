"""The posting block's error codes (C8 v2; SPEC-700; ADR-344; C-02-T02, DEC-5501).

Every code a C-02 posting route can answer, declared once so the error-code catalogue
(`docs/architecture/error-codes.yaml`) lists it before the services land (C-02-T12, T13, T18,
T19). Facts are identifiers, counts and booleans only (`abacus.kernel.errors.check_facts`).
"""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainForbidden


class OverApprovalLimit(DomainConflict):
    """The entry is over the approver's class limit under the firm's threshold policy: "over your
    limit · Review required" (`facts.limit_class`, `facts.policy_version`)."""

    code = "over_approval_limit"


class EntryLocked(DomainConflict):
    """An approved entry's lines or date cannot change until its approval is withdrawn."""

    code = "entry_locked"


class PostingNotEnabled(DomainConflict):
    """Posting is off for this engagement (`posting_enabled`): export the approved entries."""

    code = "posting_not_enabled"


class AttestClientPostingRefused(DomainForbidden):
    """The client is attest-flagged: nothing is ever posted to its ledger (ADR-164, ADR-344)."""

    code = "attest_client_posting_refused"


class ClosingDateLocked(DomainConflict):
    """The entry is dated on or before the client's closing date: ask the client to lift the
    date, or re-date the entry (`facts.closing_date`)."""

    code = "closing_date_locked"


class InactiveAccount(DomainConflict):
    """An entry line names an account the client's ledger shows inactive (`facts.account_ref`)."""

    code = "inactive_account"


class UnmappedAccount(DomainConflict):
    """An entry line names an account with no ledger mapping (`facts.account_ref`)."""

    code = "unmapped_account"


class ApprovalGrantMismatch(DomainConflict):
    """The batch's approval grant does not cover this payload: the entries, lines, dates or
    closing date changed after the grant was issued."""

    code = "approval_grant_mismatch"
