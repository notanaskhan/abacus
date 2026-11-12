"""T-05-T16 (TASK-7307; ADR-237; DEC-4307): property tests for E13, the workbook engine
(Hypothesis): random acyclic workbooks evaluate in an order where every formula follows what it
reads, the dirty set is exactly the transitive dependents (minimal), recomputing the dirty set
equals a full evaluation, a back reference is refused as a cycle, and render-then-parse is a round
trip. The nightly mutation job's `compute` scope covers `workpapers/compute`."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.workpapers.compute.dag import (
    CellInput,
    CycleError,
    Workbook,
    build_graph,
    dirty,
    evaluate,
    recompute,
)
from abacus.modules.workpapers.compute.formula import parse, render

SHEET = "01"


@st.composite
def workbooks(draw: st.DrawFn) -> Workbook:
    """Row 1 holds values; each later row's cell is a formula over earlier rows only."""
    book = Workbook((SHEET,))
    values = draw(st.lists(st.integers(-1000, 1000), min_size=1, max_size=4))
    for i, v in enumerate(values, start=1):
        book.set(SHEET, f"A{i}", CellInput(value=Decimal(v)))
    for row in range(len(values) + 1, len(values) + draw(st.integers(1, 6)) + 1):
        reads = draw(st.lists(st.integers(1, row - 1), min_size=1, max_size=3))
        op = draw(st.sampled_from(["+", "-", "*"]))
        text = "=" + op.join(f"A{r}" for r in reads)
        if draw(st.booleans()):
            text = f"=SUM(A1:A{row - 1})"
        book.set(SHEET, f"A{row}", CellInput(formula=text))
    return book


def _dependents(reads: dict[str, tuple[str, ...]], changed: str) -> set[str]:
    found: set[str] = set()
    frontier = {changed}
    while frontier:
        nxt = {c for c, rs in reads.items() if frontier & set(rs)} - found
        found |= nxt
        frontier = nxt
    return found


@settings(max_examples=150, deadline=None)
@given(book=workbooks())
def test_the_order_respects_every_read(book: Workbook) -> None:
    graph = build_graph(book)
    position = {address: i for i, address in enumerate(graph.order)}
    for cell, reads in graph.reads.items():
        for read in reads:
            if read in position:
                assert position[read] < position[cell]


@settings(max_examples=150, deadline=None)
@given(book=workbooks(), new_value=st.integers(-1000, 1000))
def test_the_dirty_set_is_minimal_and_recompute_equals_a_full_evaluation(
    book: Workbook, new_value: int
) -> None:
    graph = build_graph(book)
    before = evaluate(book, graph)
    changed = book.set(SHEET, "A1", CellInput(value=Decimal(new_value)))
    touched = dirty(graph, [changed])
    assert set(touched) == _dependents(dict(graph.reads), changed)
    after, recomputed = recompute(book, graph, before, [changed])
    assert recomputed == touched
    full = evaluate(book, graph)
    assert {a: r.value for a, r in after.items()} == {a: r.value for a, r in full.items()}


@settings(max_examples=100, deadline=None)
@given(book=workbooks())
def test_a_back_reference_is_refused_as_a_cycle(book: Workbook) -> None:
    last = max(int(a.split("!")[-1][1:]) for a in book.cells)
    book.set(SHEET, "A1", CellInput(formula=f"=A{last}+1"))
    if last == 1:
        book.set(SHEET, "A1", CellInput(formula="=A1+1"))
    with pytest.raises(CycleError):
        build_graph(book)


_atoms = st.one_of(
    st.integers(0, 10**6).map(str),
    st.sampled_from(["A1", "B2", "'06 Schedule K'!C31", "Sheet2!D4"]),
)


@st.composite
def formulas(draw: st.DrawFn, depth: int = 3) -> str:
    if depth == 0 or draw(st.booleans()):
        return draw(_atoms)
    kind = draw(st.sampled_from(["bin", "neg", "pct", "fn", "paren"]))
    a = draw(formulas(depth - 1))
    if kind == "bin":
        return f"{a} {draw(st.sampled_from(['+', '-', '*', '/']))} {draw(formulas(depth - 1))}"
    if kind == "neg":
        return f"-{a}"
    if kind == "pct":
        return f"({a})%"
    if kind == "fn":
        return f"ROUND({a}, {draw(st.integers(0, 4))})"
    return f"({a})"


@settings(max_examples=300, deadline=None)
@given(text=formulas())
def test_render_then_parse_is_a_round_trip(text: str) -> None:
    tree = parse("=" + text)
    assert parse(render(tree)) == tree
