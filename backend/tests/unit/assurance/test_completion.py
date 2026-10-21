"""SPEC-314 (TASK-332): G6-G9 facts, release and lock blockers, the digest and the seal, by
code; who may do what."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from abacus.modules.assurance.completion import (
    CompletionBlocked,
    CompletionState,
    digest_hash,
    documentation_due,
    g6_of,
    g7_of,
    lock_blockers,
    merkle_root,
    release_blockers,
)
from abacus.modules.assurance.completion_models import CompletionRecord, EqrConcurrence, Release
from abacus.modules.engagements.api import GateFact, Judgment
from abacus.modules.identity.authz.matrix import RULES

J = [Judgment("materiality", "Materiality", (("Overall", "252,200.00"),), True)]
EQR = uuid4()


def _rec(kind: str, **over: object) -> CompletionRecord:
    values: dict[str, object] = {
        "id": uuid4(),
        "kind": kind,
        "choice": None,
        "document_date": None,
        "report_record_id": None,
        "created_at": datetime.now(UTC),
    }
    return CompletionRecord(**{**values, **over})


def _state(
    records: list[CompletionRecord],
    *,
    eqrs: list[UUID] | None = None,
    concurred: str | None = None,
    released: bool = False,
) -> CompletionState:
    return CompletionState(
        records,
        EqrConcurrence(digest_hash=concurred) if concurred else None,
        Release() if released else None,
        None,
        J,
        eqrs if eqrs is not None else [EQR],
    )


def _complete() -> list[CompletionRecord]:
    report = _rec("report", choice="unmodified", document_date=date(2026, 10, 9))
    return [
        _rec("rep_letter", document_date=date(2026, 10, 9)),
        _rec("report_approval", report_record_id=report.id),
        report,
        _rec("going_concern", choice="no_substantial_doubt"),
    ]


def test_ac2_g6_needs_a_concurrence_on_the_current_digest() -> None:
    assert g6_of(_state([], eqrs=[])).met  # no EQR on the team: not required
    assert g6_of(_state([])).blockers == ("eqr_not_concurred",)
    assert g6_of(_state([], concurred="0" * 64)).blockers == ("eqr_digest_changed",)
    assert g6_of(_state([], concurred=digest_hash(J))).met


def test_ac5_g7_needs_the_letter_dated_the_report_date() -> None:
    assert g7_of(_state(_complete())).met
    late = [_rec("rep_letter", document_date=date(2026, 10, 8)), *_complete()[1:]]
    assert g7_of(_state(late)).blockers == ("rep_letter_date_mismatch",)
    assert set(g7_of(_state([])).blockers) == {"no_report", "no_rep_letter"}


def test_ac6_release_names_everything_missing() -> None:
    met = GateFact(met=True)
    assert release_blockers(_state(_complete(), concurred=digest_hash(J)), met) == []
    blocked = release_blockers(_state([]), GateFact(met=False, blockers=("unsigned:C-100:L2",)))
    assert blocked == [
        "G5:unsigned:C-100:L2",
        "G6:eqr_not_concurred",
        "G7:no_report",
        "G7:no_rep_letter",
        "going_concern_not_decided",
        "report_not_approved",
    ]
    stale_approval = [
        *_complete()[:1],
        _rec("report_approval", report_record_id=uuid4()),
        *_complete()[2:],
    ]
    assert "report_not_approved" in release_blockers(
        _state(stale_approval, concurred=digest_hash(J)), met
    )
    assert "already_released" in release_blockers(_state(_complete(), released=True), met)


def test_ac7_lock_needs_release_and_review_still_complete() -> None:
    assert lock_blockers(_state([]), GateFact(met=True)) == ["not_released"]
    assert lock_blockers(_state([], released=True), GateFact(met=True)) == []


def test_ac7_the_seal_is_a_merkle_root_over_sorted_leaves() -> None:
    a = merkle_root(["b=2", "a=1", "c=3"])
    assert a == merkle_root(["c=3", "b=2", "a=1"])  # order-free
    assert a != merkle_root(["a=1", "b=2", "c=4"])
    single = merkle_root(["only=1"])
    assert single == hashlib.sha256(b"only=1").hexdigest()
    with pytest.raises(CompletionBlocked):
        merkle_root([])


def test_ac6_documentation_is_due_sixty_days_after_the_report_date() -> None:
    assert documentation_due(date(2026, 10, 9)) == date(2026, 12, 8)


def test_ac8_who_decides() -> None:
    def allowed(action: str) -> set[str]:
        return {r for r, d in RULES[action].decisions.items() if d == "allow"}

    assert allowed("report.release") == {"engagement_partner"}
    assert allowed("completion.decide") == {"engagement_partner"}
    assert allowed("eqr.concur") == {"reviewer"}
    assert allowed("archive.lock") == {"engagement_partner", "manager"}
    for action in ("report.release", "eqr.concur", "archive.lock", "completion.record"):
        assert "agent" not in allowed(action)
