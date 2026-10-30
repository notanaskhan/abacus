"""SPEC-316 (TASK-345): the grouping-set import's problems, the range rules, the mapping's
content hash and the statements, all by code."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.ledger.mapping import (
    HEADER as TAXONOMY_HEADER,
)
from abacus.modules.ledger.mapping import (
    FsLineView,
    GroupingView,
    MappedAccount,
    build_statements,
    content_hash,
    normalised_code,
    parse_grouping_set,
    resolve_line,
    rule_line,
)

D = Decimal
HEADER = ",".join(TAXONOMY_HEADER) + "\n"
GOOD = HEADER + (
    "cash,Cash,assets,cash,Cash,debit,1000,1099\n"
    "ap,Payables,liabilities,ap,Accounts payable,credit,2000,2099\n"
    "equity,Equity,equity,re,Retained earnings,credit,3000,3999\n"
    "revenue,Revenue,revenue,rev,Revenue,credit,4000,4999\n"
    "expenses,Expenses,expenses,opex,Operating expenses,debit,5000,7999\n"
    "expenses,Expenses,expenses,opex,Operating expenses,debit,900,999\n"
)


def test_ac1_a_clean_taxonomy_parses_in_order() -> None:
    t = parse_grouping_set(GOOD)
    assert t.problems == []
    assert [g.key for g in t.groupings] == ["cash", "ap", "equity", "revenue", "expenses"]
    assert [line.key for line in t.lines] == ["cash", "ap", "re", "rev", "opex"]
    assert ("900", "999", "opex") in t.ranges
    assert parse_grouping_set(GOOD).payload_hash == t.payload_hash


def test_ac1_problems_are_named_by_row_and_code() -> None:
    bad = HEADER + (
        "cash,Cash,assets,cash,Cash,debit,1000,1099\n"
        "x,X,asset,x,X,debit,,\n"
        "y,Y,assets,y,Y,sideways,,\n"
        "cash,Cash,liabilities,c2,C2,debit,,\n"
        "z,Z,assets,z,Z,debit,1050,1060\n"
        "w,W,assets,w,W,debit,1999,1500\n"
    )
    codes = [(p.row, p.code) for p in parse_grouping_set(bad).problems]
    assert (3, "class_invalid") in codes
    assert (4, "normal_balance_invalid") in codes
    assert (5, "duplicate_key") in codes
    assert (7, "range_invalid") in codes
    assert (0, "overlapping_range") in codes
    assert [p.code for p in parse_grouping_set("a,b\n1,2\n").problems] == ["header"]


def test_ac3_ranges_compare_account_codes_as_numbers() -> None:
    a, b = uuid4(), uuid4()
    ranges = [("900", "999", a), ("1000", "1999", b)]
    assert rule_line("950", ranges) == a
    assert rule_line("1000", ranges) == b
    assert rule_line("10000", ranges) is None  # not "1000" < "10000" < "1999" as text
    assert rule_line("ABC", ranges) is None


def _line(key: str, normal: str, grouping: str) -> FsLineView:
    return FsLineView(uuid4(), key, key.title(), normal, grouping)


def _account(
    code: str, eoy: str, line: FsLineView | None, boy: str | None = None
) -> MappedAccount:
    return MappedAccount(
        code,
        code,
        D(eoy),
        None,
        D(boy) if boy else None,
        line.id if line else None,
        "number_range" if line else None,
        None,
        None,
    )


def test_ac6_statements_present_on_the_normal_side_and_balance() -> None:
    cash, ap, re, rev, opex = (
        _line("cash", "debit", "cash"),
        _line("ap", "credit", "ap"),
        _line("re", "credit", "equity"),
        _line("rev", "credit", "revenue"),
        _line("opex", "debit", "expenses"),
    )
    groupings = [
        GroupingView(uuid4(), "cash", "Cash", "assets", [cash]),
        GroupingView(uuid4(), "ap", "Payables", "liabilities", [ap]),
        GroupingView(uuid4(), "equity", "Equity", "equity", [re]),
        GroupingView(uuid4(), "revenue", "Revenue", "revenue", [rev]),
        GroupingView(uuid4(), "expenses", "Expenses", "expenses", [opex]),
    ]
    accounts = [
        _account("1000", "500.00", cash, "300.00"),
        _account("2000", "-120.00", ap, "-100.00"),
        _account("3000", "-200.00", re, "-200.00"),
        _account("4000", "-400.00", rev),
        _account("6000", "220.00", opex),
        _account("9999", "0.00", None),
    ]
    s = build_statements(groupings, accounts, "unadjusted")
    assert s.totals == {
        "assets": D("500.00"),
        "liabilities": D("120.00"),
        "equity": D("200.00"),
        "revenue": D("400.00"),
        "expenses": D("220.00"),
    }
    assert s.net_income == D("180.00") and s.balanced and s.unmapped == 1
    assert s.py_totals is not None and s.py_totals["assets"] == D("300.00")
    off = build_statements(groupings, accounts[:-2], "unadjusted")
    assert not off.balanced and off.difference == D("-220.00")


def test_ac3_the_content_hash_follows_the_mapping() -> None:
    v, line = uuid4(), uuid4()
    one = content_hash(v, [("1000", line), ("2000", None)])
    assert one == content_hash(v, [("2000", None), ("1000", line)])
    assert one != content_hash(v, [("1000", line), ("2000", line)])


def test_ac7_people_map_and_publish() -> None:
    def allowed(action: str) -> set[str]:
        return {r for r, d in RULES[action].decisions.items() if d == "allow"}

    assert "agent" not in allowed("mapping_set.edit")
    assert allowed("grouping_set.publish") == {"practice_leader", "quality_partner"}
    assert RULES["grouping_set.publish"].mfa_recent


# --- A-03-T08 (TASK-5009): prior-year match before the ranges ----------------------------


def test_a03_t08_codes_normalise_for_the_prior_year_match() -> None:
    assert normalised_code(" 1000-01 ") == normalised_code("100001") == "100001"
    assert normalised_code("AR.Trade") == "artrade"


def test_a03_t08_edit_then_prior_year_then_ranges() -> None:
    cash, ar, edited = uuid4(), uuid4(), uuid4()
    by_key = {"cash": cash, "ar": ar}
    ranges = [("1000", "1099", cash), ("1100", "1199", ar)]
    prior = {normalised_code("1150"): "cash"}  # last year this AR-range account sat in cash
    assert resolve_line("1150", edited, prior, by_key, ranges) == (edited, "manual")
    assert resolve_line("1150", None, prior, by_key, ranges) == (cash, "prior_year")
    assert resolve_line("1160", None, prior, by_key, ranges) == (ar, "number_range")
    assert resolve_line("9999", None, prior, by_key, ranges) == (None, None)


def test_a03_t08_a_prior_key_missing_from_this_version_falls_back_to_the_ranges() -> None:
    ar = uuid4()
    assert resolve_line(
        "1150", None, {"1150": "retired_line"}, {"ar": ar}, [("1100", "1199", ar)]
    ) == (
        ar,
        "number_range",
    )
