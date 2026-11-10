"""P-11-T33 (TASK-6128; DEC-2715): per-firm daily OCR page caps and the 80% warning.

Row: "per-tenant daily page cap and cost alarm". P-11 §cost: default 5,000 pages (OQ-10); R9: "cap
raised by both founders"; alarms: "daily page cap at 80%". The table's CHECKs are exercised in
tests/integration/test_p11t33_ocr_daily_caps_migration.py.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.evidence import ocr_gate
from abacus_tools.ocr_daily_cap import problem

TENANT = TenantContext(uuid.uuid4(), "system", "test")


def _patch(monkeypatch: pytest.MonkeyPatch, *, used: int, cap: int | None) -> None:
    async def scalar(sql: object, *_args: object) -> int | None:
        return cap if "ocr_daily_caps" in str(sql) else used

    @asynccontextmanager
    async def session(_tenant: object) -> AsyncGenerator[object]:
        yield SimpleNamespace(scalar=scalar)

    monkeypatch.setattr(ocr_gate, "tenant_session", session)


async def test_no_row_means_the_default_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, used=0, cap=None)
    assert await ocr_gate.daily_page_cap(TENANT) == ocr_gate.DAILY_PAGE_CAP == 5000


@pytest.mark.parametrize(
    ("cap", "used", "pages", "over"),
    [
        (12000, 9000, 2999, False),  # a raised cap lets the firm past 5,000
        (12000, 11999, 2, True),
        (800, 799, 1, False),  # a lowered cap refuses sooner
        (800, 800, 1, True),
    ],
)
async def test_a_firm_s_own_cap_is_the_one_counted(
    monkeypatch: pytest.MonkeyPatch, cap: int, used: int, pages: int, over: bool
) -> None:
    _patch(monkeypatch, used=used, cap=cap)
    assert await ocr_gate.over_daily_cap(TENANT, pages) is over


@pytest.mark.parametrize(
    ("before", "pages", "cap", "crossed"),
    [
        (3999, 1, 5000, True),  # 4,000 is 80% of 5,000: this read reaches it
        (3998, 1, 5000, False),
        (4000, 5, 5000, False),  # already past it: only the crossing read warns
        (0, 20, 20, True),
        (100, 700, 1000, True),
    ],
)
def test_the_warning_fires_once_on_the_read_that_crosses_80_percent(
    before: int, pages: int, cap: int, crossed: bool
) -> None:
    assert ocr_gate.crossed_warning(before, pages, cap) is crossed


async def test_the_warning_logs_counts_never_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, used=4001, cap=None)  # after this read of 2 pages: 3,999 then 4,001
    logged: list[tuple[str, dict[str, object]]] = []

    def warning(event: str, **fields: object) -> None:
        logged.append((event, fields))

    monkeypatch.setattr(ocr_gate, "_log", SimpleNamespace(warning=warning))
    assert await ocr_gate.warn_if_near_cap(TENANT, 2) is True
    assert logged == [
        ("ocr.daily_cap_warning", {"tenant_id": str(TENANT.tenant_id), "used": 4001, "cap": 5000})
    ]


@pytest.mark.parametrize(
    ("pages", "raised_by", "second_by", "reason", "refused"),
    [
        (12000, "founder-a", "founder-b", "December peak for a large firm", None),
        (12000, "founder-a", None, "December peak for a large firm", "second, different"),
        (12000, "founder-a", "Founder-A", "December peak for a large firm", "second, different"),
        (2000, "founder-a", None, "Lower while the firm is in trial", None),  # lowering: one
        (5000, "founder-a", None, "Back to the default after peak", None),
        (0, "founder-a", None, "Out of bounds below one page", "between 1 and 100,000"),
        (100001, "founder-a", "founder-b", "Out of bounds above the ceiling", "between 1"),
        (3000, "founder-a", None, "short", "10 characters"),
    ],
)
def test_the_tool_says_what_the_table_would_refuse(
    pages: int, raised_by: str, second_by: str | None, reason: str, refused: str | None
) -> None:
    said = problem(pages, raised_by, second_by, reason)
    if refused is None:
        assert said is None
    else:
        assert said is not None and refused in said
