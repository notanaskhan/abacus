"""T-08 tax practice tools error codes (SPEC-710; T-08-T03, DEC-5602), declared before their
services (T-08-T11 onward). Facts are identifiers, counts and booleans."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainInvalid


class ExplanationStale(DomainConflict):
    """The line's values changed since the explanation was read: read it again (`values_hash`)."""

    code = "explanation_stale"


class CheckCodeUnknown(DomainInvalid):
    """A checklist item names a check code no module registered for this form."""

    code = "check_code_unknown"


class Consent7216Missing(DomainConflict):
    """Both §7216 consents (use, ai_disclosure) are needed before the agent reads this return."""

    code = "consent_7216_missing"


class ReturnAccepted(DomainConflict):
    """The return is accepted: it is never changed; amend it instead (AC6.7)."""

    code = "return_accepted"


class NotBbaSigner(DomainConflict):
    """Only the AAR return's signer decides the BBA election (AC6.6)."""

    code = "not_bba_signer"
