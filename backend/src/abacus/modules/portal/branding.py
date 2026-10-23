"""Portal branding before sign-in (P-08-T05; ADR-163 §5-§7, ADR-152).

The request host is a branding hint and nothing else: it picks which firm's Public slots POR-01
shows, through the definer lookups, and never a tenant for anything else. An unknown, inactive or
malformed host gets the same shape with neutral values, and no answer carries a tenant id.

The logo is re-encoded on the way in (`reencode_logo`: decoded in the isolated child, PNG out,
metadata dropped, at most `LOGO_SIDE` pixels on its longer side and `LOGO_MAX_BYTES`), stored with
its SHA-256, and served same-origin by the logo route (CSP `img-src 'self'`). The "Secured by"
footer defaults to off (§7).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import re
from dataclasses import asdict, dataclass
from typing import Final, Literal
from uuid import UUID

from PIL import Image

from abacus.kernel.db import platform_transaction
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.portal import repository

LOGO_PATH: Final = "/v1/portal/branding/logo"
LOGO_SIDE: Final = 512
LOGO_MAX_BYTES: Final = 262_144
_LOGO_MAX_INPUT: Final = 5 * 1024 * 1024
_LOGO_MAX_PIXELS: Final = 25_000_000
# A hostname as a browser sends it (an optional port is dropped); anything else is unknown.
_HOST: Final = re.compile(
    r"^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)(?::\d{1,5})?$"
)
_ACTOR: Final = "portal:branding"


@dataclass(frozen=True)
class Branding:
    """What POR-01 renders before sign-in: Public fields only."""

    firm_name: str | None = None
    portal_name: str | None = None
    logo_url: str | None = None
    address_line: str | None = None
    help_url: str | None = None
    privacy_url: str | None = None
    support_contact_name: str | None = None
    secured_footer: bool = False
    maintenance_banner: str | None = None


NEUTRAL: Final = Branding()


def _hostname(host: str | None) -> str | None:
    if not host or len(host) > 260:
        return None
    found = _HOST.fullmatch(host.strip().lower())
    return None if found is None else found.group(1)


async def branding_for_host(host: str | None) -> Branding:
    """The firm's Public slots for an active host, else `NEUTRAL` (the same shape)."""
    name = _hostname(host)
    if name is None:
        return NEUTRAL
    async with platform_transaction(_ACTOR) as conn:
        row = await repository.resolve_host(conn, name)
    if row is None:
        return NEUTRAL
    return Branding(
        firm_name=row["display_name"],
        portal_name=row["portal_name"],
        logo_url=LOGO_PATH if row["has_logo"] else None,
        address_line=row["address_line"],
        help_url=row["help_url"],
        privacy_url=row["privacy_url"],
        support_contact_name=row["support_contact_name"],
        secured_footer=bool(row["secured_footer"]),
        maintenance_banner=row["maintenance_banner"],
    )


async def logo_for_host(host: str | None) -> bytes:
    """The re-encoded PNG for an active host; `NotFound` for anything else (no tenant leaks)."""
    name = _hostname(host)
    if name is not None:
        async with platform_transaction(_ACTOR) as conn:
            png = await repository.host_logo(conn, name)
        if png is not None:
            return png
    raise NotFound("portal_logo")


# --- writing (the ADM branding screen's route calls these; authorised there) -------------------


class LogoUnreadable(DomainInvalid):
    """The logo isn't a PNG or JPEG this server can decode, or is too large."""

    code = "logo_unreadable"


def _reencode(content: bytes) -> bytes | None:
    Image.MAX_IMAGE_PIXELS = _LOGO_MAX_PIXELS
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in ("PNG", "JPEG"):
                return None
            image.load()
            image.thumbnail((LOGO_SIDE, LOGO_SIDE))
            clean = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
            out = io.BytesIO()
            clean.save(out, format="PNG", optimize=True)  # no metadata is carried over
            return out.getvalue()
    except Exception:  # a damaged, hostile or oversized image
        return None


async def reencode_logo(content: bytes) -> tuple[bytes, bytes]:
    """A firm's uploaded logo as a clean PNG and its SHA-256, decoded in the isolated child
    (Pillow is native code reading a file a person uploaded)."""
    if not content or len(content) > _LOGO_MAX_INPUT:
        raise LogoUnreadable
    try:
        png = await asyncio.to_thread(run_isolated, _reencode, content)
    except (IsolationFailed, OSError, ValueError):
        raise LogoUnreadable from None
    if png is None or len(png) > LOGO_MAX_BYTES:
        raise LogoUnreadable
    return png, hashlib.sha256(png).digest()


@dataclass(frozen=True)
class BrandingSlots:
    """Every slot a firm sets (ADR-163 §7); the accent and CSS stay the product's (ADR-155)."""

    display_name: str
    portal_name: str | None = None
    address_line: str | None = None
    help_url: str | None = None
    privacy_url: str | None = None
    support_contact_name: str | None = None
    secured_footer: bool = False
    maintenance_banner: str | None = None


async def set_branding(tx: UnitOfWork, tenant_id: UUID, slots: BrandingSlots, by: UUID) -> int:
    """Inside the caller's unit of work; one `portal_branding.updated` event."""
    version = await repository.upsert_branding(tx.session, tenant_id, asdict(slots), by)
    tx.record(
        "portal_branding.updated", target=Target("firm", tenant_id), after=Ref(version=version)
    )
    return version


async def set_logo(tx: UnitOfWork, tenant_id: UUID, content: bytes | None, by: UUID) -> int:
    """Re-encode and store the logo (None removes it); `NotFound` before branding exists."""
    png, sha = await reencode_logo(content) if content is not None else (None, None)
    version = await repository.set_logo(tx.session, tenant_id, png, sha, by)
    if version is None:
        raise NotFound("portal_branding")
    tx.record(
        "portal_branding.updated", target=Target("firm", tenant_id), after=Ref(version=version)
    )
    return version


class HostInvalid(DomainInvalid):
    """Not a hostname a portal can answer on."""

    code = "portal_host_invalid"


async def add_portal_host(
    tx: UnitOfWork, tenant_id: UUID, hostname: str, kind: Literal["default", "custom"]
) -> None:
    """A host for the firm's portal, `pending_dns` until verified (provisioning's default host;
    ADM-10's custom ones from P1)."""
    name = _hostname(hostname)
    if name is None:
        raise HostInvalid
    await repository.add_domain(tx.session, tenant_id, name, kind)
    tx.record("portal_domain.added", target=Target("firm", tenant_id))


async def activate_portal_host(tx: UnitOfWork, tenant_id: UUID, hostname: str) -> None:
    """The host answers with the firm's branding from now on (DNS and certificate verified)."""
    name = _hostname(hostname)
    if name is None or not await repository.activate_domain(tx.session, name):
        raise NotFound("portal_domain")
    tx.record("portal_domain.activated", target=Target("firm", tenant_id))
