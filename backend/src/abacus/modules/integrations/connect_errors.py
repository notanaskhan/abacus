"""The Connect errors (W-01-T03 contract, W-01-T08 service; SPEC-659 AC-12, AC-14, AC-24)."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainInvalid


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
