"""Feature flags (ADR-089; SPEC-011). Read per firm, defaulting safely.

Flags are declared in `docs/architecture/feature-flags.yaml` and generated into
`kernel/_flags.py`; code passes those constants, never names (FLAG-001). `flag()` returns the
firm's value, or the registry default when the firm has none, the stored value is no longer
valid, or the read fails (it never raises). Values are cached per process for 30 seconds (Q5).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter

CACHE_SECONDS: Final = 30.0
_log = get_logger(__name__)
_failed = meter(__name__).create_counter(
    "abacus.flags.read_failed", description="Flag reads that fell back to the default"
)
_cache: dict[tuple[UUID, str], tuple[float, str | None]] = {}


@dataclass(frozen=True)
class Flag:
    name: str
    kind: Literal["boolean", "variant"]
    default: str  # "true" / "false" for booleans
    values: tuple[str, ...] = ()

    def parse(self, stored: str | None) -> bool | str:
        value = stored if stored is not None and self.valid(stored) else self.default
        return value == "true" if self.kind == "boolean" else value

    def valid(self, value: str) -> bool:
        return value in (("true", "false") if self.kind == "boolean" else self.values)


def forget_flags() -> None:
    """Drop cached values (tests; the operator CLI after a change in the same process)."""
    _cache.clear()


async def _stored(tenant: TenantContext, name: str) -> str | None:
    key = (tenant.tenant_id, name)
    hit = _cache.get(key)
    if hit is not None and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    async with tenant_session(tenant) as session:
        value = await session.scalar(
            text("SELECT value FROM feature_flag_states WHERE flag = :flag"), {"flag": name}
        )
    stored = str(value) if value is not None else None
    _cache[key] = (time.monotonic(), stored)
    return stored


async def flag(tenant: TenantContext, f: Flag) -> bool | str:
    """The firm's value for `f`, else its default (AC-1, AC-2)."""
    try:
        return f.parse(await _stored(tenant, f.name))
    except Exception as exc:
        _failed.add(1, {"flag": f.name})
        _log.warning("flag.read_failed", flag=f.name, error=type(exc).__name__)
        return f.parse(None)


async def flag_enabled(tenant: TenantContext, f: Flag) -> bool:
    """A boolean flag's value."""
    if f.kind != "boolean":
        raise TypeError(f"{f.name} is a variant flag")
    return bool(await flag(tenant, f))


async def flag_variant(tenant: TenantContext, f: Flag) -> str:
    """A variant flag's value."""
    if f.kind != "variant":
        raise TypeError(f"{f.name} is a boolean flag")
    return str(await flag(tenant, f))
