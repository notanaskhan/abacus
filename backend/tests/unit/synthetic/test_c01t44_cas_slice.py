"""C-01-T44 (TASK-8700; DEC-5700): the `cas` slice's events, the copperleaf holdout and the
fixture-equals-seed check against the web fixtures' close book (CLS-01, CLS-09)."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from abacus_tools.synthetic.scenarios.brightwater_hale import cas_slice as cas
from abacus_tools.synthetic.scenarios.brightwater_hale import close_slice as close
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT, build

WEB_BOOK = Path(__file__).parents[4] / "apps/web/src/fixtures/seed/close-book.ts"


def _cas_events(holdouts: tuple[str, ...] = ()) -> list[object]:
    slices = ("audit_core", *loader.expand_slices(("cas",)))
    return [e for e in build("E0", holdouts, slices).events if e.slice == cas.SLICE]


def test_ac_the_slice_needs_binders_and_runs_after_its_setup() -> None:
    assert loader.expand_slices(("cas",)) == ("binders", "cas")
    assert all(e.at > SETUP_AT for e in cas.events())


def test_ac_the_slice_carries_every_handled_kind() -> None:
    kinds = {e.kind for e in cas.events()}
    assert kinds <= set(loader.HANDLERS)
    assert kinds == {
        "closes.template_imported",
        "closes.plan_version_seeded",
        "closes.year_generated",
        "closes.exception_seeded",
        "closes.portfolio_close_seeded",
    }


def test_ac_the_copperleaf_holdout_leaves_j02_free_to_create_copperleaf() -> None:
    full = _cas_events()
    held = _cas_events(("copperleaf",))
    assert all(getattr(e, "client", None) != close.COPPERLEAF for e in held)
    # 3 plan versions + the year + 7 exceptions leave with Copperleaf; the template stays.
    assert len(full) - len(held) == 3 + 1 + len(close.ISSUES)
    assert any(getattr(e, "kind", "") == "closes.template_imported" for e in held)


def test_ac_the_portfolio_foots_3_11_5_3() -> None:
    statuses = Counter(c.status for c in close.PORTFOLIO)
    assert statuses == {"not_started": 3, "in_progress": 11, "in_review": 5, "delivered": 3}
    assert len(cas.others()) == 21
    assert cas.copperleaf_close().ref == "C1"
    assert {e.data["ref"] for e in cas.events() if e.kind == "closes.portfolio_close_seeded"} == {
        c.ref for c in cas.others()
    }
    for c in close.PORTFOLIO:
        assert c.preparer in cas.ENGAGEMENT_ROLE and c.reviewer in cas.ENGAGEMENT_ROLE


def test_ac_plan_versions_count_23_22_and_seven_requests() -> None:
    assert len(close.PLAN_V3) == 23  # 21 accounts + 2 income-statement procedures
    assert len(cas.v2_rows()) == 22
    assert len(close.REQUEST_TEMPLATES) == 8
    assert len(cas.v2_request_templates()) == 7
    assert len(cas.v4_requests()) == close.V4_REQUESTS_PER_MONTH == 7
    savings = next(r for r in close.PLAN_V3 if r.account == cas.SAVINGS)
    assert savings.source == "client_upload"  # v3; v4 moves it to the bank feed


def test_ac_seven_open_exceptions_two_medium_five_low() -> None:
    assert Counter(i.severity for i in close.ISSUES) == {"medium": 2, "low": 5}
    seeded = [e for e in cas.events() if e.kind == "closes.exception_seeded"]
    assert sorted(int(e.data["index"]) for e in seeded) == list(range(7))


def test_ac_fixture_equals_seed_for_the_cls01_portfolio() -> None:
    rows = re.findall(
        r'\[\s*"(C\d+)",\s*(?:COPPERLEAF|"([^"]+)"),\s*"(\w+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*'
        r'"([0-9-]+)",\s*(?:null|\d+),\s*"(\w+)/(\w+)"',
        WEB_BOOK.read_text(),
    )
    assert len(rows) == 22
    for ref, client, status, rec, accounts, issues, due, prep, rev in rows:
        seed = next(c for c in close.PORTFOLIO if c.ref == ref)
        assert (client or close.COPPERLEAF) == seed.client
        assert (status, int(rec), int(accounts), int(issues)) == (
            seed.status,
            seed.reconciled,
            seed.accounts,
            seed.open_issues,
        )
        assert (due, prep, rev) == (seed.due_on.isoformat(), seed.preparer, seed.reviewer)
