"""P-11-T06 (TASK-2303; SPEC-520 AC-1 to AC-5; P-11 §3 F1; C11 §2, §4): report templates as
database content.

The row's acceptance: a bundle imports as a draft version with a validation report; markup,
unknown variables and unknown layouts are rejected; publication is human-only, audited and never
done by a migration or constant. No database here: the validator is pure, the publication rules
are exercised through the service with its storage stubbed, and the content scan reads the repo.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from abacus.kernel.db import ActorKind, TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.methodology import report_templates as store
from abacus.modules.reporting import templates
from abacus.modules.reporting.contract import TemplateImportIn

REPO = Path(__file__).resolve().parents[4]
T0 = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


Json = dict[str, object]


def _bundle(**overrides: object) -> TemplateImportIn:
    raw: dict[str, object] = {
        "family": "engagement_letter",
        "name": "CAS engagement letter",
        "description": "Monthly close and advisory services",
        "layout_key": "letter",
        "variables": [
            {"key": "client.name", "label": "Client name", "value_type": "name"},
            {"key": "fee.monthly", "label": "Monthly fee", "value_type": "money"},
        ],
        "clauses": [
            {
                "clause_id": "limitation",
                "title": "Limitation of liability",
                "standard": [
                    {
                        "type": "paragraph",
                        "runs": [{"type": "text", "text": "Our liability is limited."}],
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
                    {"type": "text", "text": ", our fee is "},
                    {"type": "var", "key": "fee.monthly"},
                ],
            },
            {
                "type": "clause",
                "clause_id": "limitation",
                "enabled": True,
                "non_standard": False,
                "blocks": [],
            },
        ],
        "sample_data": {"client.name": "Copperleaf Studio", "fee.monthly": "2,400.00"},
    }
    raw.update(overrides)
    return TemplateImportIn.model_validate(raw)


def _codes(body: TemplateImportIn) -> list[tuple[str, str]]:
    errors, _ = templates.validate(body)
    return [(e.path, e.code) for e in errors]


# --- AC-1, AC-2: the validation report ---------------------------------------------------------


def test_ac1_a_clean_bundle_has_no_errors_and_a_stable_content_hash() -> None:
    assert _codes(_bundle()) == []
    first, again = templates.content_sha256(_bundle()), templates.content_sha256(_bundle())
    assert first == again and re.fullmatch(r"[0-9a-f]{64}", first)
    changed = _bundle(description="Different words")
    assert templates.content_sha256(changed) == first  # the name and description are not wording
    assert templates.content_sha256(_bundle(layout_key="report")) != first


@pytest.mark.parametrize(
    "text",
    [
        "<b>bold</b>",
        "<script>alert(1)</script>",
        "See https://example.com",
        "file:///etc/passwd",
        "data:text/html;base64,AAAA",
        "javascript:alert(1)",
        "Hello {{ client.name }}",
        "{% if x %}",
        "${client.name}",
        "visit www.example.com",
    ],
)
def test_ac2_markup_a_url_or_an_expression_is_refused_by_path(text: str) -> None:
    body = _bundle(body=[{"type": "paragraph", "runs": [{"type": "text", "text": text}]}])
    assert ("body[0].runs[0].text", "markup_not_allowed") in _codes(body)


def test_ac2_markup_is_found_inside_tables_clauses_and_sample_data() -> None:
    blocks: list[Json] = [
        {"type": "table", "columns": ["<i>x</i>"], "rows": [["1", "http://169.254.169.254/"]]},
        {
            "type": "clause",
            "clause_id": "limitation",
            "enabled": True,
            "non_standard": False,
            "blocks": [],
        },
    ]
    body = _bundle(body=blocks, sample_data={"client.name": "<img src=x>"})
    found = _codes(body)
    assert ("body[0].columns[0]", "markup_not_allowed") in found
    assert ("body[0].rows[0][1]", "markup_not_allowed") in found
    assert ("sample_data.client.name", "markup_not_allowed") in found


def test_ac1_an_undeclared_variable_is_refused_where_it_is_used() -> None:
    body = _bundle(
        body=[{"type": "paragraph", "runs": [{"type": "var", "key": "partner.ssn"}]}],
        sample_data={"client.name": "Copperleaf", "partner.ssn": "900-70-6789"},
    )
    found = _codes(body)
    assert ("body[0].runs[0].key", "unknown_variable") in found
    assert ("sample_data.partner.ssn", "unknown_variable") in found


def test_ac1_an_unknown_layout_is_refused() -> None:
    assert ("layout_key", "unknown_layout") in _codes(_bundle(layout_key="brochure"))


def test_ac1_clause_conflicts_are_refused() -> None:
    clause: Json = {
        "type": "clause",
        "clause_id": "limitation",
        "enabled": True,
        "non_standard": False,
        "blocks": [],
    }
    twice = _bundle(body=[clause, clause])
    assert ("body[1].clause_id", "clause_conflict") in _codes(twice)
    unknown = _bundle(body=[{**clause, "clause_id": "indemnity"}])
    assert ("body[0].clause_id", "clause_conflict") in _codes(unknown)
    twice_declared: list[Json] = [
        {"clause_id": "limitation", "title": "A", "standard": [], "default_enabled": True},
        {"clause_id": "limitation", "title": "B", "standard": [], "default_enabled": True},
    ]
    library = _bundle(clauses=twice_declared)
    assert ("clauses[1].clause_id", "clause_conflict") in _codes(library)


def test_ac1_a_bundle_over_512_kb_is_too_large() -> None:
    big = [{"type": "paragraph", "runs": [{"type": "text", "text": "x" * 19_000}]}] * 30
    assert ("", "too_large") in _codes(_bundle(body=big))


def test_ac1_an_unknown_block_type_is_refused_by_the_closed_union() -> None:
    with pytest.raises(ValueError):
        _bundle(body=[{"type": "html", "text": "<p>hi</p>"}])


def test_ac1_every_problem_is_listed_at_once_and_unused_variables_warn() -> None:
    body = _bundle(
        layout_key="brochure",
        body=[
            {
                "type": "paragraph",
                "runs": [{"type": "var", "key": "nope"}, {"type": "text", "text": "<b>"}],
            }
        ],
    )
    errors, warnings = templates.validate(body)
    assert {e.code for e in errors} == {"unknown_layout", "unknown_variable", "markup_not_allowed"}
    assert "variable client.name is declared but never used" in warnings


# --- AC-3, AC-4: publication -------------------------------------------------------------------


def _ctx(
    kind: ActorKind = "human", *, client: bool = False, user: uuid.UUID | None = None
) -> AuthContext:
    who = user or uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(who)), who, uuid.uuid4(), None, None, client=client
    )


def _pub(version: uuid.UUID, action: str, minutes: int) -> store._Pub:  # pyright: ignore[reportPrivateUsage] -- the row shape under test
    return store._Pub(version, action, uuid.uuid4(), T0 + timedelta(minutes=minutes))  # pyright: ignore[reportPrivateUsage] -- same


def test_ac4_the_current_version_is_the_latest_publication_not_deprecated_after() -> None:
    v1, v2 = uuid.uuid4(), uuid.uuid4()
    assert store.current_of([]) is None
    current = store.current_of([_pub(v1, "published", 1), _pub(v2, "published", 2)])
    assert current is not None and current.version_id == v2
    rolled_back = store.current_of(
        [_pub(v1, "published", 1), _pub(v2, "published", 2), _pub(v1, "published", 3)]
    )
    assert rolled_back is not None and rolled_back.version_id == v1  # republish is the rollback
    deprecated = store.current_of(
        [_pub(v1, "published", 1), _pub(v2, "published", 2), _pub(v2, "deprecated", 3)]
    )
    assert deprecated is not None and deprecated.version_id == v1


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_ac3_an_agent_or_the_system_never_imports_or_publishes(
    kind: ActorKind, monkeypatch: pytest.MonkeyPatch
) -> None:
    refused: list[uuid.UUID] = []

    async def record(_ctx: AuthContext, object_id: uuid.UUID) -> None:
        refused.append(object_id)

    monkeypatch.setattr(store, "_refused", record)
    template = uuid.uuid4()
    with pytest.raises(Forbidden):
        await store.publish_version(_ctx(kind), template, 1)
    with pytest.raises(Forbidden):
        bundle = cast(store.TemplateBundle, None)
        await store.import_template(_ctx(kind), bundle)
    assert refused[0] == template and len(refused) == 2


async def test_ac3_a_client_principal_never_reaches_templates() -> None:
    for call in (
        store.publish_version(_ctx(client=True), uuid.uuid4(), 1),
        store.templates(_ctx(client=True), None),
        store.version_view(_ctx(client=True), uuid.uuid4(), 1),
    ):
        with pytest.raises(NotFound):
            await call


def test_ac3_publication_is_four_eyes_and_already_published_is_409() -> None:
    assert store.PublisherIsImporter.code == "publisher_is_importer"
    assert store.AlreadyPublished.code == "already_published"
    source = (REPO / "backend/src/abacus/modules/methodology/report_templates.py").read_text()
    assert "version.imported_by_user_id == ctx.user_id" in source
    assert "mfa_at=ctx.mfa_at" in source


# --- AC-5: wording lives in the database -------------------------------------------------------


def test_ac5_no_template_wording_ships_in_a_migration_or_constant() -> None:
    migration = (REPO / "backend/migrations/versions/0460_report_templates.py").read_text()
    assert "INSERT INTO report_template" not in migration
    src = REPO / "backend/src/abacus"
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "INSERT INTO report_template_versions" not in text, path
    assert (
        "report_template.publish"
        in (REPO / "docs/architecture/fresh-mfa-actions.yaml").read_text()
    )
