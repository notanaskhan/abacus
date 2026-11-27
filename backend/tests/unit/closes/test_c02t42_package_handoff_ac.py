# ac-test-author: notanaskhan
"""C-02-T42 (TASK-9037; ADR-078; SPEC-701 F7, F8; DEC-6041): the independent AC suite on the amber
package and hand-off. Row acceptance: "a release with 9 of 21 accounts reconciled is refused with
the three reasons of CLS-08c."

Found writing it: `release()` filtered its blockers with `if not p.done`, but `done` is a count
("9 of 21"), so any precondition with progress (9 accounts, 7 issues, 3 entries) let the release
through; only a reason with nothing done blocked. And the refusal joined its blockers into one
fact with commas, which facts refuse (`FactsNotIdentifiers`), so it would have answered 500. Every
listed reason now blocks, one boolean fact each.

Covered here, at the module seams: the three reasons in CLS-08c's order; the release gate; the
SSARS route matrix (Aug 31 2026 · Dec 31 2026 · early adoption · the firm's No answer); and the
TJE posting ban (the database CHECK and TJE-001 both hold it). Lock before the client's approval
and supersede are C-02-T29's and C-02-T39's tests, which this suite does not repeat."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from abacus.modules.closes import release
from abacus.modules.closes.compute import package as pkg
from abacus.modules.methodology.api import PolicyRef, SsarsCasSettingsPayload, ssars_framework_for

BACKEND = Path(__file__).resolve().parents[3]


def test_ac_cls08c_names_the_three_reasons_in_order() -> None:
    reasons = pkg.preconditions(reconciled=9, accounts=21, open_issues=7, unposted_entries=3)
    assert [(r.blocker, r.done, r.of) for r in reasons] == [
        ("accounts_unreconciled", 9, 21),
        ("issues_open", 7, None),
        ("entries_unposted", 3, None),
    ]
    assert pkg.preconditions(reconciled=21, accounts=21, open_issues=0, unposted_entries=0) == []


async def test_ac_a_release_with_9_of_21_reconciled_is_refused_with_the_three_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reasons = pkg.preconditions(reconciled=9, accounts=21, open_issues=7, unposted_entries=3)
    package = SimpleNamespace(preconditions=reasons, version=3)
    close = SimpleNamespace(engagement_id=uuid.uuid4())

    async def fresh(_: object) -> None:
        return None

    async def get_package(_ctx: object, _close: object) -> object:
        return package

    async def close_row(_session: object, _close: object, **_: object) -> object:
        return close

    async def get_ref(_ctx: object, _engagement: object) -> object:
        return SimpleNamespace(resource=lambda: object())

    async def authorise(*_: object, **__: object) -> None:
        return None

    class _Session:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            return None

    def session(_tenant: object) -> _Session:
        return _Session()

    from abacus.modules.closes import package_service
    from abacus.modules.engagements import api as engagements_api

    monkeypatch.setattr(release, "_fresh", fresh)
    monkeypatch.setattr(package_service, "get_package", get_package)
    monkeypatch.setattr(release.repo, "close_row", close_row)
    monkeypatch.setattr(engagements_api, "get_ref", get_ref)
    monkeypatch.setattr(release, "authorise", authorise)
    monkeypatch.setattr(release, "tenant_session", session)
    ctx = SimpleNamespace(tenant=SimpleNamespace(actor_kind="human"), tenant_id=uuid.uuid4())
    with pytest.raises(release.PreconditionsUnmet) as refused:
        await release.release(ctx, uuid.uuid4(), seen_version=3)  # type: ignore[arg-type] -- a stand-in person
    assert refused.value.facts == {
        "accounts_unreconciled": True,
        "issues_open": True,
        "entries_unposted": True,
    }


@pytest.mark.parametrize(
    ("period_end", "early", "answer", "route", "legend"),
    [
        (date(2026, 8, 31), False, True, "ar_c_70_preparation", pkg.NO_ASSURANCE),
        (date(2026, 12, 31), False, True, "cas_by_product", None),
        (date(2026, 8, 31), True, True, "cas_by_product", None),
        (date(2026, 12, 31), False, False, "standalone_letter", None),
    ],
)
def test_ac_the_ssars_route_matrix(
    period_end: date, early: bool, answer: bool, route: str, legend: str | None
) -> None:
    """Before SSARS 27 (periods ending before Dec 15, 2026) AR-C 70 preparation carries "No
    assurance is provided."; after it, or adopted early, a CAS by-product; and when the firm
    answers No (not a by-product), a standalone preparation letter."""
    policy = PolicyRef("bh-ssars-cas", uuid.uuid4(), 1, "SSARS and CAS settings")
    framework = ssars_framework_for(
        SsarsCasSettingsPayload(kind="ssars_cas_settings", early_adopt_ssars27=early),
        policy,
        period_end=period_end,
    )
    routed = pkg.route(framework.framework, cas_answer=answer)
    assert (routed.route, routed.legend_key) == (route, legend)


def test_ac_a_tje_never_enters_a_posting_batch() -> None:
    """The database refuses a tax-only entry in a batch, and TJE-001 keeps `tje` out of the
    posting code: the hand-off carries the TB only."""
    migration = (BACKEND / "migrations" / "versions" / "0950_adjustments_posting.py").read_text()
    assert "posting_batch_id IS NULL" in migration and "'tje'" in migration
    posting = (BACKEND / "src" / "abacus" / "modules" / "adjustments" / "posting.py").read_text()
    assert '"tje"' not in posting and "'tje'" not in posting
    from abacus_tools.quality import banned_patterns as bp

    assert "TJE-001" in Path(bp.__file__).read_text()
