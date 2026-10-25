"""ENG-05's conflicts (P-07-T30; `docs/contracts/acceptance-independence.md` §6), apart so the
service and `team.py` share them without importing each other."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict


class EqrOnTeam(DomainConflict):
    """The engagement quality reviewer is never on the team: pick someone who isn't, or keep the
    EQR off the team roles."""

    code = "eqr_on_team"


class EqrApproverIsEp(DomainConflict):
    """The EQR's eligibility is approved by the quality owner, never the engagement partner."""

    code = "eqr_approver_is_ep"


class EqrNotEligible(DomainConflict):
    """The candidate fails an eligibility check (each failing check is a fact): pick an eligible
    reviewer."""

    code = "eqr_not_eligible"


class EqrApproverOnEngagement(DomainConflict):
    """The EQR's eligibility is approved by a quality owner with no role on this engagement."""

    code = "eqr_approver_on_engagement"


class EqrApprovalRequired(DomainConflict):
    """The candidate's competence is not shown by their history here: the quality owner approves
    their eligibility first."""

    code = "eqr_approval_required"


class TeamChanged(DomainConflict):
    """The team changed since it was read: read it again and approve what is there now."""

    code = "stale_version"
