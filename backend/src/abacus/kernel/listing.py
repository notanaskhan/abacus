"""The list envelope and its keyset cursors (ADR-139, P-36; F-03-T29; plan 03 §5.2).

Every index returns `{items, next_cursor, total, total_capped, counts, facets}`:

- **Cursors** are opaque AES-GCM tokens over the last row's `(sort key, id)`. A cursor is bound to
  its tenant, its resource and the query it came from (the associated data), so it cannot be
  replayed against another firm, another list or other filters, and a sort key such as a client
  name never sits readable in a URL or a log. Sealing is `kernel.crypto.cursor`'s.
- **Pages** are keyset pages on `(sort key, id)`: ties break on `id`, and a page asks for one more
  row than it returns to know whether there is a next one.
- **Counts** are per status code over the filters minus the tile, so a tile never counts itself out
  (`status_counts` takes the query built without the tile).
- **Totals** are exact up to 10,000 rows, then capped (`total_capped`).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Final
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, Select, Text, func, literal, select, tuple_
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.classification import classified
from abacus.kernel.crypto.cursor import CursorUnreadable, open_cursor, seal_cursor
from abacus.kernel.errors import DomainInvalid

DEFAULT_LIMIT: Final = 50
MAX_LIMIT: Final = 200
TOTAL_CAP: Final = 10_000


class CursorInvalid(DomainInvalid):
    """The cursor is not one this list issued for this firm and these filters: start again."""

    code = "cursor_invalid"


class Facet(BaseModel):
    value: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    n: Annotated[int, classified("internal")]


class ListPage[T](BaseModel):
    """The one list envelope (P-36)."""

    # The rows' own fields carry their classifications; the list adds nothing to them.
    items: Annotated[list[T], classified("internal")]
    next_cursor: Annotated[str | None, classified("internal")] = None
    total: Annotated[int, classified("internal")]
    total_capped: Annotated[bool, classified("internal")] = False
    counts: Annotated[dict[str, int], classified("internal")] = Field(default_factory=dict)
    facets: Annotated[dict[str, list[Facet]], classified("internal")] = Field(default_factory=dict)


def clamp_limit(limit: int | None) -> int:
    """The page size a request may ask for: 50 by default, at most 200, at least 1."""
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, limit))


# --- cursors -----------------------------------------------------------------------------------


SortKey = str | int | float | bool | None


@dataclass(frozen=True)
class Position:
    """Where the last page ended: its last row's sort key and id."""

    key: SortKey
    id: str


def query_hash(**query: object) -> str:
    """A short, stable digest of the filters, sort and search a list was asked with."""
    canonical = json.dumps(query, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


def _aad(tenant_id: UUID, resource: str, query: str) -> bytes:
    return f"{tenant_id}|{resource}|{query}".encode()


def _scalar(key: object) -> SortKey:
    if key is None or isinstance(key, str | int | float | bool):
        return key
    if isinstance(key, datetime | date):
        return key.isoformat()
    if isinstance(key, Decimal | UUID):
        return str(key)
    raise TypeError(f"a sort key must be a scalar, not {type(key).__name__}")


def encode_cursor(position: Position, *, tenant_id: UUID, resource: str, query: str) -> str:
    body = json.dumps({"k": _scalar(position.key), "i": position.id}, separators=(",", ":"))
    return seal_cursor(body.encode(), _aad(tenant_id, resource, query))


def decode_cursor(token: str, *, tenant_id: UUID, resource: str, query: str) -> Position:
    """The position a cursor names; `CursorInvalid` for anything this list did not issue."""
    try:
        data = json.loads(open_cursor(token, _aad(tenant_id, resource, query)))
        return Position(key=data["k"], id=str(data["i"]))
    except (CursorUnreadable, ValueError, KeyError, TypeError) as exc:
        raise CursorInvalid from exc


# --- pages, counts and totals ------------------------------------------------------------------


def _typed(value: SortKey, column: ColumnElement[object]) -> ColumnElement[object]:
    """A cursor scalar as the column's type: text is bound as text and cast in SQL."""
    if isinstance(value, str):
        return sql_cast(literal(value, type_=Text()), column.type)
    return literal(value, type_=column.type)


def keyset[*Ts](
    stmt: Select[*Ts],
    *,
    sort: ColumnElement[object],
    id_column: ColumnElement[object],
    after: Position | None,
    descending: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> Select[*Ts]:
    """`stmt` ordered by `(sort, id)` from just after `after`, one row more than `limit`."""
    if after is not None:
        pair = tuple_(sort, id_column)
        # A cursor holds the key and id as JSON scalars (a timestamp as ISO text, a UUID as
        # text); cast them back to the columns' types so the comparison is typed.
        mark = tuple_(_typed(after.key, sort), _typed(after.id, id_column))
        stmt = stmt.where(pair < mark if descending else pair > mark)
    order = (sort.desc(), id_column.desc()) if descending else (sort.asc(), id_column.asc())
    return stmt.order_by(*order).limit(limit + 1)


def page_of[T](
    rows: Sequence[T],
    *,
    limit: int,
    key: Callable[[T], object],
    id_of: Callable[[T], object],
) -> tuple[list[T], Position | None]:
    """Split a keyset fetch (`limit + 1` rows) into the page and where the next one starts."""
    page = list(rows[:limit])
    if len(rows) <= limit or not page:
        return page, None
    last = page[-1]
    return page, Position(key=_scalar(key(last)), id=str(id_of(last)))


async def status_counts(
    session: AsyncSession,
    without_tile: Select[Any],  # Any: any row shape; only its status column is read
    status: ColumnElement[str],
) -> dict[str, int]:
    """Rows per status over `without_tile`: the list's filters with the tile left out, so a tile's
    own count never drops to the rows the tile already shows."""
    sub = without_tile.with_only_columns(status.label("status")).order_by(None).subquery()
    rows = await session.execute(select(sub.c.status, func.count()).group_by(sub.c.status))
    return {str(code): int(n) for code, n in rows.all()}


async def capped_total(
    session: AsyncSession,
    stmt: Select[Any],  # Any: any row shape; only its rows are counted
    cap: int = TOTAL_CAP,
) -> tuple[int, bool]:
    """The row count, exact up to `cap`; beyond it, `cap` and capped."""
    sub = stmt.order_by(None).limit(cap + 1).subquery()
    n = int((await session.execute(select(func.count()).select_from(sub))).scalar_one())
    return (cap, True) if n > cap else (n, False)


def envelope[T](
    items: list[T],
    *,
    next_position: Position | None,
    tenant_id: UUID,
    resource: str,
    query: str,
    total: tuple[int, bool],
    counts: Mapping[str, int] | None = None,
    facets: Mapping[str, list[Facet]] | None = None,
) -> ListPage[T]:
    """The envelope a route returns."""
    cursor = (
        None
        if next_position is None
        else encode_cursor(next_position, tenant_id=tenant_id, resource=resource, query=query)
    )
    return ListPage[T](
        items=items,
        next_cursor=cursor,
        total=total[0],
        total_capped=total[1],
        counts=dict(counts or {}),
        facets={k: list(v) for k, v in (facets or {}).items()},
    )
