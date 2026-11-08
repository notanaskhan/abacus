"""A-06-T29 (TASK-6020; DEC-2615) against Postgres: Northwind v3 renders as a composed C11 draft.

Brightwater Hale's completion slice loads the three statement versions; rendering v3 twice seals
the same body and the same content hash (the PDF bytes are the image's check), the body is the
statements and notes only, and the version's draft is a person's, DRAFT mode, with no template.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import cast
from uuid import UUID

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting.api import render_statement_draft
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import (
    BY_LABEL,
    TENANT,
    engagement_id_of,
    user_id_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

LEAKS = ("TB!", "certified", "Disclosure checklist", '"cite"', "citation")


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


@pytest.fixture(scope="module")
def loaded(own_db: Database, object_store: str) -> Iterator[Database]:
    async def load() -> None:
        await dispose_engine()
        configure_engine(own_db.app_url)
        try:
            await loader.load(
                own_db.superuser_dsn, "2026-10-21T14:10", slices=("completion",), wait=False
            )
        finally:
            await dispose_engine()

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
        settings.cache_clear()
        forget_flags()
        asyncio.run(load())
        yield own_db
    settings.cache_clear()
    forget_flags()


async def test_ac_northwind_v3_renders_twice_to_the_same_sealed_draft(loaded: Database) -> None:
    await dispose_engine()
    configure_engine(loaded.app_url)
    seed = Seeder(loaded.superuser_dsn)
    engagement = engagement_id_of(BY_LABEL["A1"])
    v3 = cast(
        UUID,
        await seed.value(
            "SELECT id FROM statement_versions WHERE tenant_id = $1 AND engagement_id = $2 "
            "AND version_no = 3",
            TENANT,
            engagement,
        ),
    )
    hannah = user_id_of(next(x for x in SEATS if x.initials == "HL"))
    person = AuthContext(
        TenantContext(TENANT, "human", str(hannah)), hannah, UUID(int=0), None, system_now()
    )
    documents: list[UUID] = []
    for _ in range(2):
        async with uow(person.tenant) as tx:
            documents.append(await render_statement_draft(tx, person, v3))
    assert documents[0] == documents[1]  # one document per version, a new draft each render

    rows = await seed.rows(
        "SELECT v.mode, v.template_version_id, v.layout_key, v.content_hash, s.snapshot, "
        "v.requested_by_kind, d.kind FROM generated_document_versions v "
        "JOIN generated_documents d ON d.id = v.generated_document_id "
        "JOIN generated_document_snapshots s ON s.version_id = v.id "
        "WHERE d.id = $1 ORDER BY v.version_no",
        documents[0],
    )
    assert [(r["mode"], r["template_version_id"], r["layout_key"], r["kind"]) for r in rows] == [
        ("draft", None, "financial_statements", "fs_package")
    ] * 2
    assert rows[0]["requested_by_kind"] == "human"
    assert rows[0]["content_hash"] == rows[1]["content_hash"]
    snapshot = rows[0]["snapshot"]
    sealed = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
    body = json.dumps(sealed["body"])
    assert "of Net Assets Available for Benefits" in body  # a plan's captions (ebp_audit)
    assert "Changes in Net Assets Available for Benefits" in body
    for leak in LEAKS:
        assert leak not in body
