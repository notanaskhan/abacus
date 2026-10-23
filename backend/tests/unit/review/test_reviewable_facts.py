"""P-04-T14: `ReviewableFacts` through the review slot (content hash, version number, preparers,
required levels, locked). Fail closed: an unregistered type is refused, an unknown target is not
found, and a provider answering for another target is not trusted."""

from __future__ import annotations

import uuid

import pytest

import abacus.modules.workpapers.api as workpapers_api
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.review.api import (
    REQUIRED_LEVELS,
    ReviewableFacts,
    UnregisteredKind,
    content_hash,
    register_reviewable_facts,
    reviewable_fact_types,
    reviewable_facts,
)

pytestmark = pytest.mark.asyncio
TENANT = TenantContext(uuid.uuid4(), "human", "probe")
KNOWN = uuid.uuid4()
ENGAGEMENT = uuid.uuid4()
PREPARER = uuid.uuid4()
WRONG = uuid.uuid4()


async def _facts(_tenant: TenantContext, target_id: uuid.UUID) -> ReviewableFacts | None:
    if target_id == WRONG:  # a provider that answers for another target
        return ReviewableFacts("probe_target", KNOWN, ENGAGEMENT, content_hash({}), 1, frozenset())
    if target_id != KNOWN:
        return None
    digest = content_hash({"cells": {}, "citations": []})
    return ReviewableFacts("probe_target", KNOWN, ENGAGEMENT, digest, 3, frozenset({PREPARER}))


async def test_registered_facts_are_the_owners() -> None:
    register_reviewable_facts("probe_target", _facts)
    register_reviewable_facts("probe_target", _facts)  # the same provider again is a no-op
    found = await reviewable_facts(TENANT, "probe_target", KNOWN)
    assert (found.version_no, found.preparer_user_ids) == (3, frozenset({PREPARER}))
    assert found.required_levels == REQUIRED_LEVELS and found.locked is False
    assert found.content_hash == content_hash({"citations": [], "cells": {}})


async def test_facts_fail_closed() -> None:
    register_reviewable_facts("probe_target", _facts)
    with pytest.raises(UnregisteredKind):
        await reviewable_facts(TENANT, "never_registered", KNOWN)
    with pytest.raises(NotFound):
        await reviewable_facts(TENANT, "probe_target", uuid.uuid4())
    with pytest.raises(NotFound):
        await reviewable_facts(TENANT, "probe_target", WRONG)


async def test_another_provider_for_the_same_type_is_refused() -> None:
    async def other(_tenant: TenantContext, _target: uuid.UUID) -> ReviewableFacts | None:
        return None

    register_reviewable_facts("probe_target", _facts)
    with pytest.raises(ValueError, match="already registered"):
        register_reviewable_facts("probe_target", other)


async def test_workpapers_register_their_facts() -> None:
    assert workpapers_api.ROUTERS  # importing the module registers its facts
    assert "workpaper" in reviewable_fact_types()
