"""P-03-T05 against Postgres and the S3 gateway (SPEC-322 AC-1, AC-3, AC-32; ADR-166, ADR-104,
ADR-110): `upload.words` gives every page of a PDF upload an `evidence_pages` row and every text
page a sealed layer object; it is idempotent and audited, and the evidence's bytes and
fingerprint never change. The backfill finds what has no layer yet."""

from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import text

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import tenant_session
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import WORDS_VERSION, BackfillInput
from abacus.modules.evidence.models import EvidencePage
from abacus.modules.evidence.repository import pages_of
from abacus.modules.evidence.words import pending_words, read_page_layer, words_upload
from abacus_tools.synthetic.documents import encrypted_pdf, positioned_pdf, scanned_pdf

from .support import MASTER, Seeder, as_inbox, as_version, make_firm

TWO_PAGES = positioned_pdf(
    [
        [(72.0, 700.0, "Total investments 16,500,000.00")],
        [(72.0, 600.0, "Net assets 16,812,400.00")],
    ]
)


async def _pages(firm_tenant: uuid.UUID, version_id: uuid.UUID) -> list[EvidencePage]:
    from abacus.kernel.db import TenantContext

    async with tenant_session(TenantContext(firm_tenant, "system", "test")) as session:
        return list(
            await pages_of(
                session, evidence_version_id=version_id, extractor_version=WORDS_VERSION
            )
        )


async def test_p03t05_ac1_every_text_page_gets_word_boxes_in_page_points(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(TWO_PAGES)
    assert await words_upload(as_version(firm, version)) == 2
    async with tenant_session(firm.system) as session:
        pages = await pages_of(
            session, evidence_version_id=version, extractor_version=WORDS_VERSION
        )
    assert [(p.page_no, p.has_text_layer, p.word_count) for p in pages] == [
        (1, True, 3),
        (2, True, 3),
    ]
    assert (float(pages[0].width_pt), float(pages[0].height_pt), pages[0].rotation) == (
        612.0,
        792.0,
        0,
    )
    layer = await read_page_layer(firm.tenant_id, pages[0])
    assert [w.text for w in layer.words] == ["Total", "investments", "16,500,000.00"]
    assert 80 < layer.words[2].top < layer.words[2].bottom < 100


async def test_p03t05_adr104_the_layer_is_sealed_under_the_firms_key(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(TWO_PAGES)
    await words_upload(as_version(firm, version))
    [page, _] = await _pages(firm.tenant_id, version)
    key, version_id = page.text_layer_key, page.text_layer_version_id
    digest, size = page.text_layer_fingerprint, page.text_layer_size
    assert key is not None and version_id is not None and digest is not None and size
    assert key.startswith(f"tenants/{firm.tenant_id}/")
    stored = storage.StoredObject(key, version_id, digest, size)
    other = await make_firm(seed)
    with pytest.raises(storage.IntegrityError):  # another firm's key never opens it
        await storage.get(other.tenant_id, stored)
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    assert b"16,500,000.00" in await storage.get(firm.tenant_id, stored)


async def test_p03t05_a_scanned_page_is_recorded_without_a_text_layer(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(scanned_pdf(pages=2))
    assert await words_upload(as_version(firm, version)) == 2
    pages = await _pages(firm.tenant_id, version)
    assert [(p.has_text_layer, p.word_count, p.text_layer_key) for p in pages] == [
        (False, 0, None),
        (False, 0, None),
    ]


async def test_p03t05_it_is_idempotent_and_audited_once(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(TWO_PAGES)
    assert await words_upload(as_version(firm, version)) == 2
    assert await words_upload(as_version(firm, version)) == 2
    assert len(await _pages(firm.tenant_id, version)) == 2
    actions = [
        r["action"]
        for r in await seed.rows(
            "SELECT action FROM audit_events WHERE tenant_id = $1 AND action LIKE 'upload.words%'",
            firm.tenant_id,
        )
    ]
    assert actions == ["upload.words_extracted"]


async def test_p03t05_ac32_the_evidence_bytes_and_fingerprint_never_change(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version = await firm.version(TWO_PAGES)
    before = await seed.rows(
        "SELECT fingerprint, storage_key, storage_version_id, size_bytes FROM evidence_versions "
        "WHERE id = $1",
        version,
    )
    await words_upload(as_version(firm, version))
    after = await seed.rows(
        "SELECT fingerprint, storage_key, storage_version_id, size_bytes FROM evidence_versions "
        "WHERE id = $1",
        version,
    )
    assert [dict(r) for r in before] == [dict(r) for r in after]
    row = after[0]
    stored = storage.StoredObject(
        row["storage_key"], row["storage_version_id"], row["fingerprint"], row["size_bytes"]
    )
    content = await storage.get(firm.tenant_id, stored)
    assert content == TWO_PAGES
    assert hashlib.sha256(content).hexdigest() == row["fingerprint"]


async def test_p03t05_an_inbox_file_gets_its_layer_too(seed: Seeder) -> None:
    firm = await make_firm(seed)
    inbox = await firm.inbox_file(TWO_PAGES)
    assert await words_upload(as_inbox(firm, inbox)) == 2
    count = await seed.value(
        "SELECT count(*) FROM evidence_pages WHERE inbox_file_id = $1 AND has_text_layer", inbox
    )
    assert count == 2


async def test_p03t05_locked_and_non_pdf_uploads_write_nothing(seed: Seeder) -> None:
    firm = await make_firm(seed)
    locked = await firm.version(encrypted_pdf())
    sheet = await firm.version(b"a,b\n1,2\n", "text/csv")
    assert await words_upload(as_version(firm, locked)) == 0
    assert await words_upload(as_version(firm, sheet)) == 0
    assert (
        await seed.value(
            "SELECT count(*) FROM evidence_pages WHERE tenant_id = $1", firm.tenant_id
        )
        == 0
    )


async def test_p03t05_the_backfill_lists_readable_pdfs_without_a_layer(seed: Seeder) -> None:
    firm = await make_firm(seed)
    layered = await firm.version(TWO_PAGES)
    waiting = await firm.version(positioned_pdf([[(72.0, 700.0, "Waiting")]]))
    locked = await firm.version(encrypted_pdf())
    for version in (layered, waiting):
        await firm.extracted(version)
    await firm.extracted(locked, "unreadable")
    await words_upload(as_version(firm, layered))
    todo = await pending_words(BackfillInput(str(firm.tenant_id)))
    assert [(u.kind, u.source_id) for u in todo] == [("version", str(waiting))]
    # The cursor moves past what it reached, so a file that yields nothing isn't retried forever.
    assert (
        await pending_words(BackfillInput(str(firm.tenant_id), after_version=str(waiting))) == []
    )


async def test_p03t05_the_layer_rows_are_insert_only(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(TWO_PAGES)
    await words_upload(as_version(firm, version))
    from sqlalchemy.exc import DBAPIError

    from abacus.kernel.uow import Target, uow

    async with uow(firm.system) as tx:
        tx.record("upload.words_extracted", target=Target("evidence_version", version))
    with pytest.raises(DBAPIError, match=r"permission denied|insert-only"):
        async with uow(firm.system) as tx:
            await tx.session.execute(text("UPDATE evidence_pages SET word_count = 0"))
            tx.record("upload.words_extracted", target=Target("evidence_version", version))


async def test_p03t04_extraction_and_previews_still_record_once_after_0109(seed: Seeder) -> None:
    """0109 put `derivation_id` in the one-per-source indexes; the extraction and preview
    inserts name that index again, so each records once and a rerun is a no-op."""
    from abacus.modules.evidence.processing import preview_upload, process_upload

    firm = await make_firm(seed)
    version = await firm.version(TWO_PAGES)
    for _ in range(2):
        assert await process_upload(as_version(firm, version)) == "extracted"
        assert await preview_upload(as_version(firm, version)) == "pages"
    counts = await seed.rows(
        "SELECT (SELECT count(*) FROM upload_extractions WHERE evidence_version_id = $1) AS e, "
        "(SELECT count(*) FROM upload_previews WHERE evidence_version_id = $1) AS p",
        version,
    )
    assert (counts[0]["e"], counts[0]["p"]) == (1, 1)


async def test_review_a_hostile_page_size_writes_rows_without_a_layer(seed: Seeder) -> None:
    """Security review (#1): a 0 x 0 or oversized MediaBox never fails the step (the insert's
    numeric(8, 2) > 0 check would refuse it, and every retry with it)."""
    firm = await make_firm(seed)
    hostile = positioned_pdf([[(72.0, 700.0, "Tiny")], [(72.0, 700.0, "Huge")]])
    hostile = hostile.replace(b"/MediaBox [0 0 612 792]", b"/MediaBox [0 0 0 0]", 1).replace(
        b"/MediaBox [0 0 612 792]", b"/MediaBox [0 0 9000000 9000000]", 1
    )
    version = await firm.version(hostile)
    assert await words_upload(as_version(firm, version)) == 2
    pages = await _pages(firm.tenant_id, version)
    assert [(p.has_text_layer, p.word_count) for p in pages] == [(False, 0), (False, 0)]
