"""The staff session behind a request, for the audit request context (G-02-T06; SPEC-349 AC-9).

The HTTP edge keeps the BFF cookie only as its SHA-256; at write time the unit of work asks this
resolver which live session that cookie belongs to, and only when it is the acting person's own
(`audit_request_session`, migration 0172). Identity owns `auth_sessions`, so the lookup lives
here and the kernel calls it through `kernel.request_context`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from abacus.kernel.request_context import ResolvedSession, register_session_resolver
from abacus.modules.identity.staff_session import COOKIE_NAME

_LOOKUP = text("SELECT session_id, mfa_at FROM audit_request_session(:cookie, :user_id)")


async def resolve_request_session(
    conn: AsyncConnection, cookie_sha256: str, user_id: UUID
) -> ResolvedSession | None:
    row = (await conn.execute(_LOOKUP, {"cookie": cookie_sha256, "user_id": user_id})).first()
    return None if row is None else ResolvedSession(row[0], row[1])


register_session_resolver(COOKIE_NAME, resolve_request_session)
