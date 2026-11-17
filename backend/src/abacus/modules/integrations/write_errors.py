"""W1 write-capability error codes (C20 v2.1; SPEC-700; ADR-344; C-02-T02, DEC-5501).

Raised by the firm switch, the client's write grant and `execute_write` once W1 lands (C-02-T13,
T19, T25). Until then every W1 call is still `write_capability_refused` (ADR-150).
"""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict


class WriteGrantMissing(DomainConflict):
    """The client owner has not granted, or has revoked, the posting scope in the portal."""

    code = "write_grant_missing"


class WriteCapabilityNotReleased(DomainConflict):
    """The registry entry is `enabled: false`: the firm switch is shown but cannot turn on."""

    code = "write_capability_not_released"


class WriteCapabilityDisabled(DomainConflict):
    """The firm's switch or its kill switch for this capability is off."""

    code = "write_capability_disabled"
