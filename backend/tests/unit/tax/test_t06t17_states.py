"""T-06-T17 (SPEC-702; DEC-5628): E9 on Ridgeline's 2025 Form 1065 (TXP-09)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.tax.compute import states as e9

D = Decimal
BASE = D("1231600")
NUMERATORS = {"IL": D("566536"), "CO": D("387954"), "NY": D("277110")}
WEIGHTS = {
    "Ridgeline GP LLC": D("2"),
    "Meera Shah": D("38"),
    "Pell Street Ventures LLC": D("32.5"),
    "Pell Street II LLC": D("2.5"),
    "Jonah Feld": D("25"),
}


def test_apportionment_is_46_0_31_5_22_5() -> None:
    rows = e9.apportion(NUMERATORS, BASE)
    assert [r.share for r in rows] == [D("46.0"), D("31.5"), D("22.5")]
    assert sum(r.share for r in rows) == D("100.0")


def test_ptet_is_64_096() -> None:
    amounts = {s: e9.ptet(n, e9.rate(2025, s)) for s, n in NUMERATORS.items()}
    assert amounts == {"IL": D("28044"), "CO": D("17070"), "NY": D("18982")}
    assert sum(amounts.values()) == D("64096")


def test_credits_foot_to_each_state_and_feld_is_16_025() -> None:
    expected = {
        "IL": [D("561"), D("10657"), D("9114"), D("701"), D("7011")],
        "CO": [D("341"), D("6486"), D("5548"), D("427"), D("4268")],
        "NY": [D("380"), D("7213"), D("6169"), D("474"), D("4746")],
    }
    feld = D("0")
    for state, amount in {"IL": D("28044"), "CO": D("17070"), "NY": D("18982")}.items():
        credits = e9.partner_credits(amount, WEIGHTS, half_up=["Jonah Feld"])
        assert list(credits.values()) == expected[state]
        assert sum(credits.values()) == amount
        feld += credits["Jonah Feld"]
    assert feld == D("16025")


def test_a_state_without_a_published_rate_is_refused() -> None:
    with pytest.raises(e9.ParameterMissing):
        e9.rate(2025, "CA")
    with pytest.raises(e9.ParameterMissing):
        e9.rate(2031, "IL")


def test_numerators_must_foot_and_payment_gaps_are_found() -> None:
    with pytest.raises(ValueError, match="foot"):
        e9.apportion({"IL": D("1")}, BASE)
    gaps = e9.payment_gaps({"IL": D("28044"), "NY": D("18982")}, {"IL": D("28044")})
    assert gaps == ["NY"]
