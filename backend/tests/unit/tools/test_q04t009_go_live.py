"""Q-04-T009 (SPEC-403 AC-11; Q-04 AC-6.1 to AC-6.4, AC-5.6, AC-5.7): the go-live check's items.
Every shadow-level item reports a value (pass, fail, or manual with its dossier section); a
tenant below 100% MFA or with a lapsed provider-terms review fails with the item named; each
level adds its own."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import yaml

from abacus_tools import go_live, release_windows
from abacus_tools.go_live import Facts, evaluate, report

A1 = UUID("00000000-0000-4000-8000-0000000000a1")
AT = datetime.fromisoformat("2027-05-24T10:00:00-05:00")  # before PW1


def calendar() -> release_windows.Calendar:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(release_windows.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [{"tenant_id": str(A1), "code": "PF-A1", "real_data_since": "2027-06-01"}]
    return release_windows.parse(doc)


GREEN = Facts(
    tenant_id=A1,
    synthetic=False,
    provisioned=True,
    pilot_code="PF-A1",
    sso_enforced=True,
    sso_exempt_designated=True,
    mfa_enrolled=46,
    mfa_seats=46,
    firm_admins=2,
    security_admins=1,
    support_requests_allowed=True,
    ai_opted_in=True,
    agent_stages={"evidence.screener": "shadow"},
    flags_on=frozenset({"engagements.v2"}),
    terms_review_by=(date(2027, 12, 31),),
    writes_enabled=0,
    flag_expiries={"engagements.v2": date(2027, 8, 20)},
    runbooks_rehearsed={"RB-16": date(2027, 8, 1)},
    on_call_updated=date(2027, 5, 20),
)


def by_id(items: list[go_live.Item]) -> dict[str, go_live.Item]:
    return {i.id: i for i in items}


def test_ac11_every_shadow_item_reports_a_value_and_a_green_firm_passes() -> None:
    items = evaluate("shadow", GREEN, AT, calendar())
    assert len(items) == 20
    assert all(i.value for i in items)
    assert all(i.dossier for i in items if i.status == "manual")
    assert [i.id for i in items if i.status == "fail"] == []
    out = report("shadow", GREEN, AT, items)
    assert (out["passed"], out["failed"], out["pilot_code"]) == (True, [], "PF-A1")


def test_ac11_a_tenant_below_100_percent_mfa_fails_with_the_item_named() -> None:
    items = evaluate("shadow", replace(GREEN, mfa_enrolled=45), AT, calendar())
    out = report("shadow", GREEN, AT, items)
    assert out["failed"] == ["identity.mfa_all_staff"]
    assert by_id(items)["identity.mfa_all_staff"].value == "45 of 46 staff"


@pytest.mark.parametrize(
    ("review_by", "failed"),
    [
        ((date(2027, 8, 1),), True),  # inside go-live + 90 days
        ((date(2027, 8, 22),), False),  # exactly 90 days on
        ((date(2027, 12, 31), date(2027, 6, 30)), True),  # one lapsed among several
        ((), True),  # none registered
    ],
)
def test_ac11_a_lapsed_provider_terms_review_fails_with_the_item_named(
    review_by: tuple[date, ...], failed: bool
) -> None:
    items = evaluate("shadow", replace(GREEN, terms_review_by=review_by), AT, calendar())
    assert (by_id(items)["ai.provider_terms"].status == "fail") is failed


@pytest.mark.parametrize(
    ("change", "item"),
    [
        ({"sso_enforced": False}, "identity.sso_enforced"),
        ({"sso_exempt_designated": False}, "identity.break_glass"),
        ({"security_admins": 0}, "identity.roles_mapped"),
        ({"ai_opted_in": False}, "ai.client_data_opt_in"),
        ({"agent_stages": {"evidence.screener": None}}, "ai.agents_at_shadow"),
        ({"writes_enabled": 1}, "integrations.no_writes"),
        ({"flags_on": frozenset({"portal.pbc_v2"})}, "communications.no_client_facing"),
        ({"on_call_updated": None}, "operations.on_call_current"),
        ({"on_call_updated": date(2027, 4, 1)}, "operations.on_call_current"),
        ({"pilot_code": None}, "windows.entry"),
        ({"synthetic": True}, "tenant.real"),
        ({"provisioned": False}, "tenant.provisioned"),
    ],
)
def test_each_readable_shadow_item_fails_on_its_own(change: dict[str, object], item: str) -> None:
    items = evaluate("shadow", replace(GREEN, **change), AT, calendar())
    assert [i.id for i in items if i.status == "fail"] == [item]


def test_client_facing_adds_its_items_and_refuses_jan_15_to_apr_15() -> None:
    items = by_id(evaluate("client_facing", GREEN, AT, calendar()))
    assert items["season.no_client_facing_go_live"].status == "pass"
    for manual in ("contract.delta_1", "communications.sender_domain", "ai.autonomy_level_1"):
        assert items[manual].status == "manual"
    for when, ok in (
        ("2028-01-14T23:59", True),
        ("2028-01-15T00:00", False),
        ("2028-04-15T23:59", False),
        ("2028-04-16T00:00", True),
    ):
        at = datetime.fromisoformat(when).replace(tzinfo=release_windows.CT)
        found = by_id(evaluate("client_facing", GREEN, at, calendar()))
        assert (found["season.no_client_facing_go_live"].status == "pass") is ok


def test_tax_adds_the_tax_items_on_top_of_client_facing() -> None:
    ids = [i.id for i in evaluate("tax", GREEN, AT, calendar())]
    assert "season.no_client_facing_go_live" in ids and "tax.consent_7216" in ids
    assert len(ids) == 20 + 8 + 6


def test_season_needs_no_flag_expiring_in_the_coming_window_and_rehearsed_runbooks() -> None:
    at = datetime.fromisoformat("2027-08-16T10:00:00-05:00")
    green = by_id(evaluate("season", GREEN, at, calendar()))
    assert green["season.windows_entries"].value == "autumn-2027"
    assert green["season.flags_outside_window"].status == "pass"
    late = replace(
        GREEN,
        flag_expiries={"engagements.v2": date(2027, 9, 10)},
        runbooks_rehearsed={"RB-16": None},
    )
    bad = by_id(evaluate("season", late, at, calendar()))
    assert bad["season.flags_outside_window"].value == "expire inside: engagements.v2"
    assert bad["season.runbooks_rehearsed"].status == "fail"


def test_the_runbook_and_on_call_dates_are_read_from_frontmatter(tmp_path: Path) -> None:
    assert go_live.runbooks_rehearsed(["RB-16"]) == {"RB-16": None}  # last_rehearsed: never
    assert go_live.on_call_updated(tmp_path / "missing.md") is None
    page = tmp_path / "on-call.md"
    page.write_text("---\nupdated: 2027-05-20\n---\n# On-call\n", encoding="utf-8")
    assert go_live.on_call_updated(page) == date(2027, 5, 20)
