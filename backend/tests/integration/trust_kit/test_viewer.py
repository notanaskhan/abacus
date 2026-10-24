"""P-03-T09 against Postgres and the S3 gateway (SPEC-322 AC-16, AC-21, AC-22, AC-24; C4 §3.3,
§3.4; DEC-266): the viewer manifest carries geometry and mask tokens only; a page is served only
from a masked rendition (none exists before P-03-T15, so the interim answer is 409
`preview_outdated`) and its read is logged; regions come from verified citations; search answers
rects only and never logs the query; walls answer 404 and clients 403."""

from __future__ import annotations

import dataclasses
import json
import uuid

import pytest
from structlog.testing import capture_logs

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.evidence import viewer
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    process_upload,
    record_citations,
)
from abacus.modules.evidence.processing import preview_upload
from abacus.modules.evidence.viewer import (
    PreviewOutdated,
    viewer_manifest,
    viewer_page,
    viewer_regions,
    viewer_search,
)
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import Forbidden
from abacus_tools.synthetic.documents import encrypted_pdf, positioned_pdf

from .support import Firm, Seeder, as_version, make_firm, scanned

STATEMENT = positioned_pdf(
    [
        [(72.0, 700.0, "Harborline statement")],
        [(72.0, 700.0, "Employee SSN 000-00-6081 on file")],
        [(72.0, 700.0, "Total investments 16,500,000.00"), (72.0, 600.0, "Total investments")],
    ]
)


async def _rendered(firm: Firm, content: bytes = STATEMENT) -> uuid.UUID:
    version = await firm.version(content)
    given = as_version(firm, version)
    await process_upload(given)
    await words_upload(given)
    await preview_upload(given)
    return version


async def _masked(seed: Seeder, firm: Firm, version: uuid.UUID) -> uuid.UUID:
    """A masked rendition of the version (what P-03-T15 writes), over the same page images."""
    masked = await seed.id(
        "INSERT INTO upload_previews (tenant_id, engagement_id, evidence_version_id, "
        "renderer_version, kind, page_count, truncated, mask_version) SELECT tenant_id, "
        "engagement_id, evidence_version_id, 'v99', kind, page_count, truncated, 'k1' "
        "FROM upload_previews WHERE evidence_version_id = $1 RETURNING id",
        version,
    )
    await seed.run(
        "INSERT INTO upload_preview_pages (tenant_id, preview_id, page_no, storage_key, "
        "storage_version_id, fingerprint, size_bytes, width, height) SELECT p.tenant_id, $2, "
        "p.page_no, p.storage_key, p.storage_version_id, p.fingerprint, p.size_bytes, p.width, "
        "p.height FROM upload_preview_pages p JOIN upload_previews v ON v.id = p.preview_id "
        "WHERE v.evidence_version_id = $1 AND v.mask_version IS NULL",
        version,
        masked,
    )
    return masked


async def _ssn_region(seed: Seeder, firm: Firm, version: uuid.UUID) -> None:
    """T13 writes these; seeded over the SSN's words on page 2 (wide enough to cover them)."""
    await seed.run(
        "INSERT INTO pii_regions (tenant_id, evidence_version_id, page_no, bbox, kind, "
        "value_sealed, last4, label_anchored, detector_version) VALUES ($1, $2, 2, "
        "ARRAY[130, 80, 200, 100]::numeric[], 'ssn', '\\x00'::bytea, '6081', true, 'd1')",
        firm.tenant_id,
        version,
    )


async def test_ac16_the_manifest_is_geometry_and_tokens_and_processing_until_masked(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    await _ssn_region(seed, firm, version)
    manifest = await viewer_manifest(firm.person(), version)
    # The interim rule (DEC-266): no masked rendition yet.
    assert (manifest.status, manifest.reason, manifest.kind) == (
        "processing",
        "preview_outdated",
        "pages",
    )
    assert manifest.page_count == 3 and [p.n for p in manifest.pages] == [1, 2, 3]
    page = manifest.pages[0]
    assert (page.image_w, page.text_layer, page.pii_scan) == (1240, True, "not_scannable")
    assert page.width_pt > 0 and page.image_h > 0
    [mask] = manifest.pii_masks
    assert (mask.page, mask.kind, mask.display) == (2, "ssn", "•••-••-6081")
    dumped = json.dumps(dataclasses.asdict(manifest), default=str)
    for text in ("Harborline", "Employee", "000-00", "investments"):
        assert text not in dumped  # geometry and tokens only, never text
    await _masked(seed, firm, version)
    ready = await viewer_manifest(firm.person(), version)
    assert (ready.status, ready.reason) == ("ready", None)


async def test_ac16_password_protected_and_unprocessed_versions(seed: Seeder) -> None:
    firm = await make_firm(seed)
    locked = await _rendered(firm, encrypted_pdf())
    found = await viewer_manifest(firm.person(), locked)
    assert (found.status, found.kind, found.pages) == ("password_protected", "none", [])
    fresh = await firm.version(STATEMENT)  # nothing rendered yet
    assert (await viewer_manifest(firm.person(), fresh)).status == "processing"


async def test_ac24_no_unmasked_page_is_ever_served(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    with pytest.raises(PreviewOutdated):
        await viewer_page(firm.person(), version, 1)
    reads = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1", firm.tenant_id
    )
    assert reads == 0  # nothing served, nothing logged as read
    unrendered = await firm.version(STATEMENT)
    with pytest.raises(NotFound):
        await viewer_page(firm.person(), unrendered, 1)


async def test_ac24_a_masked_page_is_served_after_its_read_is_logged(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    await _masked(seed, firm, version)
    png = await viewer_page(firm.person(), version, 1)
    assert png.startswith(b"\x89PNG")
    [event] = await seed.rows(
        "SELECT kind, subject_type, subject_id, engagement_id FROM access_events "
        "WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert (event["kind"], event["subject_type"], event["subject_id"]) == (
        "evidence_content.read",
        "evidence_version",
        version,
    )
    with pytest.raises(NotFound):
        await viewer_page(firm.person(), version, 9)


async def test_ac22_walls_answer_404_and_clients_403(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    client_id = await seed.id(
        "SELECT client_id FROM engagements WHERE id = $1", firm.engagement_id
    )
    walled = await firm.outsider()
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant_id,
        walled,
        client_id,
        firm.user_id,
    )
    for reader in (firm.person(walled), firm.person(await firm.outsider())):
        with pytest.raises(NotFound):
            await viewer_manifest(reader, version)
    elsewhere = await make_firm(seed)
    with pytest.raises(NotFound):
        await viewer_manifest(elsewhere.person(), version)
    client = dataclasses.replace(firm.person(), client=True)
    with pytest.raises(Forbidden) as refused:
        await viewer_manifest(client, version)
    assert refused.value.layer == "role"


async def test_regions_come_from_verified_citations_into_the_version(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    me = firm.person()
    async with uow(me.tenant) as tx:
        cited = await record_citations(
            tx,
            actor=me,
            anchor=CitationAnchor(
                "workpaper_cell", uuid.uuid4(), "TB!C9", None, firm.engagement_id
            ),
            claims=[
                CitationClaim(
                    "document_text",
                    {"evidence_version_id": str(version), "page": 3},
                    value="16,500,000.00",
                ),
                CitationClaim(
                    "document_text",
                    {"evidence_version_id": str(version), "page": 3},
                    quote="Total liabilities",
                ),
            ],
        )
    assert [c.verified for c in cited] == [True, False]
    match = str(cited[0].match_id)
    [region] = await viewer_regions(me, version, [match])
    assert (region.match_id, region.page, region.citation_id) == (match, 3, cited[0].id)
    assert len(region.rects) == 1 and region.label == "16,500,000.00"
    assert [r.match_id for r in await viewer_regions(me, version, None)] == [match]
    assert await viewer_regions(me, version, ["ev:nothing#p1"]) == []


async def test_ac21_search_answers_rects_only_never_logs_the_query_and_skips_masks(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await _rendered(firm)
    await _ssn_region(seed, firm, version)
    await scanned(seed, firm, [1, 2, 3], version=version)
    with capture_logs() as logs:
        found = await viewer_search(firm.person(), version, "total investments")
    assert (found.total, found.truncated) == (2, False)
    assert [h.page for h in found.items] == [3, 3]
    assert all(len(h.rects) == 1 and len(h.rects[0]) == 4 for h in found.items)
    assert "total investments" not in json.dumps(logs, default=str).casefold()
    assert "investments" not in json.dumps(dataclasses.asdict(found))
    # A masked value isn't found by its digits.
    assert (await viewer_search(firm.person(), version, "000-00-6081")).total == 0
    assert (await viewer_search(firm.person(), version, "investment")).total == 0  # whole words


async def test_search_fails_closed_on_pages_no_pii_scan_covers(seed: Seeder) -> None:
    """Security review #1: an unscanned page is never searched (no SSN oracle)."""
    firm = await make_firm(seed)
    version = await _rendered(firm)
    with pytest.raises(PreviewOutdated):
        await viewer_search(firm.person(), version, "000-00-6081")
    await scanned(seed, firm, [1, 3], version=version)  # page 2 holds the SSN, unscanned
    assert (await viewer_search(firm.person(), version, "000-00-6081")).total == 0
    assert (await viewer_search(firm.person(), version, "Harborline statement")).total == 1
    manifest = await viewer_manifest(firm.person(), version)
    assert [p.pii_scan for p in manifest.pages] == ["done", "not_scannable", "done"]


async def test_search_leaves_an_access_event_and_never_the_query(seed: Seeder) -> None:
    """Security review #2: a search is an oracle for content; that it ran is logged."""
    firm = await make_firm(seed)
    version = await _rendered(firm)
    await scanned(seed, firm, [1, 2, 3], version=version)
    await viewer_search(firm.person(), version, "Net assets nowhere")
    rows = await seed.rows(
        "SELECT kind, subject_type, subject_id, row_to_json(a)::text AS whole "
        "FROM access_events a WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert [(r["kind"], r["subject_type"], r["subject_id"]) for r in rows] == [
        ("evidence_content.read", "evidence_version", version)
    ]
    assert "nowhere" not in rows[0]["whole"]


async def test_search_needs_three_characters_and_caps_its_pages(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Security review #4: a minimum query and a page cap bound each search's cost."""
    firm = await make_firm(seed)
    version = await _rendered(firm)
    await scanned(seed, firm, [1, 2, 3], version=version)
    short = await viewer_search(firm.person(), version, "to")
    assert (short.items, short.total, short.truncated) == ([], 0, False)
    assert (
        await seed.value("SELECT count(*) FROM access_events WHERE tenant_id = $1", firm.tenant_id)
        == 0
    )  # nothing was read
    monkeypatch.setattr(viewer, "MAX_SEARCH_PAGES", 2)
    capped = await viewer_search(firm.person(), version, "total investments")
    assert (capped.total, capped.truncated) == (0, True)  # both hits are on page 3
