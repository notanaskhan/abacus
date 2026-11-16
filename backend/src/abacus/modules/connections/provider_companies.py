"""A firm app's client companies (W-01-T15 rest; SPEC-659 AC-17 to AC-19; WB-11 d; DEC-5335).

The live and needing-reauth connections a provider holds for the firm's client entities, newest
connection first, 50 a page (cursor `<connected_at>|<id>`), each named by its client entity and
who connected it ("Tess Moreno (client)"). A client the viewer is walled off from is left out and
never counted (ADR-026). Read only; the caller authorised `integration.read_client_companies`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.modules.identity.api import AuthContext, hidden_clients, names_of

PAGE: Final = 50
_LIVE: Final = text(
    "SELECT id, client_entity_id, connected_by_user_id, connected_at, last_sync_at, status "
    "FROM connections WHERE provider = :p AND revoked_at IS NULL "
    "AND status IN ('connected', 'needs_reauth', 'needs_attention') "
    "AND (CAST(:at AS timestamptz) IS NULL OR (connected_at, id) < "
    "(CAST(:at AS timestamptz), CAST(:id AS uuid))) "
    "ORDER BY connected_at DESC NULLS LAST, id DESC LIMIT :n"
)


@dataclass(frozen=True)
class ClientCompany:
    id: UUID
    client_name: str
    connected_by_label: str
    connected_on: datetime | None
    last_sync_at: datetime | None
    ok: bool


def _cursor(value: str | None) -> tuple[datetime | None, UUID | None]:
    if not value or "|" not in value:
        return None, None
    at, _, ident = value.partition("|")
    try:
        return datetime.fromisoformat(at), UUID(ident)
    except ValueError:
        return None, None


async def client_companies(
    ctx: AuthContext, provider: str, q: str | None = None, cursor: str | None = None
) -> tuple[list[ClientCompany], str | None]:
    from abacus.modules.organisations.api import client_names

    at, ident = _cursor(cursor)
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(_LIVE, {"p": provider, "at": at, "id": ident, "n": PAGE + 1})
        ).all()
        names = await client_names(session, list({r[1] for r in rows}))
    hidden = await hidden_clients(ctx.tenant, ctx.user_id, [n.client_id for n in names.values()])
    people = await names_of(sorted({r[2] for r in rows if r[2] is not None}, key=str))
    out: list[ClientCompany] = []
    needle = (q or "").strip().casefold()
    for row in rows[:PAGE]:
        named = names.get(row[1])
        if named is None or named.client_id in hidden:
            continue
        if needle and needle not in named.client_entity_name.casefold():
            continue
        by = people.get(row[2]) if row[2] is not None else None
        out.append(
            ClientCompany(
                id=row[0],
                client_name=named.client_entity_name,
                connected_by_label=f"{by} (client)" if by else "",
                connected_on=row[3],
                last_sync_at=row[4],
                ok=row[5] == "connected",
            )
        )
    last = rows[PAGE - 1] if len(rows) > PAGE else None
    following = f"{last[3].isoformat()}|{last[0]}" if last is not None and last[3] else None
    return out, following
