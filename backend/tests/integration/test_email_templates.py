"""P-01-T05 against Postgres (migration 0092): a staff import stores a platform-default version
once, a changed text is the next version, the renderer reads the current one, and versions are
insert-only for every role."""

from __future__ import annotations

import asyncpg
import pytest

from abacus.kernel.db import configure_engine
from abacus.modules.communications.templates import (
    current_version,
    import_platform_version,
    render,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
BODY = "Hi {{recipient_first_name}},\n{{kind_sentence}}: {{app_link}}\n"
USED = ["recipient_first_name", "kind_sentence", "app_link"]


async def test_import_is_idempotent_versioned_and_rendered(migrated_db: MigratedDatabase) -> None:
    configure_engine(migrated_db.app_url)
    first = await import_platform_version(
        "s-1", "notification.mention", "en-US", "{{kind_sentence}}", BODY, USED
    )
    again = await import_platform_version(
        "s-1", "notification.mention", "en-US", "{{kind_sentence}}", BODY, USED
    )
    assert (first.version, first.created) == (1, True)
    assert (again.version, again.created, again.content_sha256) == (1, False, first.content_sha256)
    second = await import_platform_version(
        "s-2", "notification.mention", "en-US", "You were mentioned", BODY, USED
    )
    assert (second.version, second.created) == (2, True)

    found = await current_version("notification.mention")
    assert found is not None and found.version == 2
    out = render(
        found,
        {
            "recipient_first_name": "Hannah",
            "kind_sentence": "Margaret mentioned you",
            "app_link": "x",
        },
    )
    assert out.subject == "You were mentioned"
    assert await current_version("notification.missing") is None


async def test_versions_are_insert_only_even_for_the_owner(migrated_db: MigratedDatabase) -> None:
    configure_engine(migrated_db.app_url)
    await import_platform_version("s-1", "notification.review", "en-US", "S", "B", [])
    seed = Seeder(migrated_db.superuser_dsn)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("UPDATE email_template_versions SET subject = 'changed'")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("DELETE FROM email_template_versions")
