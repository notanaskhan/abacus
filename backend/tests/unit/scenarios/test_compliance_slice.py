"""Q-02-T39: the `compliance` slice (FIL-02a's eight retention policies, FIL-02b's two holds,
INC-2026-005 and the flags they sit behind). Opt-in, deterministic, every kind has a loader
handler, it replays after the people it names, it carries no legal floor, and its facts match the
fixtures G-02 and Q-05 read (apps/web/src/fixtures/seed/compliance.ts)."""

from __future__ import annotations

import re
from datetime import UTC
from pathlib import Path

from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, build, loader
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import build_clients
from abacus_tools.synthetic.scenarios.brightwater_hale.compliance import (
    FLAGS,
    HOLDS,
    INCIDENT,
    INCIDENT_DISCOVERED,
    POLICIES,
    compliance_events,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.people import FIRM_ROLES, SEATS
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

WEB_SEED = Path(__file__).parents[4] / "apps/web/src/fixtures/seed"
SLICES = ("audit_core", "people", "compliance")


def _compliance() -> list[Event]:
    return [e for e in build(slices=SLICES).events if e.slice == "compliance"]


def test_the_slice_is_registered_opt_in_and_brings_people() -> None:
    assert "compliance" in registered()
    assert all(e.slice == "audit_core" for e in build().events)
    assert build().fingerprint() == SCENARIO_HASH
    assert loader.expand_slices(("compliance",)) == ("people", "compliance")


def test_the_slice_is_deterministic_and_every_kind_has_a_handler() -> None:
    assert build(slices=SLICES).fingerprint() == build(slices=SLICES).fingerprint()
    assert [e.id for e in compliance_events()] == [e.id for e in compliance_events()]
    assert {e.kind for e in compliance_events()} <= set(loader.HANDLERS)


def test_its_events_fall_between_setup_and_e0_after_the_people_they_name() -> None:
    events = _compliance()
    assert len(events) == len(FLAGS) + len(POLICIES) + len(HOLDS) + 1 == 13
    assert all(SETUP_AT <= e.at <= DEMO_INSTANT for e in events)
    kinds = [e.kind for e in loader.replay_order(build(slices=SLICES).events)]
    last_profile = max(i for i, k in enumerate(kinds) if k == "identity.member_profile_set")
    first_flag = kinds.index("platform.flag_set")
    first_policy = kinds.index("evidence.retention_policy_set")
    first_hold = kinds.index("evidence.legal_hold_placed")
    assert last_profile < first_flag < first_policy < first_hold
    assert kinds.index("platform.incident_recorded") > first_hold


def test_fil02a_has_eight_firm_policies_of_seven_years_and_only_audit_documentation_locked() -> (
    None
):
    assert len(POLICIES) == 8
    assert {p.firm_years for p in POLICIES} == {"7"}
    assert [p.record_type for p in POLICIES if p.lock] == ["audit_documentation"]
    assert all(re.fullmatch(r"[a-z][a-z0-9_]{1,62}", p.record_type) for p in POLICIES)
    assert len({(p.record_type, p.service_line) for p in POLICIES}) == 8


def test_no_legal_floor_or_authority_is_seeded() -> None:
    """DEC-71: floors are counsel's, published through the two-person import, never committed."""
    for event in _compliance():
        assert not {"legal_floor_years", "authority", "floor"} & set(event.data)
    assert not any(e.kind.startswith("platform.retention_floor") for e in _compliance())


def test_the_holds_are_fil02bs_two_on_existing_clients_by_partners() -> None:
    names = {c.name for c in build_clients()}
    partners = {s.initials for s in SEATS if s.role == "Partner"}
    holds = [e for e in _compliance() if e.kind == "evidence.legal_hold_placed"]
    assert [(e.data["client"], e.data["tax_year"], e.actor) for e in holds] == [
        ("Wren & Avery Collins", 2023, "VH"),
        ("Meridian Tool & Die, Inc.", 2024, "NA"),
    ]
    assert all(e.data["client"] in names and e.actor in partners for e in holds)
    assert [h.canon_placed_on for h in HOLDS] == ["2026-08-12", "2026-08-14"]


def test_the_incident_matches_the_adm06_fixture() -> None:
    fixture = (WEB_SEED / "compliance.ts").read_text(encoding="utf-8")
    assert f'title: "{INCIDENT["title"]}"' in fixture
    assert f'event_kind: "{INCIDENT["event_kind"]}"' in fixture
    discovered = INCIDENT_DISCOVERED.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert f'discovered_at: "{discovered}"' in fixture
    assert f"consumers_affected: {INCIDENT['consumers_affected']}," in fixture
    assert "unencrypted: null," in fixture and INCIDENT["unencrypted"] is None
    (incident,) = [e for e in _compliance() if e.kind == "platform.incident_recorded"]
    assert incident.actor == "FA" and incident.at == INCIDENT_DISCOVERED
    assert "FA" in FIRM_ROLES  # Felix is staff with a firm role; `people` makes it security_admin
