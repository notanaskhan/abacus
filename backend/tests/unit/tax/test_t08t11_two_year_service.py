"""T-08-T11 (S51 partials, TASK-8740; DEC-5731; SPEC-710 AC-21 to AC-25): a line's state is code's
(unexplained only when flagged, proposed until accepted, stale once the values move), engine
amounts parse by line key and skip what is not a number, and the over-threshold view keeps only
flagged lines with the accepted count over them."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from abacus.modules.tax import two_year_service as svc
from abacus.modules.tax.compute import two_year as calc
from abacus.modules.tax.compute.two_year_lines import LINE_MAPS
from abacus.modules.tax.practice_tools_contract import (
    _two_year_out,  # pyright: ignore[reportPrivateUsage] -- the mapping under test
)

D = Decimal
T = calc.Threshold(D("10"), D("1000"), "v3")


def _line(code: str, cy: str, py: str, explained: svc.Explanation | None) -> svc.Line:
    ln = calc.compare({code: D(cy)}, {code: D(py)}, [(code, code)], T)[0]
    return svc.Line(ln, calc.values_hash([ln]), explained)


def _ex(accepted_hash: str | None) -> svc.Explanation:
    at = datetime(2026, 9, 14, tzinfo=UTC)
    return svc.Explanation(
        uuid4(), "Halvard dividends up.", "agent", uuid4(),
        uuid4() if accepted_hash else None, at if accepted_hash else None, accepted_hash,
    )  # fmt: skip


def test_ac_states_follow_the_values() -> None:
    flagged = _line("1040.3b", "14820", "13240", None)
    assert flagged.line.flagged and flagged.state == "unexplained"
    within = _line("1040.1a", "268400", "251000", None)
    assert not within.line.flagged and within.state is None
    proposed = _line("1040.3b", "14820", "13240", _ex(None))
    assert proposed.state == "proposed"
    accepted = _line("1040.3b", "14820", "13240", _ex(flagged.values_hash))
    assert accepted.state == "accepted"
    moved = _line("1040.3b", "14900", "13240", _ex(flagged.values_hash))
    assert moved.state == "stale"


def test_ac_engine_amounts_parse_by_key() -> None:
    got = svc._amounts(  # pyright: ignore[reportPrivateUsage] -- the parser under test
        [{"line_key": "1040.11", "amount": "598030"}, {"line_key": "x", "amount": "n/a"}, 3]
    )
    assert got == {"1040.11": D("598030")}
    assert LINE_MAPS["1040"][0][0] == "1040.1a"


def test_ac_the_over_threshold_view_counts_accepted() -> None:
    a = _line("1040.3b", "14820", "13240", None)
    b = _line("1040.16", "110531", "99381", _ex(None))
    b = svc.Line(b.line, b.values_hash, _ex(b.values_hash))
    c = _line("1040.1a", "268400", "251000", None)
    found = svc.Comparison(
        uuid4(), uuid4(), "2025I:FeldJ:V2", T, uuid4(), (a, b, c),
        D("598030"), D("551940"), D("123223"), D("110826"), D("253"), D("1174"),
    )  # fmt: skip
    out = _two_year_out(found, "over_threshold")
    assert [ln.line_key for ln in out.lines] == ["1040.3b", "1040.16"]
    assert (out.over_threshold, out.accepted) == (2, 1)
    assert out.agi_delta_pct == D("8.4")
