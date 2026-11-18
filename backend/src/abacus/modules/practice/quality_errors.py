"""Q-05 quality management error codes (SPEC-711; Q-05-T02, DEC-5609), declared before their
services (Q-05-T08, T13) so the catalogue and the stubs name them. Facts are identifiers only."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict


class InspectorNotObjective(DomainConflict):
    """The inspector is the EP, the EQR or a member of the inspected engagement (AC-7)."""

    code = "inspector_not_objective"


class InspectionsOpen(DomainConflict):
    """The cycle still has planned or in-progress inspections: the evaluation waits."""

    code = "inspections_open"
