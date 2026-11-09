"""S33 partials round (P-11-T36; DEC-3139): the TABLES pages count against the daily cap before
any is sent (a refused pass records its refusal and reads nothing), and an intake attachment's
tables are not read at all (its filed version is read on its own)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.kernel.ocr import OcrPage, OcrWord
from abacus.modules.evidence import ocr_step
from abacus.modules.evidence.ocr_normalise import PageImage
from abacus.modules.evidence.workflow_types import INBOX, INTAKE, VERSION, UploadInput

TENANT = uuid.uuid4()
WORDS = tuple(
    OcrWord(t, (Decimal(10 * i), Decimal(10), Decimal(10 * i + 9), Decimal(20)), Decimal("0.99"))
    for i, t in enumerate(["Statement", "period", "Ending", "balance", "15,600.00"])
)


class Engine:
    name = "fake"

    def __init__(self) -> None:
        self.apis: list[str] = []

    async def read(
        self, _png: bytes, *, width_pt: Decimal, height_pt: Decimal, api: str
    ) -> OcrPage:
        del width_pt, height_pt
        self.apis.append(api)
        return OcrPage("sha", WORDS, None)


def _wire(
    monkeypatch: pytest.MonkeyPatch, *, over_on: int | None
) -> tuple[Engine, list[dict[str, Any]]]:
    engine = Engine()
    runs: list[dict[str, Any]] = []  # Any: record_run's keyword arguments

    async def nothing(*_a: object, **_k: object) -> None:
        return None

    async def facts(*_a: object) -> object:
        return SimpleNamespace(synthetic_firm=True)

    async def over(_t: object, pages: int) -> bool:
        return over_on is not None and pages >= over_on

    async def record(_t: object, **kw: object) -> uuid.UUID:
        runs.append(kw)
        return uuid.uuid4()

    async def raster(*_a: object) -> list[PageImage]:
        return [PageImage(1, b"png", 612.0, 792.0)]

    async def variant(*_a: object) -> str:
        return "all"

    async def put(*_a: object, **_k: object) -> object:
        return SimpleNamespace(key="k", version_id="v", fingerprint="f", size=1)

    async def inserted(*_a: object) -> int:
        return 1

    @asynccontextmanager
    async def unit(_t: object) -> AsyncGenerator[object]:
        yield SimpleNamespace(session=None, record=lambda *_a, **_k: None, emit=lambda *_a: None)

    async def raw(*_a: object) -> bytes:
        return b"%PDF"

    monkeypatch.setattr(ocr_step, "gate_facts", facts)
    monkeypatch.setattr(ocr_step, "first_refusal", nothing)
    monkeypatch.setattr(ocr_step, "over_daily_cap", over)
    monkeypatch.setattr(ocr_step, "provider", lambda: engine)
    monkeypatch.setattr(ocr_step.storage, "get", raw)
    monkeypatch.setattr(ocr_step.storage, "put", put)
    monkeypatch.setattr(ocr_step.asyncio, "to_thread", lambda _f, *_a: raster())
    monkeypatch.setattr(ocr_step, "names_a_tin", lambda _w: False)
    monkeypatch.setattr(ocr_step, "flag_variant", variant)
    monkeypatch.setattr(ocr_step, "record_run", record)
    monkeypatch.setattr(ocr_step, "under_key", lambda _f: "under")
    monkeypatch.setattr(ocr_step, "uow", unit)
    monkeypatch.setattr(ocr_step, "insert_pages", inserted)
    monkeypatch.setattr(ocr_step, "record_tables", nothing)
    monkeypatch.setattr(ocr_step, "record_ocr_extraction", nothing)
    monkeypatch.setattr(ocr_step, "warn_if_near_cap", nothing)
    return engine, runs


def _source() -> object:
    return SimpleNamespace(
        engagement_id=uuid.uuid4(), storage_key="k", storage_version_id="v", fingerprint="f",
        size_bytes=1, media_type="application/pdf",
    )  # fmt: skip


async def _read(kind: str) -> None:
    source = uuid.uuid4()
    given = UploadInput(str(TENANT), kind, str(source))
    tenant = ocr_step._system(TENANT)  # pyright: ignore[reportPrivateUsage]  # the step's context
    await ocr_step._read(  # pyright: ignore[reportPrivateUsage]  # the step under test
        given,
        tenant,
        source if kind == VERSION else None,
        source if kind == INBOX else None,
        source if kind == INTAKE else None,
        _source(),  # type: ignore[arg-type]  # a source double
        [1],
    )


async def test_a_statement_page_is_read_for_its_tables_within_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, runs = _wire(monkeypatch, over_on=None)
    await _read(VERSION)
    assert engine.apis == ["detect_text", "analyze_tables"]
    assert [r["api"] for r in runs] == ["detect_text", "analyze_tables"]


async def test_tables_that_would_pass_the_cap_are_refused_and_never_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, runs = _wire(monkeypatch, over_on=2)  # the page read plus one TABLES page
    await _read(VERSION)
    assert engine.apis == ["detect_text"]
    refused = [r for r in runs if r["api"] == "analyze_tables"]
    assert len(refused) == 1 and refused[0]["refused"] == "quota_exceeded"


async def test_an_intake_attachment_pays_for_no_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, runs = _wire(monkeypatch, over_on=None)
    await _read(INTAKE)
    assert engine.apis == ["detect_text"]
    assert all(r["api"] != "analyze_tables" for r in runs)
