"""Independent AC tests and goldens for the EBP-07 and AUD-27 services (A-05-T59; ADR-078;
TASK-6216; A-05 F7, F11).

Written from A-05 §3 (Hannah's EBP-07 and AUD-27) and the handoff's figures, not from the
implementation. Row acceptance: "The 4i schedule totals 16,812,400 with party-in-interest
asterisks, and a non-EP decide answers 403." Also: the 5500 ties (only the 48,600 receivable,
15,060 + 33,540, differs), Part IV 4a agrees with the one late-remittance record, and that record
is read where it lives, never copied.
"""

from __future__ import annotations

import re
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest

from abacus.modules.assurance import aud27, ebp_form5500
from abacus.modules.assurance.compute.ebp import form5500 as engine
from abacus.modules.identity.authz import matrix
from abacus.modules.identity.authz.conditions import ConditionFacts, conditions_hold

SRC = Path(__file__).resolve().parents[3] / "src" / "abacus"
MIGRATIONS = Path(__file__).resolve().parents[3] / "migrations" / "versions"

# The handoff's 4i schedule (EBP-07 c): eight holdings, every one but the brokerage window a party
# in interest, cost omitted for the participant-directed investments.
RIC = "registered investment company"


def _held(
    name: str, value: str, *, pii: bool = True, directed: bool = True, desc: str = RIC
) -> engine.HeldAsset:
    return engine.HeldAsset(name, desc, D(value), None if directed else D(0), pii, directed)


HOLDINGS = [
    _held("KRS 500 Index Fund", "6120450"),
    _held("KRS Target 2035 Fund", "2384910"),
    _held("KRS Target 2045 Fund", "2915330"),
    _held("KRS Bond Index Fund", "1408220"),
    _held("KRS International Index Fund", "902610"),
    _held("Harborline Stable Value Fund", "1163480", desc="common/collective trust"),
    _held("Self-directed brokerage accounts (BrokerWindow)", "1605000", pii=False, desc="various"),
    _held("Participant loans", "312400", directed=False, desc="maturities through 2040"),
]


# --- 4i ----------------------------------------------------------------------------------------


def test_the_4i_schedule_totals_16_812_400_and_ties_to_the_draft() -> None:
    schedule = engine.schedule_4i(HOLDINGS, D("16812400"))
    assert schedule.total == D("16812400")
    assert schedule.ties


def test_parties_in_interest_carry_the_asterisk_and_only_they_do() -> None:
    schedule = engine.schedule_4i(HOLDINGS, D("16812400"))
    marked = {r.identity for r in schedule.rows if r.mark == "*"}
    assert "Self-directed brokerage accounts (BrokerWindow)" not in marked
    assert len(marked) == 7
    assert all(r.mark in {"*", ""} for r in schedule.rows)


def test_cost_is_omitted_for_participant_directed_investments_only() -> None:
    schedule = engine.schedule_4i(HOLDINGS, D("16812400"))
    omitted = [r for r in schedule.rows if r.cost_omitted]
    assert len(omitted) == 7 and all(r.cost is None for r in omitted)
    [loans] = [r for r in schedule.rows if not r.cost_omitted]
    assert loans.identity == "Participant loans"


def test_a_4i_total_off_the_draft_does_not_tie() -> None:
    assert not engine.schedule_4i(HOLDINGS[:-1], D("16812400")).ties
    assert not engine.schedule_4i(HOLDINGS, None).ties


def test_the_4i_hash_moves_with_a_mark() -> None:
    flipped = [
        *HOLDINGS[:-1],
        engine.HeldAsset("Participant loans", "", D("312400"), D("0"), False, False),
    ]
    assert (
        engine.schedule_4i(HOLDINGS, None).inputs_hash
        != engine.schedule_4i(flipped, None).inputs_hash
    )


# --- 5500 ties and Part IV -----------------------------------------------------------------------


def test_net_assets_per_5500_are_beginning_plus_net_income() -> None:
    assert engine.sums_to(D("16812400"), [D("14228500"), D("2583900")])


def test_only_the_receivable_differs_and_it_is_a_reconciling_item() -> None:
    lines = [("1c(9)", D("1163480")), ("1b(2)", D("0")), ("1l", D("16812400"))]
    fs = {"1c(9)": D("1163480"), "1b(2)": D("48600"), "1l": D("16861000")}
    result = ebp_form5500.compute(lines, fs, [], D("0"))
    differences = {t.line_code: t.difference for t in result.lines if t.difference}
    assert differences == {"1b(2)": D("48600"), "1l": D("48600")}
    split = engine.classify("1b(2)", D("48600"), D("0"), [D("15060"), D("33540")])
    assert split.classification == "reconciling_item"
    # A documented basis difference is never an inconsistency; an unexplained one always is.
    assert engine.classify("1b(2)", D("48600"), D("0")).classification == "inconsistent"


@pytest.mark.parametrize(
    ("answer", "amount", "late", "expected"),
    [
        ("yes", D("33540"), D("33540"), "consistent"),
        ("no", None, D("33540"), "inconsistent"),
        ("yes", D("15060"), D("33540"), "inconsistent"),
        ("no", None, D("0"), "consistent"),
    ],
)
def test_part_iv_4a_agrees_with_the_late_deposits(
    answer: str, amount: D | None, late: D, expected: str
) -> None:
    assert engine.part_iv_4a(answer, amount, late) == expected


# --- the EP-reserved conclusion ------------------------------------------------------------------


def test_an_estimate_conclusion_is_reserved_to_the_engagement_partner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []  # Any: test doubles
    monkeypatch.setattr(aud27, "register_decision_kind", seen.append)
    aud27.register_estimate_conclusion_kind()
    assert [(k.code, k.reserved_role) for k in seen] == [
        (aud27.CONCLUSION_KIND, "engagement_partner")
    ]


def test_a_non_ep_decide_is_refused() -> None:
    """`decision.decide` carries `reserved_role`: a manager (or any non-holder) is refused, which
    the route answers 403; an agent never holds it."""
    rule = matrix.RULES["decision.decide"]
    assert rule.reserved_role
    assert not conditions_hold(
        rule, ConditionFacts(reserved_holder=False, level="manager"), person=True
    )
    assert not conditions_hold(rule, ConditionFacts(reserved_holder=True), person=False)


def test_the_agent_never_concludes_an_estimate() -> None:
    for action in ("estimate.evaluate", "related_party.screen_out", "decision.decide"):
        entries = matrix.ACTIONS[action]
        assert entries.get("agent", "deny") == "deny", action


# --- one late-remittance record ------------------------------------------------------------------


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_late_remittances_live_in_one_object() -> None:
    """One object (0658): the remittance row, and its event log (corrections, status moves).
    Only the object holds the late principal; nothing else names a late-remittance table."""
    created: set[str] = set()
    for path in MIGRATIONS.glob("*.py"):
        created |= set(re.findall(r"CREATE TABLE (\w*late_remit\w*)", path.read_text()))
    assert created == {"ebp_late_remittances", "ebp_late_remittance_events"}
    source = next(MIGRATIONS.glob("0658_*.py")).read_text()
    events = source[source.index("CREATE TABLE ebp_late_remittance_events") :]
    events = events[: events.index(")\n")]
    assert "principal" not in events


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_4a_aud27_and_ebp04_read_the_same_record() -> None:
    readers = {
        "ebp_form5500.py": "ebp_late_remittances",
        "aud27.py": "ebp_late_remittances",
    }
    for name, table in readers.items():
        source = (SRC / "modules" / "assurance" / name).read_text()
        assert re.search(rf"FROM {table}\b", source), name
    # EBP-04 maps the table itself (the late-remittance object, 0658).
    remittances = (SRC / "modules" / "assurance" / "ebp_remittances.py").read_text()
    assert '__tablename__ = "ebp_late_remittances"' in remittances
    # Nothing outside assurance reads or copies it.
    others = [
        p for p in (SRC / "modules").rglob("*.py")
        if "assurance" not in p.parts and "ebp_late_remittances" in p.read_text()
    ]  # fmt: skip
    assert others == []
