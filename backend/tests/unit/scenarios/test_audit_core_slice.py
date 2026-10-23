"""F-04-T20 (F-04.10; SPEC-307 AC-1, AC-3, AC-5): the E0 audit-core slice's content foots to the
plan's figures before anything is loaded. The figures are typed here from F-04 §3.2 and blueprint
01 §9.5 / §9.7, never read back from the code under test."""

from __future__ import annotations

from collections import Counter

from abacus_tools.synthetic.scenarios.brightwater_hale import build, loader
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import (
    AUDITS,
    BY_LABEL,
    FIRM_SETTINGS,
    PBC_LISTS,
    PORTAL_USERS,
    SINK_DOMAIN,
    created_at,
    team_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id

# F-04.10: EBP 14 · FS 6 · Review 4 · Compilation/preparation 3, and the stages in C2 codes.
TYPES = {"ebp_audit": 14, "fs_audit": 6, "review": 4, "compilation+preparation": 3}
PHASES = {"planning": 7, "fieldwork": 9, "in_review": 6, "ready_to_release": 2, "released": 3}


def _group(kind: str) -> str:
    return "compilation+preparation" if kind in ("compilation", "preparation") else kind


def test_ac1_27_audits_with_the_exact_type_and_stage_splits() -> None:
    assert len(AUDITS) == 27 == sum(TYPES.values()) == sum(PHASES.values())
    assert Counter(_group(a.type) for a in AUDITS) == TYPES
    assert Counter(a.phase for a in AUDITS) == PHASES
    assert [a.label for a in AUDITS] == [f"A{n}" for n in range(1, 28)]


def test_ac1_released_is_delivered_or_archived_and_the_letters_out_stay_accepted() -> None:
    status = {a.label: a.status for a in AUDITS}
    assert {k for k, v in status.items() if v == "archived"} == {"A4", "A20"}  # ENG-01
    assert {k for k, v in status.items() if v == "accepted"} == {"A2", "A7"}  # E14, E11 out
    assert all(a.status in ("delivered", "archived") for a in AUDITS if a.phase == "released")


def test_ac1_engagement_partners_are_the_section_9_7_ep_column() -> None:
    ep = "MO MO CM PR TW CM MO TW CM MO TW CM MO MO TW CM CM TW CM MO TW CM CM TW CM PR PR"
    assert [a.ep for a in AUDITS] == ep.split()
    assert all(team_of(a)[0] == (a.ep, "engagement_partner") for a in AUDITS)


def test_northwind_is_the_deep_ebp_with_its_handoff_team_and_dates() -> None:
    northwind = BY_LABEL["A1"]
    assert (northwind.client, northwind.entity) == (
        "Northwind Robotics, Inc.",
        "Northwind Robotics 401(k) Plan",
    )
    assert [i for i, _ in team_of(northwind)] == ["MO", "HL", "MD", "AC", "TW"]  # AUD-03 rail
    assert created_at(northwind).date().isoformat() == "2026-05-28"
    assert str(northwind.due_on) == "2026-10-09"  # report target 9 Oct
    assert BY_LABEL["A22"].client == "Oakline Software, Inc."
    assert ("TW", "reviewer") in team_of(BY_LABEL["A22"])  # "EQR TW"


def test_ac1_northwind_pbc_reads_11_of_24() -> None:
    northwind = next(p for p in PBC_LISTS if p.engagement == "A1")
    statuses = Counter(r.status for r in northwind.requests)
    assert len(northwind.requests) == 24
    assert statuses == {"received": 11, "uploaded": 1, "requested": 12}  # AUD-03 totals
    assert northwind.published


def test_ac1_granite_peak_fs_pbc_has_41_requests_held_as_drafts() -> None:
    granite = next(p for p in PBC_LISTS if p.engagement == "A2")
    assert len(granite.requests) == 41
    assert {r.status for r in granite.requests} == {"draft"}  # G3 not met: the letter is out
    assert not granite.published
    assert len(granite.categories()) == 13


def test_staff_can_accept_evidence_is_on() -> None:
    assert FIRM_SETTINGS == (("staff_can_accept_evidence", True),)  # DEC-37


def test_ac5_portal_people_are_on_the_sink_and_keyed_like_the_ts_seed() -> None:
    assert [u.name for u in PORTAL_USERS] == [
        "Dana Kowalski",
        "Victoria Lam",
        "Robert Haines",
        "Luis Ferrante",
    ]
    assert all(u.email.endswith(f"@{SINK_DOMAIN}") for u in PORTAL_USERS)
    assert PORTAL_USERS[0].id == stable_id("user:dana-kowalski")
    assert {u.role for u in PORTAL_USERS} == {"owner", "tcwg"}


def test_ids_derive_from_labels_as_the_ts_seed_does() -> None:
    assert BY_LABEL["A1"].id == stable_id("engagement:A1")
    northwind = next(p for p in PBC_LISTS if p.engagement == "A1")
    assert northwind.request_id(1) == stable_id("request:northwind:1")


def test_slice_events_are_dated_by_e0_and_ordered_for_their_dependencies() -> None:
    events = build().events
    kinds = [e.kind for e in loader.replay_order(events)]
    assert all(e.at <= DEMO_INSTANT for e in events)
    assert kinds.count("engagements.engagement_created") == 27
    assert kinds.count("requests.pbc_list_created") == 2
    assert kinds.count("organisations.client_entity_added") == 2
    last_client = max(i for i, k in enumerate(kinds) if k == "organisations.client_created")
    first_engagement = kinds.index("engagements.engagement_created")
    assert last_client < first_engagement
    assert max(i for i, k in enumerate(kinds) if k == "identity.portal_user_added") < min(
        i for i, k in enumerate(kinds) if k == "requests.pbc_list_created"
    )


def test_ac3_fairhaven_takes_its_engagement_with_it() -> None:
    held = build(holdouts=("fairhaven_ebp",)).events
    engagements = [e for e in held if e.kind == "engagements.engagement_created"]
    assert len(engagements) == 26
    assert "engagement:A7" not in {e.label for e in engagements}
