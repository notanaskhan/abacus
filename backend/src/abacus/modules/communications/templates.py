"""Email templates, the C16 email half (P-01-T05; migration 0092).

Template text lives in the database, imported by platform staff (`POST
/v1/platform/email-templates/import`), never in code or `packages/domain` (AGENTS 16). The
renderer is deterministic and whitelisted:
- a template may use only the C16 variables `{{recipient_first_name}}`, `{{kind_sentence}}`,
  `{{engagement_display_name}}` and `{{app_link}}`, and must declare each one it uses;
- rendering needs exactly the declared values. An unknown variable, in the text or among the
  values, is refused, and so is a missing one;
- values are single-line: line breaks are refused, so a value can't add headers or lines;
- the same version and values always give byte-identical output.

No Restricted fact ever reaches an email: the values are names and a link the recipient can
already see (C16).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from sqlalchemy import text

from abacus.kernel.db import platform_transaction
from abacus.kernel.errors import DomainInvalid

VARIABLES: Final = frozenset(
    {"recipient_first_name", "kind_sentence", "engagement_display_name", "app_link"}
)
_PLACEHOLDER: Final = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")
_BRACES: Final = re.compile(r"\{\{|\}\}")
_KEY: Final = re.compile(r"[a-z][a-z_]*(\.[a-z][a-z_]*)+")
_LOCALE: Final = re.compile(r"[a-z]{2}-[A-Z]{2}")


class UnknownTemplateVariable(DomainInvalid):
    """A template or a render used a variable outside the C16 whitelist or its declaration."""

    code = "unknown_template_variable"


class TemplateInvalid(DomainInvalid):
    """The template's key, locale, text or values are malformed."""

    code = "template_invalid"


@dataclass(frozen=True)
class TemplateVersion:
    key: str
    locale: str
    version: int
    subject: str
    body_text: str
    variables: tuple[str, ...]


@dataclass(frozen=True)
class Rendered:
    subject: str
    body_text: str


@dataclass(frozen=True)
class Imported:
    template_id: str
    version: int
    content_sha256: str
    created: bool


def _used(*texts: str) -> set[str]:
    used = {m.group(1) for t in texts for m in _PLACEHOLDER.finditer(t)}
    # Stray braces outside a well-formed placeholder are refused rather than sent as text.
    if any(_BRACES.search(_PLACEHOLDER.sub("", t)) for t in texts):
        raise TemplateInvalid
    return used


def check_source(
    key: str, locale: str, subject: str, body_text: str, variables: list[str]
) -> None:
    """What an import must satisfy before it is stored."""
    if not _KEY.fullmatch(key) or not _LOCALE.fullmatch(locale):
        raise TemplateInvalid
    if not subject.strip() or not body_text.strip() or "\n" in subject or "\r" in subject:
        raise TemplateInvalid
    declared = set(variables)
    if len(declared) != len(variables) or not declared <= VARIABLES:
        raise UnknownTemplateVariable
    if not _used(subject, body_text) <= declared:
        raise UnknownTemplateVariable


def content_sha256(
    key: str, locale: str, subject: str, body_text: str, variables: list[str]
) -> str:
    canonical = json.dumps(
        [key, locale, subject, body_text, sorted(variables)], separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def render(version: TemplateVersion, values: Mapping[str, str]) -> Rendered:
    """Fill the declared variables. Byte-identical for the same version and values."""
    declared = set(version.variables)
    if set(values) != declared or not declared <= VARIABLES:
        raise UnknownTemplateVariable
    if not _used(version.subject, version.body_text) <= declared:
        raise UnknownTemplateVariable
    if any("\n" in v or "\r" in v for v in values.values()):
        raise TemplateInvalid

    def fill(source: str) -> str:
        return _PLACEHOLDER.sub(lambda m: values[m.group(1)], source)

    return Rendered(fill(version.subject), fill(version.body_text))


async def import_platform_version(
    staff_id: str, key: str, locale: str, subject: str, body_text: str, variables: list[str]
) -> Imported:
    """Store a platform-default version; importing the current content again writes nothing."""
    check_source(key, locale, subject, body_text, variables)
    sha = content_sha256(key, locale, subject, body_text, variables)
    async with platform_transaction(f"staff:{staff_id}") as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT (email_template_import("
                    ":key, :locale, :subject, :body, :variables, :sha, :by)).*"
                ),
                {
                    "key": key,
                    "locale": locale,
                    "subject": subject,
                    "body": body_text,
                    "variables": sorted(variables),
                    "sha": sha,
                    "by": f"staff:{staff_id}",
                },
            )
        ).one()
    return Imported(str(row.template_id), int(row.version), str(row.content_sha256), row.created)


async def current_version(key: str, locale: str = "en-US") -> TemplateVersion | None:
    """The platform default in use for `key`, or None when none is imported."""
    async with platform_transaction("system:email-templates") as conn:
        row = (
            await conn.execute(
                text("SELECT (email_template_current(:key, :locale)).*"),
                {"key": key, "locale": locale},
            )
        ).one_or_none()
    if row is None:
        return None
    return TemplateVersion(
        key, locale, int(row.version), row.subject, row.body_text, tuple(row.variables)
    )
