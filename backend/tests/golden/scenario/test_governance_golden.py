"""G-02-T07 (ADR-078): the governance golden at E0 against the backend.

`brightwater_hale/governance_e0.json` is transcribed from the ADM-04, ADM-06 and ADM-07 handoff
specs and G-02 §5.4; the SPA's fixtures foot to the same file
(`apps/web/src/fixtures/governance.foot.test.ts`), so fixture mode and the seed read one set of
figures. Here: the incident register's FTC clock gives Day 4 of 30 and Oct 10 for the seeded
discovery; the Copperleaf batch foots in Decimal; every policy version was approved by someone
other than its publisher (DEC-415 Q2); the MFA counts and the audit-log counts hold together."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

from abacus.modules.platform.api import clock_day, incident_clock
from abacus_tools.synthetic.scenarios.brightwater_hale import compliance

GOLDEN: Final = cast(
    dict[str, object],
    json.loads(
        (Path(__file__).parent / "brightwater_hale" / "governance_e0.json").read_text("utf-8")
    ),
)
ZONE: Final = "America/Chicago"


def _part(key: str) -> dict[str, object]:
    return cast(dict[str, object], GOLDEN[key])


def test_inc_2026_005_reads_day_4_of_30_and_notice_by_oct_10() -> None:
    [i5, *_] = cast(list[dict[str, object]], GOLDEN["incidents"])
    discovered = datetime.fromisoformat(str(i5["discovered_at"]))
    assert discovered == compliance.INCIDENT_DISCOVERED  # the seeded slice agrees
    e0 = datetime.fromisoformat(str(GOLDEN["at"])).date()
    assert clock_day(discovered, ZONE, e0) == i5["clock_day"] == 4
    assert incident_clock(discovered, ZONE) == date.fromisoformat(str(i5["ftc_notify_by"]))


def test_the_closed_incidents_are_not_notification_events() -> None:
    for incident in cast(list[dict[str, object]], GOLDEN["incidents"])[1:]:
        assert incident["notification_event"] is False
        assert incident["state"] == "closed"


def test_the_copperleaf_batch_foots_to_20020() -> None:
    copperleaf = _part("copperleaf")
    amounts = [Decimal(str(a)) for a in cast(list[str], copperleaf["amounts"])]
    assert sum(amounts, Decimal(0)) == Decimal(str(copperleaf["total"])) == Decimal("20020.00")
    left = cast(dict[str, str], copperleaf["not_included"])
    assert Decimal(left["amount"]) == Decimal("14900.00")


def test_the_audit_log_counts_hold_together() -> None:
    log = cast(dict[str, int], GOLDEN["audit_log"])
    assert (log["total"], log["via_agent_total"], log["via_agent_shown"]) == (18_406, 1_962, 4)
    assert log["via_agent_shown"] <= log["rows"] <= log["total"]
    assert log["policy_events"] == 0  # the policy principal is dormant (ADR-187)


def test_mfa_is_46_of_46_at_e0_and_41_of_46_on_jan_11() -> None:
    mfa = cast(dict[str, dict[str, int]], GOLDEN["mfa"])
    assert (mfa["e0"]["enrolled"], mfa["e0"]["seats"]) == (46, 46)
    jan = mfa["jan_11_2026"]
    assert (jan["enrolled"], jan["seats"], jan["seats"] - jan["enrolled"]) == (41, 46, 5)


def test_each_policy_version_was_approved_by_another_partner() -> None:
    versions = cast(list[dict[str, object]], GOLDEN["ai_policy_versions"])
    assert [v["version"] for v in versions] == [1, 2, 3]
    assert [v["published_on"] for v in versions] == ["2026-01-05", "2026-01-09", "2026-01-14"]
    for v in versions:
        assert v["approved_by"] != v["published_by"]
