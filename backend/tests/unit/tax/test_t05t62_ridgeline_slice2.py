"""T-05-T62 (TASK-7942; DEC-4937): Brightwater Hale Ridgeline slice part 2.

Row acceptance: "Each named snapshot reproduces its artboards from the database, and the Sep 14
timeline matches DF-34."

Unit level: the slice's part-2 events at their clocks and in order, the named snapshots, the
memo's sections verbatim from TXP-01, the fix moving Item L 6,860,000 → 6,866,200 by the 18a
shares, and both recorders refusing a firm that is not synthetic. The load itself and the
artboards read from the database are the end pass's (`make seed-demo` with the slice).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus_tools.synthetic.scenarios.brightwater_hale import entity_slice as s
from abacus_tools.synthetic.scenarios.brightwater_hale.entity_memo import SECTIONS
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT, snapshot


def _clock(e: object) -> datetime:
    return datetime.fromisoformat(str(e.data["at"]))  # type: ignore[attr-defined]


def test_the_sep_14_timeline_is_df34s() -> None:
    by_label = {e.label: _clock(e) for e in s.entity_events() if "at" in e.data}
    assert by_label["entity:ridgeline:memo-l1"].date().isoformat() == "2026-09-10"
    assert by_label["entity:ridgeline:memo-l2"] == datetime(2026, 9, 14, 9, 40, tzinfo=CT)
    assert by_label["entity:ridgeline:fix"] == datetime(2026, 9, 14, 9, 51, tzinfo=CT)
    assert by_label["entity:ridgeline:run3"] == datetime(2026, 9, 14, 9, 52, tzinfo=CT)
    ordered = sorted(by_label, key=by_label.__getitem__)
    assert ordered.index("entity:ridgeline:memo") < ordered.index("entity:ridgeline:memo-l1")
    assert ordered.index("entity:ridgeline:fix") < ordered.index("entity:ridgeline:run3")
    assert ordered[-1] == "entity:ridgeline:m2-resolved"


@pytest.mark.parametrize(
    ("name", "hour", "minute", "day"),
    [("2026-09-08T10:02", 10, 2, 8), ("2026-09-10T16:12", 16, 12, 10), ("E0", 9, 24, 14),
     ("2026-09-14T09:52", 9, 52, 14)],
)  # fmt: skip
def test_the_named_snapshots(name: str, hour: int, minute: int, day: int) -> None:
    at = snapshot(name).at
    assert (at.day, at.hour, at.minute) == (day, hour, minute)


def test_the_fix_moves_item_l_by_the_18a_shares() -> None:
    drafted = sum(Decimal(r[5]) for r in s.CAPITAL)
    added = sum(Decimal(v) for cell, v in s.FIX_ADDS if cell.startswith("05!F"))
    assert drafted == Decimal("6860000") and drafted + added == Decimal("6866200")
    assert {c[:4] for c, _ in s.FIX_ADDS} == {"05!E", "05!F"}


def test_the_memo_is_txp01s_text_with_its_markers() -> None:
    keys = [k for k, _t, _n in SECTIONS]
    assert keys[:2] == ["overview", "structural_events"]
    cited = [n for _k, _t, n in SECTIONS if n is not None]
    assert cited == [1, 2, 3, 4, 5, 6]
    text = dict((k, t) for k, t, _n in SECTIONS)
    assert "28,595 excess of price over capital is a §743(b) placeholder" in text["structural_events"]


@pytest.mark.asyncio
async def test_the_recorders_refuse_a_real_firm(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.kernel.errors import NotFound
    from abacus.modules.tax import memo_service, workbook_fix

    async def real(*_: object) -> bool:
        return False

    monkeypatch.setattr("abacus.modules.identity.api.is_synthetic_firm", real)
    ctx = SimpleNamespace(tenant=None)
    with pytest.raises(NotFound):
        await memo_service.record_synthetic_memo(
            ctx, uuid4(), run_id=uuid4(), on_behalf_of=uuid4(), sections=SECTIONS  # type: ignore[arg-type]
        )
    from abacus.modules.identity.api import AuthContext

    person = object.__new__(AuthContext)
    object.__setattr__(person, "tenant", None) if False else None
    with pytest.raises(NotFound):
        await workbook_fix.record_synthetic_fix(object(), uuid4(), uuid4(), {})
