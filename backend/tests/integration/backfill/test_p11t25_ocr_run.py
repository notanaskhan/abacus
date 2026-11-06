"""P-11-T25 (TASK-3343; DEC-2375): one scan through the real step, on Postgres and object storage.

Row acceptance: "A scanned W-2 at a flagged firm gets OCR words ... and the version's bytes and
fingerprint never change." The provider is `FakeOcr` over the synthetic corpus. Bug it caught: the
run's audit reference held text, so every read raised before any page was stored.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import cast

import pytest
from PIL import Image

from abacus.kernel.db import TenantContext
from abacus.kernel.ocr import Api, FakeOcr, OcrKeyValue, OcrPage, OcrWord
from abacus.kernel.uow import uow
from abacus.modules.evidence import masked_previews, ocr_gate, ocr_step, pii
from abacus.modules.evidence.api import (
    LongOcr,
    NewItem,
    Provenance,
    add_version,
    masked_pages,
    stage_content,
)
from abacus.modules.evidence.ocr_gate import GateFacts
from abacus.modules.evidence.previews import MASKED_RENDERER_VERSION
from abacus.modules.evidence.repository import rerender_version, rescan_version
from abacus.modules.evidence.words import words_upload
from abacus.modules.evidence.workflow_types import VERSION, BackfillInput, UploadInput
from abacus_tools.synthetic.scanned_corpus import generate, recordings

from .tb_support import Books, books


@pytest.fixture
async def world(net: object, object_store: str) -> Books:
    return await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net`


@pytest.fixture(autouse=True)
def _fake_provider() -> Iterator[None]:
    pages = generate()
    ocr_step.set_provider(FakeOcr(recordings(pages)))
    yield
    ocr_step._provider.clear()  # pyright: ignore[reportPrivateUsage] -- the module's own slot


async def _scan(world: Books) -> tuple[uuid.UUID, str]:
    page = generate()[0]
    stored = await stage_content(world.tenant_id, page.image)
    tenant = TenantContext(world.tenant_id, "human", str(world.senior.user_id))
    async with uow(tenant) as tx:
        version = await add_version(
            tx,
            engagement_id=world.site.engagement_id,
            item=NewItem(title="W-2 scan.png"),
            stored=stored,
            media_type=page.media_type,
            provenance=Provenance(source="firm_upload", method="uploaded"),
            requested_by=world.senior.user_id,
        )
    return version.id, stored.fingerprint


async def _open_gate(_tenant: object, _facts: object) -> None:
    return None


async def _facts(_tenant: object, _engagement: object) -> GateFacts:
    return GateFacts(synthetic_firm=True, tri_scope=False, tri_consented=False)


async def test_ac_a_scan_gets_words_and_an_extraction_and_its_bytes_never_change(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ocr_step, "first_refusal", _open_gate)
    monkeypatch.setattr(ocr_step, "_facts", _facts)
    version, fingerprint = await _scan(world)
    given = UploadInput(str(world.tenant_id), VERSION, str(version))
    assert await ocr_step.ocr_upload(given) == 1
    (page,) = await world.seed.rows(
        "SELECT text_source, ocr_run_id IS NOT NULL AS has_run, word_count > 0 AS worded "
        "FROM evidence_pages WHERE evidence_version_id = $1",
        version,
    )
    assert (page["text_source"], page["has_run"], page["worded"]) == ("ocr", True, True)
    (run,) = await world.seed.rows(
        "SELECT status, page_units FROM ocr_runs WHERE evidence_version_id = $1", version
    )
    assert (run["status"], run["page_units"]) == ("completed", 1)
    (row,) = await world.seed.rows(
        "SELECT extractor_version, status FROM upload_extractions WHERE evidence_version_id = $1",
        version,
    )
    assert (row["extractor_version"], row["status"]) == ("ocr-v1", "extracted")
    assert (
        cast(
            str,
            await world.seed.value(
                "SELECT fingerprint FROM evidence_versions WHERE id = $1", version
            ),
        )
        == fingerprint
    )


async def test_ac_a_firm_over_its_daily_cap_is_refused_and_reads_nothing(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def over(_tenant: object, _pages: int) -> bool:
        return True

    monkeypatch.setattr(ocr_step, "first_refusal", _open_gate)
    monkeypatch.setattr(ocr_step, "_facts", _facts)
    monkeypatch.setattr(ocr_step, "over_daily_cap", over)
    version, _ = await _scan(world)
    given = UploadInput(str(world.tenant_id), VERSION, str(version))
    assert await ocr_step.ocr_upload(given) == 0
    (run,) = await world.seed.rows(
        "SELECT status, refused_reason, page_units FROM ocr_runs WHERE evidence_version_id = $1",
        version,
    )
    assert tuple(run) == ("refused", "quota_exceeded", 0)


class _ScannedW2:
    """A provider for a PDF's one scanned page: the label, and the value far from it, where only
    the form's key-value position anchors it (AC7.3). Counts what it's asked."""

    name = "fake"

    def __init__(self) -> None:
        self.apis: list[str] = []

    async def read(
        self, image: bytes, *, width_pt: Decimal, height_pt: Decimal, api: Api
    ) -> OcrPage:
        del image, width_pt, height_pt
        self.apis.append(api)
        q = Decimal
        words = (
            OcrWord("Employee's", (q(50), q(50), q(100), q(60)), q("0.99")),
            OcrWord("social", (q(102), q(50), q(130), q(60)), q("0.99")),
            OcrWord("security", (q(132), q(50), q(170), q(60)), q("0.99")),
            OcrWord("number", (q(172), q(50), q(210), q(60)), q("0.99")),
            OcrWord("123456789", (q(400), q(400), q(460), q(410)), q("0.99")),
        )
        key_values = (
            ()
            if api == "detect_text"
            else (
                OcrKeyValue(
                    "Employee's social security number",
                    (q(395), q(395), q(470), q(415)),
                    q("0.95"),
                ),
            )
        )
        return OcrPage("sha", words, None, key_values)


def _scanned_pdf() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (612, 792), "white").save(out, format="PDF")
    return out.getvalue()


async def test_ac74_a_page_no_scan_could_read_is_read_masked_and_rendered_again(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC7.3, AC7.4: a scanned PDF first reads `not_scannable`. OCR reads it, the re-scan masks the
    value through the form's key, a new rendition carries the mask, and a second pass changes
    nothing. The first run and rendition stay on file, and the bytes never change."""
    engine = _ScannedW2()
    ocr_step.set_provider(engine)
    stored = await stage_content(world.tenant_id, _scanned_pdf())
    person = TenantContext(world.tenant_id, "human", str(world.senior.user_id))
    async with uow(person) as tx:
        version = (
            await add_version(
                tx,
                engagement_id=world.site.engagement_id,
                item=NewItem(title="W-2 scan.pdf"),
                stored=stored,
                media_type="application/pdf",
                provenance=Provenance(source="firm_upload", method="uploaded"),
                requested_by=world.senior.user_id,
            )
        ).id
    given = UploadInput(str(world.tenant_id), VERSION, str(version))
    assert await words_upload(given) >= 0
    await pii.pii_scan_upload(given)
    (first,) = await world.seed.rows(
        "SELECT detector_version, pages_not_scannable FROM pii_scan_runs "
        "WHERE evidence_version_id = $1",
        version,
    )
    assert list(first["pages_not_scannable"]) == [1]
    await masked_previews.masked_preview_upload(given)
    assert given in await ocr_step.pending_ocr(BackfillInput(str(world.tenant_id)))

    monkeypatch.setattr(ocr_step, "first_refusal", _open_gate)
    monkeypatch.setattr(ocr_step, "_facts", _facts)
    assert await ocr_step.ocr_upload(given) == 1
    assert engine.apis == ["detect_text", "analyze_forms"]
    assert given not in await ocr_step.pending_ocr(BackfillInput(str(world.tenant_id)))
    for _ in range(2):
        await pii.pii_scan_upload(given)
        await masked_previews.masked_preview_upload(given)

    again = rescan_version(pii.DETECTOR_VERSION)
    runs = await world.seed.rows(
        "SELECT detector_version, pages_scanned, pages_not_scannable FROM pii_scan_runs "
        "WHERE evidence_version_id = $1 ORDER BY detector_version",
        version,
    )
    assert [r["detector_version"] for r in runs] == [pii.DETECTOR_VERSION, again]
    assert (list(runs[1]["pages_scanned"]), list(runs[1]["pages_not_scannable"])) == ([1], [])
    (region,) = await world.seed.rows(
        "SELECT last4, label_anchored, detector_version FROM pii_regions "
        "WHERE evidence_version_id = $1",
        version,
    )
    assert tuple(region) == ("6789", True, again)
    tenant = TenantContext(world.tenant_id, "system", "test")
    pages = await masked_pages(tenant, evidence_version_id=version)
    assert pages is not None
    assert "123456789" not in pages[1]
    previews = await world.seed.rows(
        "SELECT renderer_version FROM upload_previews WHERE evidence_version_id = $1 "
        "AND mask_version IS NOT NULL ORDER BY created_at",
        version,
    )
    assert previews[-1]["renderer_version"] == rerender_version(MASKED_RENDERER_VERSION)
    assert len(previews) <= 2
    assert (
        await world.seed.value("SELECT fingerprint FROM evidence_versions WHERE id = $1", version)
        == stored.fingerprint
    )
    forms = await world.seed.rows(
        "SELECT api FROM ocr_runs WHERE evidence_version_id = $1 ORDER BY api", version
    )
    assert [r["api"] for r in forms] == ["analyze_forms", "detect_text"]


async def test_ac_a_long_scan_hands_off_and_the_route_stays_short_otherwise(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[object] = []

    async def dispatched(workflow: object, given: object, **_: object) -> None:
        started.append((workflow, given))

    monkeypatch.setattr(ocr_step, "dispatch", dispatched)
    stored = await stage_content(world.tenant_id, _scanned_pdf())
    person = TenantContext(world.tenant_id, "human", str(world.senior.user_id))
    async with uow(person) as tx:
        version = (
            await add_version(
                tx,
                engagement_id=world.site.engagement_id,
                item=NewItem(title="short.pdf"),
                stored=stored,
                media_type="application/pdf",
                provenance=Provenance(source="firm_upload", method="uploaded"),
                requested_by=world.senior.user_id,
            )
        ).id
    given = UploadInput(str(world.tenant_id), VERSION, str(version))
    await words_upload(given)
    assert await ocr_step.route_ocr(given) == ocr_step.SHORT
    assert started == []
    monkeypatch.setattr(ocr_step, "BACKGROUND_ABOVE_PAGES", 0)
    assert await ocr_step.route_ocr(given) == ocr_step.LONG
    assert started == [(LongOcr, given)]


async def test_ac_a_forms_call_counts_towards_the_next_reads_cap(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    version, _ = await _scan(world)
    tenant = TenantContext(world.tenant_id, "system", "ocr:test")
    await ocr_gate.record_run(
        tenant, evidence_version_id=version, inbox_file_id=None, provider="fake",
        api=ocr_step.FORMS_API, pages=[1, 2], refused=None, synthetic_firm=True, request_ids=[],
    )  # fmt: skip
    monkeypatch.setattr(ocr_gate, "DAILY_PAGE_CAP", 3)
    assert not await ocr_gate.over_daily_cap(tenant, 1)
    assert await ocr_gate.over_daily_cap(tenant, 2)
