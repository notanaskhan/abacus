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
import re
import uuid
from typing import cast

import pytest
from PIL import Image

from abacus.kernel.db import tenant_session
from abacus.kernel.tin_patterns import has_tin
from abacus.kernel.uow import uow
from abacus.modules.agents.upload_review import review_material_for
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
from abacus.modules.evidence.previews import MASK_VERSION, MASKED_RENDERER_VERSION, pixel_box
from abacus.modules.evidence.processing import preview_upload
from abacus.modules.evidence.repository import masked_preview_for
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
_APPEARANCE = b"BT /F1 24 Tf 2 6 Td (900-70-1234) Tj ET"
_PAGE = b"BT /F1 12 Tf 72 720 Td (Form W-9 taxpayer identification number) Tj ET"


def _annotated() -> bytes:
    """A W-9 whose TIN is a FreeText annotation (Fill & Sign): only flattening shows it."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R "
        b">> >> /Contents 4 0 R /Annots [6 0 R] >>",
        b"<< /Length %d >>\nstream\n" % len(_PAGE) + _PAGE + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Annot /Subtype /FreeText /Contents (900-70-1234) /DA (/F1 24 Tf) "
        b"/Rect [100 600 300 640] /P 3 0 R /AP << /N 7 0 R >> >>",
        b"<< /Type /XObject /Subtype /Form /BBox [0 0 200 40] /Resources << /Font << /F1 5 0 R "
        b">> >> /Length %d >>\nstream\n" % len(_APPEARANCE) + _APPEARANCE + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for n, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % n + body + b"\nendobj\n")
    start = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, start)
    )
    return out.getvalue()


ANNOTATED = _annotated()
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
    # No unmasked rendition was made; the one stored is the current masker's (review L5).
    assert [tuple(r) for r in stored] == [(MASKED_RENDERER_VERSION, MASK_VERSION)]


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


# --- Security review fix round (DEC-369: M1, L1) ------------------------------------------------


async def test_review_m1_no_sheet_for_an_offshore_initiator_or_a_portal_drop(seed: Seeder) -> None:
    """Cells are masked by heuristic, so they stay out where TASK-1207 and DEC-322 fail closed:
    a run acting for an offshore member, and a client's portal drop."""
    firm = await make_firm(seed)
    sheet = await _version(firm, SHEET, "text/csv")
    onshore = await review_material(firm.system, sheet)
    assert onshore is not None and onshore.sheets  # the onshore control: masked cells
    offshore = await review_material(firm.system, sheet, sheets=False)
    assert offshore is not None and offshore.sheets == {} and offshore.excerpt_tables == ()
    await _offshore(firm)
    agent = await _agent(firm, "evidence.upload_reviewer")
    via_agent = await review_material_for(agent, sheet)
    assert via_agent is not None and via_agent.sheets == {}
    drop = await firm.inbox_file(SHEET, "text/csv")
    await seed.run(
        "UPDATE inbox_files SET channel = 'portal_drop', drop_batch_id = $2, "
        "drop_binder_id = $3, drop_key = 'k' WHERE id = $1",
        drop,
        uuid.uuid4(),
        uuid.uuid4(),
    )
    await extract_upload(as_inbox(firm, drop))
    material = await match_material(firm.system, drop)
    assert material is not None and material.sheets == {}


async def test_review_l1_the_backfill_never_re_announces_an_upload(seed: Seeder) -> None:
    firm = await make_firm(seed)
    announced = (
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'inbox_file.extracted'"
    )
    live = await firm.inbox_file(w2_pdf())
    await _processed(firm, as_inbox(firm, live))
    assert await seed.value(announced, firm.tenant_id) == 2  # extraction, then the scan
    old = await firm.inbox_file(TINS)
    await extract_upload(as_inbox(firm, old))
    [pending] = [
        u
        for u in await pending_masks(BackfillInput(str(firm.tenant_id)))
        if u.source_id == str(old)
    ]
    assert pending.announce is False
    await words_upload(pending)
    await pii_scan_upload(pending)
    assert await seed.value(announced, firm.tenant_id) == 3  # only the old file's extraction


async def test_review_h2_a_filled_annotation_is_masked_in_the_served_page(seed: Seeder) -> None:
    """The FreeText value is flattened into the content, read, detected and burned out."""
    firm = await make_firm(seed)
    version = await _version(firm, ANNOTATED)
    regions = await seed.rows(
        "SELECT kind, last4 FROM pii_regions WHERE evidence_version_id = $1", version
    )
    assert [(r["kind"], r["last4"]) for r in regions] == [("itin", "1234")]
    material = await review_material(firm.system, version)
    assert material is not None and not has_tin(" ".join(material.pages.values()))


@pytest.mark.parametrize(
    "geometry", [b"/CropBox [20 30 600 780]", b"/Rotate 90 /CropBox [20 30 600 780]"]
)
async def test_review_h1_a_cropped_or_rotated_w2_is_served_masked(
    seed: Seeder, geometry: bytes
) -> None:
    """The word layer is in render space, so the served page's regions hold one colour, and the
    legacy JSON's printed lines carry tokens (or, on a rotated page, are left out)."""
    firm = await make_firm(seed)
    content = w2_pdf().replace(b"/MediaBox [0 0 612 792]", b"/MediaBox [0 0 612 792] " + geometry)
    version = await _version(firm, content)
    regions = await seed.rows(
        "SELECT bbox FROM pii_regions WHERE evidence_version_id = $1", version
    )
    assert len(regions) == 2
    [page] = (await viewer.viewer_manifest(firm.person(), version)).pages
    image = Image.open(io.BytesIO(await viewer.viewer_page(firm.person(), version, 1)))
    scale_x, scale_y = image.width / page.width_pt, image.height / page.height_pt
    for row in regions:
        box = cast(tuple[float, float, float, float], tuple(float(v) for v in row["bbox"]))
        assert _colours(image, pixel_box(box, scale_x, scale_y, image.width, image.height)) == 1
    view = await preview_of(firm.system, evidence_version_id=version, inbox_file_id=None)
    lines = " ".join(text for p in view.page_lines for text, _ in p)
    assert SSN not in lines and "00-1230287" not in lines
    if b"Rotate" in geometry:
        assert lines == ""
    else:
        assert MASKED in lines


# --- Security review round 2 (DEC-369: N1, L4, L5) ----------------------------------------------


def _with_image(share: bytes) -> bytes:
    """A W-9-like page: a typed TIN line and a picture (a pasted card) holding a number."""
    picture = io.BytesIO()
    card = Image.new("L", (300, 120), 255)
    for x in range(20, 280, 30):  # dark strokes where the card's digits are
        for y in range(40, 80):
            card.putpixel((x, y), 0)
    card.save(picture, format="PNG")
    raw = card.tobytes()
    page = (
        b"BT /F1 12 Tf 72 720 Td (Recipient's TIN 900-70-1234) Tj ET q " + share + b" cm /Im1 Do Q"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R "
        b">> /XObject << /Im1 6 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(page) + page + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /XObject /Subtype /Image /Width 300 /Height 120 /ColorSpace /DeviceGray "
        b"/BitsPerComponent 8 /Length %d >>\nstream\n" % len(raw) + raw + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for n, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % n + body + b"\nendobj\n")
    start = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, start)
    )
    return out.getvalue()


@pytest.mark.parametrize("share", [b"200 0 0 194 100 300", b"440 0 0 220 80 300"])  # 8%, 20%
async def test_review_n1_an_image_page_is_never_served_offshore(
    seed: Seeder, share: bytes
) -> None:
    """The typed TIN is masked for everyone; the picture can't be read before OCR, so the page
    reads `not_scannable` and an offshore reader is refused it (no image pixels reach them);
    agent material is the masked text only."""
    firm = await make_firm(seed)
    version = await _version(firm, _with_image(share))
    [region] = await seed.rows(
        "SELECT kind, last4 FROM pii_regions WHERE evidence_version_id = $1", version
    )
    assert (region["kind"], region["last4"]) == ("itin", "1234")
    [page] = (await viewer.viewer_manifest(firm.person(), version)).pages
    assert page.pii_scan == "not_scannable"
    assert (await viewer.viewer_page(firm.person(), version, 1)).startswith(b"\x89PNG")  # onshore
    material = await review_material(firm.system, version)
    assert material is not None
    # Text only, masked (pdfplumber prints the apostrophe curly).
    assert material.pages == {1: "Recipient\u2019s TIN •••-••-1234"}
    await _offshore(firm)
    with pytest.raises(Forbidden):
        await viewer.viewer_page(firm.person(), version, 1)


async def test_review_l5_an_earlier_maskers_rendition_is_never_served(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _version(firm, w2_pdf())
    await seed.run(
        "INSERT INTO upload_previews (tenant_id, engagement_id, evidence_version_id, "
        "renderer_version, kind, page_count, truncated, mask_version) SELECT tenant_id, "
        "engagement_id, evidence_version_id, 'v2', kind, page_count, truncated, 'm1' "
        "FROM upload_previews WHERE evidence_version_id = $1",
        version,
    )  # newer, but burned with the old geometry
    async with tenant_session(firm.system) as session:
        current = await masked_preview_for(
            session, version, renderer_version=MASKED_RENDERER_VERSION
        )
    assert current is not None and current.renderer_version == MASKED_RENDERER_VERSION


async def test_review_l4_page_lines_are_left_out_when_a_region_word_is_not_a_token(
    seed: Seeder,
) -> None:
    """The extraction prints the SSN joined to its label (`SSN:000-00-6081`), the word layer as
    its own word: no token matches, so the page's lines are left out rather than shown clear."""
    from abacus.modules.evidence.projection import projection_of
    from abacus.modules.evidence.repository import pages_of
    from abacus.modules.evidence.uploads import masked_page_lines
    from abacus.modules.evidence.words import WORDS_VERSION

    firm = await make_firm(seed)
    version = await _version(firm, w2_pdf())
    async with tenant_session(firm.system) as session:
        projection = await projection_of(session, evidence_version_id=version)
        layer = await pages_of(
            session, evidence_version_id=version, extractor_version=WORDS_VERSION
        )
    box = (0.1, 0.1, 0.9, 0.2)
    clear = ((("a Employee's SSN:000-00-6081", box),),)
    assert await masked_page_lines(firm.tenant_id, clear, projection, layer) == ((),)
    punctuated = ((("SSN (000-00-6081), EIN 00-1230287.", box),),)
    [[(text, _)]] = await masked_page_lines(firm.tenant_id, punctuated, projection, layer)
    assert "6081" in text and "000-00" not in text and "1230287" not in text


async def test_review_r5_a_tin_split_by_a_page_break_is_masked_on_both_pages(
    seed: Seeder,
) -> None:
    """The scan carries a fragment ending one page over to the next page's leading digits."""
    firm = await make_firm(seed)
    content = positioned_pdf(
        [
            [(72.0, 40.0, "Social security number 900-70-")],
            [(72.0, 760.0, "1234 continued")],
        ]
    )
    version = await _version(firm, content)
    rows = await seed.rows(
        "SELECT page_no, kind, last4 FROM pii_regions WHERE evidence_version_id = $1 "
        "ORDER BY page_no",
        version,
    )
    assert [(r["page_no"], r["kind"], r["last4"]) for r in rows] == [
        (1, "ssn", None),
        (2, "ssn", None),
    ]
    material = await review_material(firm.system, version)
    assert material is not None
    text = " ".join(material.pages.values())
    assert "900-70" not in text and "1234" not in text and not has_tin(text)


# --- Ayush, 2026-10-26 (DEC-369): offshore readers get the masked text view only -------------


def _page(content: bytes) -> bytes:
    """One page with Helvetica as /F1 and a grey picture as /Im1, drawn only when the content
    says `/Im1 Do`."""
    picture = b"\x00\xff\xff\x00"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R "
        b">> /XObject << /Im1 6 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray "
        b"/BitsPerComponent 8 /Length 4 >>\nstream\n" + picture + b"\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for n, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % n + body + b"\nendobj\n")
    start = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, start)
    )
    return out.getvalue()


_LABEL = b"BT /F1 9 Tf 100 420 Td (Social security number) Tj ET\n"
_COMB = b"".join(
    b"BT /F1 12 Tf %d 620 Td (%s) Tj ET\n" % (380 + i * 18, bytes([c]))
    for i, c in enumerate(b"900701234")
)
_OUTLINE = (
    b"q 1 w 0 g "
    + b"".join(
        b"%d 400 m %d 414 l %d 414 l S " % (100 + i * 11, 100 + i * 11, 108 + i * 11)
        for i in range(9)
    )
    + b"Q "
)
VARIANTS = {
    "upright_spaced_dashes": b"BT /F1 12 Tf 100 600 Td (SSN 900 - 70 - 1234) Tj ET",
    "upright_dots": b"BT /F1 12 Tf 100 600 Td (SSN 900.70.1234) Tj ET",
    "upright_slashes": b"BT /F1 12 Tf 100 600 Td (SSN 900/70/1234) Tj ET",
    "comb": _LABEL + _COMB,
    "sideways": _LABEL + b"BT /F1 14 Tf 0 1 -1 0 300 300 Tm (900-70-1234) Tj ET",
    "sideways_spaced": _LABEL + b"BT /F1 14 Tf 0 1 -1 0 300 300 Tm (900  70  1234) Tj ET",
    "outlined": _LABEL + _OUTLINE,
    "image_strip": _LABEL + b"q 90 0 0 10.5 100 400 cm /Im1 Do Q",
    "clean": b"BT /F1 12 Tf 100 600 Td (Recipient's TIN 900-70-1234) Tj ET",
}


@pytest.mark.parametrize("variant", list(VARIANTS))
async def test_offshore_reader_gets_masked_text_and_never_a_page_image(
    seed: Seeder, variant: str
) -> None:
    """Every r3 layout variant, and a clean upright page: no page image for the offshore reader
    (403 before anything is read), the masked text with no TIN (spaced or not, nor reversed)."""
    firm = await make_firm(seed)
    version = await _version(firm, _page(VARIANTS[variant]))
    await _offshore(firm)
    manifest = await viewer.viewer_manifest(firm.person(), version)
    assert manifest.view == "text"
    with pytest.raises(Forbidden):
        await viewer.viewer_page(firm.person(), version, 1)
    found = await viewer.viewer_text(firm.person(), version)
    text = " ".join(p.text for p in found.items)
    assert not has_tin(text), text
    assert not re.search(r"9\D{0,3}0\D{0,3}0\D{0,3}7\D{0,3}0", text), text
    assert not re.search(r"4\D{0,3}3\D{0,3}2\D{0,3}1\D{0,3}0\D{0,3}7", text), text  # reversed
    [page] = found.items
    flagged = variant in ("sideways", "sideways_spaced", "outlined", "image_strip")
    assert page.unread is flagged


async def test_onshore_reader_keeps_the_image_view(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _version(firm, _page(VARIANTS["clean"]))
    assert (await viewer.viewer_manifest(firm.person(), version)).view == "images"
    assert (await viewer.viewer_page(firm.person(), version, 1)).startswith(b"\x89PNG")


async def test_the_text_view_of_a_workbook_is_masked_cells(seed: Seeder) -> None:
    firm = await make_firm(seed)
    sheet = await _version(firm, SHEET, "text/csv")
    await _offshore(firm)
    found = await viewer.viewer_text(firm.person(), sheet)
    cells = " ".join(c for s in found.sheets for row in s.rows for c in row)
    assert found.items == [] and "Claire Feld" in cells and not has_tin(cells)
