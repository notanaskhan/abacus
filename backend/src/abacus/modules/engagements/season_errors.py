"""T-08 season-setup error codes (SPEC-710; T-08-T03, DEC-5602), declared before their services
(T-08-T09 onward) so the catalogue and the stubs name them. Facts are identifiers and counts."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict


class CohortApproved(DomainConflict):
    """The cohort is approved: its rows are frozen until the approval is withdrawn (AC1.3)."""

    code = "cohort_approved"


class ExecutionStarted(DomainConflict):
    """The cohort's first step ran: the approval can no longer be withdrawn (AC1.5)."""

    code = "execution_started"


class ManifestSuperseded(DomainConflict):
    """A newer manifest version is ready; act on that one (`facts.manifest_version`)."""

    code = "manifest_superseded"
