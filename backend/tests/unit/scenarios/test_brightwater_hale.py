"""F-04-T10 (SPEC-307 AC-1 to AC-4; DEC-47): "Deterministic package with a SCENARIO_VERSION
golden hash yields 184 clients with no suffix and only reserved identifier ranges." The TS seed
must produce the same clients row for row (golden `clients.json`, checked from both sides)."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, build
from abacus_tools.synthetic.scenarios.brightwater_hale.clients import build_clients
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import SNAPSHOTS, snapshot
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event, ordered

GOLDEN = Path(__file__).parents[2] / "golden/scenario/brightwater_hale/clients.json"


def test_ac1_184_clients_16_named_66_roster_102_filler() -> None:
    clients = build().clients
    assert len(clients) == 184
    assert Counter(c.origin for c in clients) == {"named": 16, "roster": 66, "filler": 102}
    assert len({c.slug for c in clients}) == 184
    assert len({c.id for c in clients}) == 184


def test_ac1_46_seats_14_named_22_14_10_by_office() -> None:
    assert len(SEATS) == 46
    assert sum(s.named for s in SEATS) == 14
    assert Counter(s.office for s in SEATS) == {"Chicago": 22, "Denver": 14, "New York": 10}


def test_ac1_no_scenario_name_carries_the_synthetic_suffix() -> None:
    names = [c.name for c in build_clients()] + [s.name for s in SEATS]
    assert not [n for n in names if "(Synthetic)" in n]


def test_ac1_filler_never_reuses_a_canonical_word_or_surname() -> None:
    clients = build_clients()
    canonical = [c.name for c in clients if c.origin != "filler"] + [s.name for s in SEATS]
    generic = {"inc", "llc", "llp", "the", "and", "plan", "trust", "family", "estate"}
    generic |= {"partners", "holdings", "foundation", "group", "company"}

    def words(text: str) -> set[str]:
        return {w for w in re.split(r"[^a-z]+", text.lower()) if len(w) >= 3} - generic

    reserved: set[str] = set()
    for name in canonical:
        reserved |= words(name)
    for client in clients:
        if client.origin == "filler":
            assert not words(client.name) & reserved, client.name


def test_the_ts_seed_and_the_scenario_agree_row_for_row() -> None:
    golden = json.loads(GOLDEN.read_text())["clients"]
    built = [
        {
            "slug": c.slug,
            "name": c.name,
            "kind": c.kind,
            "origin": c.origin,
            "office": c.office,
            "partner": c.partner,
            "services": list(c.services),
            "attest": c.attest,
            "portal": c.portal,
            "entities": list(c.entities),
            "recency": c.recency,
        }
        for c in build_clients()
    ]
    assert built == golden


def test_the_scenario_is_deterministic_and_pinned_to_its_version() -> None:
    assert build().fingerprint() == build().fingerprint()
    # A content change must bump SCENARIO_VERSION and this hash together.
    assert build().fingerprint() == SCENARIO_HASH


# --- AC-2: snapshots ----------------------------------------------------------------------------


def test_ac2_the_named_snapshots() -> None:
    assert [s.name for s in SNAPSHOTS] == [
        "E0",
        "2026-09-24",
        "2026-10-01",
        "2026-10-06T11:20",
        "2026-10-21T14:10",
        "2026-10-26T16:15",
        "2026-10-27",
        "2026-11-09",
        "2026-11-13",
        "2026-11-16",
        "2027-01-11",
    ]
    assert snapshot("E0").at.isoformat() == "2026-09-14T09:24:00-05:00"
    with pytest.raises(KeyError):
        snapshot("2026-09-15")


def test_ac2_a_snapshot_replays_only_events_up_to_it() -> None:
    e0 = build("E0")
    assert all(e.at <= e0.snapshot.at for e in e0.events)
    assert len(build("2027-01-11").events) >= len(e0.events)


def test_timeline_labels_are_unique_and_dated() -> None:
    from datetime import UTC, datetime

    at = datetime(2026, 9, 14, tzinfo=UTC)
    with pytest.raises(ValueError, match="twice"):
        ordered([Event("a", at, "x.y", "system", "s"), Event("a", at, "x.y", "system", "s")])
    assert build().events[0].trace_id("bh-x").startswith("scenario:bh-x:")


# --- AC-3: holdouts -----------------------------------------------------------------------------


def test_ac3_fairhaven_is_held_out_with_its_events() -> None:
    held = build(holdouts=("fairhaven_ebp",))
    assert len(held.clients) == 183
    assert "Fairhaven Foods 401(k) Plan" not in {c.name for c in held.clients}
    assert not [e for e in held.events if e.client == "Fairhaven Foods 401(k) Plan"]
    assert len(build(holdouts=("fairhaven_ebp", "copperleaf")).clients) == 182
    with pytest.raises(KeyError):
        build(holdouts=("nobody",))


# --- AC-4: reserved ranges (no identifiers at all yet) ------------------------------------------


def test_ac4_no_unreserved_identifier_shape_appears() -> None:
    text = json.dumps(build().canonical())
    ein = re.findall(r"\b(?!00-)\d{2}-\d{7}\b", text)
    ssn = re.findall(r"\b(?!000-|666-|9\d\d-)\d{3}-\d{2}-\d{4}\b", text)
    phone = re.findall(r"\b\d{3}[-.)]\s?(?!555-01)\d{3}-\d{4}\b", text)
    assert (ein, ssn, phone) == ([], [], [])


def test_ac5_every_mailbox_is_the_firms_display_domain() -> None:
    from abacus_tools.synthetic.scenarios.brightwater_hale.people import email_of

    assert all(email_of(s.name).endswith("@brightwaterhale.com") for s in build().seats)
