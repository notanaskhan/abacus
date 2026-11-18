"""Q-05 consultations log v2 and post-issuance error codes (SPEC-711; Q-05-T02, DEC-5609),
declared before their services (Q-05-T09, T12). Facts are identifiers only."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainInvalid


class DifferenceUnresolved(DomainConflict):
    """A difference of opinion on this engagement is unresolved: release waits (OQ-8)."""

    code = "difference_unresolved"


class ConsulteeNotEligible(DomainInvalid):
    """A consultee is a partner or specialist with a human membership, not walled."""

    code = "consultee_not_eligible"


class ComparisonUnavailable(DomainConflict):
    """The case has no as-certified and as-corrected figures yet: analysis waits (DV-9)."""

    code = "comparison_unavailable"
