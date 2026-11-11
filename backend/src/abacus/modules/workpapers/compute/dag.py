"""E13 part 2: the workbook's dependency graph and its evaluation (T-05-T08; ADR-237 §3; ADR-050;
DEC-3407).

Formulas are parsed by `formula.parse` into typed trees; this module never evaluates text. Pure: no
clock, no database, no I/O, no `eval` (the package's banned-pattern test reads this file too).

- **Graph.** Every formula cell depends on each address it reads (a range is every cell in it,
  across the workbook's sheets by canonical address). A cell nobody wrote reads as 0.
- **Cycles.** A cycle is refused before anything is evaluated: `FormulaError(cycle)` naming the
  cycle's addresses in order (the code and the addresses, never formula text).
- **Order.** Deterministic: a topological order that, among cells ready at once, takes the
  workbook's sheet order, then row, then column. The same workbook evaluates the same way every
  time.
- **Dirty set.** An edit recomputes only its dependents (transitively), in evaluation order; the
  rest keep their values.
- **Arithmetic.** Exact `Decimal` (`kernel.numeric`'s context): `+ - * /`, unary minus, `%`,
  `SUM`, `MIN`, `MAX`, `ROUND(x, n)` half up, `IF(cond, a, b)`. A division by zero makes that
  cell `div_zero` (no value) and every cell reading it `div_zero` too; nothing raises.
- **Provenance.** Each computed cell records its formula as written back by `formula.render` and
  its inputs' canonical addresses (`formula_inputs`), so SHL-09 can say how a figure was made.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Final

from abacus.kernel.numeric import CONTEXT
from abacus.modules.workpapers.compute.formula import (
    Binary,
    BinaryOp,
    Call,
    CellRef,
    Compare,
    CompareOp,
    Expr,
    Formula,
    FormulaError,
    FormulaErrorCode,
    Function,
    Negate,
    Number,
    Percent,
    RangeRef,
    column_number,
    format_address,
    parse,
    render,
)

ZERO: Final = Decimal(0)


@dataclass(frozen=True, slots=True)
class CellInput:
    """One cell as stored: a typed value or a formula's text (never both)."""

    value: Decimal | None = None
    formula: str | None = None


@dataclass(frozen=True, slots=True)
class Provenance:
    text: str
    inputs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CellResult:
    value: Decimal | None
    error: FormulaErrorCode | None = None
    provenance: Provenance | None = None


def _split(address: str) -> tuple[str, str]:
    """`'05 Capital'!H12` → (`05 Capital`, `H12`)."""
    sheet, _, a1 = address.rpartition("!")
    if sheet.startswith("'") and sheet.endswith("'"):
        sheet = sheet[1:-1].replace("''", "'")
    return sheet, a1


def _rowcol(a1: str) -> tuple[int, int]:
    letters = "".join(c for c in a1 if c.isalpha())
    digits = "".join(c for c in a1 if c.isdigit())
    return int(digits), column_number(letters.upper())


def canonical(sheet: str, a1: str) -> str:
    return format_address(sheet, a1.replace("$", "").upper())


@dataclass
class Workbook:
    """The cells of one workbook by canonical address, and its sheets in tab order."""

    sheets: tuple[str, ...]
    cells: dict[str, CellInput] = field(default_factory=dict[str, CellInput])

    def set(self, sheet: str, a1: str, cell: CellInput) -> str:
        if sheet not in self.sheets:
            raise FormulaError(FormulaErrorCode.REF_INVALID, 0)
        address = canonical(sheet, a1)
        self.cells[address] = cell
        return address

    def sort_key(self, address: str) -> tuple[int, int, int]:
        sheet, a1 = _split(address)
        row, column = _rowcol(a1)
        index = self.sheets.index(sheet) if sheet in self.sheets else len(self.sheets)
        return index, row, column


@dataclass(frozen=True)
class Graph:
    formulas: Mapping[str, Formula]
    reads: Mapping[str, tuple[str, ...]]  # formula cell → the addresses it reads
    dependents: Mapping[str, tuple[str, ...]]  # address → the formula cells that read it
    order: tuple[str, ...]  # every formula cell, in evaluation order


def _expand(ref: CellRef | RangeRef, own_sheet: str) -> list[str]:
    if isinstance(ref, RangeRef):
        return [c.address(own_sheet) for c in ref.cells()]
    return [ref.address(own_sheet)]


def _reads(node: Expr | RangeRef | Compare, own_sheet: str, out: dict[str, None]) -> None:
    if isinstance(node, CellRef | RangeRef):
        for address in _expand(node, own_sheet):
            out.setdefault(address, None)
    elif isinstance(node, Negate):
        _reads(node.operand, own_sheet, out)
    elif isinstance(node, Binary | Compare):
        _reads(node.left, own_sheet, out)
        _reads(node.right, own_sheet, out)
    elif isinstance(node, Call):
        for argument in node.arguments:
            _reads(argument, own_sheet, out)


def build_graph(book: Workbook) -> Graph:
    """Parse every formula and order the graph; a cycle is `FormulaError(cycle)`."""
    formulas: dict[str, Formula] = {}
    reads: dict[str, tuple[str, ...]] = {}
    for address, cell in book.cells.items():
        if cell.formula is None:
            continue
        parsed = parse(cell.formula)
        found: dict[str, None] = {}
        _reads(parsed.tree, _split(address)[0], found)
        formulas[address] = parsed
        reads[address] = tuple(found)
    dependents: dict[str, list[str]] = {}
    for cell, inputs in reads.items():
        for read in inputs:
            dependents.setdefault(read, []).append(cell)
    order = _order(book, reads, dependents)
    return Graph(
        formulas,
        reads,
        {k: tuple(sorted(v, key=book.sort_key)) for k, v in dependents.items()},
        order,
    )


def _order(
    book: Workbook, reads: Mapping[str, tuple[str, ...]], dependents: Mapping[str, list[str]]
) -> tuple[str, ...]:
    """Kahn's algorithm over formula cells, ties broken by sheet, row, column."""
    waiting = {cell: sum(1 for r in inputs if r in reads) for cell, inputs in reads.items()}
    ready = [(book.sort_key(c), c) for c, n in waiting.items() if n == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        _, cell = heapq.heappop(ready)
        order.append(cell)
        for dependent in dependents.get(cell, ()):
            waiting[dependent] -= 1
            if waiting[dependent] == 0:
                heapq.heappush(ready, (book.sort_key(dependent), dependent))
    if len(order) != len(reads):
        raise CycleError(_cycle(reads, set(reads) - set(order), book))
    return tuple(order)


class CycleError(FormulaError):
    """A cycle among formula cells; `addresses` names it in order (never formula text)."""

    def __init__(self, addresses: Sequence[str]) -> None:
        super().__init__(FormulaErrorCode.CYCLE, 0)
        self.addresses = tuple(addresses)


def _cycle(reads: Mapping[str, tuple[str, ...]], stuck: set[str], book: Workbook) -> list[str]:
    """One cycle among the cells Kahn could not order, starting at its first cell in order."""
    start = min(stuck, key=book.sort_key)
    path: list[str] = []
    seen: dict[str, int] = {}
    cell = start
    while cell not in seen:
        seen[cell] = len(path)
        path.append(cell)
        cell = min((r for r in reads[cell] if r in stuck), key=book.sort_key)
    return path[seen[cell] :]


# --- evaluation ---------------------------------------------------------------------------------


class _DivZero(Exception):
    pass


def _value(address: str, book: Workbook, results: Mapping[str, CellResult]) -> Decimal:
    found = results.get(address)
    if found is not None:
        if found.error is not None:
            raise _DivZero
        return found.value if found.value is not None else ZERO
    cell = book.cells.get(address)
    return cell.value if cell is not None and cell.value is not None else ZERO


def _eval(
    node: Expr | RangeRef | Compare,
    own: str,
    book: Workbook,
    results: Mapping[str, CellResult],
) -> Decimal | list[Decimal] | bool:
    if isinstance(node, Number):
        return node.value
    if isinstance(node, Percent):
        return node.value / Decimal(100)
    if isinstance(node, CellRef):
        return _value(node.address(own), book, results)
    if isinstance(node, RangeRef):
        return [_value(a, book, results) for a in _expand(node, own)]
    if isinstance(node, Negate):
        return -_number(_eval(node.operand, own, book, results))
    if isinstance(node, Binary):
        left = _number(_eval(node.left, own, book, results))
        right = _number(_eval(node.right, own, book, results))
        if node.op is BinaryOp.ADD:
            return left + right
        if node.op is BinaryOp.SUB:
            return left - right
        if node.op is BinaryOp.MUL:
            return left * right
        if right == 0:
            raise _DivZero
        return left / right
    if isinstance(node, Compare):
        left = _number(_eval(node.left, own, book, results))
        right = _number(_eval(node.right, own, book, results))
        return {
            CompareOp.EQ: left == right,
            CompareOp.NE: left != right,
            CompareOp.LT: left < right,
            CompareOp.LE: left <= right,
            CompareOp.GT: left > right,
            CompareOp.GE: left >= right,
        }[node.op]
    return _call(node, own, book, results)


def _number(value: Decimal | list[Decimal] | bool) -> Decimal:
    if isinstance(value, list):
        raise FormulaError(FormulaErrorCode.TYPE, 0)
    if isinstance(value, bool):
        return Decimal(1) if value else ZERO
    return value


def _flat(values: Iterable[Decimal | list[Decimal] | bool]) -> list[Decimal]:
    out: list[Decimal] = []
    for v in values:
        out.extend(v) if isinstance(v, list) else out.append(_number(v))
    return out


def _call(node: Call, own: str, book: Workbook, results: Mapping[str, CellResult]) -> Decimal:
    if node.function is Function.IF:
        condition = _eval(node.arguments[0], own, book, results)
        branch = node.arguments[1] if bool(condition) else node.arguments[2]
        return _number(_eval(branch, own, book, results))
    values = [_eval(a, own, book, results) for a in node.arguments]
    if node.function is Function.SUM:
        return sum(_flat(values), ZERO)
    if node.function is Function.MIN:
        return min(_flat(values), default=ZERO)
    if node.function is Function.MAX:
        return max(_flat(values), default=ZERO)
    # ROUND(x, places): half up, places an integer
    amount, places = _number(values[0]), int(_number(values[1]))
    return amount.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _evaluate_cell(
    address: str, graph: Graph, book: Workbook, results: dict[str, CellResult]
) -> CellResult:
    parsed = graph.formulas[address]
    own = _split(address)[0]
    provenance = Provenance(render(parsed, own), parsed.inputs(own))
    try:
        with localcontext(CONTEXT):
            value = _number(_eval(parsed.tree, own, book, results))
    except _DivZero:
        return CellResult(None, FormulaErrorCode.DIV_ZERO, provenance)
    return CellResult(value, None, provenance)


def evaluate(book: Workbook, graph: Graph | None = None) -> dict[str, CellResult]:
    """Every formula cell's result, in evaluation order."""
    graph = graph or build_graph(book)
    results: dict[str, CellResult] = {}
    for address in graph.order:
        results[address] = _evaluate_cell(address, graph, book, results)
    return results


def dirty(graph: Graph, changed: Iterable[str]) -> tuple[str, ...]:
    """The formula cells an edit of `changed` must recompute, in evaluation order."""
    found: set[str] = set()
    stack = list(changed)
    while stack:
        for dependent in graph.dependents.get(stack.pop(), ()):
            if dependent not in found:
                found.add(dependent)
                stack.append(dependent)
    return tuple(c for c in graph.order if c in found)


def recompute(
    book: Workbook,
    graph: Graph,
    results: Mapping[str, CellResult],
    changed: Iterable[str],
) -> tuple[dict[str, CellResult], tuple[str, ...]]:
    """After an edit of `changed` (already in `book`): the new results and the cells recomputed
    (only the dependents; every other cell keeps its value)."""
    out = dict(results)
    touched = dirty(graph, changed)
    for address in touched:
        out[address] = _evaluate_cell(address, graph, book, out)
    return out, touched
