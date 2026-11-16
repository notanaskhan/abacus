"""The Connect errors (W-01-T03 contract, W-01-T08 service; SPEC-659 AC-12, AC-14, AC-24)."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid


class InvalidState(DomainConflict):
    code = "invalid_state"


class ConnectDeclined(DomainConflict):
    code = "connect_declined"


class PrerequisiteScopeMissing(DomainConflict):
    code = "prerequisite_scope_missing"


class ConfirmNameMismatch(DomainInvalid):
    code = "confirm_name_mismatch"


class FirmAppDisabled(DomainConflict):
    code = "firm_app_disabled"


class IntegrationNotAvailable(DomainConflict):
    code = "integration_not_available"


class StaleVersion(DomainConflict):
    code = "stale_version"


class ConnectNeedsMfa(DomainForbidden):
    """AC-7: the role allows it, but the last second factor is older than 15 minutes: verify
    again, then retry (the shell's step-up). Answers `facts.reason = mfa_required`, so WB-10
    opens the step-up only for this and never for a role refusal."""

    code = "forbidden"
