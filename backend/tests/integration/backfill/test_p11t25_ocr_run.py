"""P-11-T25 (TASK-3343; DEC-2375): one scan through the real step, on Postgres and object storage.

Row acceptance: "A scanned W-2 at a flagged firm gets OCR words ... and the version's bytes and
fingerprint never change." The provider is `FakeOcr` over the synthetic corpus. Bug it caught: the
run's audit reference held text, so every read raised before any page was stored.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.ocr import FakeOcr
from abacus.kernel.uow import uow
from abacus.modules.evidence import ocr_step
from abacus.modules.evidence.api import NewItem, Provenance, add_version, stage_content
from abacus.modules.evidence.ocr_gate import GateFacts
from abacus.modules.evidence.workflow_types import VERSION, UploadInput
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
