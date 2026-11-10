"""The anchor slot (P-05-T05; ADR-236 decision 2; SPEC-650 AC-2): what a thread or a to-do may sit
on. Each kind is registered by the module that owns it through `register_anchor(kind, provider)`;
collaboration never imports its hosts. An unregistered kind answers 409
`anchor_kind_not_registered` and nothing is written (fail closed, chapter 03 §2.4). During the 2028
window `request_item` and `evidence_version` are never registered here: their comments stay on
the live SPEC-032 path until CL-1.

A provider answers `AnchorFacts` for one anchor as the caller may see it, or None when the record
does not exist in the tenant (404). The service then authorises the caller's action on
`facts.resource()`, so a provider never decides who may comment.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.modules.identity.api import Resource

VersionPolicy = Literal["pin", "follow"]
Locator = Mapping[str, str | int]
# Live SPEC-032 kinds: never registered for v2 in the window (ADR-236 decision 2, AC-2).
LIVE_SPEC032_KINDS: Final = frozenset({"request_item", "evidence_version"})
_KIND: Final = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_LOCATOR_KEY: Final = 400


class AnchorKindNotRegistered(DomainConflict):
    code = "anchor_kind_not_registered"


class AnchorNotShareable(DomainConflict):
    code = "anchor_not_shareable"


class AnchorScopeMismatch(DomainInvalid):
    code = "anchor_scope_mismatch"


class LocatorInvalid(DomainInvalid):
    """The locator names a key the provider's schema does not know, or a value too long."""

    code = "anchor_locator_invalid"


@dataclass(frozen=True)
class AnchorFacts:
    """One anchor as its provider reports it at read time (the label is never stored)."""

    tenant_id: UUID
    engagement_id: UUID | None
    client_id: UUID | None
    label: str  # "Northwind · Exceptions row 6"
    archived: bool = False
    work_item_id: UUID | None = None
    client_visible: bool = False
    version_no: int | None = None
    version_policy: VersionPolicy = "follow"
    # The row's text when a to-do is made from it (Restricted; sealed by the caller), or None.
    row_text: str | None = field(default=None, repr=False)

    def resource(self) -> Resource:
        if self.engagement_id is None:
            return Resource.firm(self.tenant_id)
        return Resource.engagement(
            self.tenant_id, self.engagement_id, archived=self.archived, client_id=self.client_id
        )


class AnchorProvider(Protocol):
    """Registered by an anchor's owning module."""

    # The locator keys this kind accepts (an empty set: no locator).
    locator_keys: frozenset[str]

    async def facts(
        self, tenant: TenantContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None: ...


_providers: dict[str, AnchorProvider] = {}


def register_anchor(kind: str, provider: AnchorProvider) -> None:
    """Call at import time from the owning module's api (P-39)."""
    if not _KIND.fullmatch(kind) or len(kind) > 40:
        raise ValueError(f"anchor kind {kind!r} is not a lower-case identifier")
    if kind in LIVE_SPEC032_KINDS:
        raise ValueError(f"{kind} stays on the SPEC-032 path until CL-1 (ADR-236)")
    known = _providers.get(kind)
    if known is not None and known is not provider:
        raise RuntimeError(f"the anchor kind {kind} is already registered")
    _providers[kind] = provider


def registered_kinds() -> frozenset[str]:
    return frozenset(_providers)


def provider_of(kind: str) -> AnchorProvider:
    found = _providers.get(kind)
    if found is None:
        raise AnchorKindNotRegistered(facts={"anchor_kind": kind})
    return found


def locator_key(provider: AnchorProvider, locator: Locator | None) -> str:
    """The normalised locator (sorted keys, compact JSON): one thread per anchor and key."""
    if not locator:
        return ""
    if not provider.locator_keys >= set(locator):
        raise LocatorInvalid
    key = json.dumps(dict(sorted(locator.items())), separators=(",", ":"))
    if len(key) > MAX_LOCATOR_KEY:
        raise LocatorInvalid
    return key


async def anchor_facts(
    tenant: TenantContext, kind: str, anchor_id: UUID, locator: Locator | None
) -> AnchorFacts | None:
    """The registered provider's facts (409 for an unregistered kind, before anything else)."""
    provider = provider_of(kind)
    locator_key(provider, locator)
    return await provider.facts(tenant, anchor_id, locator)
