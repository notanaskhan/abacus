"""A WorkOS fake (F-04-T27; F-04.24; F-04 §4.8; DEC-22, DEC-155). Local runs and tests only.

Two halves, as WorkOS has:

- **Portal** (`FakeWorkOsPortalIdp`): implements the portal's `PortalIdp` port
  (`abacus.modules.identity.portal_idp`) exactly. It holds client users and their TOTP factors,
  which is all WorkOS keeps for the portal (DEC-155). It has no email method at all: the portal
  issues its own sign-in codes and sends them through SES, so a client never gets a
  WorkOS-branded email. The port's contract tests (`tests/contracts/portal_idp/`) run against it.
  The portal's email-code attempts and lockout (POR-01f, 3 wrong codes; POR-01g) are the portal
  BFF's (P-08-T10), not the provider's, so they are not here.
- **Staff** (`StaffSignIn`): AuthKit's hosted email-code sign-in as SHL-06 draws it. The work
  email (a) gets a 6-digit code (b), written to the local mailbox at the address the synthetic
  sink routes it to, so `mail().latest(to)` reads it; a wrong code says how many attempts are left
  (e: "4 attempts left"); the fifth locks the account for 30 minutes and names the firm's IT /
  Security person (f); the right code asks for the authenticator code (c); then the person is
  signed in (g, the BFF's landing). `oidc_server.py` serves its pages.

Every user, code and factor is synthetic and lives in this process. Readers for the harness:
`FakeWorkOsPortalIdp.current_code`, `StaffSignIn.current_totp`, `StaffSignIn.latest_code`.
Refused outside the synthetic environments (local, test, evaluation).
"""

from __future__ import annotations

import base64
import hmac
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, Literal
from urllib.parse import quote
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.modules.communications.api import LocalMailbox, sink_address
from abacus.modules.identity.api import (
    CODE_DIGITS,
    TOTP_STEP_SECONDS,
    TOTP_WINDOW,
    PortalIdpUnavailable,
    TotpEnrolment,
    check_issuer,
    totp_at,
)
from abacus_tools.harness.mailbox import LocalMailboxReader
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import PORTAL_USERS
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.people import (
    FIRM_NAME,
    SEATS,
    email_of,
    slug_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import FIRM_ID

# SHL-06 (spec frames 2, 5, 6): codes expire in 10 minutes; five failed codes lock the account;
# "Try again at 9:54 AM" from 9:24 is a 30-minute lock.
STAFF_CODE_TTL: Final = timedelta(minutes=10)
STAFF_ATTEMPTS: Final = 5
STAFF_LOCK: Final = timedelta(minutes=30)
FIRM_ISSUER: Final = "Brightwater Hale"


def synthetic_only() -> None:
    if settings().environment not in SYNTHETIC_ENVIRONMENTS:
        raise RuntimeError("the WorkOS fake is for local runs and tests only")


def _ulid_like(prefix: str) -> str:
    """A WorkOS-shaped id: `user_01…`, `auth_factor_01…`, `auth_challenge_01…`."""
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return f"{prefix}_01" + "".join(secrets.choice(alphabet) for _ in range(24))


def _new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _totp_matches(secret: str, code: str, at: float) -> bool:
    return any(
        hmac.compare_digest(totp_at(secret, at + d * TOTP_STEP_SECONDS), code)
        for d in range(-TOTP_WINDOW, TOTP_WINDOW + 1)
    )


# --- the portal half: the PortalIdp port -------------------------------------------------------


@dataclass
class _Factor:
    user_id: str
    secret: str
    issuer: str
    account: str


@dataclass
class FakeWorkOsPortalIdp:
    """WorkOS User Management and MFA for portal clients, in memory. `now` (unix seconds) is
    injectable for tests; otherwise the system clock, as MFA always is (F-04-T36)."""

    now: float | None = None
    unavailable: bool = False
    users: dict[str, str] = field(default_factory=dict[str, str])  # email -> user id
    names: dict[str, str | None] = field(default_factory=dict[str, str | None])  # user -> name
    factors: dict[str, _Factor] = field(default_factory=dict[str, _Factor])
    challenges: dict[str, str] = field(default_factory=dict[str, str])  # challenge -> factor

    def __post_init__(self) -> None:
        synthetic_only()

    def _check(self) -> None:
        if self.unavailable:
            raise PortalIdpUnavailable("ServerException")

    def _clock(self) -> float:
        return system_now().timestamp() if self.now is None else self.now

    async def upsert_user(self, email: str, *, name: str | None = None) -> str:
        self._check()
        address = email.strip().lower()
        user = self.users.get(address)
        if user is None:
            user = self.users[address] = _ulid_like("user")
            self.names[user] = name
        return user

    async def enrol_totp(self, user_id: str, *, issuer: str, account: str) -> TotpEnrolment:
        self._check()
        issuer = check_issuer(issuer)
        if user_id not in self.names:
            raise PortalIdpUnavailable("NotFoundError")
        secret = _new_secret()
        factor = _ulid_like("auth_factor")
        self.factors[factor] = _Factor(user_id, secret, issuer, account)
        uri = (
            f"otpauth://totp/{quote(f'{issuer}:{account}')}?secret={secret}&issuer={quote(issuer)}"
        )
        return TotpEnrolment(factor, secret, uri)

    async def challenge(self, factor_id: str) -> str:
        self._check()
        if factor_id not in self.factors:
            raise PortalIdpUnavailable("NotFoundError")
        challenge = _ulid_like("auth_challenge")
        self.challenges[challenge] = factor_id
        return challenge

    async def verify(self, challenge_id: str, code: str) -> bool:
        self._check()
        factor_id = self.challenges.pop(challenge_id, None)  # single use, right or wrong
        factor = self.factors.get(factor_id or "")
        if factor is None or len(code) != CODE_DIGITS or not code.isdigit():
            return False
        return _totp_matches(factor.secret, code, self._clock())

    async def remove_factor(self, factor_id: str) -> None:
        self._check()
        self.factors.pop(factor_id, None)

    # --- harness readers ---

    def user_for(self, email: str) -> str | None:
        return self.users.get(email.strip().lower())

    def factors_of(self, user_id: str) -> list[str]:
        return [f for f, factor in self.factors.items() if factor.user_id == user_id]

    def current_code(self, factor_id: str) -> str:
        """The code the client's authenticator app shows now (POR-01c)."""
        return totp_at(self.factors[factor_id].secret, self._clock())


@dataclass(frozen=True)
class PortalPersona:
    email: str
    name: str
    mfa: bool  # the firm requires an authenticator (owners and signers; POR-01c)


def scenario_portal_personas() -> tuple[PortalPersona, ...]:
    """The scenario's portal people on the sink domain; `owner` grants meet the MFA floor."""
    return tuple(PortalPersona(u.email, u.name, u.role == "owner") for u in PORTAL_USERS)


async def seed_portal_personas(
    idp: FakeWorkOsPortalIdp, people: Iterable[PortalPersona] | None = None
) -> dict[str, str | None]:
    """Each persona's user, and a TOTP factor for those the firm asks for one: email -> factor."""
    out: dict[str, str | None] = {}
    for person in scenario_portal_personas() if people is None else people:
        user = await idp.upsert_user(person.email, name=person.name)
        factor: str | None = None
        if person.mfa:
            enrolled = await idp.enrol_totp(user, issuer=FIRM_ISSUER, account=person.email)
            factor = enrolled.factor_id
        out[person.email] = factor
    return out


# --- the staff half: AuthKit's hosted email code, second factor and lockout ---------------------


@dataclass(frozen=True)
class StaffUser:
    email: str
    subject: str  # the provider subject the users row holds (`scenario-<slug>`)
    name: str


def scenario_staff() -> tuple[StaffUser, ...]:
    """The firm's seats, as the loader writes their users rows."""
    return tuple(StaffUser(email_of(s.name), f"scenario-{slug_of(s.name)}", s.name) for s in SEATS)


def it_security_person() -> str:
    """Who unlocks a locked account (SHL-06f): the firm's IT / Security seat."""
    return next(s.name for s in SEATS if s.role == "IT / Security")


Stage = Literal["code", "mfa", "done"]


@dataclass
class _Pending:
    email: str
    code: str | None  # None for an unknown email: no mail is sent and every code is wrong
    expires: datetime
    stage: Stage = "code"


@dataclass(frozen=True)
class Outcome:
    """What the hosted page shows next."""

    state: Literal["mfa_required", "signed_in", "wrong_code", "locked", "expired", "unknown"]
    attempts_left: int | None = None
    locked_until: datetime | None = None
    subject: str | None = None


class StaffSignIn:
    """The staff email-code flow, one pending sign-in per token. `clock` is injectable."""

    def __init__(
        self,
        users: Iterable[StaffUser] | None = None,
        *,
        clock: Callable[[], datetime] = system_now,
        mailbox_dir: Path | None = None,
    ) -> None:
        synthetic_only()
        self._users = {u.email.lower(): u for u in (scenario_staff() if users is None else users)}
        self._clock = clock
        self._mailbox_dir = mailbox_dir or Path(settings().local_mailbox_dir)
        self._pending: dict[str, _Pending] = {}
        self._failures: dict[str, int] = {}
        self._locked: dict[str, datetime] = {}
        self._secrets: dict[str, str] = {}  # email -> the TOTP secret of its authenticator

    @staticmethod
    def delivered_to(email: str) -> str:
        """Where the code email lands: the synthetic sink, never the firm's own domain."""
        routed = sink_address(email, UUID(FIRM_ID))
        if routed is None:
            raise RuntimeError("no synthetic sink in this environment")
        return routed

    def user(self, email: str) -> StaffUser | None:
        return self._users.get(email.strip().lower())

    def by_subject(self, subject: str) -> StaffUser | None:
        return next((u for u in self._users.values() if u.subject == subject), None)

    def locked_until(self, email: str) -> datetime | None:
        until = self._locked.get(email.strip().lower())
        if until is not None and until <= self._clock():
            del self._locked[email.strip().lower()]
            self._failures.pop(email.strip().lower(), None)
            return None
        return until

    def start(self, email: str) -> str:
        """SHL-06a → b: a pending sign-in token. The same answer for any email (no enumeration);
        only a known, unlocked person gets a code."""
        address = email.strip().lower()
        token = secrets.token_urlsafe(24)
        known = self.user(address) is not None and self.locked_until(address) is None
        code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}" if known else None
        self._pending[token] = _Pending(address, code, self._clock() + STAFF_CODE_TTL)
        if code is not None:
            LocalMailbox(self._mailbox_dir).send(
                to=self.delivered_to(address),
                subject=f"Your sign-in code is {code}",
                body=(
                    f"Your {FIRM_NAME} sign-in code is {code}. It expires in 10 minutes. "
                    "If you didn't ask for it, you can ignore this email."
                ),
                sender_name="Sign-in",
            )
        return token

    def email_of(self, token: str) -> str | None:
        pending = self._pending.get(token)
        return pending.email if pending else None

    def _fail(self, email: str) -> Outcome:
        failures = self._failures.get(email, 0) + 1
        self._failures[email] = failures
        if failures >= STAFF_ATTEMPTS:
            until = self._clock() + STAFF_LOCK
            self._locked[email] = until
            return Outcome("locked", 0, until)
        return Outcome("wrong_code", STAFF_ATTEMPTS - failures)

    def submit_code(self, token: str, code: str) -> Outcome:
        """SHL-06b → c (right), → e (wrong), → f (the fifth wrong code, or already locked)."""
        pending = self._pending.get(token)
        if pending is None or pending.stage != "code":
            return Outcome("unknown")
        until = self.locked_until(pending.email)
        if until is not None:
            return Outcome("locked", 0, until)
        if pending.expires <= self._clock():
            return Outcome("expired")
        if pending.code is None or not hmac.compare_digest(pending.code, code.strip()):
            return self._fail(pending.email)
        pending.stage = "mfa"
        return Outcome("mfa_required")

    def submit_totp(self, token: str, code: str) -> Outcome:
        """SHL-06c → g. Wrong authenticator codes count toward the same lock."""
        pending = self._pending.get(token)
        if pending is None or pending.stage != "mfa":
            return Outcome("unknown")
        until = self.locked_until(pending.email)
        if until is not None:
            return Outcome("locked", 0, until)
        if not _totp_matches(self._secret(pending.email), code.strip(), self._now()):
            return self._fail(pending.email)
        pending.stage = "done"
        del self._pending[token]
        self._failures.pop(pending.email, None)
        user = self.user(pending.email)
        return Outcome("signed_in", subject=user.subject if user else None)

    def unlock(self, email: str) -> None:
        """What IT does from the admin console (SHL-06f "ask Felix Andersen")."""
        self._locked.pop(email.strip().lower(), None)
        self._failures.pop(email.strip().lower(), None)

    def _now(self) -> float:
        return self._clock().timestamp()

    def _secret(self, email: str) -> str:
        return self._secrets.setdefault(email.strip().lower(), _new_secret())

    # --- harness readers ---

    def current_totp(self, email: str) -> str:
        """The code the person's authenticator app shows now (SHL-06c)."""
        return totp_at(self._secret(email), self._now())

    def latest_code(self, email: str) -> str | None:
        """The last emailed code, read back from the mailbox as the harness reads it (b)."""
        found = LocalMailboxReader(self._mailbox_dir).latest(self.delivered_to(email))
        return found.code if found else None


def try_again_at(until: datetime) -> str:
    """SHL-06f's time: "9:54 AM", in the firm's time zone."""
    local = until.astimezone(CT)
    return f"{local:%-I:%M %p}"
