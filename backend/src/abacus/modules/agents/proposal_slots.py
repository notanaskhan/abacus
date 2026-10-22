"""Where agent suggestions and proposals may land (P-04-T06; ADR-161).

- A module registers each target type its fields may receive suggestions on
  (`register_suggestion_target`).
- A module registers an adapter per proposal kind that applies an approved change set through
  its own service (`register_proposal_adapter`).

Agents never write another module's rows. Fail closed: a suggestion on an unregistered target is
refused, and approving a proposal whose adapter isn't registered answers 503.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid, ServiceUnavailable

_CODE: Final = re.compile(r"[a-z][a-z_]{0,39}")
ProposalAdapter = Callable[[TenantContext, UUID], Awaitable[None]]
_TARGETS: set[str] = set()
_ADAPTERS: dict[str, ProposalAdapter] = {}


class UnregisteredTarget(DomainInvalid):
    """Nobody accepts suggestions on this target type."""

    code = "unregistered_target"


def register_suggestion_target(target_type: str) -> None:
    if not _CODE.fullmatch(target_type):
        raise ValueError(f"suggestion target {target_type!r} must be snake_case")
    _TARGETS.add(target_type)


def check_suggestion_target(target_type: str) -> None:
    if target_type not in _TARGETS:
        raise UnregisteredTarget


def register_proposal_adapter(kind: str, adapter: ProposalAdapter) -> None:
    if not _CODE.fullmatch(kind):
        raise ValueError(f"proposal kind {kind!r} must be snake_case")
    known = _ADAPTERS.get(kind)
    if known is not None and (known.__module__, known.__qualname__) != (
        adapter.__module__,
        adapter.__qualname__,
    ):
        raise ValueError(f"proposal kind {kind!r} is already registered")
    _ADAPTERS[kind] = adapter


async def apply_proposal(tenant: TenantContext, kind: str, proposal_id: UUID) -> None:
    adapter = _ADAPTERS.get(kind)
    if adapter is None:
        raise ServiceUnavailable
    await adapter(tenant, proposal_id)
