"""The catalogue load, planned (A-02-T12; C20 v1; P-62 reference data).

The operator's command (`abacus_tools.integration_catalog load`) reads a reviewed YAML document,
validates it here, plans it against the rows the database holds, and writes only when not a dry
run, through `integration_catalog_load(rows, operator)` as `abacus_ops`. The plan is pure: the
same rows the definer compares (every column but the revision and the load facts), so a dry run
reports exactly the adds and changes a real load makes, and writes nothing. Nothing is deleted:
a row leaves a surface by `listing_status: hidden`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified
from abacus.modules.integrations.ports import CatalogCategory, Key, ScopeCode

Text = Annotated[str, Field(min_length=1, max_length=400)]


class ConsentCopyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Annotated[Text, classified("public")]
    will: Annotated[list[Text], Field(min_length=1, max_length=10), classified("public")]
    wont: Annotated[list[Text], Field(min_length=1, max_length=10), classified("public")]
    authorization: Annotated[Text, classified("public")]
    continue_label: Annotated[Text, classified("public")]
    helper: Annotated[Text | None, classified("public")] = None


class ScopeIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Annotated[ScopeCode, classified("public")]
    label: Annotated[Annotated[str, Field(min_length=1, max_length=80)], classified("public")]


class ScopesIn(BaseModel):
    """Read scopes only: a document that names a write scope does not validate (ADR-040)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    read: Annotated[list[ScopeIn], Field(min_length=1, max_length=20), classified("public")]


class CatalogRowIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[Key, classified("public")]
    name: Annotated[Annotated[str, Field(min_length=1, max_length=80)], classified("public")]
    category: Annotated[CatalogCategory, classified("public")]
    ownership_mode: Annotated[
        Literal["firm", "personal", "client_authorised"], classified("public")
    ]
    surfaces: Annotated[
        list[Literal["portal", "workbench"]], Field(min_length=1), classified("public")
    ]
    connector_provider: Annotated[Key | None, classified("public")] = None
    adapter_key: Annotated[Key | None, classified("public")] = None
    listing_status: Annotated[Literal["available", "coming_soon", "hidden"], classified("public")]
    consent_copy: Annotated[ConsentCopyIn | None, classified("public")] = None
    consent_version: Annotated[int | None, Field(ge=1), classified("public")] = None
    scopes: Annotated[ScopesIn, classified("public")]
    icon: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,39}$"), classified("public")]
    tone: Annotated[Literal["olive", "espresso", "clay", "ochre"], classified("public")]
    sort_order: Annotated[int, Field(ge=0), classified("public")]

    @model_validator(mode="after")
    def _rules(self) -> Self:
        if (self.consent_copy is None) != (self.consent_version is None):
            raise ValueError("consent copy and its version come together")
        if self.ownership_mode == "client_authorised" and self.connector_provider is None:
            raise ValueError("a client-authorised app names its connection provider")
        return self

    def as_row(self) -> dict[str, Any]:  # Any: JSON for the definer
        return self.model_dump(mode="json")


class CatalogDocument(BaseModel):
    """The reviewed document: `version: 1` and its rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[Literal[1], classified("public")]
    rows: Annotated[list[CatalogRowIn], Field(max_length=200), classified("public")]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        keys = [r.key for r in self.rows]
        if len(set(keys)) != len(keys):
            raise ValueError("a catalogue key appears once")
        providers = [r.connector_provider for r in self.rows if r.connector_provider]
        if len(set(providers)) != len(providers):
            raise ValueError("a connection provider appears once")
        return self


# The columns the definer compares; `revision`, `loaded_by` and `loaded_at` are the load's.
COMPARED = (
    "name",
    "category",
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
)


@dataclass(frozen=True)
class LoadPlan:
    added: tuple[str, ...]
    changed: tuple[tuple[str, tuple[str, ...]], ...]  # key, the columns that differ
    unchanged: tuple[str, ...]

    @property
    def writes(self) -> bool:
        return bool(self.added or self.changed)


def _norm(value: object) -> object:
    """JSON as compared: a null member is the same as an absent one."""
    if isinstance(value, list):
        return [_norm(v) for v in cast(list[object], value)]
    if isinstance(value, dict):
        items = cast(dict[str, object], value).items()
        return {k: _norm(v) for k, v in items if v is not None}
    return value


def plan_load(current: Sequence[Mapping[str, object]], document: CatalogDocument) -> LoadPlan:
    """What a load of `document` adds and changes against `current` (the rows as
    `integration_catalog_rows()` returns them). Pure; writes nothing."""
    by_key = {str(r["key"]): r for r in current}
    added: list[str] = []
    changed: list[tuple[str, tuple[str, ...]]] = []
    unchanged: list[str] = []
    for row in document.rows:
        new = row.as_row()
        old = by_key.get(row.key)
        if old is None:
            added.append(row.key)
            continue
        diff = tuple(c for c in COMPARED if _norm(old.get(c)) != _norm(new.get(c)))
        if diff:
            changed.append((row.key, diff))
        else:
            unchanged.append(row.key)
    return LoadPlan(tuple(added), tuple(changed), tuple(unchanged))
