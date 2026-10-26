"""The request context a person's audit events carry (G-02-T06; SPEC-349 AC-9; DEC-60).

The HTTP edge binds one `RequestContext` per request (`abacus.api.request_context`): the client
IP (after the trusted proxy chain), the user agent's family and a short device label ("Chrome ·
macOS"), and the SHA-256 of the staff session cookie when the request carries one. Identity adds
what it learns while resolving the caller (`note_session`: the portal or support session, the
sign-in method, the MFA time). The unit of work reads it when it writes a human's or a support
engineer's audit events, and asks the registered session resolver for the staff session behind
the cookie (identity registers it, so the kernel never reads identity's tables itself).

`ip` and `device_label` are personal data (Confidential): never logged, never put in a domain
event, never in an error. Agent and system events never carry any of it; the database refuses
them (`audit_events_request_context_is_a_persons`).
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection

AuthMethod = Literal["sso", "email_code", "passkey", "totp", "support", "service"]
# Request-context columns may be set only on these actor kinds' events (the database CHECK).
PERSON_KINDS: Final = frozenset({"human", "support"})
MAX_LABEL: Final = 80


@dataclass(frozen=True)
class RequestContext:
    ip: str | None = None
    user_agent_family: str | None = None
    device_label: str | None = None
    # The staff BFF cookie's SHA-256, for the session resolver; never stored or logged.
    session_cookie_sha256: str | None = None
    session_id: UUID | None = None
    auth_method: AuthMethod | None = None
    mfa_at: datetime | None = None


@dataclass(frozen=True)
class ResolvedSession:
    session_id: UUID
    mfa_at: datetime | None


# (connection, cookie SHA-256, acting user id) -> the live session that cookie belongs to.
SessionResolver = Callable[[AsyncConnection, str, UUID], Awaitable[ResolvedSession | None]]

_current: ContextVar[RequestContext | None] = ContextVar("abacus_request_context", default=None)
_resolver: list[tuple[str, SessionResolver]] = []


def register_session_resolver(cookie_name: str, resolver: SessionResolver) -> None:
    """Identity's staff session lookup, and the cookie it reads (one per process)."""
    if _resolver:
        raise ValueError("a session resolver is already registered")
    _resolver.append((cookie_name, resolver))


def session_cookie_name() -> str | None:
    return _resolver[0][0] if _resolver else None


def session_resolver() -> SessionResolver | None:
    return _resolver[0][1] if _resolver else None


def current() -> RequestContext | None:
    return _current.get()


@contextmanager
def bound(context: RequestContext) -> Generator[RequestContext]:
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


def note_session(
    *,
    session_id: UUID | None = None,
    auth_method: AuthMethod | None = None,
    mfa_at: datetime | None = None,
) -> None:
    """What identity learned about the caller's session; a no-op outside a request."""
    found = _current.get()
    if found is None:
        return
    _current.set(
        replace(
            found,
            session_id=session_id if session_id is not None else found.session_id,
            auth_method=auth_method if auth_method is not None else found.auth_method,
            mfa_at=mfa_at if mfa_at is not None else found.mfa_at,
        )
    )


def cookie_sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def client_ip(host: str | None) -> str | None:
    """The peer's address as Postgres `inet` reads it, or None when it isn't an IP (a test
    client's "testclient")."""
    if not host:
        return None
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


# Ordered: Edge and Opera carry "Chrome", Chrome carries "Safari".
_BROWSERS: Final = (
    ("Edge", re.compile(r"\bEdg(e|A|iOS)?/")),
    ("Opera", re.compile(r"\bOPR/")),
    ("Firefox", re.compile(r"\b(Firefox|FxiOS)/")),
    ("Chrome", re.compile(r"\b(Chrome|CriOS)/")),
    ("Safari", re.compile(r"\bVersion/[\d.]+.*\bSafari/")),
)
_SYSTEMS: Final = (
    ("iOS", re.compile(r"\b(iPhone|iPad|iPod)\b")),
    ("Android", re.compile(r"\bAndroid\b")),
    ("Windows", re.compile(r"\bWindows\b")),
    ("macOS", re.compile(r"\bMac OS X\b|\bMacintosh\b")),
    ("ChromeOS", re.compile(r"\bCrOS\b")),
    ("Linux", re.compile(r"\bLinux\b")),
)


def device_of(user_agent: str | None) -> tuple[str | None, str | None]:
    """The user agent's family and a device label ("Chrome · macOS"), from a closed list: no
    version numbers and no free text from the header ever reach the audit log."""
    if not user_agent:
        return None, None
    text = user_agent[:512]
    family = next((name for name, pattern in _BROWSERS if pattern.search(text)), "Other")
    system = next((name for name, pattern in _SYSTEMS if pattern.search(text)), None)
    return family, family if system is None else f"{family} · {system}"


__all__ = [
    "PERSON_KINDS",
    "AuthMethod",
    "RequestContext",
    "ResolvedSession",
    "SessionResolver",
    "bound",
    "client_ip",
    "cookie_sha256",
    "current",
    "device_of",
    "note_session",
    "register_session_resolver",
    "session_cookie_name",
    "session_resolver",
]
