"""P-03-T13 against Postgres and the S3 gateway (SPEC-322 AC4.1, AC4.8; P-03 §4.4; DEC-322): the
`upload.pii_scan` step over the word layer.

- The seeded W-2's box-a SSN becomes a `pii_regions` row (`ssn`, last four 6081, the value sealed
  with the tenant's key and bound to the region); the scan run lists the page as scanned, and the
  re-read quote shows the mask token.
- A page with no text layer is recorded `not_scannable`, never silently clean.
- The scan is idempotent, and it never runs for a withdrawn version or an active-content PDF.
"""

from __future__ import annotations

import uuid

from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import tenant_session
from abacus.modules.evidence.api import match_material, worth_matching
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.pii import DETECTOR_VERSION, pii_scan_upload, value_context
from abacus.modules.evidence.projection import projection_of
from abacus.modules.evidence.words import words_upload
from abacus_tools.synthetic.documents import pii_corpus, scanned_pdf, w2_pdf

from .support import Firm, Seeder, as_inbox, as_version, make_firm


async def _scanned(firm: Firm, content: bytes) -> tuple[uuid.UUID, int]:
    version = await firm.version(content)
    await firm.extracted(version)
    await words_upload(as_version(firm, version))
    return version, await pii_scan_upload(as_version(firm, version))


async def _runs(firm: Firm, version: uuid.UUID) -> list[tuple[list[int], list[int], int]]:
    rows = await firm.seed.rows(
        "SELECT pages_scanned, pages_not_scannable, region_count FROM pii_scan_runs "
        "WHERE evidence_version_id = $1",
        version,
    )
    return [(list(r[0]), list(r[1]), r[2]) for r in rows]


async def test_ac4_1_the_w2_box_a_ssn_is_a_sealed_region(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version, found = await _scanned(firm, w2_pdf())
    assert found == 2
    rows = await seed.rows(
        "SELECT id, page_no, kind, last4, label_anchored, value_sealed, detector_version "
        "FROM pii_regions WHERE evidence_version_id = $1 ORDER BY kind",
        version,
    )
    assert [(r["kind"], r["last4"], r["label_anchored"]) for r in rows] == [
        ("ein", "0287", True),
        ("ssn", "6081", True),
    ]
    ssn = rows[1]
    assert ssn["detector_version"] == DETECTOR_VERSION
    assert b"6081" not in bytes(ssn["value_sealed"])  # sealed, not stored in the clear
    opened = await open_sealed(
        firm.tenant_id, bytes(ssn["value_sealed"]), value_context(ssn["id"])
    )
    assert opened == b"000006081"
    assert await _runs(firm, version) == [([1], [], 2)]


async def test_ac4_1_the_corpus_is_found_at_recall_one_end_to_end(seed: Seeder) -> None:
    firm = await make_firm(seed)
    for doc in pii_corpus():
        version, found = await _scanned(firm, doc.content)
        rows = await seed.rows(
            "SELECT page_no, kind, last4 FROM pii_regions WHERE evidence_version_id = $1",
            version,
        )
        assert sorted((r[0], r[1], r[2]) for r in rows) == sorted(doc.expected), doc.name
        assert found == len(doc.expected)


async def test_ac4_8_a_page_without_a_text_layer_is_not_scannable_never_clean(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version, found = await _scanned(firm, scanned_pdf(2))
    assert found == 0
    assert await _runs(firm, version) == [([], [1, 2], 0)]
    async with tenant_session(firm.system) as session:
        projection = await projection_of(session, evidence_version_id=version)
    assert [projection.scan_state(n) for n in (1, 2)] == ["not_scannable", "not_scannable"]
    assert projection.words([], 1) is None  # never read: fail closed


async def test_the_scan_is_idempotent(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version, found = await _scanned(firm, w2_pdf())
    again = await pii_scan_upload(as_version(firm, version))
    assert again == found
    assert len(await _runs(firm, version)) == 1
    assert (
        await seed.value(
            "SELECT count(*) FROM pii_regions WHERE evidence_version_id = $1", version
        )
        == found
    )


async def test_a_withdrawn_version_and_an_active_pdf_are_never_scanned(seed: Seeder) -> None:
    firm = await make_firm(seed)
    withdrawn = await firm.version(w2_pdf())
    await firm.extracted(withdrawn)
    await words_upload(as_version(firm, withdrawn))
    await seed.run_untriggered(
        "INSERT INTO evidence_withdrawals (tenant_id, evidence_version_id, engagement_id, "
        "withdrawn_by_user_id, withdrawn_at, erase_after) "
        "VALUES ($1, $2, $3, $4, now(), now() + interval '7 days')",
        firm.tenant_id,
        withdrawn,
        firm.engagement_id,
        firm.user_id,
    )
    assert await pii_scan_upload(as_version(firm, withdrawn)) == 0
    assert await _runs(firm, withdrawn) == []
    # DEC-296: an active-content PDF is kept and never read (its extraction says so).
    active = await firm.version(w2_pdf())
    await firm.extracted(active, status="not_extracted")
    await seed.run(
        "UPDATE upload_extractions SET reason = 'active_content' WHERE evidence_version_id = $1",
        active,
    )
    await words_upload(as_version(firm, active))
    assert await pii_scan_upload(as_version(firm, active)) == 0
    assert await _runs(firm, active) == []
    assert (
        await seed.value(
            "SELECT count(*) FROM pii_regions WHERE evidence_version_id = ANY($1::uuid[])",
            [withdrawn, active],
        )
        == 0
    )


# --- Security review (DEC-322): agents never read a portal drop's PII ----------------------------


async def test_sec3_a_portal_drop_reaches_the_matcher_only_masked_after_its_scan(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    inbox_id = await firm.inbox_file(w2_pdf())
    await seed.run(
        "UPDATE inbox_files SET channel = 'portal_drop', drop_batch_id = $2, "
        "drop_binder_id = $3, drop_key = 'k' WHERE id = $1",
        inbox_id,
        uuid.uuid4(),
        uuid.uuid4(),
    )
    await extract_upload(as_inbox(firm, inbox_id))
    await words_upload(as_inbox(firm, inbox_id))
    # Extracted, not yet scanned: the matcher gets nothing (fail closed).
    assert await match_material(firm.system, inbox_id) is None
    assert await worth_matching(firm.system, inbox_id) is False
    await pii_scan_upload(as_inbox(firm, inbox_id))
    material = await match_material(firm.system, inbox_id)
    assert material is not None
    text = " ".join(material.pages.values()) + " ".join(t for _, t in material.excerpt_pages)
    assert "6081" in text and "000-00-6081" not in text and "00-1230287" not in text
    assert "•••-••-6081" in text
    assert material.sheets == {}
