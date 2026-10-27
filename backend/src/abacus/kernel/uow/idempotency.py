"""`Idempotency-Key` (P-36; P-06-T06; migrations 0099 and 0214).

A request that changes something outside the firm (a publish, a send, a bulk sign-off) may carry
an `Idempotency-Key`. Per (tenant, actor, route, key), for 24 hours:
- the first request claims the key (a pending row holding a hash of its request) in its own
  short committed statement, before its effect runs, then fills the row with its response;
- a retry with the same key and request gets the stored response, and the effect doesn't run
  again; while the first is still running it is told so (409 `idempotency_in_progress`);
- the same key with a different request is refused (422 `idempotency_key_reused`).

Each claim carries its own `claim_id`: only that claim fills or releases its row (re-review M1),
so a run whose claim was taken over can't answer for, or release, the one that took it. A run
that fails before any unit of work reached its commit releases its claim (shielded from
cancellation); a failure after an effect committed leaves the claim pending, so a retry is told
409 rather than running the effect again (re-review M2). A claim left pending by a crash is taken
over, by the same request only, after `PENDING_RECLAIM_S`; an expired row by the next request
(DEC-507). No connection is held while the effect runs (security re-review M1). The database
allows only those changes to a row (0214's trigger).

The stored response must not hold Restricted data: store identifiers, as routes return.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Final, cast
from uuid import uuid4

from sqlalchemy import TextClause, text

from abacus.kernel.db import TenantContext, tenant_connection, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import watching_commits

HEADER: Final = "Idempotency-Key"
# Far above the slowest keyed effect (a 50-item bulk sign-off, an export request): seconds.
PENDING_RECLAIM_S: Final = 3600
_KEY: Final = re.compile(r"[A-Za-z0-9_.:-]{8,200}")
_FIND = text(
    "SELECT request_sha256, status_code, response FROM idempotency_keys WHERE actor_id = :actor "
    "AND route = :route AND key = :key AND expires_at > clock_timestamp()"
)
# Insert the claim, or take over an expired row, or a stale pending one of the same request; a
# live row, or a stale one of another request, is left alone (no row returned).
_CLAIM = text(
    "INSERT INTO idempotency_keys (tenant_id, actor_id, route, key, request_sha256, claim_id) "
    "VALUES (:tenant, :actor, :route, :key, :sha, :claim) "
    "ON CONFLICT (tenant_id, actor_id, route, key) DO UPDATE SET "
    "request_sha256 = EXCLUDED.request_sha256, claim_id = EXCLUDED.claim_id, "
    "status_code = NULL, response = NULL, "
    "created_at = clock_timestamp(), expires_at = clock_timestamp() + interval '24 hours' "
    "WHERE idempotency_keys.expires_at <= clock_timestamp() "
    "OR (idempotency_keys.status_code IS NULL "
    "AND idempotency_keys.request_sha256 = EXCLUDED.request_sha256 "
    "AND idempotency_keys.created_at < clock_timestamp() - make_interval(secs => :reclaim)) "
    "RETURNING claim_id"
)
_FILL = text(
    "UPDATE idempotency_keys SET status_code = :status, response = CAST(:response AS jsonb) "
    "WHERE actor_id = :actor AND route = :route AND key = :key AND claim_id = :claim "
    "AND status_code IS NULL"
)
_RELEASE = text(
    "UPDATE idempotency_keys SET expires_at = clock_timestamp() "
    "WHERE actor_id = :actor AND route = :route AND key = :key AND claim_id = :claim "
    "AND status_code IS NULL"
)
_log = get_logger(__name__)
_releases: set[asyncio.Task[int]] = set()  # held until done, so a shielded release isn't lost


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
    mine = {"actor": ctx.actor_id, "route": route, "key": key, "claim": uuid4()}
    claimed = await _write(
        ctx,
        _CLAIM,
        {"tenant": ctx.tenant_id, "sha": sha, "reclaim": PENDING_RECLAIM_S, **mine},
    )
    if claimed != 1:
        found = await _find(ctx, route, key)
        if found is None:  # expired between the claim and the read: refuse, the retry claims
            raise IdempotencyInProgress
        return _replay(found, sha)
    with watching_commits() as commits:
        try:
            status, response = await run()
        except BaseException:
            if not commits:  # nothing committed: the effect never happened, free the key
                await _release(ctx, mine)
            else:
                _log.warning("idempotency.failed_after_commit", route=route)
            raise
    filled = await _write(
        ctx, _FILL, {**mine, "status": status, "response": json.dumps(response, default=str)}
    )
    if filled != 1:
        # Our claim was taken over (it outlived PENDING_RECLAIM_S): the effect ran, its answer
        # stands for this caller, and the row belongs to the run that took it.
        _log.error("idempotency.claim_lost", route=route)
    return Stored(status, response, replayed=False)


async def _release(ctx: TenantContext, mine: Mapping[str, object]) -> None:
    """Release the claim even if the request is being cancelled: the release runs as its own
    task, shielded, and is kept referenced until it is done."""
    task = asyncio.ensure_future(_write(ctx, _RELEASE, mine))
    _releases.add(task)
    task.add_done_callback(_releases.discard)
    await asyncio.shield(task)


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
