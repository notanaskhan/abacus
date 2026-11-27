# ac-test-author: ayushkbhatia
"""T-06-T49 (TASK-9017; T-06 F7; TAX-11; DEC-6023) on the migrated Postgres. Row acceptance:
"Thumbnails show every page in TAX-11's list, and a page without a template shows the placeholder
rather than a blank."

Ridgeline's 2025 Form 1065 has an approved workbook checkpoint. The firm imports and publishes
(two people, P-11's four eyes) its 1065 face and its Form 8825 face; no other attached form has a
template. TAX-11's page list is the face's pages, then Form 8825's page (drawn, with its fields),
then Form 4562 and the section 199A statement as placeholders (listed, no fields, no image, never
rendered); M-3's pages are not listed below 10,000,000 of total assets and the section 754
statement not without a transfer of interest. The draft PDF carries only drawn pages."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import AuthContext, member_context
from abacus.modules.reporting import templates
from abacus.modules.reporting.api import TemplateImportIn
from abacus.modules.tax import form_pages_service as fp

from .support import Seeder

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def keys() -> Iterator[None]:
    configure_key_service(LocalKeyService(b"t06t49-attached-forms-master-key-0123456"))
    yield
    reset_key_service()


def _face(form: str, name: str, pages: list[tuple[str, str]]) -> TemplateImportIn:
    return TemplateImportIn.model_validate(
        {
            "family": "tax_form_face", "name": f"{name} (TY2025)",
            "description": f"{name} for tax year 2025: draft face, not for filing.",
            "layout_key": "tax_form_face", "body": [],
            "field_manifest": {
                "form": form, "tax_year": 2025,
                "pages": [{"page_key": k, "page_no": i + 1, "title": t}
                          for i, (k, t) in enumerate(pages)],
                "fields": [
                    {"key": f"{k}_name", "page_key": k, "label": "Name of partnership",
                     "box": [0.06, 0.08, 0.66, 0.10], "format": "text",
                     "binding": {"kind": "return_fact", "ref": "entity.name"}}
                    for k, _ in pages
                ],
            },
        }
    )  # fmt: skip


async def _ctx(tenant: uuid.UUID, user: uuid.UUID) -> AuthContext:
    found = await member_context(tenant, user)
    assert found is not None
    return replace(found, mfa_at=datetime.now(UTC))


async def _publish(
    seed: Seeder, importer: AuthContext, publisher: AuthContext, body: object
) -> None:
    made = await templates.import_bundle(importer, cast(TemplateImportIn, body), dry_run=False)
    assert made.ok and made.draft_version_id is not None, made.errors
    template_id = cast(
        uuid.UUID,
        await seed.value(
            "SELECT template_id FROM report_template_versions WHERE id = $1",
            made.draft_version_id,
        ),
    )
    await templates.publish(publisher, template_id, 1)


async def test_t06t49_acceptance_every_page_is_listed_and_a_missing_template_is_a_placeholder(
    seed: Seeder,
) -> None:
    tenant = await seed.firm()
    for flag in ("reporting.generated_documents", "tax.form_preview"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'T-06-T49')",
            tenant,
            flag,
        )
    forget_flags()
    partner = await seed.person(tenant)
    leader = await seed.person(tenant, "practice_leader")
    quality = await seed.person(tenant, "quality_partner")
    site = await seed.site(tenant, partner.user_id, "Ridgeline")
    await seed.member(site, partner, "engagement_partner")
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2025 Form 1065', $5) "
            "RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            partner.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year, engine) VALUES ($1, $2, $3, $4, '1065', 2025, 'cch_axcess')",
        tenant,
        item,
        site.engagement_id,
        site.entity_id,
    )
    await seed.run_untriggered(
        "INSERT INTO checkpoints (id, tenant_id, engagement_id, target_type, target_id, seq, "
        "author_kind, author_ref, cause, status, content_hash) VALUES ($1, $2, $3, "
        "'tax_workbook', $4, 1, 'person', 'Daniel Reyes', 'human_edit', 'approved', $5)",
        uuid.uuid4(),
        tenant,
        site.engagement_id,
        item,
        hashlib.sha256(b"ridgeline-workbook").hexdigest(),
    )
    importer, publisher = await _ctx(tenant, leader.user_id), await _ctx(tenant, quality.user_id)
    face = _face("1065", "Form 1065", [("p1", "Form 1065 page 1"), ("p4", "Schedule K, page 4")])
    rental = _face("8825", "Form 8825", [("p1", "Form 8825 Rental Real Estate Income")])
    await _publish(seed, importer, publisher, face)
    await _publish(seed, importer, publisher, rental)

    reader = await _ctx(tenant, partner.user_id)
    found = await fp.pages(reader, item, None)
    assert [(k, t, found.placeholder(k)) for k, t in found.pages] == [
        ("p1", "Form 1065 page 1", False),
        ("p4", "Schedule K, page 4", False),
        ("f8825_p1", "Form 8825 Rental Real Estate Income", False),
        ("f4562_p1", "Form 4562", True),
        ("f1065_199a_p1", "§199A stmt", True),
    ]
    assert [f.key for f in fp.fields_of(found, "f8825_p1")] == ["f8825_p1_name"]
    for placeholder in ("f4562_p1", "f1065_199a_p1"):
        with pytest.raises(NotFound):
            fp.fields_of(found, placeholder)  # no fields: TAX-11 draws the placeholder
        with pytest.raises(NotFound):
            await fp.page_png(reader, item, placeholder)  # and no image to draw instead

    rendered = await fp.rendered_pages(reader.tenant, found)
    assert rendered == frozenset({"p1", "p4", "f8825_p1"})  # placeholders are never cached
    rows = await seed.rows(
        "SELECT page_key, template_version_id FROM form_page_renders WHERE work_item_id = $1 "
        "ORDER BY page_key",
        item,
    )
    assert len({r["template_version_id"] for r in rows}) == 2  # each page at its own version
    # The draft PDF draws these pages only (tests/golden_render/test_t06t49_attached_render.py).
    assert [k for k, _ in found.drawn] == ["p1", "p4", "f8825_p1"]
    again_rows = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'form_preview.rendered'",
        tenant,
    )
    await fp.pages(reader, item, None)  # every page rendered already: nothing written
    assert await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'form_preview.rendered'",
        tenant,
    ) == again_rows == 1  # fmt: skip

    # A transfer of interest adds the section 754 statement (a placeholder: no template).
    await seed.run_untriggered(
        "INSERT INTO interest_transfers (tenant_id, engagement_id, work_item_id, transfer_date, "
        "from_partner_id, to_partner_id, points) "
        "VALUES ($1, $2, $3, DATE '2025-07-01', $4, $5, 5)",
        tenant,
        site.engagement_id,
        item,
        uuid.uuid4(),
        uuid.uuid4(),
    )
    again = await fp.preview(reader, item, None)
    assert [k for k, _ in again.pages][-1] == "f1065_754_p1"
    assert again.placeholder("f1065_754_p1")
