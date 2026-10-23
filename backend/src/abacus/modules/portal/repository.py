"""Portal data access: branding, hosts and preferences only (ADR-008)."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

SLOT_COLUMNS = (
    "display_name",
    "portal_name",
    "address_line",
    "help_url",
    "privacy_url",
    "support_contact_name",
    "secured_footer",
    "maintenance_banner",
)


async def resolve_host(conn: AsyncConnection, host: str) -> RowMapping | None:
    """The Public branding of the firm whose active host this is (definer lookup; no tenant)."""
    return (
        (await conn.execute(text("SELECT * FROM portal_resolve_host(:host)"), {"host": host}))
        .mappings()
        .first()
    )


async def host_logo(conn: AsyncConnection, host: str) -> bytes | None:
    found = (
        await conn.execute(text("SELECT logo_png FROM portal_host_logo(:host)"), {"host": host})
    ).scalar_one_or_none()
    return None if found is None else bytes(found)


async def upsert_branding(
    session: AsyncSession, tenant_id: UUID, slots: Mapping[str, object], by: UUID
) -> int:
    """Set every branding slot of the firm (first write inserts the row); the new version."""
    return int(
        (
            await session.execute(
                text(
                    "INSERT INTO portal_branding (tenant_id, updated_by, display_name, "
                    "portal_name, address_line, help_url, privacy_url, support_contact_name, "
                    "secured_footer, maintenance_banner) VALUES (:tenant, :by, :display_name, "
                    ":portal_name, :address_line, :help_url, :privacy_url, "
                    ":support_contact_name, :secured_footer, :maintenance_banner) "
                    "ON CONFLICT (tenant_id) DO UPDATE SET display_name = EXCLUDED.display_name, "
                    "portal_name = EXCLUDED.portal_name, address_line = EXCLUDED.address_line, "
                    "help_url = EXCLUDED.help_url, privacy_url = EXCLUDED.privacy_url, "
                    "support_contact_name = EXCLUDED.support_contact_name, "
                    "secured_footer = EXCLUDED.secured_footer, "
                    "maintenance_banner = EXCLUDED.maintenance_banner, "
                    "updated_by = EXCLUDED.updated_by, updated_at = abacus_now(), "
                    "version = portal_branding.version + 1 RETURNING version"
                ),
                {"tenant": tenant_id, "by": by, **{c: slots[c] for c in SLOT_COLUMNS}},
            )
        ).scalar_one()
    )


async def set_logo(
    session: AsyncSession, tenant_id: UUID, png: bytes | None, sha256: bytes | None, by: UUID
) -> int | None:
    """Replace (or, with None, remove) the firm's logo; the new version, or None without a row."""
    return (
        await session.execute(
            text(
                "UPDATE portal_branding SET logo_png = :png, logo_sha256 = :sha, "
                "updated_by = :by, updated_at = abacus_now(), version = version + 1 "
                "WHERE tenant_id = :tenant RETURNING version"
            ),
            {"png": png, "sha": sha256, "by": by, "tenant": tenant_id},
        )
    ).scalar_one_or_none()


async def add_domain(session: AsyncSession, tenant_id: UUID, hostname: str, kind: str) -> None:
    await session.execute(
        text("SELECT portal_domain_add(:host, :kind)"), {"host": hostname, "kind": kind}
    )


async def activate_domain(session: AsyncSession, hostname: str) -> bool:
    found = await session.execute(text("SELECT portal_domain_activate(:host)"), {"host": hostname})
    return bool(found.scalar_one())
