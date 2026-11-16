"""Connection entity coverage, as a slot (A-09-T11, T13; DEC-5070).

The connections module registers how to tell whether a live connection covers an entity and how
to add the entities a covering ledger connection reads (a NetSuite OneWorld connection covers a
group's subsidiaries). The consolidation routes in assurance call it here, so nothing depends on
connections but integrations and the portal (BOUND-002). Unregistered, nothing is covered.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from decimal import Decimal
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound

Covers = Callable[[TenantContext, UUID, UUID], Awaitable[bool]]
Extend = Callable[[TenantContext, UUID, Sequence[UUID]], Awaitable[int]]
_COVERS: Final[list[Covers]] = []
_EXTEND: Final[list[Extend]] = []


class EntityAlreadyCovered(DomainConflict):
    code = "entity_already_covered"


def register_connection_coverage(covers: Covers, extend: Extend) -> None:
    _COVERS[:] = [covers]
    _EXTEND[:] = [extend]


async def covers(tenant: TenantContext, connection_id: UUID, client_entity_id: UUID) -> bool:
    if not _COVERS:
        return False
    return await _COVERS[0](tenant, connection_id, client_entity_id)


async def cover_entities(
    tenant: TenantContext, connection_id: UUID, client_entity_ids: Sequence[UUID]
) -> int:
    if not _EXTEND:
        raise NotFound("connection")
    return await _EXTEND[0](tenant, connection_id, client_entity_ids)


# --- A-09-T18 rest (DEC-5329): a group's trial balances by subsidiary ----------------------------
# (account code, account name, debit, credit), as the source gives them; client content.
TbRows = Sequence[tuple[str, str, Decimal, Decimal]]
TbSplit = Callable[[bytes], Mapping[str, TbRows]]
# Each subsidiary's current trial balance, or None when its token is refused (never retried).
GroupPull = Callable[[], Sequence[tuple[str, TbRows | None]]]
_SPLIT: Final[list[TbSplit]] = []
_PULL: Final[list[GroupPull]] = []


class TbSplitRefused(DomainInvalid):
    code = "tb_split_refused"


def register_group_tb_sources(split: TbSplit, pull: GroupPull) -> None:
    """connections registers NetSuite's CSV splitter and the OneWorld pull (a fake on synthetic
    tenants until a live connector exists, DV-1)."""
    _SPLIT[:] = [split]
    _PULL[:] = [pull]


def split_tb_by_subsidiary(data: bytes) -> Mapping[str, TbRows]:
    if not _SPLIT:
        raise NotFound("tb_splitter")
    try:
        return _SPLIT[0](data)
    except ValueError as refused:  # the splitter's own refusal: a header, an amount, a balance
        raise TbSplitRefused(facts={"reason": str(refused)[:40]}) from None


def pull_group_tbs() -> Sequence[tuple[str, TbRows | None]]:
    if not _PULL:
        raise NotFound("group_connector")
    return _PULL[0]()


# --- A-09-T13 rest (DEC-5340): the group's subsidiary tree, for the structure proposal -----------
# (subsidiary, parent or None), as the source names them; client content.
GroupHierarchy = Callable[[], Sequence[tuple[str, str | None]]]
_HIERARCHY: Final[list[GroupHierarchy]] = []


def register_group_hierarchy(hierarchy: GroupHierarchy) -> None:
    """connections registers the OneWorld subsidiary tree (the fake's on synthetic tenants until
    a live connector exists, DV-1)."""
    _HIERARCHY[:] = [hierarchy]


def group_hierarchy() -> Sequence[tuple[str, str | None]]:
    if not _HIERARCHY:
        raise NotFound("group_connector")
    return _HIERARCHY[0]()
