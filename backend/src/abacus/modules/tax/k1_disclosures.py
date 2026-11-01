"""The K-1 electronic-furnishing disclosure (S20e; T-02 §3.7, DV-12; Rev. Proc. 2012-17;
DEC-1579). Amber.

- **Content, not code.** The firm's counsel-approved text arrives through
  `POST /v1/k1-furnishing-disclosures` (`k1_disclosure.import`: a firm admin, a person with a
  recent second factor), each import a new version in the insert-only table (0590). Nothing seeds
  it for a real firm; until a version exists the consent sheet does not show and downloads are not
  gated (the firm furnishes by its own channel as before).
- **Before the first download** (POR-13): once a version exists, a package's statement downloads
  only after the recipient gave consent on it; a decline keeps the firm's paper or email copy
  (`k1_portal`'s download checks `consent_gate`). A consent names the version it was given on,
  which must be the newest (409 `stale_disclosure` otherwise).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise

IMPORT: Final = "k1_disclosure.import"
MAX_CHARS: Final = 20_000


class DisclosureInvalid(DomainInvalid):
    code = "disclosure_invalid"


class StaleDisclosure(DomainConflict):
    """The consent names a version that is not the newest: read the newest and decide again."""

    code = "stale_disclosure"


class ConsentRequired(DomainConflict):
    """A disclosure is published and the recipient has not consented on this package."""

    code = "e_furnishing_consent_required"


class FurnishingDeclined(DomainConflict):
    """The recipient declined electronic furnishing: the firm furnishes by its own channel."""

    code = "e_furnishing_declined"


@dataclass(frozen=True)
class Disclosure:
    id: UUID
    version_no: int
    body: str
    body_sha256: str
    imported_at: datetime


_NEWEST = text(
    "SELECT id, version_no, body, body_sha256, imported_at FROM k1_furnishing_disclosures "
    "ORDER BY version_no DESC LIMIT 1"
)


async def current(tenant: TenantContext) -> Disclosure | None:
    """The firm's newest disclosure, or None while none is published."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_NEWEST)).one_or_none()
    if row is None:
        return None
    return Disclosure(row.id, int(row.version_no), row.body, row.body_sha256, row.imported_at)


async def import_disclosure(ctx: AuthContext, body: str) -> Disclosure:
    """A firm admin's new version of the counsel-approved text (content through an endpoint)."""
    if ctx.client or ctx.is_support or ctx.tenant.actor_kind != "human":
        raise Forbidden(IMPORT, "role")
    await authorise(ctx, IMPORT, Resource.firm(ctx.tenant_id))
    text_ = body.strip()
    if not 1 <= len(text_) <= MAX_CHARS:
        raise DisclosureInvalid(facts={"field": "body"})
    digest = hashlib.sha256(text_.encode()).hexdigest()
    new_id = uuid4()
    async with uow(ctx.tenant) as tx:
        latest = await tx.session.scalar(
            text("SELECT max(version_no) FROM k1_furnishing_disclosures")
        )
        version = int(cast(int, latest or 0)) + 1
        await tx.session.execute(
            text(
                "INSERT INTO k1_furnishing_disclosures (id, tenant_id, version_no, body, "
                "body_sha256, imported_by) VALUES (:id, :t, :v, :b, :h, :by)"
            ),
            {
                "id": new_id,
                "t": ctx.tenant_id,
                "v": version,
                "b": text_,
                "h": digest,
                "by": ctx.user_id,
            },
        )
        tx.record(
            "schedule_k_disclosure.imported",  # digit-free, as the audit's (DEC-1471)
            target=Target("firm", ctx.tenant_id),
            after=Ref(disclosure=new_id, version=version, sha256=digest),
        )
    return Disclosure(new_id, version, text_, digest, await _imported_at(ctx.tenant, new_id))


async def _imported_at(tenant: TenantContext, disclosure_id: UUID) -> datetime:
    async with tenant_session(tenant) as session:
        return cast(
            datetime,
            await session.scalar(
                text("SELECT imported_at FROM k1_furnishing_disclosures WHERE id = :id"),
                {"id": disclosure_id},
            ),
        )


async def check_consent_version(tenant: TenantContext, disclosure_version_id: UUID) -> None:
    """A consent must name the newest published version."""
    newest = await current(tenant)
    if newest is None or newest.id != disclosure_version_id:
        raise StaleDisclosure(facts={"disclosure_version_id": str(disclosure_version_id)})


async def consent_gate(tenant: TenantContext, consent: str) -> None:
    """Downloads wait on consent once a disclosure is published (DV-12)."""
    if consent == "given":
        return
    if consent == "declined":
        raise FurnishingDeclined
    if await current(tenant) is not None:
        raise ConsentRequired


__all__ = [
    "IMPORT",
    "ConsentRequired",
    "Disclosure",
    "DisclosureInvalid",
    "FurnishingDeclined",
    "StaleDisclosure",
    "check_consent_version",
    "consent_gate",
    "current",
    "import_disclosure",
]
