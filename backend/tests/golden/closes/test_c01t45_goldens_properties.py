"""C-01-T45 (TASK-8305; ADR-078, written in N's session; implementer AY): goldens and properties
for the close engine (reconciliation, schedules, rollups, flux).

Goldens are exact Decimal equality against `closes_figures.yaml` (Brightwater Hale's August close,
the figure book C-01-T13). Properties hold over 500 generated ledgers: the reconciliation
conserves carry-forward (every prior open item is either cleared or carried, never both, never
lost), a reconciliation built from consistent sides ties, matching is one-to-one, hashes are
idempotent and order-independent, schedules foot to their total, and tree rollups foot.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from abacus.modules.closes.compute import reconciliation as rec
from abacus.modules.closes.compute import schedules as calc
from abacus.modules.workpapers.compute import flux
from abacus_tools.synthetic.scenarios.brightwater_hale import close_slice as bh

HERE = Path(__file__).parent
FIG = cast(
    "Mapping[str, Mapping[str, object]]",
    yaml.safe_load((HERE / "closes_figures.yaml").read_text()),
)
D = Decimal
END = bh.PERIOD_END
PROPERTIES = settings(
    max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)


def _d(value: object) -> Decimal:
    assert isinstance(value, str), "amounts are quoted text"
    return D(value)


def _inputs() -> rec.Inputs:
    statement = [
        rec.StatementLine(f"s{n}", when, text, out, into, confidence=D("0.99"))
        for n, (when, text, out, into) in enumerate(bh.STATEMENT_PAGE_2)
    ]
    register = [
        rec.RegisterLine(f"r{n}", when, into if into is not None else -(out or D(0)))
        for n, (when, text, out, into) in enumerate(bh.STATEMENT_PAGE_2)
        if "REFUND" not in text
    ]
    register.append(rec.RegisterLine("r-dit", date(2026, 8, 31), bh.DEPOSIT_IN_TRANSIT))
    register += [
        rec.RegisterLine(f"r-{c.number}", c.issued_on, -c.amount, number=c.number)
        for c in bh.OUTSTANDING_CHECKS
        if c.number != "#2281"
    ]
    c = bh.OUTSTANDING_CHECKS[0]
    prior = [
        rec.PriorItem("jul-2281", "bank", "outstanding_check", c.issued_on, c.amount, ref="#2281")
    ]
    return rec.Inputs(
        END, bh.BOOK_BALANCE, bh.BALANCE_PER_BANK, tuple(statement), tuple(register), tuple(prior)
    )


# --- goldens -------------------------------------------------------------------------------------


def test_golden_4410_both_sides_to_the_cent() -> None:
    g = FIG["reconciliation_4410"]
    r = rec.reconcile(_inputs())
    for field in (
        "balance_per_bank",
        "deposits_in_transit",
        "outstanding_checks",
        "adjusted_bank",
        "book_balance",
        "unrecorded_deposits",
        "adjusted_book",
        "difference",
    ):
        assert getattr(r, field) == _d(g[field]), field
    stale = [(i.ref, i.days_at_period_end) for i in r.items if i.stale]
    assert stale == [(s["ref"], s["days"]) for s in cast("list[dict[str, object]]", g["stale"])]
    assert dict(r.aging) == {k: _d(v) for k, v in cast("dict[str, str]", g["aging"]).items()}


def test_golden_prepaid_8400_over_12() -> None:
    g = FIG["prepaid"]
    policy = calc.Arrangement("prepaid", _d(g["total"]), date(2026, 1, 1), date(2026, 12, 31))
    lines = calc.schedule(policy)
    assert len(lines) == g["months"]
    assert {line.aje for line in lines} == {_d(g["monthly"])}
    assert calc.balance_at(policy, "2026-08") == _d(g["balance_at_2026_08"])
    tied = calc.tie(
        _d(g["gl_before_aje_02"]),
        _d(g["balance_at_2026_08"]),
        [calc.PendingEntry("AJE-02", -_d(g["monthly"]))],
    )
    assert tied.tie == "ties_once_posted"


def test_golden_flux_both_legs() -> None:
    g = FIG["flux"]
    lines = [flux.FluxLine(f.key, f.caption, D(f.current), D(f.prior)) for f in bh.FLUX]
    result = flux.evaluate(lines, flux.Thresholds(_d(g["threshold_pct"]), _d(g["threshold_usd"])))
    over = sorted(r.key for r in result.rows if r.result == "over")
    assert over == sorted(cast("list[str]", g["over"]))
    within = sorted(r.key for r in result.rows if r.result == "within")
    assert within == sorted(cast("list[str]", g["within"]))
    for f in bh.FLUX:
        assert f.over_both(_d(g["threshold_pct"]), int(_d(g["threshold_usd"]))) == (f.key in over)


def test_golden_tree_foots() -> None:
    g = FIG["tree"]
    leaves = [(a, b, _d(c)) for a, b, c in cast("list[list[str]]", g["leaves"])]
    sums = calc.rollup(leaves)
    assert sums["asset"][""] == _d(g["asset_total"])
    assert sums["asset"]["Bank"] == _d(g["bank_total"])


def test_golden_hashes_are_idempotent() -> None:
    a, b = rec.reconcile(_inputs()), rec.reconcile(_inputs())
    assert (a.inputs_hash, a.content_hash) == (b.inputs_hash, b.content_hash)


# --- properties ----------------------------------------------------------------------------------

money = st.decimals(min_value=D("0.01"), max_value=D("99999.99"), places=2, allow_nan=False)
day = st.integers(min_value=0, max_value=300)


@st.composite
def ledgers(draw: st.DrawFn) -> tuple[rec.Inputs, int]:
    """A consistent month: every register line either clears on the statement (same amount and
    date) or stays outstanding; unrecorded statement lines adjust the book; prior items either
    clear (by number) or stay. Built so the true reconciliation ties."""
    n = draw(st.integers(min_value=0, max_value=12))
    statement: list[rec.StatementLine] = []
    register: list[rec.RegisterLine] = []
    bank = book = D("0.00")
    for i in range(n):
        amount = draw(money)
        deposit = draw(st.booleans())
        when = END - timedelta(days=draw(st.integers(min_value=0, max_value=27)))
        signed = amount if deposit else -amount
        cleared = draw(st.booleans())
        register.append(
            rec.RegisterLine(f"r{i}", when, signed, number=None if deposit else str(5000 + i))
        )
        book += signed
        if cleared:
            statement.append(
                rec.StatementLine(
                    f"s{i}",
                    when,
                    "DEPOSIT" if deposit else f"CHECK {5000 + i}",
                    None if deposit else amount,
                    amount if deposit else None,
                    confidence=D("0.99"),
                )
            )
            bank += signed
    unrecorded = draw(st.lists(money, max_size=3))
    for j, amount in enumerate(unrecorded):
        statement.append(
            rec.StatementLine(
                f"u{j}", END - timedelta(days=1), "REFUND", None, amount, confidence=D("0.99")
            )
        )
        bank += amount
    priors = draw(st.lists(money, max_size=3))
    prior_items: list[rec.PriorItem] = []
    for k, amount in enumerate(priors):
        number = str(9000 + k)
        prior_items.append(
            rec.PriorItem(
                f"p{k}",
                "bank",
                "outstanding_check",
                END - timedelta(days=40 + draw(day)),
                amount,
                ref=f"#{number}",
            )
        )
        book -= amount  # the check was booked last month
        if draw(st.booleans()):
            statement.append(
                rec.StatementLine(
                    f"pc{k}",
                    END - timedelta(days=2),
                    f"CHECK {number}",
                    amount,
                    None,
                    confidence=D("0.99"),
                )
            )
            bank -= amount
    opening = draw(money)
    inputs = rec.Inputs(
        END, opening + book, opening + bank, tuple(statement), tuple(register), tuple(prior_items)
    )
    return inputs, len(priors)


@PROPERTIES
@given(ledgers())
def test_property_a_consistent_month_ties(case: tuple[rec.Inputs, int]) -> None:
    inputs, _ = case
    result = rec.reconcile(inputs)
    assert result.tally == "tie", (result.adjusted_bank, result.adjusted_book)


@PROPERTIES
@given(ledgers())
def test_property_carry_forward_is_conserved(case: tuple[rec.Inputs, int]) -> None:
    inputs, priors = case
    result = rec.reconcile(inputs)
    carried = {i.carried_from for i in result.items if i.carried_from}
    cleared = set(result.cleared_prior)
    assert not carried & cleared
    assert len(carried | cleared) == priors


@PROPERTIES
@given(ledgers())
def test_property_pairings_are_one_to_one(case: tuple[rec.Inputs, int]) -> None:
    result = rec.reconcile(case[0])
    lines = [m.statement_line_id for m in result.matches]
    refs = [m.register_line_ref for m in result.matches]
    assert len(lines) == len(set(lines)) and len(refs) == len(set(refs))


@PROPERTIES
@given(ledgers())
def test_property_hashes_are_order_independent(case: tuple[rec.Inputs, int]) -> None:
    inputs = case[0]
    flipped = rec.Inputs(
        inputs.period_end,
        inputs.book_balance,
        inputs.balance_per_bank,
        tuple(reversed(inputs.statement_lines)),
        tuple(reversed(inputs.register_lines)),
        tuple(reversed(inputs.prior_items)),
    )
    assert rec.inputs_hash(inputs) == rec.inputs_hash(flipped)


@PROPERTIES
@given(total=money, months=st.sampled_from([1, 3, 6, 12, 24, 36]))
def test_property_a_schedule_foots_to_its_total(total: Decimal, months: int) -> None:
    start = date(2026, 1, 1)
    year, month = 2026 + (months - 1) // 12, (months - 1) % 12 + 1
    finish = date(year, month, 28)
    lines = calc.schedule(calc.Arrangement("prepaid", total, start, finish))
    assert sum(line.aje for line in lines) == total
    assert lines[-1].ending_balance == 0


@PROPERTIES
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["asset", "liability", "income"]),
            st.sampled_from(["Bank", "Other", "Card"]),
            money,
        ),
        max_size=30,
    )
)
def test_property_rollups_foot(leaves: list[tuple[str, str, Decimal]]) -> None:
    sums = calc.rollup(leaves)
    for classification, types in sums.items():
        assert types[""] == sum((v for k, v in types.items() if k), D("0.00"))
        assert types[""] == sum((a for c, _, a in leaves if c == classification), D("0.00"))
