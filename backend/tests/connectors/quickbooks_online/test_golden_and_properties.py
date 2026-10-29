# ac-test-author: ayushkbhatia
"""A-02-T32 (TASK-1745; ADR-044, ADR-038, ADR-050; DEC-835): golden normalisation and property
tests for the QuickBooks Online TrialBalance normaliser the pipeline dispatches to.

- Golden: this suite's synthetic recording normalises to `golden/*.yaml`, line for line (a
  negative on one side is a balance on the other; blank is zero; the code is the account id).
- Properties (Hypothesis): for any report the provider could send within the limits, every line
  keeps its account id, name and net (debit less credit) and has no negative side; a report whose
  declared totals are the normalised totals validates; moving any one amount by a cent is refused
  as `control_totals_mismatch`; and arbitrary bytes are refused with a `NormaliseError`, never
  another exception (client content is hostile, AGENTS.md #8).
"""

from __future__ import annotations

import contextlib
import json
from datetime import date
from decimal import Decimal
from typing import Final, cast

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from abacus.modules.connections.qbo_format import parse_qbo_trial_balance
from abacus.modules.ledger.api import NormaliseError, validate

from . import targets

PERIOD: Final = (date(2026, 1, 1), date(2026, 12, 31))
CENT: Final = Decimal("0.01")
RUNS: Final = settings(
    max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)


# --- Golden --------------------------------------------------------------------------------------


def test_golden_the_recording_normalises_to_the_golden_file() -> None:
    golden = cast(dict[str, object], yaml.safe_load(targets.GOLDEN.read_text("utf-8")))
    tb = parse_qbo_trial_balance(targets.RECORDING.read_bytes())
    assert (tb.period_start, tb.period_end, tb.currency) == (
        golden["period_start"],
        golden["period_end"],
        golden["currency"],
    )
    assert (str(tb.declared_debit), str(tb.declared_credit)) == (
        golden["declared_debit"],
        golden["declared_credit"],
    )
    expected = cast(list[dict[str, str]], golden["lines"])
    assert [
        {
            "code": line.account_code,
            "name": line.account_name,
            "debit": str(line.debit),
            "credit": str(line.credit),
        }
        for line in tb.lines
    ] == expected
    assert validate(tb, period_start=tb.period_start, period_end=tb.period_end) is None


# --- Properties ----------------------------------------------------------------------------------

_amount = st.one_of(
    st.just(""),
    st.decimals(
        min_value=Decimal("-999999999.99"),
        max_value=Decimal("999999999.99"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ).map(lambda d: f"{d:.2f}"),
)
_name = st.text(
    alphabet=st.characters(categories=("Lu", "Ll", "Nd", "Zs", "Pd", "Po"), max_codepoint=0x24F),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() != "")
_rows = st.lists(
    st.tuples(st.integers(min_value=1, max_value=10**6), _name, _amount, _amount),
    min_size=1,
    max_size=40,
    unique_by=lambda r: r[0],
)


def _raw(value: str) -> Decimal:
    return Decimal(value) if value else Decimal("0.00")


def _sides(debit: Decimal, credit: Decimal) -> tuple[Decimal, Decimal]:
    """The rule from the spec, written here on its own (ADR-050: by code)."""
    if debit < 0:
        debit, credit = Decimal("0.00"), credit - debit
    if credit < 0:
        debit, credit = debit - credit, Decimal("0.00")
    return debit, credit


def _report(rows: list[tuple[int, str, str, str]], totals: tuple[Decimal, Decimal]) -> bytes:
    data: list[dict[str, object]] = [
        {"ColData": [{"value": name, "id": str(code)}, {"value": dr}, {"value": cr}]}
        for code, name, dr, cr in rows
    ]
    data.append(
        {
            "Summary": {
                "ColData": [
                    {"value": "TOTAL"},
                    {"value": f"{totals[0]:.2f}"},
                    {"value": f"{totals[1]:.2f}"},
                ]
            },
            "type": "Section",
            "group": "GrandTotal",
        }
    )
    return json.dumps(
        {
            "Header": {
                "StartPeriod": PERIOD[0].isoformat(),
                "EndPeriod": PERIOD[1].isoformat(),
                "Currency": "USD",
            },
            "Rows": {"Row": data},
        }
    ).encode()


def _balanced(
    rows: list[tuple[int, str, str, str]],
) -> tuple[list[tuple[int, str, str, str]], Decimal]:
    """Add a suspense line that balances the normalised sides; return the rows and the total."""
    debit = credit = Decimal("0.00")
    for _code, _name, dr, cr in rows:
        d, c = _sides(_raw(dr), _raw(cr))
        debit, credit = debit + d, credit + c
    gap = debit - credit
    suspense = (
        (10**6 + 1, "Suspense", "", f"{gap:.2f}")
        if gap >= 0
        else (
            10**6 + 1,
            "Suspense",
            f"{-gap:.2f}",
            "",
        )
    )
    total = max(debit, credit)
    return [*rows, suspense], total


@RUNS
@given(_rows)
def test_property_every_line_keeps_its_account_and_net_with_no_negative_side(
    rows: list[tuple[int, str, str, str]],
) -> None:
    balanced, total = _balanced(rows)
    tb = parse_qbo_trial_balance(_report(balanced, (total, total)))
    assert len(tb.lines) == len(balanced)
    for line, (code, name, dr, cr) in zip(tb.lines, balanced, strict=True):
        assert line.account_code == str(code)
        assert line.account_name == name.strip()
        assert line.debit >= 0 and line.credit >= 0
        assert line.debit - line.credit == _raw(dr) - _raw(cr)
        assert line.source_ref == f"qbo:account:{code}"


@RUNS
@given(_rows)
def test_property_declared_normalised_totals_validate(
    rows: list[tuple[int, str, str, str]],
) -> None:
    balanced, total = _balanced(rows)
    tb = parse_qbo_trial_balance(_report(balanced, (total, total)))
    expected = None if total != 0 else "zero_total"
    assert validate(tb, period_start=PERIOD[0], period_end=PERIOD[1]) == expected


@RUNS
@given(_rows, st.data())
def test_property_a_cent_moved_anywhere_is_a_control_total_mismatch(
    rows: list[tuple[int, str, str, str]], data: st.DataObject
) -> None:
    balanced, total = _balanced(rows)
    index = data.draw(st.integers(min_value=0, max_value=len(balanced) - 1))
    side = data.draw(st.sampled_from((2, 3)))
    row = list(balanced[index])
    row[side] = f"{_raw(str(row[side])) + CENT:.2f}"
    changed = [
        *balanced[:index],
        cast(tuple[int, str, str, str], tuple(row)),
        *balanced[index + 1 :],
    ]
    tb = parse_qbo_trial_balance(_report(changed, (total, total)))
    assert validate(tb, period_start=PERIOD[0], period_end=PERIOD[1]) == "control_totals_mismatch"


@RUNS
@given(st.binary(max_size=2048))
def test_property_arbitrary_bytes_are_refused_with_a_normalise_error_or_parse(
    content: bytes,
) -> None:
    with contextlib.suppress(NormaliseError):
        parse_qbo_trial_balance(content)


@RUNS
@given(
    st.recursive(
        st.none() | st.booleans() | st.integers() | st.text(max_size=8),
        lambda c: (
            st.lists(c, max_size=4)
            | st.dictionaries(
                st.sampled_from(
                    ["Header", "Rows", "Row", "ColData", "Summary", "value", "id", "group"]
                ),
                c,
                max_size=4,
            )
        ),
        max_leaves=30,
    )
)
def test_property_any_json_shape_is_refused_with_a_normalise_error_or_parse(value: object) -> None:
    with contextlib.suppress(NormaliseError):
        parse_qbo_trial_balance(json.dumps(value).encode())
