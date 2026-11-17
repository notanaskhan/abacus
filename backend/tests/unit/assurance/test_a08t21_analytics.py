"""A-08-T21 (TASK-8400; SPEC-657 F5): the analytics set's pure parts: lines from the statements
through the shared dual-threshold engine, subtotals derived, the review hash and the basis."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import date
from decimal import Decimal

from abacus.modules.assurance import analytics as svc
from abacus.modules.workpapers.compute import flux

D = Decimal
T = flux.Thresholds(D("10"), D("116250"))


def _line(key: str, group: str, cy: str, py: str) -> svc.SourceLine:
    return svc.SourceLine(key, key.title(), group, group.title(), D(cy), D(py), (f"{key}-1",))


def test_both_legs_decide_over_and_interest_stays_within() -> None:
    lines, result = svc.compute_lines(
        [
            _line("revenue", "income", "9840000", "8610000"),  # +14.3%, +1,230,000: over
            _line("interest", "income", "520000", "410000"),  # +26.8%, +110,000: within
            _line("rent", "expense", "300000", "290000"),  # +3.4%: within
        ],
        T,
    )
    by_key = {x.key: x for x in lines}
    assert by_key["revenue"].over and not by_key["interest"].over
    assert by_key["interest"].change_pct == D("26.8")
    # The income group's subtotal is derived and never evaluated; one-line groups have none.
    total = by_key["income:total"]
    assert total.derived and not total.evaluated and not total.over
    assert "expense:total" not in by_key
    assert result.evaluated == 3 and result.over == 1 and result.foots


def test_positions_and_cells_are_stable() -> None:
    source = [_line("a", "g", "100", "50"), _line("b", "g", "10", "10")]
    lines, _ = svc.compute_lines(source, T)
    assert [(x.position, x.cell) for x in lines] == [(1, "D2"), (2, "D3"), (3, "D4")]
    again, _ = svc.compute_lines(source, T)
    assert svc.content_hash(lines) == svc.content_hash(again)


def test_line_status_and_review_hash() -> None:
    lines, _ = svc.compute_lines([_line("revenue", "income", "9840000", "8610000")], T)
    computed = lines[0]
    assert svc.line_status(computed, None) == "unexplained"
    explanation = svc.ExplanationView(
        uuid.uuid4(), "Price increase", (uuid.uuid4(),), "staff", None, uuid.uuid4(), "Hannah",
        None, None, None,
    )  # fmt: skip
    assert svc.line_status(computed, explanation) == "explained"
    accepted = dataclasses.replace(explanation, accepted_by=uuid.uuid4())
    assert svc.line_status(computed, accepted) == "accepted"


def test_basis_labels() -> None:
    assert (
        svc.basis_label("audit_flux", "unadjusted", date(2026, 12, 31))
        == "Unadjusted FY2026 vs audited FY2025"
    )
    assert (
        svc.basis_label("audit_flux", "adjusted", date(2026, 12, 31))
        == "Adjusted FY2026 vs audited FY2025"
    )
    assert svc.basis_label("ssars_review", "unadjusted", date(2026, 12, 31)) == "FY2026 vs FY2025"


def test_initials() -> None:
    assert svc.initials("Hannah Leclerc") == "HL"
