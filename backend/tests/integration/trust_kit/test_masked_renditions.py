"""P-03-T15 against Postgres and the S3 gateway (SPEC-322 AC-24, AC-25, AC-30, AC-40; P-03 §4.4,
§4.5; DEC-369): "No served page has unmasked pixels inside a detected region, no agent input
contains an unmasked TIN pattern, and agent quotes of masked text still verify."

- The `upload.masked_preview` step burns every detected region of the seeded W-2 into its page;
  the viewer and the legacy page route serve those bytes, and every pixel inside each region is
  one colour. A pre-masking preview answers 409 `preview_outdated`; an unscanned PDF is never
  rendered for serving.
- An image has no text layer: it is served to an onshore reader and refused to an offshore one.
- Agent material (reviewer, matcher) carries tokens only, pages and sheets alike, for every
  initiator; quotes copied from it verify, and the clear value does not.
- The backfill lists uploads without a masked rendition until they have one.
"""

from __future__ import annotations

import io
import uuid
from typing import cast

import pytest
from PIL import Image

from abacus.kernel.tin_patterns import has_tin
from abacus.kernel.uow import uow
from abacus.modules.evidence import viewer
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    match_material,
    record_citations,
    review_material,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.citations.display import citation_display
from abacus.modules.evidence.masked_previews import (
    UNSCANNED,
    PreviewOutdated,
    masked_preview_upload,
    pending_masks,
)
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.previews import pixel_box
from abacus.modules.evidence.processing import preview_upload
from abacus.modules.evidence.uploads import preview_of, preview_page_of
from abacus.modules.evidence.words import words_upload
from abacus.modules.evidence.workflow_types import BackfillInput, UploadInput
from abacus.modules.identity.api import AgentContext, Forbidden, agent_context_for_run
from abacus_tools.synthetic.documents import positioned_pdf, w2_pdf

from .support import Firm, Seeder, as_inbox, as_version, make_firm

SSN = "000-00-6081"
MASKED = "•••-••-6081"
# Synthetic 9xx ITINs: one under a label, one unlabelled but valid (DEC-322's rules).
TINS = positioned_pdf(
    [
        [
            (36.0, 740.0, "Recipient's TIN 900-70-1234"),
            (36.0, 700.0, "Reference 900-71-5555 noted on the account"),
            (36.0, 660.0, "Interest income 1,550.00"),
        ]
    ]
)
SHEET = b"Name,SSN,Note\nClaire Feld,900-70-1234,ok\nJonah Feld,900-72-0001,ref 900-71-5555\n"


async def _processed(firm: Firm, given: UploadInput) -> str:
    await extract_upload(given)
    await words_upload(given)
    await pii_scan_upload(given)
    return await masked_preview_upload(given)


async def _version(firm: Firm, content: bytes, media_type: str = "application/pdf") -> uuid.UUID:
    version = await firm.version(content, media_type)
    await _processed(firm, as_version(firm, version))
    return version


async def _agent(firm: Firm, agent_id: str) -> AgentContext:
    return await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id=agent_id,
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=firm.user_id,
    )


async def _offshore(firm: Firm) -> None:
    await firm.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.user_id,
    )


def _colours(image: Image.Image, box: tuple[float, float, float, float]) -> int:
    left, upper, right, lower = (int(v) for v in box)
    crop = image.convert("RGB").crop((left, upper, right + 1, lower + 1))
    return len(crop.getcolors(maxcolors=crop.width * crop.height) or [])


async def test_ac24_served_pages_have_no_unmasked_pixel_in_a_region(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _version(firm, w2_pdf())
    regions = await seed.rows(
        "SELECT page_no, bbox FROM pii_regions WHERE evidence_version_id = $1", version
    )
    assert len(regions) == 2
    manifest = await viewer.viewer_manifest(firm.person(), version)
    assert (manifest.status, manifest.kind) == ("ready", "pages")
    [page] = manifest.pages
    served = await viewer.viewer_page(firm.person(), version, 1)
    legacy = await preview_page_of(
        firm.system, evidence_version_id=version, inbox_file_id=None, page_no=1
    )
    assert served == legacy  # one masked source for every route
    image = Image.open(io.BytesIO(served))
    assert image.mode == "RGB"
    scale_x, scale_y = image.width / page.width_pt, image.height / page.height_pt
    for row in regions:
        box = cast(tuple[float, float, float, float], tuple(float(v) for v in row["bbox"]))
        pixels = pixel_box(box, scale_x, scale_y, image.width, image.height)
        assert _colours(image, pixels) == 1, box
    stored = await seed.rows(
        "SELECT renderer_version, mask_version FROM upload_previews "
        "WHERE evidence_version_id = $1",
        version,
    )
    assert [tuple(r) for r in stored] == [("v2", "m1")]  # no unmasked rendition was made


async def test_ac24_a_pre_masking_preview_is_outdated_until_re_rendered(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(w2_pdf())
    given = as_version(firm, version)
    await extract_upload(given)
    await preview_upload(given)  # what v3 to v6 runs made
    with pytest.raises(PreviewOutdated):
        await preview_page_of(
            firm.system, evidence_version_id=version, inbox_file_id=None, page_no=1
        )
    with pytest.raises(PreviewOutdated):
        await viewer.viewer_page(firm.person(), version, 1)
    assert [u.source_id for u in await pending_masks(BackfillInput(str(firm.tenant_id)))] == [
        str(version)
    ]
    # The backfill's steps, as `trust_layer_backfill` v2 runs them.
    await words_upload(given)
    await pii_scan_upload(given)
    assert await masked_preview_upload(given) == "pages"
    assert await preview_page_of(
        firm.system, evidence_version_id=version, inbox_file_id=None, page_no=1
    )
    assert await pending_masks(BackfillInput(str(firm.tenant_id))) == []


async def test_ac24_an_unscanned_pdf_is_never_rendered_for_serving(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(w2_pdf())
    given = as_version(firm, version)
    await extract_upload(given)
    await words_upload(given)  # no PII scan
    assert await masked_preview_upload(given) == UNSCANNED
    count = await seed.value(
        "SELECT count(*) FROM upload_previews WHERE evidence_version_id = $1", version
    )
    assert count == 0
    assert await masked_preview_upload(given) == UNSCANNED  # still nothing, still idempotent


async def test_ac30_an_image_is_served_onshore_and_refused_offshore(seed: Seeder) -> None:
    firm = await make_firm(seed)
    picture = io.BytesIO()
    Image.new("RGB", (300, 200), (240, 240, 240)).save(picture, format="PNG")
    version = await _version(firm, picture.getvalue(), "image/png")
    manifest = await viewer.viewer_manifest(firm.person(), version)
    assert manifest.kind == "image" and manifest.pages[0].pii_scan == "not_scannable"
    assert (await viewer.viewer_page(firm.person(), version, 1)).startswith(b"\x89PNG")
    await _offshore(firm)
    with pytest.raises(Forbidden):
        await viewer.viewer_page(firm.person(), version, 1)


async def test_ac25_ac40_reviewer_material_holds_tokens_only(seed: Seeder) -> None:
    firm = await make_firm(seed)
    w2 = await _version(firm, w2_pdf())
    tins = await _version(firm, TINS)
    sheet = await _version(firm, SHEET, "text/csv")
    for version in (w2, tins, sheet):
        material = await review_material(firm.system, version)
        assert material is not None, version
        text = " ".join(material.pages.values()) + " ".join(t for _, t in material.excerpt_pages)
        cells = " ".join(c for rows in material.sheets.values() for row in rows for c in row)
        assert not has_tin(text) and not has_tin(cells), version
        assert SSN not in text
    w2_material = await review_material(firm.system, w2)
    assert w2_material is not None and MASKED in w2_material.pages[1]
    sheet_material = await review_material(firm.system, sheet)
    assert sheet_material is not None
    rows = next(iter(sheet_material.sheets.values()))
    assert rows[1][1] == "•••-••-1234" and rows[2][2] == "ref •••-••-5555"


async def test_ac25_matcher_material_is_masked_for_an_onshore_firm_upload(seed: Seeder) -> None:
    firm = await make_firm(seed)
    inbox = await firm.inbox_file(w2_pdf())
    given = as_inbox(firm, inbox)
    await extract_upload(given)
    await words_upload(given)
    assert await match_material(firm.system, inbox) is None  # before its scan: nothing
    await pii_scan_upload(given)
    material = await match_material(firm.system, inbox)
    assert material is not None
    text = " ".join(material.pages.values())
    assert MASKED in text and SSN not in text and not has_tin(text)
    # The scan re-announces a firm file so the matcher held back at extraction may follow.
    announced = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'inbox_file.extracted'",
        firm.tenant_id,
    )
    assert announced == 2  # at extraction, then after the scan


async def test_ac25_a_quote_of_masked_text_verifies_and_the_clear_value_does_not(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _version(firm, w2_pdf())
    agent = await _agent(firm, "evidence.upload_reviewer")
    anchor = CitationAnchor("workpaper_cell", uuid.uuid4(), "RA!C14", None, firm.engagement_id)
    locator = {"evidence_version_id": str(version), "page": 1}
    async with uow(agent.tenant) as tx:
        masked, clear = await record_citations(
            tx,
            actor=agent,
            anchor=anchor,
            claims=[
                CitationClaim("document_text", locator, quote=MASKED),
                CitationClaim("document_text", locator, quote=SSN),
            ],
        )
    assert (masked.verified, masked.verification_reason) == (True, None)
    assert (clear.verified, clear.verification_reason) == (False, "quote_not_found")
    shown = await citation_display(firm.person(), masked.id)
    assert (shown.quote, shown.quote_state) == (MASKED, "shown")


async def test_legacy_preview_lines_and_sheets_carry_tokens(seed: Seeder) -> None:
    firm = await make_firm(seed)
    w2 = await _version(firm, w2_pdf())
    view = await preview_of(firm.system, evidence_version_id=w2, inbox_file_id=None)
    lines = " ".join(text for page in view.page_lines for text, _ in page)
    assert view.kind == "pages" and "Employee" in lines
    assert SSN not in lines and MASKED in lines
    sheet = await _version(firm, SHEET, "text/csv")
    table = await preview_of(firm.system, evidence_version_id=sheet, inbox_file_id=None)
    cells = " ".join(c for _, rows in table.sheets for row in rows for c in row)
    assert table.kind == "table" and not has_tin(cells) and "Claire Feld" in cells
