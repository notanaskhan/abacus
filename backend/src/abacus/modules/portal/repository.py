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


async def branding_display_name(session: AsyncSession) -> str | None:
    """The session's firm's display name (G-01-T04's settings accessor)."""
    return (
        await session.execute(text("SELECT display_name FROM portal_branding"))
    ).scalar_one_or_none()


async def branding_secured_footer(session: AsyncSession) -> bool | None:
    return (
        await session.execute(text("SELECT secured_footer FROM portal_branding"))
    ).scalar_one_or_none()


async def set_display_name(session: AsyncSession, tenant_id: UUID, name: str, by: UUID) -> None:
    await session.execute(
        text(
            "INSERT INTO portal_branding (tenant_id, display_name, updated_by) "
            "VALUES (:tenant, :name, :by) ON CONFLICT (tenant_id) DO UPDATE SET "
            "display_name = EXCLUDED.display_name, updated_by = EXCLUDED.updated_by, "
            "updated_at = abacus_now(), version = portal_branding.version + 1"
        ),
        {"tenant": tenant_id, "name": name, "by": by},
    )


async def set_secured_footer(session: AsyncSession, on: bool, by: UUID) -> bool:
    found = await session.execute(
        text(
            "UPDATE portal_branding SET secured_footer = :on, updated_by = :by, "
            "updated_at = abacus_now(), version = version + 1 RETURNING tenant_id"
        ),
        {"on": on, "by": by},
    )
    return found.first() is not None


async def preference(
    session: AsyncSession, user_id: UUID, scope_kind: str, scope_id: UUID
) -> RowMapping | None:
    """The person's preferences for one scope (`welcome_dismissed_at`, `version`), or None."""
    return (
        (
            await session.execute(
                text(
                    "SELECT welcome_dismissed_at, version FROM portal_preferences "
                    "WHERE user_id = :user AND scope_kind = :kind AND scope_id = :scope"
                ),
                {"user": user_id, "kind": scope_kind, "scope": scope_id},
            )
        )
        .mappings()
        .first()
    )


async def insert_preference(
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    scope_kind: str,
    scope_id: UUID,
    on: bool,
) -> RowMapping | None:
    """The first write (version 1); None when another write made the row first."""
    return (
        (
            await session.execute(
                text(
                    "INSERT INTO portal_preferences (tenant_id, user_id, scope_kind, scope_id, "
                    "welcome_dismissed_at) VALUES (:tenant, :user, :kind, :scope, "
                    "CASE WHEN :on THEN abacus_now() END) ON CONFLICT DO NOTHING "
                    "RETURNING welcome_dismissed_at, version"
                ),
                {
                    "tenant": tenant_id,
                    "user": user_id,
                    "kind": scope_kind,
                    "scope": scope_id,
                    "on": on,
                },
            )
        )
        .mappings()
        .first()
    )


async def update_preference(
    session: AsyncSession, user_id: UUID, scope_kind: str, scope_id: UUID, on: bool, version: int
) -> RowMapping | None:
    """Set the welcome at `version`; None when the row moved on (stale). A dismissal keeps its
    first time."""
    return (
        (
            await session.execute(
                text(
                    "UPDATE portal_preferences SET welcome_dismissed_at = CASE WHEN :on THEN "
                    "coalesce(welcome_dismissed_at, abacus_now()) END, version = version + 1, "
                    "updated_at = abacus_now() WHERE user_id = :user AND scope_kind = :kind "
                    "AND scope_id = :scope AND version = :version "
                    "RETURNING welcome_dismissed_at, version"
                ),
                {
                    "user": user_id,
                    "kind": scope_kind,
                    "scope": scope_id,
                    "on": on,
                    "version": version,
                },
            )
        )
        .mappings()
        .first()
    )
