"""The catalogue's v2 import, planned (W-01-T07; C20 v2; SPEC-659 AC-32; DEC-5046).

The reviewed document (`version: 2`) is the workbench catalogue: the WB-10 tiles and the portal's
client feeds, one row each, never a seed or a constant (AGENTS 16). This validates it and plans it
against the rows the database holds; `abacus_tools.integration_catalog import` writes it through
`integration_catalog_import(...)` as `abacus_ops` (0901) only when not a dry run, and checks the
database changed exactly what the plan said. The plan compares the same columns as the definer,
so a dry run reports exactly what an apply does, and writes nothing (AC-32). A workbench row the
document no longer names is unpublished (taken off the tiles, never deleted).

Content rules checked here, before anything is written: read scopes only (ADR-040); one key and
one connection provider per row; a portal row names its v1 category, a workbench row its WB-10
category tags; a tile carries no vendor logo, brand colour or payment copy (AC-5: the icon is the
category glyph and the tone one of the five tokens); `published_at` is an instant with its offset.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Final, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified
from abacus.modules.integrations.capabilities import write_capability
from abacus.modules.integrations.catalog_load import ConsentCopyIn, ScopesIn, normalised
from abacus.modules.integrations.ports import CatalogCategory, Key

Public = classified("public")
CategoryCode = Literal[
    "tax", "practice", "erp", "grc", "docs", "comms", "prod", "crm", "hris", "spend"
]
Tone = Literal["olive", "espresso", "clay", "ochre", "brick"]
# AC-5: no payment or pricing copy on a tile, and no vendor logo or brand asset.
_BANNED: Final = re.compile(
    r"\b(free trial|pricing|per month|/mo\b|\$\d|buy now|upgrade to|logo)\b", re.IGNORECASE
)


class PrerequisiteIn(BaseModel):
    """Another integration's scope a tile needs first, and the reason shown until it is granted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[Key, Public]
    scope: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.:-]{1,60}$"), Public]
    reason: Annotated[str, Field(min_length=1, max_length=240), Public]


class CatalogRowV2In(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[Key, Public]
    name: Annotated[Annotated[str, Field(min_length=1, max_length=80)], Public]
    category: Annotated[CatalogCategory | None, Public] = None  # the portal's (C20 v1)
    categories: Annotated[list[CategoryCode], Field(max_length=4), Public] = []
    ownership_mode: Annotated[Literal["firm", "personal", "client_authorised"], Public]
    surfaces: Annotated[list[Literal["portal", "workbench"]], Field(min_length=1), Public]
    connector_provider: Annotated[Key | None, Public] = None
    adapter_key: Annotated[Key | None, Public] = None
    listing_status: Annotated[Literal["available", "coming_soon", "hidden"], Public]
    consent_copy: Annotated[ConsentCopyIn | None, Public] = None
    consent_version: Annotated[int | None, Field(ge=1), Public] = None
    scopes: Annotated[ScopesIn, Public]
    icon: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,39}$"), Public]
    tone: Annotated[Tone, Public]
    sort_order: Annotated[int, Field(ge=0), Public]
    description: Annotated[str | None, Field(max_length=400), Public] = None
    auth_line: Annotated[str | None, Field(max_length=120), Public] = None
    published_at: Annotated[datetime | None, Public] = None
    prerequisite: Annotated[PrerequisiteIn | None, Public] = None
    # W-01-T10 (OQ-4, AC-21): the declared writes a tile names; each is a write-capability
    # registry key, or the document does not validate. Checked, never stored: WB-11 joins writes
    # from the registry itself.
    writes: Annotated[list[Key], Field(max_length=8), Public] = []

    @model_validator(mode="after")
    def _rules(self) -> Self:
        if (self.consent_copy is None) != (self.consent_version is None):
            raise ValueError("consent copy and its version come together")
        if self.ownership_mode == "client_authorised" and self.connector_provider is None:
            raise ValueError("a client-authorised app names its connection provider")
        if "portal" in self.surfaces and self.category is None:
            raise ValueError("a portal row names its category")
        if "workbench" in self.surfaces:
            if not self.categories:
                raise ValueError("a workbench tile carries its category tags")
            if self.description is None or self.auth_line is None:
                raise ValueError("a workbench tile has its description and auth line")
            if self.published_at is None:
                raise ValueError("a workbench tile names when it is published")
        if self.published_at is not None and self.published_at.tzinfo is None:
            raise ValueError("published_at carries its offset")
        for text in (self.name, self.description or "", self.auth_line or ""):
            if _BANNED.search(text):
                raise ValueError("no payment copy or vendor branding on a tile (AC-5)")
        unknown = [w for w in self.writes if write_capability(w) is None]
        if unknown:
            raise ValueError("a declared write names a write-capability registry entry (OQ-4)")
        if "declared write" in (self.auth_line or "") and not self.writes:
            raise ValueError("an auth line that names a declared write names its capability")
        return self

    def as_row(self) -> dict[str, Any]:  # Any: JSON for the definer
        return self.model_dump(mode="json", exclude={"writes"})


class CatalogDocumentV2(BaseModel):
    """The reviewed document: `version: 2` and its rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[Literal[2], Public]
    rows: Annotated[list[CatalogRowV2In], Field(min_length=1, max_length=300), Public]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        keys = [r.key for r in self.rows]
        if len(set(keys)) != len(keys):
            raise ValueError("a catalogue key appears once")
        providers = [r.connector_provider for r in self.rows if r.connector_provider]
        if len(set(providers)) != len(providers):
            raise ValueError("a connection provider appears once")
        return self


# The columns 0901's definer compares and writes; the revision and the load facts are its own.
COMPARED: Final = (
    "name",
    "category",
    "categories",
    "ownership_mode",
    "surfaces",
    "connector_provider",
    "adapter_key",
    "listing_status",
    "consent_copy",
    "consent_version",
    "scopes",
    "icon",
    "tone",
    "sort_order",
    "description",
    "auth_line",
    "published_at",
    "prerequisite",
)


@dataclass(frozen=True)
class ImportPlan:
    added: tuple[str, ...]
    changed: tuple[tuple[str, tuple[str, ...]], ...]  # key, the columns that differ
    unpublished: tuple[str, ...]
    unchanged: tuple[str, ...]
    # Keys a firm could not use before and can after: newly published, or coming soon to available.
    became_available: tuple[str, ...]

    @property
    def writes(self) -> bool:
        return bool(self.added or self.changed or self.unpublished)


def document_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _instant(value: object) -> object:
    """A timestamp as compared: the instant, whatever offset the text carried."""
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return value
    return value


def _texts(value: object) -> list[str]:
    """A text[] as read, or its JSON list, as strings (NULL reads empty)."""
    return [str(v) for v in cast(list[object], value)] if isinstance(value, list | tuple) else []


def _same(column: str, old: object, new: object) -> bool:
    if column == "published_at":
        return _instant(old) == _instant(new)
    if column in ("surfaces", "categories"):
        return _texts(old) == _texts(new)
    return normalised(old) == normalised(new)


def plan_import(
    current: Sequence[Mapping[str, object]], document: CatalogDocumentV2
) -> ImportPlan:
    """What an import of `document` adds, changes and unpublishes against `current` (every
    catalogue row, as `integration_catalog_workbench()` plus the portal rows return them). Pure;
    writes nothing."""
    by_key = {str(r["key"]): r for r in current}
    named = {r.key for r in document.rows}
    added: list[str] = []
    changed: list[tuple[str, tuple[str, ...]]] = []
    unchanged: list[str] = []
    became: list[str] = []
    for row in document.rows:
        new = row.as_row()
        old = by_key.get(row.key)
        if old is None:
            added.append(row.key)
            if row.listing_status == "available":
                became.append(row.key)
            continue
        diff = tuple(c for c in COMPARED if not _same(c, old.get(c), new.get(c)))
        if diff:
            changed.append((row.key, diff))
            if row.listing_status == "available" and old.get("listing_status") != "available":
                became.append(row.key)
        else:
            unchanged.append(row.key)
    unpublished = sorted(
        str(r["key"])
        for r in current
        if "workbench" in _texts(r.get("surfaces"))
        and r.get("listing_status") != "hidden"
        and str(r["key"]) not in named
    )
    return ImportPlan(
        tuple(added), tuple(changed), tuple(unpublished), tuple(unchanged), tuple(became)
    )
