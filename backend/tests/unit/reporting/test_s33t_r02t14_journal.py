"""R-02-T14 remainder (DEC-3172): POR-08's "Download entries" as C11's `client_entries_journal`.

The journal is composed by code from the C18 item's own lines (the handoff's Account · Debit ·
Credit, "$" with cents, "—" for an empty side); the same item composes the same blocks; the kind
list stays one list; a first request renders, a filed journal is served, a failed one renders
again."""

from __future__ import annotations

import importlib.util
import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import ApprovalItem, ApprovalLine
from abacus.modules.reporting import api as c11
from abacus.modules.reporting import entries_journal as ej
from abacus.modules.reporting.contract import GeneratedDocumentKind

pytestmark = pytest.mark.asyncio
TENANT = TenantContext(uuid.uuid4(), "human", str(uuid.uuid4()))
ITEM, USER, DOC, JOB, EVIDENCE = (uuid.uuid4() for _ in range(5))


def _item() -> ApprovalItem:
    return ApprovalItem(
        kind="proposed_entry",
        item_id=ITEM,
        scope_kind="work_item",
        scope_id=uuid.uuid4(),
        sent_to_client=True,
        title="AJE 4 · August accruals",
        state="waiting",
        seen_hash="h",
        lines=(
            ApprovalLine("Inventory — Green Coffee", debit=Decimal("12600.00")),
            ApprovalLine("Utilities & Facilities", debit=Decimal("1480.00")),
            ApprovalLine("Accrued Expenses", credit=Decimal("14080.00")),
        ),
    )


def test_the_journal_is_the_items_lines_in_the_handoffs_words() -> None:
    blocks = ej.compose(_item())
    assert blocks[0] == {"type": "heading", "level": 1, "text": "AJE 4 · August accruals"}
    assert blocks[1] == {
        "type": "table",
        "columns": ["Account", "Debit", "Credit"],
        "rows": [
            ["Inventory — Green Coffee", "$12,600.00", "—"],
            ["Utilities & Facilities", "$1,480.00", "—"],
            ["Accrued Expenses", "—", "$14,080.00"],
        ],
    }


def test_the_same_item_composes_the_same_bytes() -> None:
    one = json.dumps(ej.compose(_item()), sort_keys=True).encode()
    two = json.dumps(ej.compose(_item()), sort_keys=True).encode()
    assert one == two


def test_the_kind_is_composed_in_the_code_only_layout() -> None:
    ej.ensure_kind()
    kind = c11.document_kind(ej.KIND)
    assert kind.layout == "financial_statements"
    assert kind.body_provider is not None
    assert tuple(kind.formats) == ("pdf",)


def test_the_kind_list_stays_one_list() -> None:
    path = Path(__file__).parents[3] / "migrations/versions/0763_c11_entries_journal.py"
    spec = importlib.util.spec_from_file_location("m0763", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module._NEW) == set(get_args(GeneratedDocumentKind))


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    document: uuid.UUID | None,
    status: str = "succeeded",
    calls: list[str],
) -> None:
    async def of_owner(*_a: object) -> uuid.UUID | None:
        return document

    async def outcome(*_a: object) -> object:
        return SimpleNamespace(
            status=status, evidence_version_id=EVIDENCE if status == "succeeded" else None
        )

    async def render(_tx: object, request: object) -> object:
        calls.append(f"render:{request.requested_by.user_id == USER}")  # type: ignore[attr-defined]  # a request
        return SimpleNamespace(generated_document_id=DOC, version_no=1)

    async def regenerate(*_a: object) -> object:
        calls.append("regenerate")
        return SimpleNamespace(generated_document_id=DOC, version_no=2)

    class Result:
        def first(self) -> object:
            return SimpleNamespace(version_no=1, job_id=JOB)

    class Session:
        async def execute(self, *_a: object) -> Result:
            return Result()

        async def scalar(self, *_a: object) -> uuid.UUID:
            return JOB

    @asynccontextmanager
    async def session(_t: object) -> AsyncGenerator[Session]:
        yield Session()

    @asynccontextmanager
    async def unit(_t: object) -> AsyncGenerator[object]:
        yield SimpleNamespace()

    monkeypatch.setattr(c11, "document_of_owner", of_owner)
    monkeypatch.setattr(c11, "render_outcome", outcome)
    monkeypatch.setattr(c11, "render", render)
    monkeypatch.setattr(c11, "regenerate", regenerate)
    monkeypatch.setattr(ej, "tenant_session", session)
    monkeypatch.setattr(ej, "uow", unit)


async def _journal() -> object:
    return await ej.journal(
        TENANT, USER, _item(), client_id=uuid.uuid4(), engagement_id=None, work_item_id=None
    )


async def test_a_first_request_renders_in_the_persons_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    _wire(monkeypatch, document=None, calls=calls)
    assert await _journal() == ej.JournalPending(JOB)
    assert calls == ["render:True"]


async def test_a_filed_journal_is_served_again(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _wire(monkeypatch, document=DOC, calls=calls)
    assert await _journal() == ej.JournalReady(EVIDENCE)
    assert calls == []


async def test_a_running_render_answers_its_job(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _wire(monkeypatch, document=DOC, status="running", calls=calls)
    assert await _journal() == ej.JournalPending(JOB)
    assert calls == []


async def test_a_failed_render_renders_again(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _wire(monkeypatch, document=DOC, status="failed", calls=calls)
    assert await _journal() == ej.JournalPending(JOB)
    assert calls == ["regenerate"]


async def test_a_concurrent_first_request_answers_the_other_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # End-pass review: two first requests race to make the item's one document.
    from sqlalchemy.exc import IntegrityError

    calls: list[str] = []
    _wire(monkeypatch, document=None, status="running", calls=calls)
    seen = iter([None, DOC])

    async def of_owner(*_a: object) -> uuid.UUID | None:
        return next(seen)

    async def clash(*_a: object) -> object:
        raise IntegrityError("INSERT", {}, Exception("unique"))

    monkeypatch.setattr(c11, "document_of_owner", of_owner)
    monkeypatch.setattr(c11, "render", clash)
    assert await _journal() == ej.JournalPending(JOB)
