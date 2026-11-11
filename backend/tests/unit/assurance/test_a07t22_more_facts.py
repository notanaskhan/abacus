"""A-07-T22 close (S31; TASK-6224; DEC-2819): the checklist facts the projector lacked.

Each provider answers from its owner's facts: `sign_offs` from the AUD-17 matrix, `sum` from the
EP's decided SUM card, `disclosure_checklist` from AUD-20's counts, `form5500_tie` and
`certification` from EBP-07 and EBP-06. None answers done on a person's behalf.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import completion_facts as cf
from abacus.modules.assurance import completion_projector as cp
from abacus.modules.assurance import ebp_investments, review_matrix

TENANT = cast(TenantContext, SimpleNamespace(tenant_id=uuid.uuid4()))
WI = uuid.uuid4()


@pytest.fixture(autouse=True)
def engagement(monkeypatch: pytest.MonkeyPatch) -> None:
    async def owner(_t: object, _w: object) -> uuid.UUID:
        return uuid.uuid4()

    monkeypatch.setattr(cf, "work_item_engagement", owner)


class _Session:
    def __init__(self, row: object) -> None:
        self.row = row

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
        row = self.row
        return SimpleNamespace(first=lambda: row)


def _session(row: object) -> object:
    def open_session(_t: object) -> _Session:
        return _Session(row)

    return open_session


def _row(target_type: str, *states: str) -> SimpleNamespace:
    return SimpleNamespace(
        target_type=target_type, cells=[SimpleNamespace(state=s) for s in states]
    )


@pytest.mark.parametrize(("changed", "status"), [(0, "done"), (2, "open")])
async def test_sign_offs_follow_the_matrix_footer(
    monkeypatch: pytest.MonkeyPatch, changed: int, status: str
) -> None:
    rows = [_row("workpaper", "signed", "stale") for _ in range(changed)]
    rows.append(_row("workpaper", "signed", "signed"))

    async def matrix(_t: object, _e: object) -> SimpleNamespace:
        return SimpleNamespace(rows=rows)

    monkeypatch.setattr(review_matrix, "matrix", matrix)
    fact = await cf.sign_offs(TENANT, WI)
    assert fact.status == status
    if changed:
        assert fact.evidence_text == f"{changed} changed after sign-off"


async def test_the_checklist_s_own_row_does_not_count_as_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Signing the checklist changes the checklist; its own row must not re-open this item
    (S35 follow-up: the archive load's release stayed blocked on G5 otherwise)."""

    async def matrix(_t: object, _e: object) -> SimpleNamespace:
        return SimpleNamespace(
            rows=[_row("completion_checklist", "stale", "stale"), _row("workpaper", "signed")]
        )

    monkeypatch.setattr(review_matrix, "matrix", matrix)
    assert (await cf.sign_offs(TENANT, WI)).status == "done"


@pytest.mark.parametrize(
    ("kinds", "status"), [(["sum_conclusion"], "done"), (["opinion"], "open")]
)
async def test_sum_is_done_only_with_the_ep_s_decided_card(
    monkeypatch: pytest.MonkeyPatch, kinds: list[str], status: str
) -> None:
    async def decided(_t: object, _e: object) -> list[SimpleNamespace]:
        return [SimpleNamespace(kind=k) for k in kinds]

    monkeypatch.setattr(cf, "decided_cards", decided)
    fact = await cf.sum_evaluated(TENANT, WI)
    assert fact.status == status
    assert "partner" in (fact.evidence_text or "")


@pytest.mark.parametrize(
    ("counts", "status", "text"),
    [((142, 142), "done", "142 of 142 answered"), ((140, 142), "open", "140 of 142 answered"),
     (None, "open", None), ((0, 0), "open", "0 of 0 answered")],
)  # fmt: skip
async def test_the_disclosure_checklist_needs_every_item_answered(
    monkeypatch: pytest.MonkeyPatch,
    counts: tuple[int, int] | None,
    status: str,
    text: str | None,
) -> None:
    async def found(_t: object, _w: object) -> tuple[int, int] | None:
        return counts

    monkeypatch.setattr(cf, "checklist_counts", found)
    fact = await cf.disclosure_checklist(TENANT, WI)
    assert (fact.status, fact.evidence_text) == (status, text)


@pytest.mark.parametrize(
    ("row", "status"),
    [
        (None, "open"),
        (SimpleNamespace(status="tied", lines_off=0, answers_off=0), "done"),
        (SimpleNamespace(status="tied", lines_off=0, answers_off=1), "open"),
        (SimpleNamespace(status="received", lines_off=0, answers_off=0), "open"),
    ],
)
async def test_the_form_5500_ties_with_nothing_inconsistent(
    monkeypatch: pytest.MonkeyPatch, row: object, status: str
) -> None:
    monkeypatch.setattr(cf, "tenant_session", _session(row))
    assert (await cf.form5500_tie(TENANT, WI)).status == status


@pytest.mark.parametrize(
    ("answers", "status"),
    [(["evaluated"] * 6, "done"), (["evaluated", "pending"], "open"), ([], "open")],
)
async def test_certification_needs_every_point_evaluated(
    monkeypatch: pytest.MonkeyPatch, answers: list[str], status: str
) -> None:
    async def points(_t: object, _w: object) -> tuple[SimpleNamespace, ...]:
        return tuple(SimpleNamespace(answer=a) for a in answers)

    monkeypatch.setattr(ebp_investments, "points", points)
    assert (await cf.certification(TENANT, WI)).status == status


def test_every_template_key_but_filing_has_a_provider() -> None:
    cf.register_completion_facts()
    registered = set(cp.registered_facts())
    for key in ("sign_offs", "sum", "disclosure_checklist", "form5500_tie", "certification"):
        assert key in registered, key
    assert "filing" not in registered  # the TPA files it: a person's item
