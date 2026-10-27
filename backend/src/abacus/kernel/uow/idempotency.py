"""`Idempotency-Key` (P-36; P-06-T06; migrations 0099 and 0214).

A request that changes something outside the firm (a publish, a send, a bulk sign-off) may carry
an `Idempotency-Key`. Per (tenant, actor, route, key), for 24 hours:
- the first request claims the key (a pending row holding a hash of its request) in its own
  short committed statement, before its effect runs, then fills the row with its response;
- a retry with the same key and request gets the stored response, and the effect doesn't run
  again; while the first is still running it is told so (409 `idempotency_in_progress`);
- the same key with a different request is refused (422 `idempotency_key_reused`).

A run that fails releases its claim. A claim left by a crash is reclaimed after
`PENDING_RECLAIM_S`, and an expired row by the next request (DEC-507), so a key never blocks
forever. No connection is held while the effect runs (security re-review M1).

The stored response must not hold Restricted data: store identifiers, as routes return.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Final, cast

from sqlalchemy import TextClause, text

from abacus.kernel.db import TenantContext, tenant_connection, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid

HEADER: Final = "Idempotency-Key"
PENDING_RECLAIM_S: Final = 300
_KEY: Final = re.compile(r"[A-Za-z0-9_.:-]{8,200}")
_FIND = text(
    "SELECT request_sha256, status_code, response FROM idempotency_keys WHERE actor_id = :actor "
    "AND route = :route AND key = :key AND expires_at > clock_timestamp()"
)
# Insert the claim, or take over an expired row or a stale pending one; a live row is left alone
# (no row returned).
_CLAIM = text(
    "INSERT INTO idempotency_keys (tenant_id, actor_id, route, key, request_sha256) "
    "VALUES (:tenant, :actor, :route, :key, :sha) "
    "ON CONFLICT (tenant_id, actor_id, route, key) DO UPDATE SET "
    "request_sha256 = EXCLUDED.request_sha256, status_code = NULL, response = NULL, "
    "created_at = clock_timestamp(), expires_at = clock_timestamp() + interval '24 hours' "
    "WHERE idempotency_keys.expires_at <= clock_timestamp() "
    "OR (idempotency_keys.status_code IS NULL "
    "AND idempotency_keys.created_at < clock_timestamp() - make_interval(secs => :reclaim)) "
    "RETURNING 1"
)
_FILL = text(
    "UPDATE idempotency_keys SET status_code = :status, response = CAST(:response AS jsonb) "
    "WHERE actor_id = :actor AND route = :route AND key = :key AND request_sha256 = :sha "
    "AND status_code IS NULL"
)
_RELEASE = text(
    "UPDATE idempotency_keys SET expires_at = clock_timestamp() "
    "WHERE actor_id = :actor AND route = :route AND key = :key AND request_sha256 = :sha "
    "AND status_code IS NULL"
)


class IdempotencyKeyReused(DomainInvalid):
    """This key already answered a different request."""

    code = "idempotency_key_reused"


class IdempotencyKeyInvalid(DomainInvalid):
    code = "idempotency_key_invalid"


class IdempotencyInProgress(DomainConflict):
    """A request with this key and body is still running: retry shortly for its answer."""

    code = "idempotency_in_progress"


@dataclass(frozen=True)
class Stored:
    status_code: int
    body: dict[str, object]
    replayed: bool


def request_hash(body: object) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _write(ctx: TenantContext, statement: TextClause, params: Mapping[str, object]) -> int:
    """One short statement in its own committed transaction; the rows it touched."""
    async with tenant_connection(ctx) as conn:
        result = await conn.execute(statement, dict(params))
        await conn.commit()
    return result.rowcount


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
    where = {"actor": ctx.actor_id, "route": route, "key": key, "sha": sha}
    claimed = await _write(
        ctx, _CLAIM, {"tenant": ctx.tenant_id, "reclaim": PENDING_RECLAIM_S, **where}
    )
    if claimed != 1:
        found = await _find(ctx, route, key)
        if found is None:  # expired between the claim and the read: refuse, the retry claims
            raise IdempotencyInProgress
        return _replay(found, sha)
    try:
        status, response = await run()
    except BaseException:
        await _write(ctx, _RELEASE, where)
        raise
    await _write(
        ctx, _FILL, {**where, "status": status, "response": json.dumps(response, default=str)}
    )
    return Stored(status, response, replayed=False)


async def _find(ctx: TenantContext, route: str, key: str) -> tuple[str, int | None, object] | None:
    async with tenant_session(ctx) as session:
        row = (
            await session.execute(_FIND, {"actor": ctx.actor_id, "route": route, "key": key})
        ).one_or_none()
    return None if row is None else (row.request_sha256, row.status_code, row.response)


def _replay(found: tuple[str, int | None, object], sha: str) -> Stored:
    stored_sha, status, response = found
    if stored_sha != sha:
        raise IdempotencyKeyReused
    if status is None:
        raise IdempotencyInProgress
    raw = response if isinstance(response, str) else json.dumps(response)
    return Stored(status, cast(dict[str, object], json.loads(raw)), replayed=True)
