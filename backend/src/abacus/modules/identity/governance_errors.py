"""The security center's error codes (G-02-T02 declarations; SPEC-349 AC-15, AC-17, AC-19, AC-28;
ADR-186 item 7). Raised by G-02-T14 and T24; declared here so the catalogue
(`docs/architecture/error-codes.yaml`) and the contracts name them before the routes exist."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainInvalid


class SsoNotVerified(DomainConflict):
    """Require SSO needs a verified SSO sign-in by an admin of this firm first (AC-15)."""

    code = "sso_not_verified"


class SsoExemptNeedsHardwareKey(DomainConflict):
    """The one SSO-exempt (break-glass) account must hold a hardware-key factor (AC-18; G-02-T11,
    DEC-432). Raised by G-02-T14."""

    code = "sso_exempt_needs_hardware_key"


class SupportRequestsDisabled(DomainConflict):
    """The firm turned "Allow support session requests" off; active sessions keep their expiry
    (AC-28)."""

    code = "support_requests_disabled"


class SupersededByAiPolicy(DomainConflict):
    """The firm is on the versioned AI policy (`ai_policy.v1`): the autonomy level is changed
    by publishing a policy version, not by `PUT /v1/firm/autonomy` (ADR-186 item 7)."""

    code = "superseded_by_ai_policy"


class SecurityPolicyLoosened(DomainInvalid):
    """A firm may only make its sign-in, session and portal limits stricter than the platform's
    (AC-17, AC-19); `facts.field` names the field."""

    code = "policy_loosening_refused"
