"""N-04-T16 (TASK-3382; DEC-2381) against Postgres: what the taxpayers sign is the final letter, a
person's act under the sign-off, and no other caller can render it final."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import sending
from abacus.modules.reporting import api as c11

from .agent_tests.support import Seeder
from .test_p11t08_render_service import (
    KIND,
    Values,
    _request,  # pyright: ignore[reportPrivateUsage] -- that file's world
    _world,  # pyright: ignore[reportPrivateUsage] -- that file's world
    engines,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- a fixture
    seed,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- a fixture
    values,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- a fixture
)


async def test_ac_the_sender_finalises_once_and_nobody_else_can(
    seed: Seeder,  # noqa: F811
    values: Values,  # noqa: F811
) -> None:
    del values
    c11._REGISTRY[KIND] = replace(  # pyright: ignore[reportPrivateUsage] -- the probe's kind
        c11._REGISTRY[KIND],  # pyright: ignore[reportPrivateUsage] -- the probe's kind
        approval_provider=sending._letter_approval,  # pyright: ignore[reportPrivateUsage] -- under test
    )
    tenant, user, client = await _world(seed)
    tenant_ctx = TenantContext(tenant, "human", str(user))
    person = c11.Requester("human", user_id=user)
    async with uow(tenant_ctx) as tx:
        ticket = await c11.render(tx, _request(client, uuid.uuid4(), person))
    document = ticket.generated_document_id
    latest = await c11.latest_document_version(tenant_ctx, document)
    assert latest is not None

    # Outside the sender's call the provider confirms nothing.
    refused = c11.ApprovalRef(sending.APPROVAL_KIND, uuid.uuid4(), latest[1])
    with pytest.raises(c11.RenderRefused) as no_approval:
        async with uow(tenant_ctx) as tx:
            await c11.render_final(tx, document, refused, person)
    assert no_approval.value.code == "final_requires_approval"

    ctx = AuthContext(tenant_ctx, user, uuid.UUID(int=0), None, system_now())
    row = {"id": uuid.uuid4(), "generated_document_id": document}
    await sending._final_letter(ctx, row)  # pyright: ignore[reportPrivateUsage] -- under test
    await sending._final_letter(ctx, row)  # pyright: ignore[reportPrivateUsage] -- under test
    assert await c11.document_is_final(tenant_ctx, document)
    modes = await seed.rows(
        "SELECT mode FROM generated_document_versions WHERE generated_document_id = $1 "
        "ORDER BY version_no",
        document,
    )
    assert [r["mode"] for r in modes] == ["draft", "final"]
