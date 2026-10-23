"""P-08-T14 (P-08 §1, §5.4; POR-01, POR-02; DEC-213): the `portal` slice before it is loaded. The
branding, people, roles, scopes and dates are typed here from POR-01, POR-02, CLI-04 and P-08,
never read back from the code under test."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, build, loader
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import PORTAL_USERS
from abacus_tools.synthetic.scenarios.brightwater_hale.binders import CLIENT_PEOPLE
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.portal import (
    BRANDING,
    HOST_LABEL,
    PORTAL_PEOPLE,
    SAM_ORTIZ,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SINK = "@sink.brightwaterhale.test"


def _events() -> list[Event]:
    return [
        e for e in build(slices=loader.expand_slices(("portal",))).events if e.slice == "portal"
    ]


def test_the_slice_is_registered_opt_in_and_leaves_the_default_hash() -> None:
    assert "portal" in registered()
    assert all(e.slice != "portal" for e in build().events)
    assert build().fingerprint() == SCENARIO_HASH
    slices = loader.expand_slices(("portal",))
    assert build(slices=slices).fingerprint() == build(slices=slices).fingerprint()


def test_the_slice_brings_the_binders_it_needs() -> None:
    # Meera Shah's grant names her 2025 Form 1040, a work item the binders slice opens.
    assert loader.expand_slices(("portal",)) == ("binders", "portal")
    assert loader.expand_slices(("binders", "portal")) == ("binders", "portal")
    assert loader.expand_slices(("shell",)) == ("shell",)


def test_por01_branding_is_verbatim_with_no_secured_footer() -> None:
    assert BRANDING["display_name"] == "Brightwater Hale"
    # POR-01 `footer`: "Help · Privacy · " + the branding address_line.
    assert (
        BRANDING["address_line"] == "Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL"
    )
    assert BRANDING["support_contact_name"] == "Grace Holloway"  # POR-01g names her
    assert BRANDING["secured_footer"] is False
    assert all("accrued" not in str(v).lower() for v in BRANDING.values())
    assert HOST_LABEL == "brightwaterhale"  # `brightwaterhale.<neutral-portal-domain>`


def test_the_host_comes_from_the_portal_base_domain_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        loader, "settings", lambda: SimpleNamespace(portal_base_domain="portal-example.test")
    )
    assert loader.portal_host(HOST_LABEL) == "brightwaterhale.portal-example.test"
    monkeypatch.setattr(loader, "settings", lambda: SimpleNamespace(portal_base_domain=None))
    assert loader.portal_host(HOST_LABEL) is None


def test_personas_roles_and_scopes() -> None:
    people = {p.name: (p.client, p.role, p.scope_kind) for p in PORTAL_PEOPLE}
    assert people == {
        "Claire Feld": ("Jonah & Claire Feld", "taxpayer", "client"),
        "Tess Moreno": ("Copperleaf Coffee Roasters, Inc.", "owner", "client_entity"),
        "Ben Ashby": ("Copperleaf Coffee Roasters, Inc.", "contributor", "client_entity"),
        "Meera Shah": ("Meera Shah", "taxpayer", "work_item"),
    }
    assert {p.email for p in PORTAL_PEOPLE} == {
        f"claire.feld{SINK}",
        f"tess.moreno{SINK}",
        f"ben.ashby{SINK}",
        f"meera.shah{SINK}",
    }
    # One user per person: none of them is already a portal user or a binder's client person.
    assert not {p.name for p in PORTAL_PEOPLE} & {u.name for u in PORTAL_USERS}
    assert not {p.name for p in PORTAL_PEOPLE} & set(CLIENT_PEOPLE)
    # Dana Kowalski stays audit_core's owner on the Northwind audit.
    dana = next(u for u in PORTAL_USERS if u.name == "Dana Kowalski")
    assert (dana.role, dana.engagement) == ("owner", "A1")


def test_por01d_sam_ortiz_is_invited_on_sep_2_for_northwind_only() -> None:
    assert (SAM_ORTIZ.name, SAM_ORTIZ.org) == ("Sam Ortiz", "Keystone Retirement Services")
    assert SAM_ORTIZ.email == f"sam.ortiz{SINK}"
    assert SAM_ORTIZ.engagement == "A1"  # the Northwind Robotics 401(k) Plan audit
    assert SAM_ORTIZ.sent == date(2026, 9, 2)  # Wed Sep 2, 2026
    assert SAM_ORTIZ.items == 9
    # CLI-04b's 14-day link: still pending at E0 (Mon Sep 14).
    assert SAM_ORTIZ.sent + timedelta(days=SAM_ORTIZ.days) > DEMO_INSTANT.date()
    [event] = [e for e in _events() if e.kind == "identity.client_invitation_created"]
    assert event.at.date() == date(2026, 9, 2)
    assert event.client == "Northwind Robotics, Inc."


def test_every_portal_event_has_a_handler_and_replays_after_what_it_names() -> None:
    events = build(slices=loader.expand_slices(("portal",))).events
    assert {e.kind for e in events} <= set(loader.HANDLERS)
    kinds = [e.kind for e in loader.replay_order(events)]
    people = [i for i, k in enumerate(kinds) if k == "identity.portal_person_added"]
    assert len(people) == 4
    assert max(i for i, k in enumerate(kinds) if k == "engagements.tax_engagement_created") < min(
        people
    )
    assert kinds.index("portal.branding_set") < kinds.index("portal.host_added")
    assert all(e.at <= DEMO_INSTANT for e in _events())


def test_holding_out_copperleaf_takes_tess_and_ben_with_it() -> None:
    held = build(holdouts=("copperleaf",), slices=loader.expand_slices(("portal",))).events
    names = {e.data.get("person") for e in held if e.kind == "identity.portal_person_added"}
    assert names == {"Claire Feld", "Meera Shah"}
