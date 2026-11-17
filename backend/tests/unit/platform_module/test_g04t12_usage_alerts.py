"""G-04-T12: usage alert crossings (SPEC-680 AC-35, AC-38; DEC-5419)."""

from __future__ import annotations

import uuid

from abacus.modules.platform.usage_alerts import Rule, crossed, engagement_crossed

R75 = Rule(uuid.uuid4(), 75, (), ("firm_admins",))
R90 = Rule(uuid.uuid4(), 90, (), ("firm_admins", "partners"))
R100 = Rule(uuid.uuid4(), 100, (), ("firm_admins",))


def test_ac35_crossing_18000_of_20000_reaches_the_90_percent_rule() -> None:
    assert [r.pct for r in crossed(18_000, 20_000, [R100, R90, R75])] == [75, 90]
    assert [r.pct for r in crossed(17_999, 20_000, [R100, R90, R75])] == [75]
    assert [r.pct for r in crossed(20_860, 20_000, [R75, R90, R100])] == [75, 90, 100]


def test_no_included_minutes_alerts_nothing() -> None:
    assert crossed(5_000, 0, [R75]) == []


def test_ac38_granite_peak_at_1240_of_1500_alerts_at_80_percent() -> None:
    assert engagement_crossed(1_240, 1_500, 80) is True
    assert engagement_crossed(1_199, 1_500, 80) is False
    assert engagement_crossed(10, 0, 80) is False
