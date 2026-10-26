"""Firm email template rows (R-01-T19; migration 0196). Communications' own tables only.

Template rows and versions are global: the app reaches them only through 0196's SECURITY DEFINER
functions, which take the firm from the session's tenant setting. Drafts are a tenant table
under RLS. A firm's wording (version and draft) is sealed with the firm's key and bound to the
template, the version (or draft version) and, for a version, its content hash, so a sealed body
can't be moved to another row or opened as another firm's (ADR-035).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.crypto import open_sealed, seal
from abacus.modules.communications.render import TemplateContent, content_sha256
from abacus.modules.communications.templates import TemplateInvalid

LOCALE = "en-US"
_RESOLVE = text(
    "SELECT template_id, version_id, version, firm, format, subject, preheader, blocks, sealed, "
    "cta_label, cta_target, content_sha256, published_by, published_at "
    "FROM email_template_resolve(:key, :locale)"
)
_VERSION_AT = text(
    "SELECT template_id, version_id, version, firm, format, subject, preheader, blocks, sealed, "
    "cta_label, cta_target, content_sha256, published_by, published_at "
    "FROM email_template_version_at(:key, :locale, :version)"
)


@dataclass(frozen=True)
class StoredVersion:
    template_id: UUID
    version_id: UUID
    version: int
    firm: bool
    format: str
    content: TemplateContent | None  # None: a P-01-T05 text version (not a block template)
    content_sha256: str
    published_by: str
    published_at: datetime


@dataclass(frozen=True)
class StoredDraft:
    template_id: UUID
    base_version_id: UUID | None
    draft_version: int
    content: TemplateContent
    updated_by: UUID
    updated_at: datetime


def _version_binding(template_id: UUID, version: int, sha: str) -> str:
    return f"email_template_version:{template_id}:{version}:{sha}"


def _draft_binding(template_id: UUID, draft_version: int) -> str:
    return f"email_template_draft:{template_id}:{draft_version}"


def _plain(content: TemplateContent) -> bytes:
    return json.dumps(content.to_json(), separators=(",", ":"), sort_keys=True).encode()


def _content(raw: bytes) -> TemplateContent:
    return TemplateContent.from_json(cast(dict[str, object], json.loads(raw)))


async def _stored(tenant_id: UUID, key: str, row: Row[Any]) -> StoredVersion:  # Any: a text() row
    template_id: UUID = row.template_id
    version: int = row.version
    sha: str = row.content_sha256
    content: TemplateContent | None = None
    if row.format == "blocks":
        if row.sealed is not None:
            binding = _version_binding(template_id, version, sha)
            content = _content(await open_sealed(tenant_id, row.sealed, binding))
        else:
            content = TemplateContent.from_json(
                {
                    "subject": row.subject,
                    "preheader": row.preheader or "",
                    "blocks": row.blocks or [],
                    "cta_label": row.cta_label,
                    "cta_target": row.cta_target,
                }
            )
        # The hash is over what the version says; a mismatch is a corrupt or moved row.
        if content.cta_target != row.cta_target or content_sha256(key, LOCALE, content) != sha:
            raise TemplateInvalid
    return StoredVersion(
        template_id,
        row.version_id,
        version,
        row.firm,
        row.format,
        content,
        sha,
        row.published_by,
        row.published_at,
    )


async def resolve(session: AsyncSession, tenant_id: UUID, key: str) -> StoredVersion | None:
    """The version in use for `key`: the firm's published one, else the platform default."""
    row = (
        await session.execute(
            _RESOLVE,
            {"key": key, "locale": LOCALE},
        )
    ).one_or_none()
    return None if row is None else await _stored(tenant_id, key, row)


async def version_at(
    session: AsyncSession, tenant_id: UUID, key: str, version: int
) -> StoredVersion | None:
    """A published version by number (the firm's first): v3 stays readable after v4."""
    row = (
        await session.execute(
            _VERSION_AT,
            {"key": key, "locale": LOCALE, "version": version},
        )
    ).one_or_none()
    return None if row is None else await _stored(tenant_id, key, row)


async def firm_template_id(session: AsyncSession, key: str) -> UUID | None:
    found = await session.scalar(
        text("SELECT email_template_firm_id(:key, :locale)"), {"key": key, "locale": LOCALE}
    )
    return cast(UUID | None, found)


async def ensure_firm_template(session: AsyncSession, key: str) -> UUID:
    """The firm's override row for `key`, created on its first edit or import. The database
    refuses a key its platform row does not mark firm-editable and takes the audience from that
    row (security review M1)."""
    found = await session.scalar(
        text("SELECT email_template_firm_row(:key, :locale)"), {"key": key, "locale": LOCALE}
    )
    return cast(UUID, found)


_DRAFT = text(
    "SELECT template_id, base_version_id, sealed, cta_target, draft_version, updated_by, "
    "updated_at FROM email_template_drafts WHERE template_id = :template"
)
_DRAFT_LOCKED = text(
    "SELECT template_id, base_version_id, sealed, cta_target, draft_version, updated_by, "
    "updated_at FROM email_template_drafts WHERE template_id = :template FOR UPDATE"
)


async def draft_of(
    session: AsyncSession, tenant_id: UUID, template_id: UUID, *, lock: bool = False
) -> StoredDraft | None:
    query = _DRAFT_LOCKED if lock else _DRAFT
    row = (await session.execute(query, {"template": template_id})).one_or_none()
    if row is None:
        return None
    raw = await open_sealed(tenant_id, row.sealed, _draft_binding(template_id, row.draft_version))
    content = _content(raw)
    if content.cta_target != row.cta_target:
        raise TemplateInvalid
    return StoredDraft(
        row.template_id,
        row.base_version_id,
        row.draft_version,
        content,
        row.updated_by,
        row.updated_at,
    )


async def put_draft(
    session: AsyncSession,
    tenant_id: UUID,
    template_id: UUID,
    *,
    base_version_id: UUID | None,
    draft_version: int,
    content: TemplateContent,
    updated_by: UUID,
) -> None:
    """Insert or replace the draft. The caller locked and checked `expected_version`."""
    sealed = await seal(tenant_id, _plain(content), _draft_binding(template_id, draft_version))
    values = {
        "tenant": tenant_id,
        "template": template_id,
        "base": base_version_id,
        "sealed": sealed,
        "target": content.cta_target,
        "draft_version": draft_version,
        "by": updated_by,
    }
    if draft_version == 1:
        await session.execute(
            text(
                "INSERT INTO email_template_drafts (tenant_id, template_id, base_version_id, "
                "sealed, cta_target, draft_version, updated_by) VALUES (:tenant, :template, "
                ":base, :sealed, :target, :draft_version, :by)"
            ),
            values,
        )
        return
    await session.execute(
        text(
            "UPDATE email_template_drafts SET base_version_id = :base, sealed = :sealed, "
            "cta_target = :target, draft_version = :draft_version, updated_by = :by, "
            "updated_at = clock_timestamp() WHERE tenant_id = :tenant AND template_id = :template"
        ),
        values,
    )


async def delete_draft(session: AsyncSession, template_id: UUID) -> None:
    await session.execute(
        text("DELETE FROM email_template_drafts WHERE template_id = :template"),
        {"template": template_id},
    )


async def publish_version(
    session: AsyncSession,
    tenant_id: UUID,
    key: str,
    template_id: UUID,
    version: int,
    content: TemplateContent,
    *,
    source: str,
) -> tuple[UUID, str]:
    """Insert the firm's version `version` (insert-only); the function refuses any other number
    (`serialization_failure`, a concurrent publish), records the session's person as its
    publisher and refuses any other actor (security review M1). Returns the id and the hash."""
    sha = content_sha256(key, LOCALE, content)
    sealed = await seal(tenant_id, _plain(content), _version_binding(template_id, version, sha))
    version_id = await session.scalar(
        text(
            "SELECT email_template_publish(:template, :version, :sealed, :target, :sha, :source)"
        ),
        {
            "template": template_id,
            "version": version,
            "sealed": sealed,
            "target": content.cta_target,
            "sha": sha,
            "source": source,
        },
    )
    return cast(UUID, version_id), sha
