"""The audit label index (G-02-T10; SPEC-349 AC-6, AC-11; G-02 §4.2, §4.5; DEC-436).

`audit_event_labels` is a rebuildable projection of `audit_events`, one row per event: the
actor's label (the person's display name, or the person an agent acted for), the target's label
(its owner's labeler), and a `keywords` tsvector over those labels, the labels of the people the
event's references name, and the action's words. It is what `q` searches, and all it searches:
never a value, for every reader (security review M4).

**No Restricted text by construction:** labels come only through `platform.audit_labels`, which
refuses any label classified above `confidential`, and people's display names (Confidential).
Nothing from `before_ref`/`after_ref` but identifiers is ever read, and identifiers are not
indexed as text, so a seeded SSN is never findable (AC-11).

**Maintenance:** `index_batch` indexes a firm's events after the newest indexed `seq`, upserting
on `(tenant_id, seq)`, so a replay rewrites the same rows (idempotent); `backfill` runs batches
until it has caught up. The Temporal Schedule G-02 §4.5 names (`AuditLabelIndexer`) is not wired
yet (DEC-436): until it is, a search first catches its firm's index up by one bounded batch.

The projection is operational, like the hash chain's checkpoints: its writes carry no audit event
(auditing the index of the audit trail would feed itself) and commit on their own connection
(UOW-001's exclusion names this file). It is never the record: `audit_events` is.

**Late commits (M2):** `seq` commits out of order, so each catch-up batch also re-reads the
settle window's events that have no label yet. **One indexer per firm (L4):** a batch takes the
firm's transaction advisory lock or writes nothing.

**Search (L3):** `matching` is a predicate the explorer adds to its own query, so visibility,
the page's keyset limit and the capped total apply to matches together; nothing is capped before
visibility.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Column,
    ColumnElement,
    DateTime,
    MetaData,
    Table,
    Text,
    and_,
    exists,
    false,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import REGCONFIG, TSVECTOR, insert
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from abacus.kernel.db import TenantContext, tenant_connection
from abacus.kernel.uow.explorer import AUDIT_EVENTS
from abacus.modules.identity.api import names_of
from abacus.modules.platform.api import audit_labels

BATCH: Final = 2_000  # G-02 §4.9 `audit_label_index_batch`
SETTLE_SECONDS: Final = 120  # as `kernel.uow.chain.SETTLE_SECONDS`: late commits re-scanned
MAX_Q: Final = 200
_CONFIG: Final = "simple"
_INDEXER: Final = "system:audit_label_index"
_PERSON_REF: Final = re.compile(r"(?:^|_)user_id$")
_WORDS: Final = re.compile(r"[^\w]+", re.UNICODE)

_metadata = MetaData()
AUDIT_EVENT_LABELS: Final = Table(
    "audit_event_labels",
    _metadata,
    Column("tenant_id", PgUUID(as_uuid=True), primary_key=True),
    Column("seq", BigInteger, primary_key=True),
    Column("effective_at", DateTime(timezone=True)),
    Column("actor_label", Text),
    Column("target_label", Text),
    Column("keywords", TSVECTOR),
    Column("client_id", PgUUID(as_uuid=True)),
    Column("office_id", PgUUID(as_uuid=True)),
    Column("engagement_id", PgUUID(as_uuid=True)),
    Column("indexed_at", DateTime(timezone=True)),
)
L = AUDIT_EVENT_LABELS.c
E = AUDIT_EVENTS.c


def _config() -> ColumnElement[str]:
    return sql_cast(literal(_CONFIG, Text()), REGCONFIG)


def _indexer(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", _INDEXER)


def _uuid(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _refs(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _clip(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = text.strip()[:limit]
    return text or None


def keywords_text(
    action: str, actor: str | None, target: str | None, others: Sequence[str]
) -> str:
    """What `keywords` is built from: labels and the action's words, nothing else."""
    words = action.replace(".", " ").replace("_", " ")
    return " ".join(part for part in (actor, target, *others, words) if part)


Row = Mapping[str, Any]  # Any: an untyped database row


async def _label_rows(tenant_id: UUID, rows: Sequence[Row]) -> list[dict[str, object]]:
    people: set[UUID] = set()
    for row in rows:
        if row["actor_kind"] in ("human", "support") and (u := _uuid(row["actor_id"])):
            people.add(u)
        if row["on_behalf_of_user_id"] is not None:
            people.add(cast(UUID, row["on_behalf_of_user_id"]))
        for key, value in {**_refs(row["before_ref"]), **_refs(row["after_ref"])}.items():
            if _PERSON_REF.search(key) and (u := _uuid(value)):
                people.add(u)
    names = await names_of(sorted(people, key=str)) if people else {}
    by_type: dict[str, set[str]] = {}
    for row in rows:
        by_type.setdefault(str(row["target_type"]), set()).add(str(row["target_id"]))
    targets: dict[tuple[str, str], str] = {}
    for kind, ids in by_type.items():
        for target, label in (await audit_labels(None, kind, sorted(ids))).items():
            targets[(kind, target)] = label.text
    out: list[dict[str, object]] = []
    for row in rows:
        actor_user = (
            cast(UUID | None, row["on_behalf_of_user_id"])
            if row["actor_kind"] == "agent"
            else _uuid(row["actor_id"])
            if row["actor_kind"] in ("human", "support")
            else None
        )
        actor = _clip(names.get(actor_user) if actor_user else None, 200)
        target = _clip(targets.get((str(row["target_type"]), str(row["target_id"]))), 300)
        others = [
            names[u]
            for key, value in {**_refs(row["before_ref"]), **_refs(row["after_ref"])}.items()
            if _PERSON_REF.search(key) and (u := _uuid(value)) is not None and u in names
        ]
        out.append(
            {
                "tenant_id": tenant_id,
                "seq": row["seq"],
                "effective_at": row["effective_at"],
                "actor_label": actor,
                "target_label": target,
                "text": keywords_text(str(row["action"]), actor, target, others),
                "client_id": row["client_id"],
                "office_id": row["office_id"],
                "engagement_id": row["engagement_id"],
            }
        )
    return out


class IndexBusy(RuntimeError):
    """Another indexer holds the firm's label-index lock (L4)."""

    def __init__(self, tenant_id: UUID) -> None:
        super().__init__(f"the audit label index of {tenant_id} is being written")


def _lock_key(tenant_id: UUID) -> ColumnElement[int]:
    return func.hashtextextended(literal(f"audit_label_index:{tenant_id}", Text()), 0)


def _pending(after: int | None, start: int) -> ColumnElement[bool]:
    """The events a batch indexes. From the newest indexed `seq` on, and (M2) any event of the
    settle window that has no label yet: `seq` is assigned at insert but commits in any order,
    so a lower `seq` can commit after a higher one was indexed (`chain.py` settles the same
    way). An explicit `after` (the back-fill) reads the range as given."""
    newer = E.seq > start
    if after is not None:
        return newer
    unlabelled = ~exists(select(literal(1)).where(L.tenant_id == E.tenant_id, L.seq == E.seq))
    recent = E.occurred_at > func.clock_timestamp() - func.make_interval(
        0, 0, 0, 0, 0, 0, SETTLE_SECONDS
    )
    return or_(newer, and_(recent, unlabelled))


async def index_batch(
    tenant_id: UUID, limit: int = BATCH, *, after: int | None = None
) -> tuple[int, int | None]:
    """Index up to `limit` of the firm's events (`_pending`); upserts, so a replay of the same
    range writes the same rows. One indexer per firm at a time (L4): a run that finds the firm's
    advisory lock held writes nothing and raises `IndexBusy`. Answers how many it wrote and the
    last `seq` it indexed."""
    async with tenant_connection(_indexer(tenant_id)) as conn:
        locked = (
            await conn.execute(select(func.pg_try_advisory_xact_lock(_lock_key(tenant_id))))
        ).scalar_one()
        if not locked:
            raise IndexBusy(tenant_id)
        start = (
            after
            if after is not None
            else int((await conn.execute(select(func.coalesce(func.max(L.seq), 0)))).scalar_one())
        )
        events = [
            dict(m)
            for m in (
                await conn.execute(
                    select(
                        E.seq,
                        E.effective_at,
                        E.actor_kind,
                        E.actor_id,
                        E.on_behalf_of_user_id,
                        E.action,
                        E.target_type,
                        E.target_id,
                        E.before_ref,
                        E.after_ref,
                        E.client_id,
                        E.office_id,
                        E.engagement_id,
                    )
                    .where(_pending(after, start))
                    .order_by(E.seq)
                    .limit(limit)
                )
            )
            .mappings()
            .all()
        ]
        if not events:
            return 0, None
        rows = await _label_rows(tenant_id, events)
        stmt = insert(AUDIT_EVENT_LABELS).values(
            [
                {
                    "tenant_id": row["tenant_id"],
                    "seq": row["seq"],
                    "effective_at": row["effective_at"],
                    "actor_label": row["actor_label"],
                    "target_label": row["target_label"],
                    "keywords": func.to_tsvector(_config(), literal(str(row["text"]), Text())),
                    "client_id": row["client_id"],
                    "office_id": row["office_id"],
                    "engagement_id": row["engagement_id"],
                }
                for row in rows
            ]
        )
        await conn.execute(
            stmt.on_conflict_do_update(
                index_elements=[L.tenant_id, L.seq],
                set_={
                    "effective_at": stmt.excluded.effective_at,
                    "actor_label": stmt.excluded.actor_label,
                    "target_label": stmt.excluded.target_label,
                    "keywords": stmt.excluded.keywords,
                    "client_id": stmt.excluded.client_id,
                    "office_id": stmt.excluded.office_id,
                    "engagement_id": stmt.excluded.engagement_id,
                    "indexed_at": func.now(),
                },
            )
        )
        await conn.commit()
    return len(rows), max(int(e["seq"]) for e in events)


async def backfill(
    tenant_id: UUID, *, batch: int = BATCH, retries: int = 20, pause: float = 0.25
) -> int:
    """Index the firm's whole history from the start (rewriting what is there). A batch that
    finds another indexer running waits and retries; after `retries` it raises `IndexBusy`
    rather than stop early and claim it is done (re-review 2)."""
    total, after = 0, 0
    while True:
        for attempt in range(retries + 1):
            try:
                written, last = await index_batch(tenant_id, batch, after=after)
                break
            except IndexBusy:
                if attempt == retries:
                    raise
                await asyncio.sleep(pause)
        else:  # pragma: no cover -- the loop breaks or raises
            raise IndexBusy(tenant_id)
        total += written
        if last is None or written < batch:
            return total
        after = last


def _query(q: str) -> str:
    """The search as words: labels are matched word by word, every word required."""
    return " ".join(w for w in _WORDS.split(q[:MAX_Q].lower()) if w)


async def catch_up(tenant_id: UUID) -> None:
    """One bounded batch before a search, while the Schedule is not wired (DEC-436). Another
    indexer running for the firm is catching it up already: the search does not wait."""
    with contextlib.suppress(IndexBusy):
        await index_batch(tenant_id)


def matching(seq: ColumnElement[int], q: str) -> ColumnElement[bool]:
    """Events whose labels match every word of `q`, as a predicate on the caller's query, so
    the caller's visibility and limit apply with it (L3). Labels only: never a value (M4)."""
    words = _query(q)
    if not words:
        return false()
    return seq.in_(
        select(L.seq).where(
            L.keywords.op("@@")(func.plainto_tsquery(_config(), literal(words, Text())))
        )
    )


__all__ = [
    "AUDIT_EVENT_LABELS",
    "BATCH",
    "SETTLE_SECONDS",
    "IndexBusy",
    "backfill",
    "catch_up",
    "index_batch",
    "keywords_text",
    "matching",
]
