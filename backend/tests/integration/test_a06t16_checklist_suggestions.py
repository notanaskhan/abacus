"""A-06-T16 seam (TASK-3395, DEC-2394) against Postgres, on the loaded Brightwater Hale completion
slice: an agent's suggested disclosure answer lands on its item as `suggested` (not counted, a
person's answer never touched), and a person's adoption makes it `adopted` with a field history."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import cast
from uuid import UUID, uuid4

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting import statements
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import TENANT, user_id_of
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


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


async def test_ac_a_suggestion_is_mirrored_never_counted_and_adopted_by_a_person(
    loaded: Database,
) -> None:
    await dispose_engine()
    configure_engine(loaded.app_url)
    seed = Seeder(loaded.superuser_dsn)
    document = cast(
        UUID, await seed.value("SELECT id FROM statement_documents WHERE tenant_id = $1", TENANT)
    )
    pick = (
        "SELECT item_key FROM disclosure_checklist_answers WHERE tenant_id = $1 "
        "AND answer = $2 ORDER BY item_key LIMIT 1"
    )
    yes_key = cast(str, await seed.value(pick, TENANT, "yes"))
    na_key = cast(str, await seed.value(pick, TENANT, "na"))
    # An item nobody has answered yet: the seed answers all 142, so this one starts empty.
    await seed.run(
        "DELETE FROM disclosure_checklist_answers WHERE tenant_id = $1 AND item_key = $2",
        TENANT,
        yes_key,
    )
    system = TenantContext(TENANT, "system", "test:checklist_suggestion")
    first, second = uuid4(), uuid4()

    assert await statements.record_suggested_answer(system, document, yes_key, "no", first)
    assert await statements.record_suggested_answer(system, document, yes_key, "yes", second)
    view = await statements.disclosure_view(system, document)
    item = next(i for i in view.items if i["item_key"] == yes_key)
    assert (item["state"], item["answer"], item["suggestion_id"]) == ("suggested", "yes", second)
    assert (view.answered, view.total) == (141, 142)

    # A person's answer is never touched, N/A is never suggested, an unknown item takes nothing.
    assert not await statements.record_suggested_answer(system, document, na_key, "yes", uuid4())
    assert not await statements.record_suggested_answer(system, document, yes_key, "na", uuid4())
    assert not await statements.record_suggested_answer(system, document, "zz-9", "yes", uuid4())
    kept = await seed.value(
        "SELECT state FROM disclosure_checklist_answers WHERE tenant_id = $1 AND item_key = $2",
        TENANT,
        na_key,
    )
    assert kept == "reviewed"

    hannah = user_id_of(next(x for x in SEATS if x.initials == "HL"))
    person = AuthContext(
        TenantContext(TENANT, "human", str(hannah)), hannah, UUID(int=0), None, system_now()
    )
    with pytest.raises(statements.NoSuggestion):
        async with uow(person.tenant) as tx:
            await statements.apply_suggested_answer(
                tx, person, document, yes_key, "yes",
                suggestion_id=first, edited=False, citation_note=None,
            )  # fmt: skip
    async with uow(person.tenant) as tx:
        await statements.apply_suggested_answer(
            tx, person, document, yes_key, "yes",
            suggestion_id=second, edited=False, citation_note=None,
        )  # fmt: skip
    after = await statements.disclosure_view(person.tenant, document)
    adopted = next(i for i in after.items if i["item_key"] == yes_key)
    assert (adopted["state"], adopted["answer"]) == ("adopted", "yes")
    assert (after.answered, after.total) == (142, 142)
    history = await seed.value(
        "SELECT count(*) FROM field_value_versions v JOIN disclosure_checklist_answers a "
        "ON a.id = v.target_id WHERE a.tenant_id = $1 AND a.item_key = $2 "
        "AND v.suggestion_id = $3",
        TENANT,
        yes_key,
        second,
    )
    assert history == 1
    # Once adopted it is a person's: a later suggestion doesn't land on it.
    assert not await statements.record_suggested_answer(system, document, yes_key, "no", uuid4())
    await dispose_engine()
