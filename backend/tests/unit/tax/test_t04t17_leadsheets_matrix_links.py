"""TASK-7330 (T-04-T17 rest; SPEC-649 AC-1.1, AC-1.2, AC-2.3): the live leadsheets, the Sch E -
K-1 matrix with the PY column, and the region-field-line links. The SQL's database half is
`tests/integration/test_t04t17_leadsheets_matrix_links.py`; here the session is a fake, so
the shapes, the arithmetic (code computes, ADR-050), the mismatch flag and the PY gate are the
point."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal as D
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.evidence.api import CitationBox
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax import leadsheets as ls
from abacus.modules.tax.compute.individual.k1 import sch_e_matrix

RETURN, ENGAGEMENT, PRIOR_ENGAGEMENT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
SHEET, K1_SHEET, PY_SHEET = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
DIV = uuid.uuid4()  # the Halvard 1099-DIV's evidence version
ACTIVITY = uuid.uuid4()
C1, C2, C3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


@dataclass
class _Ctx:
    tenant: object = None
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID = field(default_factory=uuid.uuid4)
    client: bool = False


def _ctx(*, client: bool = False) -> AuthContext:
    return cast(AuthContext, _Ctx(client=client))


def _typed(v: str | None) -> dict[str, str] | None:
    return None if v is None else {"t": "decimal", "v": v}


def _field(
    key: str, line: str, label: str, v: str | None, section: str = "dividends"
) -> SimpleNamespace:
    return SimpleNamespace(
        worksheet_id=SHEET,
        section_key=section,
        section_name="Dividends" if section == "dividends" else "Interest",
        field_key=key,
        line_ref=line,
        label=label,
        current_value=_typed(v),
        form_code="1040",
    )


def _box(cid: uuid.UUID, printed: str | None, match: str, page: int = 1) -> CitationBox:
    return CitationBox(cid, DIV, page, (72.0, 140.0, 180.0, 154.0), match, printed)


class _Result:
    def __init__(self, rows: Sequence[SimpleNamespace]) -> None:
        self._rows: list[SimpleNamespace] = list(rows)

    def all(self) -> list[SimpleNamespace]:
        return self._rows

    def first(self) -> SimpleNamespace | None:
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, answers: dict[str, Sequence[Any]], year: int | None) -> None:  # Any: rows
        self._answers = answers
        self._year = year

    async def execute(self, query: object, params: dict[str, object]) -> _Result:
        sql = str(query)
        if "FROM k1_activities ca" in sql:
            return _Result(self._answers.get(f"prior:{params['a']}", []))
        if "FROM k1_activities a" in sql:
            return _Result(self._answers.get("activities", []))
        if "f.worksheet_id = :w" in sql:
            return _Result(self._answers.get(f"sheet:{params['w']}", []))
        if "lower(w.form_code)" in sql:
            assert params["form"] == "1040"
            return _Result(self._answers.get("leadsheet", []))
        return _Result(self._answers.get("linked", []))

    async def scalar(self, *_args: object, **_kw: object) -> int | None:
        return self._year


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    answers: dict[str, Sequence[Any]],  # Any: fake SQL rows
    *,
    cited: dict[tuple[uuid.UUID, str], tuple[uuid.UUID, ...]] | None = None,
    boxes: Sequence[CitationBox] = (),
    year: int | None = 2025,
    prior_readable: bool = True,
) -> list[tuple[uuid.UUID, Sequence[uuid.UUID]]]:
    asked: list[tuple[uuid.UUID, Sequence[uuid.UUID]]] = []

    @asynccontextmanager
    async def session(_tenant: object) -> AsyncGenerator[_Session]:
        yield _Session(answers, year)

    async def engagement(_tenant: object, _return: uuid.UUID) -> uuid.UUID:
        return ENGAGEMENT

    async def get_ref(_ctx: object, _engagement: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(resource=lambda: "resource")

    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        assert action == "return_worksheet.read"

    async def latest(
        _tenant: object, target_type: str, _ids: Sequence[uuid.UUID]
    ) -> dict[tuple[uuid.UUID, str], tuple[uuid.UUID, ...]]:
        assert target_type == "return_worksheet"
        return cited or {}

    async def citation_boxes(
        _tenant: object, engagement_id: uuid.UUID, ids: Sequence[uuid.UUID]
    ) -> list[CitationBox]:
        asked.append((engagement_id, ids))
        return [b for b in boxes if b.citation_id in ids]

    async def may_read(_ctx: object, engagement_id: uuid.UUID) -> bool:
        assert engagement_id == PRIOR_ENGAGEMENT
        return prior_readable

    monkeypatch.setattr(ls, "tenant_session", session)
    monkeypatch.setattr(ls, "work_item_engagement", engagement)
    monkeypatch.setattr(ls, "get_ref", get_ref)
    monkeypatch.setattr(ls, "authorise", authorise)
    monkeypatch.setattr(ls, "latest_citations", latest)
    monkeypatch.setattr(ls, "citation_boxes", citation_boxes)
    monkeypatch.setattr(ls, "_may_read", may_read)
    return asked


# --- compute -------------------------------------------------------------------------------------


def test_the_matrix_pairs_each_k1_line_with_last_years_figure() -> None:
    current = [
        ("box2", "Net Rental Real Estate Income", D("307900")),
        ("box5", "Interest Income", D("4600")),
        ("item_l.contributed", "Capital Contributed", D("250000")),
    ]
    prior = [("box2", D("281600")), ("box5", D("4120"))]
    out = sch_e_matrix(current, prior)
    assert [(m.field_key, m.current_year, m.prior_year) for m in out.lines] == [
        ("box2", D("307900"), D("281600")),
        ("box5", D("4600"), D("4120")),
        ("item_l.contributed", D("250000"), None),  # no such line last year
    ]
    assert out.stamp.engine_name == "k1.sch_e_matrix"
    assert sch_e_matrix(current, prior).stamp == out.stamp  # deterministic inputs hash
    assert sch_e_matrix(current, []).stamp != out.stamp


def test_money_reads_a_typed_value_to_the_cent() -> None:
    assert ls.money({"t": "decimal", "v": "14820"}) == D("14820.00")
    assert ls.money({"t": "amount", "v": "1550.5"}) == D("1550.50")
    assert ls.money({"t": "decimal", "v": None}) is None
    assert ls.money({"t": "decimal", "v": True}) is None
    assert ls.money({"t": "decimal", "v": "n/a"}) is None
    assert ls.money("14820") is None


def test_a_box_that_printed_another_figure_is_a_mismatch() -> None:
    printed = _box(C1, "14,820", "m1")
    assert ls.box_disagrees(D("14280.00"), [printed])  # TAX-04 c
    assert not ls.box_disagrees(D("14820.00"), [printed])
    assert not ls.box_disagrees(D("14820.00"), [_box(C1, "$14,820.00", "m1")])
    assert not ls.box_disagrees(None, [printed])  # an empty field disagrees with nothing
    assert not ls.box_disagrees(D("1"), [_box(C1, None, "m1"), _box(C2, "box 1a", "m2")])


# --- leadsheets (AC-1.1) -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_line_sums_its_fields_and_flags_a_mismatched_box(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _field("int.halvard.1", "2b", "Taxable interest", "2310", "interest"),
        _field("int.ridgeline.5", "2b", "Taxable interest", "4600", "interest"),
        _field("div.halvard.1a", "3b", "Ordinary dividends", "14280"),
        _field("div.halvard.1b", "3a", "Qualified dividends", "11960"),
    ]
    _wire(
        monkeypatch,
        {"leadsheet": rows},
        cited={(SHEET, "div.halvard.1a"): (C1,), (SHEET, "div.halvard.1b"): (C2,)},
        boxes=[_box(C1, "14,820", "m1a"), _box(C2, "11,960", "m1b")],
    )
    cards = await ls.leadsheets(_ctx(), RETURN, "1040")
    assert [c.title for c in cards] == ["Interest", "Dividends"]
    interest, dividends = cards
    [line_2b] = interest.lines
    assert (line_2b.line_key, line_2b.amount) == ("1040.2b", D("6910.00"))  # 2,310 + 4,600
    assert line_2b.contributing_field_keys == ("int.halvard.1", "int.ridgeline.5")
    assert not line_2b.mismatch
    by_key = {line.line_key: line for line in dividends.lines}
    assert by_key["1040.3b"].mismatch and by_key["1040.3b"].amount == D("14280.00")
    assert not by_key["1040.3a"].mismatch


@pytest.mark.asyncio
async def test_a_line_with_no_value_has_no_amount(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, {"leadsheet": [_field("div.x", "3b", "Ordinary dividends", None)]})
    [card] = await ls.leadsheets(_ctx(), RETURN, "1040")
    assert card.lines[0].amount is None and not card.lines[0].mismatch


@pytest.mark.asyncio
async def test_boxes_are_read_on_the_returns_own_engagement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _wire(
        monkeypatch,
        {"leadsheet": [_field("div.halvard.1a", "3b", "Ordinary dividends", "14820")]},
        cited={(SHEET, "div.halvard.1a"): (C1,)},
        boxes=[_box(C1, "14,820", "m1a")],
    )
    await ls.leadsheets(_ctx(), RETURN, "1040")
    assert asked == [(ENGAGEMENT, [C1])]


@pytest.mark.asyncio
async def test_a_client_principal_reads_no_leadsheet(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, {})
    with pytest.raises(NotFound):
        await ls.leadsheets(_ctx(client=True), RETURN, "1040")


# --- links (AC-1.2, INV-2) -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_links_name_the_box_the_field_and_its_line(monkeypatch: pytest.MonkeyPatch) -> None:
    other = uuid.uuid4()
    rows = [
        _field("div.halvard.1a", "3b", "Ordinary dividends", "14820"),
        _field("div.note", "", "A note", None),
    ]
    rows[1].line_ref = None
    boxes = [
        _box(C1, "14,820", "ev:div#1a"),
        CitationBox(C3, other, 2, (1.0, 2.0, 3.0, 4.0), "ev:other#x", None),
    ]
    _wire(
        monkeypatch,
        {"linked": rows},
        cited={(SHEET, "div.halvard.1a"): (C1,), (SHEET, "div.note"): (C3,)},
        boxes=boxes,
    )
    links = await ls.field_links(_ctx(), RETURN, None)
    assert [(lk.match_id, lk.field_key, lk.line_key) for lk in links] == [
        ("ev:div#1a", "div.halvard.1a", "1040.3b"),
        ("ev:other#x", "div.note", None),
    ]
    assert links[0].page == 1 and links[0].bbox == (72.0, 140.0, 180.0, 154.0)
    only = await ls.field_links(_ctx(), RETURN, DIV)
    assert [lk.evidence_version_id for lk in only] == [DIV]


@pytest.mark.asyncio
async def test_a_field_with_no_live_box_has_no_link(monkeypatch: pytest.MonkeyPatch) -> None:
    # A withdrawn, moved or shadow citation never comes back from `citation_boxes`.
    _wire(
        monkeypatch,
        {"linked": [_field("div.halvard.1a", "3b", "Ordinary dividends", "14820")]},
        cited={(SHEET, "div.halvard.1a"): (C1,)},
        boxes=[],
    )
    assert await ls.field_links(_ctx(), RETURN, None) == []


# --- the matrix (AC-2.3) -------------------------------------------------------------------------


def _amount(key: str, label: str, v: str) -> SimpleNamespace:
    return SimpleNamespace(field_key=key, label=label, current_value=_typed(v))


def _matrix_answers() -> dict[str, Sequence[Any]]:  # Any: fake SQL rows
    return {
        "activities": [
            SimpleNamespace(id=ACTIVITY, k1_state="draft_pre_release", worksheet_id=K1_SHEET)
        ],
        f"sheet:{K1_SHEET}": [
            _amount("box2", "Net Rental Real Estate Income", "307900"),
            _amount("box5", "Interest Income", "4600"),
        ],
        f"prior:{ACTIVITY}": [
            SimpleNamespace(engagement_id=PRIOR_ENGAGEMENT, worksheet_id=PY_SHEET)
        ],
        f"sheet:{PY_SHEET}": [_amount("box2", "Net Rental Real Estate Income", "281600")],
    }


@pytest.mark.asyncio
async def test_the_matrix_carries_the_k1_lines_and_the_py_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, _matrix_answers())
    out = await ls.k1_matrix(_ctx(), RETURN)
    assert (out.tax_year, out.prior_year) == (2025, 2024)
    assert [(r.label, r.current_year, r.prior_year, r.status) for r in out.rows] == [
        ("Net Rental Real Estate Income", D("307900.00"), D("281600.00"), "draft_pre_release"),
        ("Interest Income", D("4600.00"), None, "draft_pre_release"),
    ]
    assert {r.activity_id for r in out.rows} == {ACTIVITY}


@pytest.mark.asyncio
async def test_last_years_figure_needs_last_years_engagement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, _matrix_answers(), prior_readable=False)
    out = await ls.k1_matrix(_ctx(), RETURN)
    assert [r.prior_year for r in out.rows] == [None, None]
    assert [r.current_year for r in out.rows] == [D("307900.00"), D("4600.00")]


@pytest.mark.asyncio
async def test_an_activity_without_a_worksheet_draws_no_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = _matrix_answers()
    answers["activities"] = [SimpleNamespace(id=ACTIVITY, k1_state="released", worksheet_id=None)]
    answers[f"prior:{ACTIVITY}"] = []
    _wire(monkeypatch, answers)
    assert (await ls.k1_matrix(_ctx(), RETURN)).rows == ()


@pytest.mark.asyncio
async def test_an_unknown_return_year_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, _matrix_answers(), year=None)
    with pytest.raises(NotFound):
        await ls.k1_matrix(_ctx(), RETURN)


# --- the code mismatch check (AC-1.4) ------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_document_whose_box_disagrees_is_named_with_its_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = uuid.uuid4()
    rows = [
        _field("div.halvard.1b", "3a", "Qualified dividends", "11960"),
        _field("div.halvard.1a", "3b", "Ordinary dividends", "14280"),
        _field("int.other.1", "2b", "Taxable interest", "100", "interest"),
    ]
    _wire(
        monkeypatch,
        {"linked": rows},
        cited={
            (SHEET, "div.halvard.1b"): (C2,),
            (SHEET, "div.halvard.1a"): (C1,),
            (SHEET, "int.other.1"): (C3,),
        },
        boxes=[
            _box(C1, "14,820", "m1a"),
            _box(C2, "11,960", "m1b"),
            CitationBox(C3, other, 1, (1.0, 2.0, 3.0, 4.0), "m3", "100"),
        ],
    )
    assert await ls.mismatched_documents(_ctx(), ENGAGEMENT, RETURN) == {DIV: "div.halvard.1a"}


def _review(
    monkeypatch: pytest.MonkeyPatch, mismatched: dict[uuid.UUID, str], approved: bool = False
) -> list[str]:
    from abacus.modules.tax import review_tree as rt

    writes: list[str] = []

    async def ret(_ctx: object, _r: uuid.UUID, _action: str) -> tuple[uuid.UUID, object]:
        return ENGAGEMENT, "resource"

    async def functions(_t: object, _r: uuid.UUID, _u: uuid.UUID) -> frozenset[str]:
        return frozenset({"preparer"})

    async def live(_ctx: object, _r: uuid.UUID) -> dict[tuple[uuid.UUID, str], int]:
        return {(DIV, "preparer"): 1} if approved else {}

    async def live_ids(_ctx: object, _r: uuid.UUID, _l: str) -> dict[uuid.UUID, uuid.UUID]:
        return {DIV: C1} if approved else {}

    async def documents(_t: object, _e: uuid.UUID) -> list[tuple[Any, ...]]:  # Any: tuples
        return [(DIV, uuid.uuid4(), "Halvard 1099-DIV", "Income", 1, True)]

    async def mism(_ctx: object, engagement: uuid.UUID, _r: uuid.UUID) -> dict[uuid.UUID, str]:
        assert engagement == ENGAGEMENT
        return mismatched

    @asynccontextmanager
    async def no_writes(_tenant: object) -> AsyncGenerator[None]:
        writes.append("uow")
        yield None

    monkeypatch.setattr(rt, "_return", ret)
    monkeypatch.setattr(rt, "functions_on", functions)
    monkeypatch.setattr(rt, "_live", live)
    monkeypatch.setattr(rt, "_live_ids", live_ids)
    monkeypatch.setattr(rt, "engagement_documents", documents)
    monkeypatch.setattr(rt, "mismatched_documents", mism)
    monkeypatch.setattr(rt, "uow", no_writes)
    return writes


@pytest.mark.asyncio
async def test_the_tree_reads_mismatch_with_the_field(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.tax import review_tree as rt

    _review(monkeypatch, {DIV: "div.halvard.1a"})
    docs, review, _ = await rt.tree(_ctx(), RETURN, level=None, q=None, category=None)
    assert [(d.approval, d.mismatch_field_key) for d in docs] == [("mismatch", "div.halvard.1a")]
    assert review == 1
    _review(monkeypatch, {})
    docs, _, _ = await rt.tree(_ctx(), RETURN, level=None, q=None, category=None)
    assert [(d.approval, d.mismatch_field_key) for d in docs] == [("unapproved", None)]


@pytest.mark.asyncio
async def test_an_approval_made_before_the_mismatch_stays_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.tax import review_tree as rt

    _review(monkeypatch, {DIV: "div.halvard.1a"}, approved=True)
    docs, _, _ = await rt.tree(_ctx(), RETURN, level=None, q=None, category=None)
    assert [(d.approval, d.approval_id, d.mismatch_field_key) for d in docs] == [
        ("approved", C1, None)
    ]


@pytest.mark.asyncio
async def test_approving_a_mismatched_document_is_409_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.tax import review_tree as rt

    writes = _review(monkeypatch, {DIV: "div.halvard.1a"})
    with pytest.raises(rt.Mismatch) as refused:
        await rt.approve(_ctx(), RETURN, evidence_version_id=DIV, level="preparer", seen_version=1)
    assert refused.value.code == "mismatch"
    assert refused.value.facts == {"field_key": "div.halvard.1a"}
    assert writes == []


@pytest.mark.asyncio
async def test_a_field_key_too_long_for_a_fact_still_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.tax import review_tree as rt

    long_key = "div." + "a" * 80
    writes = _review(monkeypatch, {DIV: long_key})
    with pytest.raises(rt.Mismatch) as refused:
        await rt.approve(_ctx(), RETURN, evidence_version_id=DIV, level="preparer", seen_version=1)
    assert refused.value.facts == {}
    assert writes == []
