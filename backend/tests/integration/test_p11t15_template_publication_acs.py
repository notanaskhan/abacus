"""P-11-T15 (TASK-2606; SPEC-520 AC-1 to AC-4; P-11 §4.2 "Migration 2", §4.3; ADR-078): the
independent acceptance suite for template import and publication, written from the spec and the
row's acceptance, not from P-11-T06's implementation.

The row's acceptance: "An agent or worker context never publishes, a published version never
changes, and every publication names a person." Everything runs through C11's service layer
(`reporting.templates`) against Postgres, as the routes call it; rows and audit events are read
back as the superuser.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import pytest
from pydantic import ValidationError

from abacus.kernel.config import settings
from abacus.kernel.db import ActorKind, TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import DomainConflict, DomainForbidden, NotFound
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.repository import FirmRole
from abacus.modules.reporting import templates
from abacus.modules.reporting.contract import TemplateImportIn

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

COUNTS = {
    "report_templates": "SELECT count(*) FROM report_templates WHERE tenant_id = $1",
    "report_template_versions": (
        "SELECT count(*) FROM report_template_versions WHERE tenant_id = $1"
    ),
}
STALE = timedelta(minutes=20)  # beyond the matrix's fifteen-minute `mfa_recent`

Json = dict[str, object]


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


def _as(
    who: Person,
    role: str | None,
    *,
    mfa_age: timedelta | None = timedelta(minutes=1),
    actor_kind: str = "human",
    client: bool = False,
) -> AuthContext:
    actor_id = str(who.user_id) if actor_kind == "human" else f"run-{uuid.uuid4().hex[:8]}"
    return AuthContext(
        tenant=TenantContext(
            who.tenant_id,
            cast(ActorKind, actor_kind),
            actor_id,
            on_behalf_of_user_id=None if actor_kind == "human" else who.user_id,
        ),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=cast(FirmRole | None, role),
        mfa_at=None if mfa_age is None else datetime.now(UTC) - mfa_age,
        client=client,
    )


@dataclass(frozen=True)
class Firm:
    seed: Seeder
    tenant: uuid.UUID
    importer: Person  # a quality partner who imports the wording
    publisher: Person  # a practice leader who publishes it (four eyes)
    admin: Person  # a firm admin: may import, may not publish

    async def count(self, table: str) -> int:
        return cast(int, await self.seed.value(COUNTS[table], self.tenant))

    async def publications(self) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT p.action, p.by_user_id, p.mfa_at, v.version_no FROM "
            "report_template_publications p JOIN report_template_versions v ON v.id = "
            "p.version_id WHERE p.tenant_id = $1 ORDER BY p.at, p.id",
            self.tenant,
        )


async def _firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'reporting.generated_documents', 'true', 'p11', 'TASK-2606')",
        tenant,
    )
    people = [await seed.person(tenant) for _ in range(3)]
    return Firm(seed, tenant, *people)


def _bundle(*, name: str = "Audit engagement letter", **overrides: object) -> TemplateImportIn:
    raw: Json = {
        "family": "engagement_letter",
        "name": name,
        "description": "Synthetic wording for the acceptance suite",
        "layout_key": "letter",
        "variables": [
            {"key": "client.name", "label": "Client name", "value_type": "name"},
            {"key": "period.end", "label": "Period end", "value_type": "date"},
        ],
        "clauses": [
            {
                "clause_id": "responsibilities",
                "title": "Our responsibilities",
                "standard": [
                    {
                        "type": "paragraph",
                        "runs": [{"type": "text", "text": "We plan and perform the audit."}],
                    }
                ],
                "default_enabled": True,
            }
        ],
        "body": [
            {"type": "heading", "level": 1, "text": "Engagement letter"},
            {
                "type": "paragraph",
                "runs": [
                    {"type": "text", "text": "Dear "},
                    {"type": "var", "key": "client.name"},
                    {"type": "text", "text": ", for the period ending "},
                    {"type": "var", "key": "period.end"},
                    {"type": "text", "text": "."},
                ],
            },
            {
                "type": "clause",
                "clause_id": "responsibilities",
                "enabled": True,
                "non_standard": False,
                "blocks": [],
            },
        ],
        "sample_data": {"client.name": "Brightwater Hale", "period.end": "2026-12-31"},
    }
    raw.update(overrides)
    return TemplateImportIn.model_validate(raw)


async def _draft(firm: Firm, bundle: TemplateImportIn | None = None) -> uuid.UUID:
    report = await templates.import_bundle(
        _as(firm.importer, "quality_partner"), bundle or _bundle(), dry_run=False
    )
    assert report.ok and report.draft_version_id is not None, report
    template_id = await firm.seed.value(
        "SELECT template_id FROM report_template_versions WHERE id = $1", report.draft_version_id
    )
    return cast(uuid.UUID, template_id)


def _codes(report: object) -> set[tuple[str, str]]:
    return {(e.path, e.code) for e in getattr(report, "errors", [])}


# AC-1 and AC-2: the import report


async def test_ac1_a_dry_run_lists_every_error_by_path_and_stores_nothing(seed: Seeder) -> None:
    firm = await _firm(seed)
    body: list[Json] = [
        {"type": "heading", "level": 1, "text": "<b>Engagement</b> letter"},
        {"type": "paragraph", "runs": [{"type": "var", "key": "fee.annual"}]},
        {
            "type": "clause",
            "clause_id": "indemnity",
            "enabled": True,
            "non_standard": False,
            "blocks": [],
        },
    ]
    bundle = _bundle(layout_key="brochure", body=body)
    report = await templates.import_bundle(
        _as(firm.importer, "quality_partner"), bundle, dry_run=True
    )
    assert not report.ok
    assert report.draft_version_id is None
    codes = {code for _, code in _codes(report)}
    assert {"unknown_layout", "markup_not_allowed", "unknown_variable", "clause_conflict"} <= codes
    assert all(path for path, code in _codes(report) if code != "too_large")
    for table in ("report_templates", "report_template_versions"):
        assert await firm.count(table) == 0


async def test_ac1_a_clean_dry_run_is_ok_and_still_stores_nothing(seed: Seeder) -> None:
    firm = await _firm(seed)
    report = await templates.import_bundle(
        _as(firm.importer, "quality_partner"), _bundle(), dry_run=True
    )
    assert (report.ok, report.errors, report.draft_version_id) == (True, [], None)
    assert await firm.count("report_template_versions") == 0


def test_ac1_an_unknown_block_type_never_reaches_the_service() -> None:
    with pytest.raises(ValidationError):
        _bundle(body=[{"type": "script", "text": "alert(1)"}])


@pytest.mark.parametrize(
    "text",
    [
        "<script>alert(1)</script>",
        "<style>p{color:red}</style>",
        "See https://example.test/terms",
        "Visit www.example.test",
        "{{ client.name }}",
        "{% if fee %}",
        "${client.name}",
        "<% fee %>",
        "javascript:void(0)",
    ],
)
async def test_ac2_markup_a_url_or_an_expression_is_refused(seed: Seeder, text: str) -> None:
    firm = await _firm(seed)
    bundle = _bundle(
        body=[{"type": "paragraph", "runs": [{"type": "text", "text": text}]}],
        variables=[],
        sample_data={},
    )
    report = await templates.import_bundle(
        _as(firm.importer, "quality_partner"), bundle, dry_run=False
    )
    assert not report.ok
    assert ("body[0].runs[0].text", "markup_not_allowed") in _codes(report)
    assert await firm.count("report_template_versions") == 0


async def test_ac2_markup_inside_a_clause_or_sample_data_is_refused(seed: Seeder) -> None:
    firm = await _firm(seed)
    bundle = _bundle(sample_data={"client.name": "<img src=x>", "period.end": "2026-12-31"})
    report = await templates.import_bundle(
        _as(firm.importer, "quality_partner"), bundle, dry_run=True
    )
    assert ("sample_data.client.name", "markup_not_allowed") in _codes(report)


async def test_ac1_an_import_is_an_insert_only_draft_audited_naming_the_importer(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    row = (
        await seed.rows(
            "SELECT version_no, content_sha256, imported_by_user_id FROM "
            "report_template_versions WHERE template_id = $1",
            template_id,
        )
    )[0]
    assert row["version_no"] == 1
    assert len(row["content_sha256"]) == 64
    assert row["imported_by_user_id"] == firm.importer.user_id
    assert await firm.publications() == []  # a draft: nothing is current
    events = await seed.events(firm.tenant)
    imported = [e for e in events if e.action == "report_template.imported"]
    assert len(imported) == 1
    assert (imported[0].actor_kind, imported[0].actor_id) == ("human", str(firm.importer.user_id))


# AC-3: who publishes


async def test_ac3_a_practice_leader_with_a_fresh_second_factor_publishes(seed: Seeder) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    out = await templates.publish(_as(firm.publisher, "practice_leader"), template_id, 1)
    assert [(p.action, p.by) for p in out.publications][-1][0] == "published"
    rows = await firm.publications()
    assert [(r["action"], r["by_user_id"], r["version_no"]) for r in rows] == [
        ("published", firm.publisher.user_id, 1)
    ]
    assert rows[0]["mfa_at"] is not None
    published = [
        e for e in await seed.events(firm.tenant) if e.action == "report_template.published"
    ]
    assert [(e.actor_kind, e.actor_id) for e in published] == [
        ("human", str(firm.publisher.user_id))
    ]


async def test_ac3_a_quality_partner_publishes_too(seed: Seeder) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    await templates.publish(_as(firm.publisher, "quality_partner"), template_id, 1)
    assert len(await firm.publications()) == 1


@pytest.mark.parametrize("mfa_age", [STALE, None])
async def test_ac3_a_stale_or_missing_second_factor_never_publishes(
    seed: Seeder, mfa_age: timedelta | None
) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    with pytest.raises(Forbidden):
        await templates.publish(
            _as(firm.publisher, "practice_leader", mfa_age=mfa_age), template_id, 1
        )
    assert await firm.publications() == []


@pytest.mark.parametrize("actor_kind", ["agent", "system", "support"])
async def test_ac3_an_agent_worker_or_support_context_never_publishes(
    seed: Seeder, actor_kind: str
) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    with pytest.raises(Forbidden):
        await templates.publish(
            _as(firm.publisher, "practice_leader", actor_kind=actor_kind), template_id, 1
        )
    assert await firm.publications() == []
    assert not [
        e for e in await seed.events(firm.tenant) if e.action == "report_template.published"
    ]
    refused = [
        e for e in await seed.events(firm.tenant) if e.action == "decision.refused_non_human"
    ]
    assert len(refused) == 1


@pytest.mark.parametrize("actor_kind", ["agent", "system"])
async def test_ac3_an_agent_or_worker_context_never_imports(seed: Seeder, actor_kind: str) -> None:
    firm = await _firm(seed)
    with pytest.raises(Forbidden):
        await templates.import_bundle(
            _as(firm.importer, "quality_partner", actor_kind=actor_kind), _bundle(), dry_run=False
        )
    assert await firm.count("report_template_versions") == 0


@pytest.mark.parametrize("role", ["firm_admin", "manager", "staff", None])
async def test_ac3_roles_outside_the_publishers_never_publish(
    seed: Seeder, role: str | None
) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    with pytest.raises(Forbidden):
        await templates.publish(_as(firm.admin, role), template_id, 1)
    assert await firm.publications() == []


async def test_ac3_a_client_principal_never_reaches_a_template(seed: Seeder) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    client = _as(firm.publisher, None, client=True)
    with pytest.raises(NotFound):
        await templates.publish(client, template_id, 1)
    with pytest.raises(NotFound):
        await templates.import_bundle(client, _bundle(name="Other"), dry_run=True)
    with pytest.raises(NotFound):
        await templates.version(client, template_id, 1)
    assert await firm.publications() == []


async def test_ac3_the_importer_never_publishes_their_own_wording(seed: Seeder) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    with pytest.raises(DomainForbidden) as refused:
        await templates.publish(_as(firm.importer, "quality_partner"), template_id, 1)
    assert refused.value.code == "publisher_is_importer"
    assert await firm.publications() == []


async def test_ac3_another_firm_never_publishes_this_firms_template(seed: Seeder) -> None:
    firm, other = await _firm(seed), await _firm(seed)
    template_id = await _draft(firm)
    with pytest.raises(NotFound):
        await templates.publish(_as(other.publisher, "practice_leader"), template_id, 1)
    assert await firm.publications() == []


# AC-4: a published version never changes


async def test_ac4_a_correction_is_a_new_version_and_the_published_one_is_untouched(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    leader = _as(firm.publisher, "practice_leader")
    published = await templates.publish(leader, template_id, 1)
    corrected = _bundle(
        clauses=[
            {
                "clause_id": "responsibilities",
                "title": "Our responsibilities",
                "standard": [
                    {
                        "type": "paragraph",
                        "runs": [{"type": "text", "text": "We plan and perform the review."}],
                    }
                ],
                "default_enabled": True,
            }
        ]
    )
    report = await templates.import_bundle(
        _as(firm.importer, "quality_partner"), corrected, dry_run=False
    )
    assert report.ok
    again = await templates.version(leader, template_id, 1)
    assert again.content_sha256 == published.content_sha256
    assert again.clauses == published.clauses
    second = await templates.version(leader, template_id, 2)
    assert second.content_sha256 != published.content_sha256
    listing = await templates.listing(leader, "engagement_letter")
    assert [t.current_version for t in listing.items] == [1]  # the draft is not current


async def test_ac4_the_same_content_twice_stores_no_second_version(seed: Seeder) -> None:
    firm = await _firm(seed)
    await _draft(firm)
    report = await templates.import_bundle(
        _as(firm.importer, "quality_partner"), _bundle(), dry_run=False
    )
    assert report.ok
    assert await firm.count("report_template_versions") == 1


async def test_ac4_republishing_a_prior_version_rolls_back_without_a_deploy(seed: Seeder) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    leader = _as(firm.publisher, "practice_leader")
    await templates.publish(leader, template_id, 1)
    second = {"client.name": "Copperleaf", "period.end": "2026-12-31"}
    await _draft(firm, _bundle(sample_data=second))
    await templates.publish(leader, template_id, 2)
    await templates.publish(leader, template_id, 1)  # the rollback: a new publication row
    listing = await templates.listing(leader, "engagement_letter")
    assert [t.current_version for t in listing.items] == [1]
    assert [r["version_no"] for r in await firm.publications()] == [1, 2, 1]


async def test_ac4_publishing_the_current_version_again_is_409(seed: Seeder) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    leader = _as(firm.publisher, "practice_leader")
    await templates.publish(leader, template_id, 1)
    with pytest.raises(DomainConflict) as conflict:
        await templates.publish(leader, template_id, 1)
    assert conflict.value.code == "already_published"
    assert len(await firm.publications()) == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE report_template_versions SET body = '[]'::jsonb WHERE template_id = $1",
        "DELETE FROM report_template_versions WHERE template_id = $1",
        "UPDATE report_template_publications SET by_user_id = NULL WHERE version_id IN "
        "(SELECT id FROM report_template_versions WHERE template_id = $1)",
        "DELETE FROM report_template_publications WHERE version_id IN "
        "(SELECT id FROM report_template_versions WHERE template_id = $1)",
    ],
)
async def test_ac4_no_role_changes_a_published_version_or_its_publication(
    seed: Seeder, statement: str
) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    await templates.publish(_as(firm.publisher, "practice_leader"), template_id, 1)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(statement, template_id)  # the superuser too
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            firm.tenant, ("human", str(firm.publisher.user_id)), statement, template_id
        )
    assert len(await firm.publications()) == 1


# The row's acceptance: every publication names a person


async def test_every_publication_names_a_person_and_their_second_factor(seed: Seeder) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    leader = _as(firm.publisher, "practice_leader")
    await templates.publish(leader, template_id, 1)
    await templates.deprecate(leader, template_id, 1)
    await templates.publish(leader, template_id, 1)
    rows = await firm.publications()
    assert [r["action"] for r in rows] == ["published", "deprecated", "published"]
    assert all(r["by_user_id"] == firm.publisher.user_id and r["mfa_at"] for r in rows)
    out = await templates.version(leader, template_id, 1)
    assert all(p.by for p in out.publications)
    events = [
        e
        for e in await seed.events(firm.tenant)
        if e.action in {"report_template.published", "report_template.deprecated"}
    ]
    assert len(events) == 3
    assert {(e.actor_kind, e.actor_id) for e in events} == {("human", str(firm.publisher.user_id))}


async def test_a_publication_without_a_person_never_reaches_a_row(seed: Seeder) -> None:
    firm = await _firm(seed)
    template_id = await _draft(firm)
    version = await seed.value(
        "SELECT id FROM report_template_versions WHERE template_id = $1", template_id
    )
    for by, mfa in ((None, datetime.now(UTC)), (firm.publisher.user_id, None)):
        with pytest.raises((asyncpg.NotNullViolationError, asyncpg.CheckViolationError)):
            await seed.as_actor(
                firm.tenant,
                ("human", str(firm.publisher.user_id)),
                "INSERT INTO report_template_publications (tenant_id, version_id, action, "
                "by_user_id, mfa_at) VALUES ($1, $2, 'published', $3, $4)",
                firm.tenant,
                version,
                by,
                mfa,
            )
    assert await firm.publications() == []
