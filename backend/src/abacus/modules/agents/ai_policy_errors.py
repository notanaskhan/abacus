"""The AI policy's error codes (G-02-T02 declarations; ADR-186; SPEC-349 AC-36 to AC-38).
Raised by G-02-T23 and T24; declared here so the catalogue and the contracts name them first."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainInvalid


class AiPolicyLoosened(DomainInvalid):
    """A draft may not loosen a locked or default-strict cell (AC-38); `facts.field` is the
    field path."""

    code = "policy_loosening_refused"


class ApproverMustDiffer(DomainConflict):
    """The partner who approves a policy version is not the person who requested it (AC-37,
    DEC-50)."""

    code = "approver_must_differ"
