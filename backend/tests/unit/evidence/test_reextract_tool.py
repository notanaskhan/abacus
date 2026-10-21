"""TASK-344: the re-read tool runs ordinary upload processing on each stale PDF, counts outcomes,
keeps going past a failure, and changes nothing on a dry run."""

from __future__ import annotations

from uuid import uuid4

import pytest

from abacus.modules.evidence.workflow_types import VERSION, UploadInput
from abacus_tools import reextract


async def test_it_reads_each_stale_pdf_and_counts_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = uuid4()
    todo = [UploadInput(str(tenant), VERSION, str(uuid4())) for _ in range(3)]
    seen: list[UploadInput] = []

    async def stale(_tenant: object, _limit: int) -> list[UploadInput]:
        return todo

    async def process(given: UploadInput) -> str:
        seen.append(given)
        if given is todo[2]:
            raise RuntimeError("storage")
        return "extracted"

    monkeypatch.setattr(reextract, "stale_pdfs", stale)
    monkeypatch.setattr(reextract, "process_upload", process)
    assert await reextract._run(tenant, dry_run=True, limit=10) == {"to_read": 3}  # pyright: ignore[reportPrivateUsage] -- the tool's core
    assert seen == []
    outcome = await reextract._run(tenant, dry_run=False, limit=10)  # pyright: ignore[reportPrivateUsage] -- the tool's core
    assert outcome == {"extracted": 2, "failed": 1}
    assert seen == todo
