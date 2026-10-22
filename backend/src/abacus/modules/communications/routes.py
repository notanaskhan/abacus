"""Platform routes of the communications module (P-01-T05; C16 email half)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.communications.templates import import_platform_version
from abacus.modules.identity.api import STAFF, AbacusRouter, Staff, current_staff

router = AbacusRouter(prefix="/v1/platform/email-templates", tags=["communications"])


class EmailTemplateImportIn(BaseModel):
    """Platform staff author the text here, never in code (AGENTS 16)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, Field(max_length=80), classified("internal")]
    locale: Annotated[str, Field(max_length=5), classified("internal")] = "en-US"
    subject: Annotated[str, Field(max_length=200), classified("internal")]
    body_text: Annotated[str, Field(max_length=20000), classified("internal")]
    variables: Annotated[list[str], Field(max_length=10), classified("internal")]


class EmailTemplateImportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[str, classified("internal")]
    version: Annotated[int, classified("internal")]
    content_sha256: Annotated[str, classified("internal")]
    created: Annotated[bool, classified("internal")]


@router.post("/import", action=STAFF, response_model=EmailTemplateImportOut)
async def import_email_template_route(
    body: EmailTemplateImportIn, staff: Annotated[Staff, Depends(current_staff)]
) -> EmailTemplateImportOut:
    """C16: a platform-default template version, from the staff issuer only. Importing the
    current content again returns the current version and writes nothing."""
    found = await import_platform_version(
        str(staff.id), body.key, body.locale, body.subject, body.body_text, body.variables
    )
    return EmailTemplateImportOut(
        template_id=found.template_id,
        version=found.version,
        content_sha256=found.content_sha256,
        created=found.created,
    )
