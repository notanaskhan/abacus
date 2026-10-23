"""The browser error tunnel (Q-01-T48; ADR-021, ADR-031). PROTECTED.

`@sentry/browser` posts its envelope to `POST /v1/telemetry/errors`, so the CSP keeps
`connect-src 'self'`. Nothing the browser sent is forwarded as it arrived. The event Sentry gets
is rebuilt from an allowlist:
- from the browser, only the route template and the error's type name, each refused unless it
  matches a strict, digit-free shape. No SSN, TIN, email or other free text fits either shape.
- from the server: the environment, the release and the tenant UUID.
Messages, values, frames, breadcrumbs, users, URLs and request data are dropped.

Signed-in people only (`OWN`): support sessions are refused, agents never reach HTTP, and errors
before sign-in are not reported (the documented gap). 64 KB at most per envelope, and 30 per minute
per person.
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from collections.abc import Mapping
from typing import Final, cast
from uuid import UUID, uuid4

from abacus.kernel.config import settings
from abacus.kernel.error_tracking import forward_event

MAX_BYTES: Final = 64 * 1024
PER_MINUTE: Final = 30
# `/engagements/$engagementId/requests` or `/v1/things/{id}`: words and placeholders, no digits.
_ROUTE: Final = re.compile(r"(/(\$?[A-Za-z_][A-Za-z_-]{0,39}|\{[A-Za-z_]{1,40}\}))*/?")
_ERROR_TYPE: Final = re.compile(r"[A-Za-z_][A-Za-z_.]{0,79}")
_EVENT_ID: Final = re.compile(r"[0-9a-f]{32}")
_recent: dict[UUID, deque[float]] = {}


class TooMany(Exception):
    """More than PER_MINUTE envelopes from one person in the last minute."""


def _within_rate(user_id: UUID) -> bool:
    now = time.monotonic()
    window = _recent.setdefault(user_id, deque())
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= PER_MINUTE:
        return False
    window.append(now)
    return True


def _event_of(envelope: bytes) -> Mapping[str, object] | None:
    """The `event` item of a Sentry envelope (newline-delimited JSON), or None."""
    lines = envelope.split(b"\n")
    for i in range(1, len(lines) - 1):
        try:
            header = cast(object, json.loads(lines[i]))
        except ValueError:
            continue
        if isinstance(header, dict) and cast(dict[str, object], header).get("type") == "event":
            try:
                body = cast(object, json.loads(lines[i + 1]))
            except ValueError:
                return None
            return cast(Mapping[str, object], body) if isinstance(body, dict) else None
    return None


def _error_type(event: Mapping[str, object]) -> str | None:
    exception = event.get("exception")
    values = (
        cast(Mapping[str, object], exception).get("values")
        if isinstance(exception, dict)
        else None
    )
    if not isinstance(values, list) or not values:
        return None
    last = cast(list[object], values)[-1]
    kind = cast(Mapping[str, object], last).get("type") if isinstance(last, dict) else None
    return kind if isinstance(kind, str) and _ERROR_TYPE.fullmatch(kind) else None


def _route(event: Mapping[str, object]) -> str | None:
    tags = event.get("tags")
    route = cast(Mapping[str, object], tags).get("route") if isinstance(tags, dict) else None
    return (
        route if isinstance(route, str) and len(route) <= 200 and _ROUTE.fullmatch(route) else None
    )


def rebuild(envelope: bytes, tenant_id: UUID) -> dict[str, object] | None:
    """The only event that may leave: allowlisted fields, or None when there is nothing valid."""
    event = _event_of(envelope)
    if event is None:
        return None
    error_type = _error_type(event)
    if error_type is None:
        return None
    given = event.get("event_id")
    tags: dict[str, object] = {"tenant_id": str(tenant_id), "error_type": error_type}
    route = _route(event)
    if route is not None:
        tags["route"] = route
    s = settings()
    return {
        "event_id": given
        if isinstance(given, str) and _EVENT_ID.fullmatch(given)
        else uuid4().hex,
        "level": "error",
        "platform": "javascript",
        "environment": s.environment,
        "release": s.release,
        "server_name": "abacus-web",
        "exception": {"values": [{"type": error_type}]},
        "tags": tags,
    }


def report_browser_error(user_id: UUID, tenant_id: UUID, envelope: bytes) -> bool:
    """True if an event was forwarded. Raises `TooMany` past the rate limit."""
    if not _within_rate(user_id):
        raise TooMany
    event = rebuild(envelope, tenant_id)
    return event is not None and forward_event(event)
