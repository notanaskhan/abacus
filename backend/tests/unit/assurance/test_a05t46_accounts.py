"""A-05-T46 (TASK-5120; A-05 F7; EBP-08): participant accounts by code.

Row acceptance: "Active 13,640,900 + Terminated 3,171,500 = 16,812,400 and SDBA types sum to
1,605,000, with 'Signed off' only after L4." Sign-off itself is P-04's on the workpaper.
"""

from __future__ import annotations

from decimal import Decimal as D

from abacus.modules.assurance.compute.ebp import accounts as engine


def _account(status: str, *values: int) -> engine.ParticipantBalance:
    beginning, contributions, earnings, distributions, fees, transfers, ending = values
    return engine.ParticipantBalance(
        participant_key=f"{status}-1",
        status=status,
        beginning=D(beginning),
        contributions=D(contributions),
        earnings=D(earnings),
        distributions=D(distributions),
        fees=D(fees),
        transfers=D(transfers),
        ending=D(ending),
    )


ACTIVE = _account("active", 11612300, 1318300, 1716000, -104600, -29200, -871900, 13640900)
TERMINATED = _account("terminated", 2616200, 0, 400650, -708050, -9200, 871900, 3171500)


def test_the_groups_crossfoot_and_foot() -> None:
    roll = engine.rollforward([ACTIVE, TERMINATED])
    assert [g.crossfoots for g in roll.groups] == [True, True]
    assert roll.total.ending == D(16812400)
    assert roll.total.beginning == D(14228500)
    assert roll.total.contributions == D(1318300)
    assert roll.total.earnings == D(2116650)
    assert roll.total.distributions == D(-812650)
    assert roll.total.fees == D(-38400)
    assert roll.transfers_net_zero
    assert roll.total.crossfoots


def test_a_group_that_doesnt_crossfoot_says_so() -> None:
    wrong = _account("active", 100, 0, 0, 0, 0, 0, 101)
    assert not engine.rollforward([wrong]).groups[0].crossfoots


def test_transfers_that_dont_net_to_zero_are_caught() -> None:
    assert not engine.rollforward([ACTIVE]).transfers_net_zero


def test_ties() -> None:
    assert engine.tie("fees", D(38400), D(38400)).ties is True
    assert engine.tie("fees", D(38401), D(38400)).ties is False
    assert engine.tie("fees", None, D(38400)).ties is None


def test_sdba_by_type_sums_to_the_trust_line() -> None:
    by_type, total = engine.sdba_by_type(
        [
            ("Common stocks", D(924300)),
            ("Exchange-traded funds", D(612450)),
            ("Money market sweep", D(68250)),
        ]
    )
    assert total == D(1605000)
    assert by_type["Common stocks"] == D(924300)


def test_qaca_vesting() -> None:
    assert engine.vested_pct(D(2)) == D(100)
    assert engine.vested_pct(D("1.5")) == D(0)
    assert engine.vested_pct(None) is None


def test_the_hash_ignores_row_order() -> None:
    forward = engine.rollforward([ACTIVE, TERMINATED]).inputs_hash
    backward = engine.rollforward([TERMINATED, ACTIVE]).inputs_hash
    assert forward == backward
