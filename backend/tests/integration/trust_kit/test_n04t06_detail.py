"""N-04-T06 (DEC-2950): a corrected respond-by moves the notice's work item due date in the same
unit of work and signals the response workflow; the detail carries the masked TIN and the
return's label; the search document carries no amount."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

import abacus.api as app_package  # loading it loads every module
from abacus.modules.notices import service
from abacus.modules.notices.search import notice_search_document

from .support import Firm, Seeder, make_firm

pytestmark = pytest.mark.asyncio


async def _notice(seed: Seeder, firm: Firm) -> uuid.UUID:
    work_item = await seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by, "
        "due_on) SELECT $1, $2, client_id, 'notice', 'CP14 · TY2024', $3, '2026-10-01' "
        "FROM engagements WHERE id = $2 RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        firm.user_id,
    )
    await seed.run(
        "INSERT INTO notices (tenant_id, work_item_id, engagement_id, notice_code, received_on, "
        "tax_year, respond_by, amount_total) VALUES ($1, $2, $3, 'CP14', '2026-09-10', 2024, "
        "'2026-10-01', 1106.00)",
        firm.tenant_id,
        work_item,
        firm.engagement_id,
    )
    return work_item


async def test_ac_a_corrected_respond_by_moves_the_due_date_and_signals(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert app_package.create_app
    firm = await make_firm(seed)
    notice_id = await _notice(seed, firm)
    signals: list[tuple[str, str, tuple[object, ...]]] = []

    async def signal(workflow_id: str, name: str, *args: object) -> None:
        signals.append((workflow_id, name, args))

    monkeypatch.setattr(service, "signal_workflow", signal)
    ctx = firm.person()
    found = await service.notice(ctx, notice_id)
    await service.edit(ctx, notice_id, found.row_version, respond_by=date(2026, 10, 15))

    assert await seed.value("SELECT due_on FROM work_items WHERE id = $1", notice_id) == date(
        2026, 10, 15
    )
    assert signals == [
        (f"notice_response:{firm.tenant_id}:{notice_id}", "respond_by_changed", ("2026-10-15",))
    ]


async def test_ac_the_search_document_names_the_notice_and_no_amount(seed: Seeder) -> None:
    firm = await make_firm(seed)
    notice_id = await _notice(seed, firm)
    found = await notice_search_document(firm.system, notice_id)
    assert found is not None
    assert (found.title, found.body, found.engagement_id) == (
        "CP14 · TY2024",
        "notice",
        firm.engagement_id,
    )
    assert "1106" not in f"{found.title} {found.body}"
