"""S41 leftovers (TASK-7733, DEC-4737; T-05-T46 §9.5): the rail's facts and the partners read,
pure. The routes' DB-backed answer runs at the end pass's scenario load."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from abacus.modules.tax import workbook_contract as wb
from abacus.modules.tax.entity_partners import KINDS, ladder_people, periods_of

A, B, C = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def test_periods_group_shares_by_date_range_in_order() -> None:
    rows = [
        (A, date(2025, 7, 1), date(2025, 12, 31), Decimal("30.000000")),
        (A, date(2025, 1, 1), date(2025, 6, 30), Decimal("35.000000")),
        (B, date(2025, 1, 1), date(2025, 6, 30), Decimal("65.000000")),
        (B, date(2025, 7, 1), date(2025, 12, 31), Decimal("65.000000")),
        (C, date(2025, 7, 1), date(2025, 12, 31), Decimal("5.000000")),
    ]
    periods = periods_of(rows)
    assert [(p.starts_on, p.ends_on) for p in periods] == [
        (date(2025, 1, 1), date(2025, 6, 30)),
        (date(2025, 7, 1), date(2025, 12, 31)),
    ]
    assert periods[0].shares == {str(A): Decimal("35"), str(B): Decimal("65")}
    assert str(C) not in periods[0].shares  # Pell Street II holds nothing in period 1
    assert sum(periods[1].shares.values()) == Decimal("100")


def test_the_ladder_names_preparer_first_reviewer_and_signer() -> None:
    p, r, s = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert ladder_people({"preparer": (p,), "manager_reviewer": (r,), "signer": (s,)}) == (p, r, s)
    detail = uuid.uuid4()
    assert ladder_people({"detail_reviewer": (detail,), "manager_reviewer": (r,)})[1] == detail
    assert ladder_people({}) == (None, None, None)


def test_partner_kinds_map_onto_the_frozen_literal() -> None:
    assert set(KINDS.values()) <= {"general", "limited", "llc_member"}
    assert KINDS == {"gp": "general", "lp": "limited", "member": "llc_member"}


def test_the_ownership_write_still_answers_501_and_the_reads_carry_tin_tags() -> None:
    """`PUT …/ownership` has no row (DEC-4737); the two reads carry last fours only."""
    fields = wb.WorkbookPartnerOut.model_fields
    assert "tin_last4" in fields and "tin" not in fields
    assert "ein_last4" in wb.WorkbookGeneralInformationOut.model_fields
    route = next(
        r for r in wb.workbook_router.routes if getattr(r, "path", "").endswith("/ownership")
    )
    assert "PUT" in getattr(route, "methods", set())
