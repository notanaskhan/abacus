"""The audit hash chain (Q-02-T21; AC-26; P-43). PROTECTED.

Each firm's audit events are sealed in checkpoints:
- `leaf` hashes one event's canonical form. Leaf version 1 covers every `audit_events` column
  of Q-02, `occurred_at` and `effective_at` included, as sorted-key JSON. Timestamps are ISO 8601
  in UTC with microseconds. Leaf version 2 (G-02-T06, migration 0172) adds the request context
  and the explorer's dimensions (`ip` as `inet` text, with its mask); new checkpoints seal at
  version 2, and a version 1 checkpoint keeps verifying with version 1's columns.
- `merkle_root` folds a checkpoint's leaves pairwise, carrying an odd last leaf up a level.
- `chain_hash` is SHA-256(previous chain hash ‖ root ‖ seq_from ‖ seq_to ‖ count). The first
  checkpoint chains from 32 zero bytes.

`seal_checkpoint` closes a firm's new events up to the settle horizon. Events younger than the
settle window are left for the next run, so a transaction still committing a lower `seq` isn't
skipped. `verify_chain` recomputes every checkpoint from its rows and names any that no longer
match (a changed, removed or added event, or a broken link). `verify_anchor` checks a published
(checkpoint, chain hash) pair against the recomputed chain.

Checkpoints are an operational ledger the chain itself proves, written without an audit event,
as `kernel/slots.py` is. A test fails if `audit_events` gains a column that the current leaf
version doesn't list: the canonical form must then move to the next version (Q-02 R7).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Result, text
from sqlalchemy.ext.asyncio import AsyncConnection

from abacus.kernel.db import TenantContext, tenant_connection
from abacus.kernel.metrics import meter

LEAF_VERSION: Final = 2
LEAF_V1_COLUMNS: Final = (
    "id",
    "tenant_id",
    "seq",
    "occurred_at",
    "effective_at",
    "actor_kind",
    "actor_id",
    "action",
    "target_type",
    "target_id",
    "before_ref",
    "after_ref",
    "trace_id",
    "engagement_id",
    "work_item_id",
    "on_behalf_of_user_id",
    "policy_ref",
)
LEAF_V2_COLUMNS: Final = (
    *LEAF_V1_COLUMNS,
    "ip",
    "user_agent_family",
    "device_label",
    "session_id",
    "auth_method",
    "mfa_at",
    "client_id",
    "office_id",
)
LEAF_COLUMNS: Final[dict[int, tuple[str, ...]]] = {1: LEAF_V1_COLUMNS, 2: LEAF_V2_COLUMNS}
SETTLE_SECONDS: Final = 120
MAX_EVENTS: Final = 50_000  # per checkpoint; a backlog seals over several runs
_GENESIS: Final = bytes(32)
_mismatches = meter(__name__).create_counter(
    "abacus.audit_chain.mismatch", description="Audit checkpoints that no longer verify (SEV1)"
)


def _canonical(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(value, UUID | IPv4Address | IPv6Address):
        return str(value)
    if isinstance(value, str) and value.startswith(("{", "[")):
        try:
            return json.loads(value)  # jsonb read as text: hash its value, not its spelling
        except ValueError:
            return value
    return value


def leaf(row: Mapping[str, object], version: int = 1) -> bytes:
    """The event's leaf at `version` (1 unless a checkpoint says otherwise)."""
    body = {column: _canonical(row.get(column)) for column in LEAF_COLUMNS[version]}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).digest()


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    if not leaves:
        raise ValueError("a checkpoint seals at least one event")
    level: list[bytes] = list(leaves)
    while len(level) > 1:
        folded: list[bytes] = []
        for i in range(0, len(level), 2):
            pair = level[i : i + 2]
            folded.append(
                hashlib.sha256(pair[0] + pair[1]).digest() if len(pair) == 2 else pair[0]
            )
        level = folded
    return level[0]


def chain_hash(
    previous: bytes | None, root: bytes, seq_from: int, seq_to: int, count: int
) -> bytes:
    material = (previous or _GENESIS) + root
    material += seq_from.to_bytes(8, "big") + seq_to.to_bytes(8, "big") + count.to_bytes(8, "big")
    return hashlib.sha256(material).digest()


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_no: int
    seq_from: int
    seq_to: int
    event_count: int
    leaf_version: int
    merkle_root: bytes
    prev_chain_hash: bytes | None
    chain_hash: bytes


_LATEST = text(
    "SELECT checkpoint_no, seq_from, seq_to, event_count, leaf_version, merkle_root, "
    "prev_chain_hash, chain_hash FROM audit_checkpoints ORDER BY checkpoint_no DESC LIMIT 1"
)
_ALL = text(
    "SELECT checkpoint_no, seq_from, seq_to, event_count, leaf_version, merkle_root, "
    "prev_chain_hash, chain_hash FROM audit_checkpoints ORDER BY checkpoint_no"
)
_NEW_EVENTS = text(
    "SELECT id, tenant_id, seq, occurred_at, effective_at, actor_kind, actor_id, action, "
    "target_type, target_id, before_ref, after_ref, trace_id, engagement_id, work_item_id, "
    "on_behalf_of_user_id, policy_ref, CAST(ip AS text) AS ip, user_agent_family, device_label, "
    "session_id, auth_method, mfa_at, client_id, office_id FROM audit_events "
    "WHERE seq > :after AND occurred_at <= clock_timestamp() - make_interval(secs => :settle) "
    "ORDER BY seq LIMIT :limit"
)
_RANGE = text(
    "SELECT id, tenant_id, seq, occurred_at, effective_at, actor_kind, actor_id, action, "
    "target_type, target_id, before_ref, after_ref, trace_id, engagement_id, work_item_id, "
    "on_behalf_of_user_id, policy_ref, CAST(ip AS text) AS ip, user_agent_family, device_label, "
    "session_id, auth_method, mfa_at, client_id, office_id FROM audit_events "
    "WHERE seq BETWEEN :lo AND :hi ORDER BY seq"
)
_SEAL = text(
    "INSERT INTO audit_checkpoints (tenant_id, checkpoint_no, seq_from, seq_to, event_count, "
    "leaf_version, merkle_root, prev_chain_hash, chain_hash) VALUES (:tenant, :no, :lo, :hi, "
    ":count, :version, :root, :prev, :chain)"
)


def _rows(result: Result[Any]) -> list[dict[str, object]]:  # Any: the rows are untyped text SQL
    return [{str(k): v for k, v in m.items()} for m in result.mappings()]


def _bytes(value: object) -> bytes:
    return bytes(cast(bytes, value))


def _checkpoint(row: Mapping[str, object] | None) -> Checkpoint | None:
    if row is None:
        return None
    return Checkpoint(
        int(str(row["checkpoint_no"])),
        int(str(row["seq_from"])),
        int(str(row["seq_to"])),
        int(str(row["event_count"])),
        int(str(row["leaf_version"])),
        _bytes(row["merkle_root"]),
        _bytes(row["prev_chain_hash"]) if row["prev_chain_hash"] is not None else None,
        _bytes(row["chain_hash"]),
    )


def _system(tenant_id: UUID, what: str) -> TenantContext:
    return TenantContext(tenant_id, "system", f"audit_chain:{what}")


async def _latest(conn: AsyncConnection) -> Checkpoint | None:
    found = _rows(await conn.execute(_LATEST))
    return _checkpoint(found[0] if found else None)


async def latest_checkpoint(tenant_id: UUID) -> Checkpoint | None:
    async with tenant_connection(_system(tenant_id, "read")) as conn:
        return await _latest(conn)


async def seal_checkpoint(
    tenant_id: UUID, *, settle_seconds: int = SETTLE_SECONDS
) -> Checkpoint | None:
    """Seal the firm's settled, unsealed events into the next checkpoint; None if none."""
    async with tenant_connection(_system(tenant_id, "seal")) as conn:
        last = await _latest(conn)
        after = last.seq_to if last is not None else 0
        rows = _rows(
            await conn.execute(
                _NEW_EVENTS, {"after": after, "settle": settle_seconds, "limit": MAX_EVENTS}
            )
        )
        if not rows:
            return None
        root = merkle_root([leaf(r, LEAF_VERSION) for r in rows])
        lo, hi = int(str(rows[0]["seq"])), int(str(rows[-1]["seq"]))
        previous = last.chain_hash if last is not None else None
        sealed = Checkpoint(
            (last.checkpoint_no if last is not None else 0) + 1,
            lo,
            hi,
            len(rows),
            LEAF_VERSION,
            root,
            previous,
            chain_hash(previous, root, lo, hi, len(rows)),
        )
        await conn.execute(
            _SEAL,
            {
                "tenant": tenant_id,
                "no": sealed.checkpoint_no,
                "lo": sealed.seq_from,
                "hi": sealed.seq_to,
                "count": sealed.event_count,
                "version": sealed.leaf_version,
                "root": sealed.merkle_root,
                "prev": sealed.prev_chain_hash,
                "chain": sealed.chain_hash,
            },
        )
        await conn.commit()
    return sealed


async def verify_chain(tenant_id: UUID) -> list[int]:
    """The numbers of the firm's checkpoints that no longer verify; [] when the chain holds."""
    bad: list[int] = []
    async with tenant_connection(_system(tenant_id, "verify")) as conn:
        checkpoints = [c for c in map(_checkpoint, _rows(await conn.execute(_ALL))) if c]
        previous: Checkpoint | None = None
        for c in checkpoints:
            rows = _rows(await conn.execute(_RANGE, {"lo": c.seq_from, "hi": c.seq_to}))
            expected_prev = previous.chain_hash if previous is not None else None
            ok = (
                c.leaf_version in LEAF_COLUMNS
                and len(rows) == c.event_count
                and c.prev_chain_hash == expected_prev
                and (previous is None or c.seq_from > previous.seq_to)
            )
            if ok:
                root = merkle_root([leaf(r, c.leaf_version) for r in rows])
                ok = root == c.merkle_root and c.chain_hash == chain_hash(
                    expected_prev, root, c.seq_from, c.seq_to, c.event_count
                )
            if not ok:
                bad.append(c.checkpoint_no)
            previous = c
    if bad:
        _mismatches.add(len(bad), {"tenant.id": str(tenant_id)})
    return bad


async def verify_anchor(tenant_id: UUID, checkpoint_no: int, anchored: bytes) -> bool:
    """Whether a published anchor still holds (Q-02-T27; C-09): the firm's chain recomputes
    cleanly through `checkpoint_no`, and that checkpoint's chain hash is the one published. A
    checkpoint the database no longer has fails, as does any change below it."""
    async with tenant_connection(_system(tenant_id, "anchor")) as conn:
        rows = _rows(await conn.execute(_ALL))
    found = next(
        (c for c in map(_checkpoint, rows) if c and c.checkpoint_no == checkpoint_no), None
    )
    if found is None or found.chain_hash != anchored:
        return False
    return not [n for n in await verify_chain(tenant_id) if n <= checkpoint_no]


__all__ = [
    "LEAF_COLUMNS",
    "LEAF_V1_COLUMNS",
    "LEAF_V2_COLUMNS",
    "LEAF_VERSION",
    "SETTLE_SECONDS",
    "Checkpoint",
    "chain_hash",
    "latest_checkpoint",
    "leaf",
    "merkle_root",
    "seal_checkpoint",
    "verify_anchor",
    "verify_chain",
]
