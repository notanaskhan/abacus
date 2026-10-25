"""Kill switches: the one reader of `platform_controls` (ADR-157 proposed; Q-01 §F8;
`docs/contracts/platform-ops.md` §3.7). Re-exported as `platform.api.control_active`.

Controls are rows operators set through `set_platform_control` (the `abacus_ops` role only); the
app reads them only through the definer `platform_control_state()`, here, with an in-process
cache of `CACHE_SECONDS` (10), so a change takes effect within that window and no request reads
the table itself. It never writes and never raises: when the state can't be read after the
window, `ai_pause` and `read_only` count as active (fail closed); `portal_sign_in` keeps its
last known value for at most 60 seconds after it was read and then counts as active (the sign-in
pause must not lapse, P-08-T21 security review); the others keep their last known value, or
count as inactive when there is none. Each such decision is logged by control name only.

Readers today: P-08-T21's portal sign-in pause (`portal_sign_in`, per firm); Q-01-T36's AI pause
(`ai_gateway.boundary.enforce_boundary`), route block (`ai_gateway._admitted` and `embed`) and
email pause (`communications.deliveries.deliver`); Q-01-T37's read-only mode
(`identity.routing`: the platform half in `AbacusRoute`, the firm half in `firm_writable`).
"""

from __future__ import annotations

import time
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import platform_transaction
from abacus.kernel.logging import get_logger

ControlName = Literal[
    "ai_pause", "model_route_block", "email_pause", "read_only", "portal_sign_in"
]
CACHE_SECONDS: Final = 10.0
_FAIL_CLOSED: Final = frozenset({"ai_pause", "read_only"})
# P-08-T21 (security review): these trust a last-known value only this long after it was read,
# then count as active (a pause must not lapse because its row can't be read).
STALE_LIMIT_SECONDS: Final = 60.0
_FAIL_CLOSED_AFTER_STALE: Final = frozenset({"portal_sign_in"})
# (control, scope, tenant_id, route) of every active row.
Active = frozenset[tuple[str, str, UUID | None, str | None]]
_state: list[tuple[float, Active]] = []
_log = get_logger(__name__)


def forget_controls() -> None:
    """Drop the cached state (tests)."""
    _state.clear()


def _clock() -> float:
    return time.monotonic()


async def _read() -> Active:
    async with platform_transaction("platform:controls") as conn:
        rows = (await conn.execute(text("SELECT * FROM platform_control_state()"))).all()
    return frozenset((r.control, r.scope, r.tenant_id, r.route) for r in rows)


async def _active_rows() -> tuple[Active | None, bool, float]:
    """The active rows, whether they are current, and their age: from the cache inside its
    window, else read now; after a failed read, the last rows known (or None) and False."""
    now = _clock()
    if _state and now - _state[0][0] < CACHE_SECONDS:
        return _state[0][1], True, now - _state[0][0]
    try:
        rows = await _read()
    except Exception as exc:
        _log.warning("platform_control.read_failed", error=type(exc).__name__)
        if not _state:
            return None, False, float("inf")
        return _state[0][1], False, now - _state[0][0]
    _state[:] = [(now, rows)]
    return rows, True, 0.0


class ReadOnlyMode(Exception):
    """`read_only` is on for the platform or this firm: 503 `read_only` (Q-01-T37)."""


ControlState = Literal["on", "off", "unknown"]


async def control_state(
    control: ControlName, tenant_id: UUID | None = None, *, route: str | None = None
) -> ControlState:
    """`on` or `off` as last read, or `unknown` when the state can't be read and this control
    has no value it may trust (where `control_active` would fail closed). A caller that must not
    mistake an outage for a switch (the AI pause ends runs for good) tells the two apart."""
    rows, current, age = await _active_rows()
    stale = not current and control in _FAIL_CLOSED_AFTER_STALE and age > STALE_LIMIT_SECONDS
    if rows is None or stale or (not current and control in _FAIL_CLOSED):
        _log.warning("platform_control.unknown", control=control)
        return "unknown"
    for name, scope, tenant, keyed in rows:
        if name != control or (control == "model_route_block" and keyed != route):
            continue
        if scope == "platform" or (tenant_id is not None and tenant == tenant_id):
            return "on"
    return "off"


async def control_active(
    control: ControlName, tenant_id: UUID | None = None, *, route: str | None = None
) -> bool:
    """Whether `control` is on for everyone, or for the firm `tenant_id`; `model_route_block`
    also needs the matching `route`. Unknown counts as on for `ai_pause`, `read_only` and (after
    its stale limit) `portal_sign_in`, as off for the others."""
    state = await control_state(control, tenant_id, route=route)
    if state == "unknown":
        return control in _FAIL_CLOSED or control in _FAIL_CLOSED_AFTER_STALE
    return state == "on"


async def ensure_writable(tenant_id: UUID | None = None) -> None:
    """Q-01-T37: refuse a write while `read_only` is on for the platform or this firm (and,
    failing closed, while the state can't be read)."""
    if await control_active("read_only", tenant_id):
        raise ReadOnlyMode(str(tenant_id))
