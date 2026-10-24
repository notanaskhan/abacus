"""The portal's second step (P-08-T17; SPEC-320 AC-11; DEC-34, DEC-35; DEC-250). PROTECTED.

After a right email code, a person the MFA floor covers holds a 5-minute single-use `mfa_token`
(`portal_session.SecondStepRequired`) and no session:

- **Second step** (`second_step`): a TOTP from their WorkOS factor or one of their 8 backup codes.
  Each guess is counted before it is compared (`portal_mfa_attempt`, under row locks), apart from
  code guesses and not reset by a right email code; the third wrong one locks sign-in for the
  email for 15 minutes (`mfa_locked`). A right one uses the token and starts the session, and
  "trust this device" sets a `__Host-` device cookie for the firm's days (30 at most).
- **Setup** (`setup_second_step`, `verify_setup`): only for a person with no enrolled factor. The
  secret is returned once per token and never stored; the first right code enrols the factor and
  returns 8 new backup codes, once. Backup codes are kept only as SHA-256 (80 random bits each).
- **Revocation** (`revoke_portal_access`): on `access.changed` or `client_access.revoked` the
  person's portal sessions in the firm end and their trusted devices there are revoked.

TOTP secrets, backup codes, tokens and device cookies are Restricted: never logged, never in an
audit row or event, never returned twice.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Row, text

from abacus.kernel.db import TenantContext, platform_transaction
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.identity.mfa_floor import portal_security_policy
from abacus.modules.identity.portal_idp import PortalIdpUnavailable, portal_idp
from abacus.modules.identity.portal_session import (
    LOCK_SECONDS,
    MAX_TRIES,
    PortalTokens,
    _audit,  # pyright: ignore[reportPrivateUsage] -- sign-in's audit helper, same flow
    _host,  # pyright: ignore[reportPrivateUsage] -- sign-in's host normaliser, same pinning
    open_session,
    sha256_hex,
)
from abacus.modules.identity.repository import emails_of, firm_name_of
from abacus.modules.identity.staff_session import END_REASONS

DEVICE_COOKIE: Final = "__Host-abacus-portal-device"
BACKUP_CODES: Final = 8
# 16 characters of Crockford's base32 (80 bits), shown as four groups of four.
_ALPHABET: Final = "0123456789abcdefghjkmnpqrstvwxyz"
_BACKUP_GROUPS: Final = 4
_BACKUP_SHAPE: Final = re.compile(r"[0-9a-z]{16}")
# Every refusal of the second step takes at least this long (the sign-in floor's rule).
FLOOR_SECONDS: Final = 0.5
_log = get_logger(__name__)


async def _floor(began: float) -> None:
    """Pad a refusal to the floor, as sign-in does."""
    left = FLOOR_SECONDS - (time.monotonic() - began)
    if left > 0:
        await asyncio.sleep(left)


class MfaMismatch(Exception):
    def __init__(self, tries_left: int) -> None:
        super().__init__("mfa_mismatch")
        self.tries_left = tries_left


class MfaLocked(Exception):
    def __init__(self, locked_until: datetime) -> None:
        super().__init__("mfa_locked")
        self.locked_until = locked_until


class MfaExpired(Exception):
    """The token is unknown, expired, used, of the other kind, or from another host."""


@dataclass(frozen=True)
class SecondStepDone:
    tokens: PortalTokens
    device_cookie: str | None  # set as `DEVICE_COOKIE` for `device_days`
    device_days: int


@dataclass(frozen=True)
class SetupKey:
    """Shown once: the QR code's URI and the same secret as text."""

    otpauth_uri: str
    manual_key: str


@dataclass(frozen=True)
class SetupDone:
    backup_codes: tuple[str, ...]  # shown once
    tokens: PortalTokens


def _backup_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(4 * _BACKUP_GROUPS))
    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))


def _normalised(code: str) -> str | None:
    """A backup code as stored (lower case, no separators), or None if it can't be one."""
    flat = re.sub(r"[\s-]", "", code).lower()
    return flat if _BACKUP_SHAPE.fullmatch(flat) else None


def backup_code_sha256(code: str) -> str:
    """The stored digest: of the code as `_backup_code` displays it, however it was typed."""
    flat = _normalised(code) or ""
    return sha256_hex("-".join(flat[i : i + 4] for i in range(0, len(flat), 4)))


def _ua_family(user_agent: str | None) -> str | None:
    """A coarse browser family for the device list, never the user agent itself."""
    ua = (user_agent or "").lower()
    for marker, family in (
        ("edg/", "edge"),
        ("firefox/", "firefox"),
        ("chrome/", "chrome"),
        ("safari/", "safari"),
    ):
        if marker in ua:
            return family
    return None


@dataclass(frozen=True)
class _Attempt:
    tenant_id: UUID
    user_id: UUID
    factor_ref: str
    tries_left: int


async def _attempt(token: str, host: str, kind: str, began: float) -> _Attempt:
    """Count the guess (before any comparison) and hand back what to compare against."""
    async with platform_transaction("portal:mfa") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_mfa_attempt(:token, :host, :kind, :max, :lock)"),
                {
                    "token": sha256_hex(token),
                    "host": host,
                    "kind": kind,
                    "max": MAX_TRIES,
                    "lock": LOCK_SECONDS,
                },
            )
        ).one()
    if row.outcome == "locked":
        if row.user_id is not None:  # this guess set the lock
            await _locked(cast(UUID, row.tenant_id), cast(UUID, row.user_id))
        await _floor(began)
        raise MfaLocked(row.locked_until)
    if row.outcome != "ok":
        await _floor(began)
        raise MfaExpired
    return _Attempt(
        cast(UUID, row.tenant_id),
        cast(UUID, row.user_id),
        str(row.factor_ref),
        int(row.tries_left),
    )


async def _locked(tenant_id: UUID, user_id: UUID) -> None:
    await _audit(tenant_id, user_id, "portal_mfa.locked", Target("user", user_id))


async def _missed(token: str, attempt: _Attempt, began: float) -> None:
    async with platform_transaction("portal:mfa") as conn:
        locked_until = cast(
            datetime | None,
            (
                await conn.execute(
                    text("SELECT portal_mfa_missed(:token, :left, :lock)"),
                    {"token": sha256_hex(token), "left": attempt.tries_left, "lock": LOCK_SECONDS},
                )
            ).scalar_one(),
        )
    await _audit(
        attempt.tenant_id, attempt.user_id, "portal_mfa.failed", Target("user", attempt.user_id)
    )
    if locked_until is not None:
        await _locked(attempt.tenant_id, attempt.user_id)
    await _floor(began)
    if locked_until is not None:
        raise MfaLocked(locked_until)
    raise MfaMismatch(attempt.tries_left)


async def _totp_matches(factor_ref: str, totp: str) -> bool:
    idp = portal_idp()
    return await idp.verify(await idp.challenge(factor_ref), totp)


async def second_step(
    host: str | None,
    mfa_token: str,
    *,
    totp: str | None = None,
    backup_code: str | None = None,
    trust_device: bool = False,
    previous_cookie: str | None = None,
    user_agent: str | None = None,
) -> SecondStepDone:
    """A TOTP or a backup code for the token's person; the session on success."""
    began = time.monotonic()
    pinned = _host(host)
    if (totp is None) == (backup_code is None) or len(mfa_token) > 128:
        raise MfaExpired
    attempt = await _attempt(mfa_token, pinned, "verify", began)
    if totp is not None:
        # The provider unavailable raises: the guess stays counted and there is no session.
        matched = await _totp_matches(attempt.factor_ref, totp)
    else:
        matched = False
        if _normalised(cast(str, backup_code)) is not None:
            async with platform_transaction(f"user:{attempt.user_id}") as conn:
                matched = bool(
                    (
                        await conn.execute(
                            text("SELECT portal_mfa_backup_use(:user, :code)"),
                            {
                                "user": attempt.user_id,
                                "code": backup_code_sha256(cast(str, backup_code)),
                            },
                        )
                    ).scalar_one()
                )
    if not matched:
        await _missed(mfa_token, attempt, began)
    tokens = await open_session(
        attempt.tenant_id,
        attempt.user_id,
        pinned,
        text("SELECT EXISTS (SELECT 1 FROM portal_mfa_complete(:token))"),
        {"token": sha256_hex(mfa_token)},
        previous_cookie=previous_cookie,
        mfa=True,
    )
    if tokens is None:
        raise MfaExpired  # used by a concurrent request
    target = Target("user", attempt.user_id)
    if backup_code is not None:
        await _audit(attempt.tenant_id, attempt.user_id, "portal_backup_code.used", target)
    await _audit(attempt.tenant_id, attempt.user_id, "portal_mfa.verified", target)
    device, days = None, 0
    if trust_device:
        device, days = await _trust(attempt.tenant_id, attempt.user_id, user_agent)
    return SecondStepDone(tokens, device, days)


async def _trust(tenant_id: UUID, user_id: UUID, user_agent: str | None) -> tuple[str | None, int]:
    days = (await portal_security_policy(tenant_id)).trusted_device_days
    if days <= 0:
        return None, 0
    device = secrets.token_urlsafe(32)
    async with platform_transaction(f"user:{user_id}") as conn:
        await conn.execute(
            text("SELECT * FROM portal_device_trust(:tenant, :user, :device, :days, :ua)"),
            {
                "tenant": tenant_id,
                "user": user_id,
                "device": sha256_hex(device),
                "days": days,
                "ua": _ua_family(user_agent),
            },
        )
    await _audit(tenant_id, user_id, "portal_device.trusted", Target("user", user_id))
    return device, days


async def setup_second_step(host: str | None, mfa_token: str) -> SetupKey:
    """Enrol a TOTP factor at the provider for a person with none; the secret, once."""
    began = time.monotonic()
    if len(mfa_token) > 128:
        raise MfaExpired
    async with platform_transaction("portal:mfa") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_mfa_setup_claim(:token, :host)"),
                {"token": sha256_hex(mfa_token), "host": _host(host)},
            )
        ).first()
    if row is None:
        await _floor(began)
        raise MfaExpired
    tenant_id, user_id = cast(UUID, row.tenant_id), cast(UUID, row.user_id)
    email = (await emails_of([user_id])).get(user_id)
    firm = await firm_name_of(tenant_id)
    if email is None or firm is None:
        raise PortalIdpUnavailable("no_account")
    idp = portal_idp()
    provider_user = await idp.upsert_user(email)
    try:
        enrolment = await idp.enrol_totp(provider_user, issuer=firm, account=email)
    except ValueError:  # the firm's name can't be an issuer (it names the product)
        raise PortalIdpUnavailable("issuer") from None
    async with platform_transaction(f"user:{user_id}") as conn:
        pending = (
            await conn.execute(
                text("SELECT * FROM portal_mfa_factor_pending(:user, :provider, :factor)"),
                {"user": user_id, "provider": provider_user, "factor": enrolment.factor_id},
            )
        ).one()
    if pending.outcome != "ok":  # enrolled meanwhile: drop the factor just made
        await idp.remove_factor(enrolment.factor_id)
        raise MfaExpired
    if pending.replaced is not None:  # an abandoned setup's factor
        try:
            await idp.remove_factor(str(pending.replaced))
        except PortalIdpUnavailable:
            _log.warning("portal_mfa.stale_factor_kept", user_id=user_id)
    return SetupKey(enrolment.otpauth_uri, enrolment.secret)


async def verify_setup(
    host: str | None, mfa_token: str, totp: str, *, previous_cookie: str | None = None
) -> SetupDone:
    """The new factor's first code: enrol it, replace the backup codes, start the session."""
    began = time.monotonic()
    pinned = _host(host)
    if len(mfa_token) > 128:
        raise MfaExpired
    attempt = await _attempt(mfa_token, pinned, "setup", began)
    if not await _totp_matches(attempt.factor_ref, totp):
        await _missed(mfa_token, attempt, began)
    codes = tuple(_backup_code() for _ in range(BACKUP_CODES))
    tokens = await open_session(
        attempt.tenant_id,
        attempt.user_id,
        pinned,
        text("SELECT EXISTS (SELECT 1 FROM portal_mfa_enrol(:token, :factor, :codes))"),
        {
            "token": sha256_hex(mfa_token),
            "factor": attempt.factor_ref,
            "codes": [backup_code_sha256(c) for c in codes],
        },
        previous_cookie=previous_cookie,
        mfa=True,
    )
    if tokens is None:
        raise MfaExpired
    await _audit(
        attempt.tenant_id, attempt.user_id, "portal_mfa.enrolled", Target("user", attempt.user_id)
    )
    return SetupDone(codes, tokens)


async def revoke_portal_access(event: OutboxEvent) -> None:
    """`access.changed` / `client_access.revoked`: the person's portal sessions in the firm end
    and their trusted devices there are revoked (P-08 Story 3.4). Idempotent."""
    user = event.payload.get("user_id")
    if not isinstance(user, str):
        return
    user_id = UUID(user)
    # One transaction: the revocation and its audit rows commit together, so a failed write is
    # retried whole by the relay instead of revoking silently. Nothing to revoke rolls back.
    try:
        async with uow(TenantContext(event.tenant_id, "system", "identity:access_changed")) as tx:
            rows = (
                await tx.session.execute(
                    text("SELECT * FROM portal_access_revoke(:tenant, :user)"),
                    {"tenant": event.tenant_id, "user": user_id},
                )
            ).all()
            if not rows:
                raise _NothingRevoked
            _record_revoked(tx, user_id, rows)
    except _NothingRevoked:
        return


class _NothingRevoked(Exception):
    pass


def _record_revoked(
    tx: UnitOfWork,
    user_id: UUID,
    rows: Sequence[Row[Any]],  # Any: a text() row's columns are untyped
) -> None:
    for row in rows:
        if row.kind == "session":
            tx.record(
                "session.ended",
                target=Target("auth_session", cast(UUID, row.id)),
                after=Ref(reason=END_REASONS["revoked"]),
            )
        else:
            tx.record("portal_device.revoked", target=Target("user", user_id))
