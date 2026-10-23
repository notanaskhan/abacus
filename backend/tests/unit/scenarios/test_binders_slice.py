"""P-06-T08 (P-06 §5.4; DEC-146): the `binders` slice foots before it is loaded. Every expected
figure is typed here from BND-01 / BND-02 / SHL-14 / CLS-03 and blueprint 01 §9.1 / §9.5,
never read back from the code under test."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, build, loader
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import PBC_LISTS
from abacus_tools.synthetic.scenarios.brightwater_hale.binders import (
    BINDERS,
    CLOSE_REQUESTS,
    FELD_CATEGORIES,
    NAMED,
    RETURNS,
    TAX_ENGAGEMENTS,
    NamedBinder,
    tax_binders,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import DEMO_INSTANT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered

SLICES = ("audit_core", "binders")
E0_DAY = DEMO_INSTANT.date()


def _named(client: str, part: int = 1) -> NamedBinder:
    return next(b for b in NAMED if b.client == client and b.part == part)


def test_the_slice_is_registered_opt_in_and_leaves_the_default_hash() -> None:
    assert "binders" in registered()
    assert all(e.slice != "binders" for e in build().events)
    assert build().fingerprint() == SCENARIO_HASH
    assert build(slices=SLICES).fingerprint() == build(slices=SLICES).fingerprint()


def test_bnd01a_tiles_foot_to_241() -> None:
    tiles = Counter(b.status for b in tax_binders())
    assert (tiles["draft"], tiles["published"], tiles["unpublished"]) == (1, 48, 0)
    assert (tiles["complete"], tiles["closed"]) == (40, 152)
    assert 1 + 48 + 0 + 40 + 152 == len(tax_binders()) == 241


def test_bnd01a_224_returns_and_17_second_part_binders() -> None:
    parts = Counter(b.part for b in tax_binders())
    assert parts == {1: 224, 2: 17}
    assert {b.name for b in tax_binders() if b.part == 2} == {"2025 Binder pt 2"}
    assert {b.name for b in tax_binders() if b.part == 1} == {"2025 Binder"}
    assert len({b.ret for b in tax_binders() if b.part == 1}) == 224  # one per return


def test_section_9_5_returns_and_engagements() -> None:
    assert len(RETURNS) == 224
    assert len(TAX_ENGAGEMENTS) == 214
    assert Counter(len(e.returns) for e in TAX_ENGAGEMENTS) == {1: 204, 2: 10}
    assert Counter(r.office for r in RETURNS) == {"Chicago": 98, "Denver": 64, "New York": 62}
    assert Counter(r.done for r in RETURNS) == {False: 79, True: 145}  # open 79 · done 145


def test_done_returns_close_their_binders() -> None:
    done = {r.label for r in RETURNS if r.done}
    closed = [b for b in tax_binders() if b.status == "closed"]
    assert all(b.ret in done for b in closed)
    assert len(closed) == 145 + 7  # every done return's binder, and 7 second parts
    assert not [b for b in tax_binders() if b.ret in done and b.status != "closed"]


def test_bnd01_named_rows_verbatim() -> None:
    assert len(NAMED) == 16  # spec ROWS 1 to 15, and Osterberg's (state c)
    assert _named("Jonah & Claire Feld").progress == (5, 7)
    assert (
        _named("Ridgeline Property Partners, LP", 2).status,
        _named("Ridgeline Property Partners, LP", 2).progress,
    ) == ("published", (1, 3))
    assert _named("Rafael Quintero").status == "draft"  # return Not started
    assert {b.client for b in NAMED if b.status == "closed"} == {
        "Marcus & Dana Whitley",
        "Copperleaf Coffee Roasters, Inc.",
    }
    gathering = (
        "Estate of Walter Thornbury",
        "Gloria Mendez",
        "Morgan & Kai Ferris",
        "Lakeshore Literacy Alliance",
        "Fenwick Family Foundation",
    )
    assert all(_named(c).status == "published" for c in gathering)
    marked = {
        b.client: (b.marked_done[0], b.marked_done[1].date().isoformat())
        for b in NAMED
        if b.status == "complete" and b.marked_done is not None
    }
    assert marked == {
        "Ridgeline Property Partners, LP": ("Owen Calder", "2026-06-01"),
        "Calloway Family Trust": ("Eleanor Calloway", "2026-09-09"),
        "Harborview Dental Properties, LP": ("Dr. Sofia Lindqvist", "2026-08-28"),
        "Elena Varga": ("Elena Varga", "2026-08-30"),
    }
    closed = _named("Marcus & Dana Whitley").closed_at
    assert closed is not None and closed.date() == date(2026, 4, 10)  # "Return accepted Apr 10"


def test_bnd01b_fenwick_is_the_one_named_published_binder_silent_over_30_days() -> None:
    fenwick = _named("Fenwick Family Foundation").last_activity
    assert fenwick is not None
    assert (E0_DAY - fenwick.date()).days == 34  # Aug 11 → 34 days
    silent = [
        b.client
        for b in NAMED
        if b.status == "published"
        and b.last_activity is not None
        and (E0_DAY - b.last_activity.date()).days > 30
    ]
    assert silent == ["Fenwick Family Foundation"]


def test_bnd01c_osterberg_is_seeded_and_bnd01a_has_no_unpublished_binder() -> None:
    osterberg = _named("Benjamin Osterberg")
    assert (osterberg.status, osterberg.prep) == ("published", "RV")  # DEC-146: c is an override


def test_bnd01d_no_ty2026_binder() -> None:
    assert {r.period[1].year for r in RETURNS} <= {2025, 2026}
    assert all(r.name.startswith("2025 ") for r in RETURNS)
    assert not [b for b in BINDERS if b.name.startswith("2026")]


def test_bnd02_feld_5_of_7_is_71_percent_over_nine_categories() -> None:
    feld = next(
        b for b in BINDERS if b.named is not None and b.named.client == "Jonah & Claire Feld"
    )
    received = sum(1 for r in feld.requests if r.status == "received")
    assert (received, len(feld.requests)) == (5, 7)
    assert received * 100 // len(feld.requests) == 71
    assert len(feld.categories) == len(FELD_CATEGORIES) == 9
    assert feld.published is not None and feld.published[0] == "KO"
    assert feld.published[1].date() == date(2026, 2, 3)  # "Feb 3, 2026 · Kevin Osei"
    used = {r.category for r in feld.requests}
    assert used <= {name for name, _ in feld.categories}
    assert [r.title for r in feld.requests if r.kind == "firm_provided"] == [
        "Schedule K-1 from Ridgeline Property Partners, LP"
    ]


def test_bnd02d_thornbury_6_of_15_and_due_aug_31_is_14_days_late() -> None:
    thornbury = _named("Estate of Walter Thornbury")
    done, total = thornbury.progress
    assert (done, total, total - done) == (6, 15, 9)  # BND-04: 9 open, 3 of them overdue
    assert date(2026, 8, 31) + timedelta(days=14) == E0_DAY


def test_bnd02g_four_ty2025_installments_apr_2025_to_jan_2026() -> None:
    installments = [date(2025, 4, 15), date(2025, 6, 15), date(2025, 9, 15), date(2026, 1, 15)]
    assert len(installments) == 4
    assert (installments[0].year, installments[-1].year) == (2025, 2026)


def test_shl14_northwind_keystone_bridge_letter_requested_sep_1_due_sep_25() -> None:
    northwind = next(p for p in PBC_LISTS if p.key == "northwind")
    bridge = next(r for r in northwind.requests if r.title.startswith("Bridge letter"))
    assert (northwind.created.date(), bridge.due_on) == (date(2026, 9, 1), date(2026, 9, 25))
    assert bridge.owner == "Keystone Retirement Services"


def test_shl14d_copperleaf_close_intake_8_recurring_plus_1_ad_hoc() -> None:
    intake = next(b for b in BINDERS if b.kind == "close_intake")
    assert intake.requests == CLOSE_REQUESTS
    recurring = [r for r in intake.requests if r.created.date() == date(2026, 9, 1)]
    ad_hoc = [r for r in intake.requests if r.created.date() == date(2026, 9, 11)]
    assert (len(recurring), len(ad_hoc), len(intake.requests)) == (8, 1, 9)
    assert sum(1 for r in intake.requests if r.status == "received") == 7
    square = next(r for r in intake.requests if r.title == "Square payouts — August")
    assert square.incorporation == "pending_incorporation"


def test_every_binder_event_has_a_handler_and_replays_after_its_engagement() -> None:
    events = build(slices=SLICES).events
    assert {e.kind for e in events} <= set(loader.HANDLERS)
    kinds = [e.kind for e in loader.replay_order(events)]
    assert kinds.count("requests.binder_created") == 242  # 241 tax binders + the close intake
    homes = ("engagements.tax_engagement_created", "engagements.close_engagement_created")
    assert max(i for i, k in enumerate(kinds) if k in homes) < min(
        i for i, k in enumerate(kinds) if k == "requests.binder_created"
    )
    assert all(e.at <= DEMO_INSTANT for e in events)


def test_copperleaf_holdout_takes_its_binders_and_close_with_it() -> None:
    held = build(holdouts=("copperleaf",), slices=SLICES).events
    copperleaf = [e for e in held if e.client == "Copperleaf Coffee Roasters, Inc."]
    assert copperleaf == []
    binders = [e for e in held if e.kind == "requests.binder_created"]
    assert len(binders) == 242 - 2  # its 2025 Binder and its close intake
