# ac-test-author: ayushkbhatia
"""Q-04-T013 (TASK-1734; ADR-078 independent; Q-04-T009, DEC-808): the go-live check, c09, from
chapter 06 §8.3 and SPEC-403, not Q-04-T009's tests.

Acceptance (the task row): "... a failing go-live item for each chapter 06 section 8.3 category."
Every category the check reads (Tenant, Identity, AI, Integrations, Operations) fails with its own
item named when one fact is broken, and the report fails as a whole; a category held only in the
dossier (Data protection) reports manual items with their dossier section, never a silent pass.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date, datetime
from typing import Any
from uuid import UUID

import pytest
import yaml

from abacus_tools import release_windows
from abacus_tools.go_live import Facts, evaluate, report

FIRM = UUID("00000000-0000-4000-8000-0000000000b7")
AT = datetime.fromisoformat("2027-05-24T10:00:00-05:00")


def _calendar() -> release_windows.Calendar:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(release_windows.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    doc["firms"] = [{"tenant_id": str(FIRM), "code": "PF-B7", "real_data_since": "2027-06-01"}]
    return release_windows.parse(doc)


READY = Facts(
    tenant_id=FIRM,
    synthetic=False,
    provisioned=True,
    pilot_code="PF-B7",
    sso_enforced=True,
    sso_exempt_designated=True,
    mfa_enrolled=12,
    mfa_seats=12,
    firm_admins=1,
    security_admins=1,
    support_requests_allowed=False,
    ai_opted_in=True,
    agent_stages={"evidence.screener": "live"},
    flags_on=frozenset(),
    terms_review_by=(date(2028, 1, 31),),
    writes_enabled=0,
    on_call_updated=date(2027, 5, 1),
)

# One broken fact per category and the item that must name it.
BROKEN: list[tuple[str, dict[str, object], str]] = [
    ("Tenant", {"provisioned": False}, "tenant.provisioned"),
    ("Tenant", {"synthetic": True}, "tenant.real"),
    ("Identity", {"sso_enforced": False}, "identity.sso_enforced"),
    ("Identity", {"mfa_enrolled": 11}, "identity.mfa_all_staff"),
    ("Identity", {"sso_exempt_designated": False}, "identity.break_glass"),
    ("Identity", {"security_admins": 0}, "identity.roles_mapped"),
    ("AI", {"terms_review_by": ()}, "ai.provider_terms"),
    ("AI", {"ai_opted_in": False}, "ai.client_data_opt_in"),
    ("AI", {"agent_stages": {"evidence.screener": "draft"}}, "ai.agents_at_shadow"),
    ("Integrations", {"writes_enabled": 1}, "integrations.no_writes"),
    ("Operations", {"pilot_code": None}, "windows.entry"),
    (
        "Operations",
        {"flags_on": frozenset({"portal.sign_in_v2"})},
        "communications.no_client_facing",
    ),
    ("Operations", {"on_call_updated": None}, "operations.on_call_current"),
]


def test_a_ready_firm_passes_shadow() -> None:
    items = evaluate("shadow", READY, AT, _calendar())
    assert report("shadow", READY, AT, items)["failed"] == []


@pytest.mark.parametrize(("section", "change", "item"), BROKEN)
def test_ac_each_category_fails_with_its_item_named(
    section: str, change: dict[str, object], item: str
) -> None:
    broken = replace(READY, **change)
    items = evaluate("shadow", broken, AT, _calendar())
    out = report("shadow", broken, AT, items)
    assert out["passed"] is False
    assert out["failed"] == [item]
    named = next(i for i in items if i.id == item)
    assert (named.section, named.status) == (section, "fail")
    assert named.value != ""


def test_every_readable_category_has_a_failing_case() -> None:
    sections = {
        i.section for i in evaluate("shadow", READY, AT, _calendar()) if i.status != "manual"
    }
    assert sections <= {s for s, _, _ in BROKEN}


def test_a_dossier_only_category_reports_manual_items_with_their_section() -> None:
    items = [
        i for i in evaluate("shadow", READY, AT, _calendar()) if i.section == "Data protection"
    ]
    assert items
    assert all(i.status == "manual" and i.dossier.startswith("§Data protection") for i in items)
