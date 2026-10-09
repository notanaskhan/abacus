"""Acceptance files and signed engagement letters (SPEC-025 AC-4, AC-6; TASK-044 D2).

Stored write-once and encrypted like evidence (never opened or rendered here); engagements keeps
only the reference. Downloads are attachments, audited and fingerprint-verified, as SPEC-021.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import (
    StoredFile,
    attach_acceptance_file,
    attach_letter_file,
    stored_file,
)
from abacus.modules.evidence import storage
from abacus.modules.evidence.item_detail import IntegrityFailed, download_name
from abacus.modules.evidence.uploads import checked, clean_name
from abacus.modules.identity.api import AuthContext

Which = Literal["acceptance", "letter"]


async def upload_setup_file(
    ctx: AuthContext, engagement_id: UUID, which: Which, *, file_name: str, content: bytes
) -> None:
    media_type, _ = checked(content)
    stored = await storage.put(ctx.tenant_id, content)
    file = StoredFile(
        stored.key,
        stored.version_id,
        stored.fingerprint,
        stored.size,
        media_type,
        clean_name(file_name),
    )
    async with uow(ctx.tenant) as tx:
        if which == "acceptance":
            await attach_acceptance_file(tx, ctx, engagement_id, file)
        else:
            await attach_letter_file(tx, ctx, engagement_id, file)


async def download_setup_file(
    ctx: AuthContext, engagement_id: UUID, which: Which
) -> tuple[bytes, str, str]:
    """(content, media type, file name); audited and verified."""
    file = await stored_file(ctx, engagement_id, which)  # authorises `setup.read`
    async with uow(ctx.tenant) as tx:
        tx.record(
            f"engagement.{which}_file_read",
            target=Target("engagement", engagement_id),
            after=Ref(fingerprint=file.fingerprint),
        )
    try:
        content = await storage.get(
            ctx.tenant_id,
            storage.StoredObject(file.key, file.version_id, file.fingerprint, file.size),
        )
    except storage.IntegrityError:
        raise IntegrityFailed from None
    return content, file.media_type, download_name(file.name, 1, None, file.media_type)
