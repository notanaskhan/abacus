"""T-06 error codes (SPEC-702; T-06-T03, DEC-5511), declared before their services (T-06-T22
onward) so the catalogue and the stubs name them. Facts are identifiers, counts and booleans."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict


class OpenFlagsNoteRequired(DomainConflict):
    """A section sign-off with an open flag needs a note (`facts.open_flags`)."""

    code = "open_flags_note_required"


class TieOutOffNoteRequired(DomainConflict):
    """A sign-off over a tally that is off needs a note."""

    code = "tie_out_off_note_required"


class ReturnLocked(DomainConflict):
    """The return is Accepted or filed: its workpapers are read-only."""

    code = "return_locked"


class DecisionAlreadySent(DomainConflict):
    """The decision request already went to the client; it is not sent twice."""

    code = "decision_already_sent"


class BlockingDiagnostics(DomainConflict):
    """Final approval is refused while form diagnostics block (`facts.blocking`)."""

    code = "blocking_diagnostics"


class FormTemplateMissing(DomainConflict):
    """No form-face template exists for this form and tax year: the preview waits on the engine."""

    code = "form_template_missing"
