"""`Idempotency-Key` (P-36; P-06-T06; migration 0099).

A request that changes something outside the firm (a publish, a send) may carry an
`Idempotency-Key`. The first response for (tenant, actor, route, key) is stored with a hash of
its request. For 24 hours:
- a retry with the same key and the same request gets the stored response, and the effect
  doesn't run again;
- the same key with a different request is refused (422 `idempotency_key_reused`).

The stored response must not hold Restricted data: store identifiers, as routes return.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, cast

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_connection, tenant_session
from abacus.kernel.errors import DomainInvalid

HEADER: Final = "Idempotency-Key"
_KEY: Final = re.compile(r"[A-Za-z0-9_.:-]{8,200}")
_FIND = text(
    "SELECT request_sha256, status_code, response FROM idempotency_keys WHERE actor_id = :actor "
    "AND route = :route AND key = :key AND expires_at > clock_timestamp()"
)
_STORE = text(
    "INSERT INTO idempotency_keys (tenant_id, actor_id, route, key, request_sha256, status_code, "
    "response) VALUES (:tenant, :actor, :route, :key, :sha, :status, CAST(:response AS jsonb)) "
    "ON CONFLICT DO NOTHING"
)


class IdempotencyKeyReused(DomainInvalid):
    """This key already answered a different request."""

    code = "idempotency_key_reused"


class IdempotencyKeyInvalid(DomainInvalid):
    code = "idempotency_key_invalid"


@dataclass(frozen=True)
class Stored:
    status_code: int
    body: dict[str, object]
    replayed: bool


def request_hash(body: object) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def idempotent(
    ctx: TenantContext,
    *,
    route: str,
    key: str | None,
    body: object,
    run: Callable[[], Awaitable[tuple[int, dict[str, object]]]],
) -> Stored:
    """Run `run` once per key, or return what the first run answered."""
    if key is None:
        status, response = await run()
        return Stored(status, response, replayed=False)
    if not _KEY.fullmatch(key):
        raise IdempotencyKeyInvalid
    sha = request_hash(body)
    found = await _find(ctx, route, key)
    if found is not None:
        return _replay(found, sha)
    status, response = await run()
    async with tenant_connection(ctx) as conn:
        result = await conn.execute(
            _STORE,
            {
                "tenant": ctx.tenant_id,
                "actor": ctx.actor_id,
                "route": route,
                "key": key,
                "sha": sha,
                "status": status,
                "response": json.dumps(response, default=str),
            },
        )
        await conn.commit()
    if result.rowcount == 1:
        return Stored(status, response, replayed=False)
    # A concurrent first request stored before us: its answer is the one kept.
    kept = await _find(ctx, route, key)
    return _replay(kept, sha) if kept is not None else Stored(status, response, replayed=False)


async def _find(ctx: TenantContext, route: str, key: str) -> tuple[str, int, object] | None:
    async with tenant_session(ctx) as session:
        row = (
            await session.execute(_FIND, {"actor": ctx.actor_id, "route": route, "key": key})
        ).one_or_none()
    return None if row is None else (row.request_sha256, row.status_code, row.response)


def _replay(found: tuple[str, int, object], sha: str) -> Stored:
    stored_sha, status, response = found
    if stored_sha != sha:
        raise IdempotencyKeyReused
    raw = response if isinstance(response, str) else json.dumps(response)
    return Stored(status, cast(dict[str, object], json.loads(raw)), replayed=True)
