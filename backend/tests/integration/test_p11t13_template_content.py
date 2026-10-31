"""P-11-T13 (TASK-2515; P-11 §5.4; C11 v1; AGENTS 16) against Postgres: Brightwater Hale's
document templates load through C11's import and publication services.

The row's acceptance: `make seed-demo` publishes every template through the import API into the
synthetic tenant only, and a scan finds no template text in any migration or constant. Also:
every bundle validates with no error and no unused variable, Grace imports and Margaret
publishes (four eyes), the two §7216 consents are separate documents with one purpose each, and
a second load writes nothing.

The load gets its own database (the session's `migrated_db` holds the loader test's E0).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

import pytest

import abacus.modules.organisations.api  # registers member teams and the office list
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.reporting import templates
from abacus.modules.reporting.contract import TemplateImportIn
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.report_templates import BUNDLES, SLICE

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.organisations.api
pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
BACKEND = Path(__file__).resolve().parents[2]
FAMILIES = {
    "engagement_letter": 3,
    "consent_7216": 2,
    "representation_letter": 1,
    "governance_letter": 1,
    "audit_report": 1,
    "review_report": 1,
    "compilation_report": 1,
    "notice_response": 1,
    "delivery_cover_letter": 1,
}


def _texts(raw: object) -> Iterator[str]:
    """Every literal string a bundle's body and clauses carry (text runs, headings, cells)."""
    if isinstance(raw, dict):
        node = cast(dict[str, object], raw)
        for key in ("text", "title"):
            value = node.get(key)
            if isinstance(value, str) and len(value) > 40:
                yield value
        for value in node.values():
            yield from _texts(value)
    elif isinstance(raw, list):
        for value in cast(list[object], raw):
            yield from _texts(value)


@pytest.mark.parametrize("bundle", BUNDLES, ids=[str(b["name"]) for b in BUNDLES])
def test_every_bundle_validates_with_no_error_and_no_unused_variable(
    bundle: dict[str, object],
) -> None:
    body = TemplateImportIn.model_validate(bundle)
    errors, warnings = templates.validate(body)
    assert (errors, warnings) == ([], [])


def test_the_set_covers_every_family_the_row_names() -> None:
    families: dict[str, int] = {}
    for b in BUNDLES:
        families[str(b["family"])] = families.get(str(b["family"]), 0) + 1
    assert families == FAMILIES
    purposes = sorted(
        str(cast(dict[str, object], b["consent"])["purpose"])
        for b in BUNDLES
        if b["family"] == "consent_7216"
    )
    assert purposes == ["ai_disclosure", "use"]  # two documents, one purpose each


def test_no_template_text_is_in_any_migration_or_constant() -> None:
    phrases = sorted({t for b in BUNDLES for t in _texts([b["body"], b.get("clauses", [])])})
    assert len(phrases) >= 10
    roots = (BACKEND / "migrations", BACKEND / "src/abacus")
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for phrase in phrases:
                assert phrase not in text, (path, phrase[:60])


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


@pytest.fixture
async def loaded(own_db: Database, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Database]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(own_db.app_url)
    await loader.load(own_db.superuser_dsn, "E0", slices=(SLICE,), wait=False)
    yield own_db
    await dispose_engine()
    settings.cache_clear()


async def test_the_load_publishes_every_template_into_the_synthetic_tenant_only(
    loaded: Database,
) -> None:
    seed = Seeder(loaded.superuser_dsn)
    rows = await seed.rows(
        "SELECT t.tenant_id, t.name, t.family, v.imported_by_user_id, p.by_user_id "
        "FROM report_templates t JOIN report_template_versions v ON v.template_id = t.id "
        "JOIN report_template_publications p ON p.version_id = v.id AND p.action = 'published'"
    )
    assert {r["tenant_id"] for r in rows} == {TENANT}
    assert sorted(r["name"] for r in rows) == sorted(str(b["name"]) for b in BUNDLES)
    grace = stable_id("user:grace-holloway")
    margaret = stable_id("user:margaret-okonkwo")
    assert {str(r["imported_by_user_id"]) for r in rows} == {grace}
    assert {str(r["by_user_id"]) for r in rows} == {margaret}
    actions = await seed.actions(TENANT)
    assert actions.count("report_template.imported") == len(BUNDLES)
    assert actions.count("report_template.published") == len(BUNDLES)
    again = await loader.load(loaded.superuser_dsn, "E0", slices=(SLICE,), wait=False)
    assert again.replayed == 0
    assert await seed.value("SELECT count(*) FROM report_template_versions") == len(BUNDLES)
