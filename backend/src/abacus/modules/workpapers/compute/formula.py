"""E13 part 1: the workbook formula grammar, tokenizer and parser (T-05-T07; ADR-237 §2).

A formula is parsed by code into a typed expression tree and never evaluated as Python: there is
no `eval`, `exec`, `compile`, dynamic import or host function anywhere in this package (a
banned-pattern test proves it). The grammar is closed (ADR-237 §2):

    formula     := "="? expression
    expression  := additive
    comparison  := additive (("=" | "<>" | "≠" | "<" | "<=" | "≤" | ">" | ">=" | "≥") additive)?
    additive    := term (("+" | "-" | "-") term)*
    term        := unary (("*" | "x" | "/" | "÷") unary)*
    unary       := ("-" | "-" | "+") unary | postfix
    postfix     := primary "%"?
    primary     := NUMBER | reference | function | "(" expression ")"
    reference   := [sheet "!"] CELL [":" CELL]
    sheet       := "'" quoted-title "'" | bare-title
    function    := ("SUM" | "ROUND" | "IF" | "MIN" | "MAX") "(" arguments ")"

A comparison is allowed only as the first argument of `IF`; a range only as an argument of `SUM`,
`MIN` or `MAX`. Cell references follow the P-07 cell-address SPEC (SPEC-641): `C31`, `Sheet!A1`,
`'06 Schedule K'!C31`; `$` absolute markers are accepted and dropped. Anything else is a
`FormulaError` with a code and a character position, never the formula text (ADR-237: 422
`formula_invalid`). The codes are the T-05-T07 set plus the parser's own:

- `syntax`: a token or construct outside the grammar (unbalanced parenthesis, stray character,
  trailing input, empty formula).
- `ref_invalid`: a reference the grammar cannot address (a column past `XFD`, row 0 or past
  1,048,576, an empty or unterminated sheet title, a range across sheets, a range whose corners
  are reversed).
- `unsupported_function`: a function name outside SUM, ROUND, IF, MIN, MAX, or a known function
  with the wrong number of arguments.
- `type`: a construct in the wrong place (a range outside SUM/MIN/MAX, a comparison outside IF's
  condition, a percent sign after anything but a number).
- `cycle` and `div_zero` belong to evaluation (T-05-T08's `dag.py`) and are declared here so the
  code set is one list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final

MAX_FORMULA_LENGTH: Final = 2000
MAX_COLUMN: Final = 16384  # XFD, Excel's last column
MAX_ROW: Final = 1_048_576
MAX_DEPTH: Final = 64  # nesting bound, so a hostile formula cannot exhaust the stack


class FormulaErrorCode(StrEnum):
    SYNTAX = "syntax"
    REF_INVALID = "ref_invalid"
    UNSUPPORTED_FUNCTION = "unsupported_function"
    TYPE = "type"
    CYCLE = "cycle"
    DIV_ZERO = "div_zero"


class FormulaError(ValueError):
    """A formula outside the closed grammar. Carries a code and a 0-based position only."""

    def __init__(self, code: FormulaErrorCode, position: int) -> None:
        super().__init__(f"{code.value} at {position}")
        self.code = code
        self.position = position


class Function(StrEnum):
    SUM = "SUM"
    ROUND = "ROUND"
    IF = "IF"
    MIN = "MIN"
    MAX = "MAX"


class BinaryOp(StrEnum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


class CompareOp(StrEnum):
    EQ = "="
    NE = "<>"
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


# --- AST --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CellRef:
    """One cell. `sheet` is the sheet title as written (None: the formula's own sheet)."""

    sheet: str | None
    column: int  # 1-based (A = 1)
    row: int  # 1-based

    @property
    def a1(self) -> str:
        return f"{column_letters(self.column)}{self.row}"

    def address(self, own_sheet: str) -> str:
        """The canonical address, `'05 Capital'!H12` style when the title needs quoting."""
        return format_address(self.sheet or own_sheet, self.a1)


@dataclass(frozen=True, slots=True)
class RangeRef:
    start: CellRef
    end: CellRef  # same sheet, end column and row >= start's

    def cells(self) -> tuple[CellRef, ...]:
        return tuple(
            CellRef(self.start.sheet, column, row)
            for row in range(self.start.row, self.end.row + 1)
            for column in range(self.start.column, self.end.column + 1)
        )


@dataclass(frozen=True, slots=True)
class Number:
    value: Decimal


@dataclass(frozen=True, slots=True)
class Percent:
    """`25%`: a number literal divided by 100, kept apart so it renders back as written."""

    value: Decimal


@dataclass(frozen=True, slots=True)
class Negate:
    operand: Expr


@dataclass(frozen=True, slots=True)
class Binary:
    op: BinaryOp
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Compare:
    op: CompareOp
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Call:
    function: Function
    arguments: tuple[Expr | RangeRef | Compare, ...]


Expr = Number | Percent | CellRef | Negate | Binary | Call


@dataclass(frozen=True, slots=True)
class Formula:
    """A parsed formula: its tree and every cell it reads, in first-seen order."""

    tree: Expr
    references: tuple[CellRef, ...]

    def inputs(self, own_sheet: str) -> tuple[str, ...]:
        """The canonical addresses this formula reads (`formula_inputs` in the cell store)."""
        seen: dict[str, None] = {}
        for ref in self.references:
            seen.setdefault(ref.address(own_sheet), None)
        return tuple(seen)


# --- addresses --------------------------------------------------------------------------------

# Patterns as strings, matched through `re`'s module functions (which cache them): the no-eval
# scan of this package refuses a `compile` name of any kind.
_BARE_TITLE: Final = r"^[A-Za-z0-9_.]+$"
_CELL: Final = r"\$?([A-Za-z]{1,3})\$?([0-9]{1,7})"
_DIGIT_WORD: Final = r"[A-Za-z0-9_.]+"


def _match_at(pattern: str, text: str, index: int) -> str | None:
    """The match of `pattern` at `index` of `text` (anchored there), or None."""
    found = re.match(pattern, text[index:])
    return None if found is None else found.group()


def column_letters(column: int) -> str:
    letters = ""
    while column:
        column, rest = divmod(column - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def column_number(letters: str) -> int:
    number = 0
    for char in letters.upper():
        number = number * 26 + (ord(char) - 64)
    return number


def format_address(sheet: str, a1: str) -> str:
    """`Sheet!A1`, quoting the title (and doubling its quotes) when it is not a bare word."""
    if re.match(_BARE_TITLE, sheet) and not sheet[0].isdigit():
        return f"{sheet}!{a1}"
    return "'" + sheet.replace("'", "''") + f"'!{a1}"


# --- tokenizer --------------------------------------------------------------------------------


class _Kind(StrEnum):
    NUMBER = "number"
    CELL = "cell"
    SHEET = "sheet"  # a quoted or bare title followed by "!"
    NAME = "name"  # a function name
    OP = "op"
    LPAREN = "("
    RPAREN = ")"
    COMMA = ","
    COLON = ":"
    PERCENT = "%"
    END = "end"


@dataclass(frozen=True, slots=True)
class _Token:
    kind: _Kind
    text: str
    position: int


_OPERATORS: Final = {
    "+": "+",
    "-": "-",
    "\u2212": "-",  # MINUS SIGN, as the handoff writes it
    "*": "*",
    "\u00d7": "*",  # MULTIPLICATION SIGN
    "/": "/",
    "÷": "/",
    "=": "=",
    "<>": "<>",
    "≠": "<>",
    "<": "<",
    "<=": "<=",
    "≤": "<=",
    ">": ">",
    ">=": ">=",
    "≥": ">=",
}
_NUMBER: Final = r"[0-9]+(?:\.[0-9]+)?|\.[0-9]+"
_WORD: Final = r"\$?[A-Za-z_][A-Za-z0-9_.]*\$?[0-9]*"
_SUPPORTED: Final = frozenset(f.value for f in Function)


def _tokens(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char in " \t":
            index += 1
            continue
        start = index
        if char == "'":
            index += 1
            title: list[str] = []
            while True:
                if index >= length:
                    raise FormulaError(FormulaErrorCode.REF_INVALID, start)
                if text[index] == "'":
                    if index + 1 < length and text[index + 1] == "'":
                        title.append("'")
                        index += 2
                        continue
                    index += 1
                    break
                title.append(text[index])
                index += 1
            if not title or index >= length or text[index] != "!":
                raise FormulaError(FormulaErrorCode.REF_INVALID, start)
            tokens.append(_Token(_Kind.SHEET, "".join(title), start))
            index += 1
            continue
        if char.isdigit() or (char == "." and index + 1 < length and text[index + 1].isdigit()):
            # A digit-led word followed by "!" is a bare sheet title (`05!H12`).
            word = _match_at(_DIGIT_WORD, text, index)
            if word is None:  # the digit at `index` always matches; kept for the type checker
                raise FormulaError(FormulaErrorCode.SYNTAX, start)
            after = index + len(word)
            if after < length and text[after] == "!":
                tokens.append(_Token(_Kind.SHEET, word, start))
                index = after + 1
                continue
            number = _match_at(_NUMBER, text, index)
            if number is None:
                raise FormulaError(FormulaErrorCode.SYNTAX, start)
            tokens.append(_Token(_Kind.NUMBER, number, start))
            index += len(number)
            continue
        if char.isalpha() or char in "$_":
            raw = _match_at(_WORD, text, index)
            if raw is None:
                raise FormulaError(FormulaErrorCode.SYNTAX, start)
            index += len(raw)
            if index < length and text[index] == "!":
                if "$" in raw:
                    raise FormulaError(FormulaErrorCode.REF_INVALID, start)
                tokens.append(_Token(_Kind.SHEET, raw, start))
                index += 1
                continue
            if index < length and text[index] == "(":
                # A name before "(" is a function call, even when it looks like a cell (LOG10).
                # One outside the grammar is refused here, at its name, before its arguments
                # (which may hold what the grammar has no token for: `INDIRECT("A1")`).
                if raw.upper() not in _SUPPORTED:
                    raise FormulaError(FormulaErrorCode.UNSUPPORTED_FUNCTION, start)
                tokens.append(_Token(_Kind.NAME, raw.upper(), start))
                continue
            if re.fullmatch(_CELL, raw):
                tokens.append(_Token(_Kind.CELL, raw, start))
                continue
            # A bare word that is neither a cell, a sheet nor a function (a name, TRUE, a
            # string-looking token): outside the grammar.
            raise FormulaError(FormulaErrorCode.SYNTAX, start)
        two = text[index : index + 2]
        if two in _OPERATORS and len(two) == 2:
            tokens.append(_Token(_Kind.OP, _OPERATORS[two], start))
            index += 2
            continue
        if char in _OPERATORS:
            tokens.append(_Token(_Kind.OP, _OPERATORS[char], start))
            index += 1
            continue
        single = {"(": _Kind.LPAREN, ")": _Kind.RPAREN, ",": _Kind.COMMA, ":": _Kind.COLON}
        if char in single:
            tokens.append(_Token(single[char], char, start))
            index += 1
            continue
        if char == "%":
            tokens.append(_Token(_Kind.PERCENT, char, start))
            index += 1
            continue
        raise FormulaError(FormulaErrorCode.SYNTAX, start)
    tokens.append(_Token(_Kind.END, "", length))
    return tokens


# --- parser -----------------------------------------------------------------------------------

_ARITY: Final = {
    Function.SUM: (1, 255),
    Function.MIN: (1, 255),
    Function.MAX: (1, 255),
    Function.ROUND: (2, 2),
    Function.IF: (3, 3),
}
_RANGE_FUNCTIONS: Final = frozenset({Function.SUM, Function.MIN, Function.MAX})


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._index = 0
        self._depth = 0
        self.references: list[CellRef] = []

    def _peek(self) -> _Token:
        return self._tokens[self._index]

    def _next(self) -> _Token:
        token = self._tokens[self._index]
        self._index += 1
        return token

    def _expect(self, kind: _Kind) -> _Token:
        token = self._next()
        if token.kind is not kind:
            raise FormulaError(FormulaErrorCode.SYNTAX, token.position)
        return token

    def _enter(self, position: int) -> None:
        self._depth += 1
        if self._depth > MAX_DEPTH:
            raise FormulaError(FormulaErrorCode.SYNTAX, position)

    def _leave(self) -> None:
        self._depth -= 1

    def formula(self) -> Expr:
        if self._peek().kind is _Kind.END:
            raise FormulaError(FormulaErrorCode.SYNTAX, 0)
        tree = self._additive()
        token = self._peek()
        if token.kind is _Kind.OP and token.text in {"=", "<>", "<", "<=", ">", ">="}:
            raise FormulaError(FormulaErrorCode.TYPE, token.position)
        if token.kind is not _Kind.END:
            raise FormulaError(FormulaErrorCode.SYNTAX, token.position)
        return tree

    def _comparison(self) -> Expr | Compare:
        left = self._additive()
        token = self._peek()
        if token.kind is _Kind.OP and token.text in {"=", "<>", "<", "<=", ">", ">="}:
            self._next()
            right = self._additive()
            return Compare(CompareOp(token.text), left, right)
        return left

    def _additive(self) -> Expr:
        left = self._term()
        while (token := self._peek()).kind is _Kind.OP and token.text in {"+", "-"}:
            self._next()
            left = Binary(BinaryOp(token.text), left, self._term())
        return left

    def _term(self) -> Expr:
        left = self._unary()
        while (token := self._peek()).kind is _Kind.OP and token.text in {"*", "/"}:
            self._next()
            left = Binary(BinaryOp(token.text), left, self._unary())
        return left

    def _unary(self) -> Expr:
        token = self._peek()
        if token.kind is _Kind.OP and token.text in {"+", "-"}:
            self._next()
            self._enter(token.position)
            operand = self._unary()
            self._leave()
            return operand if token.text == "+" else Negate(operand)
        return self._postfix()

    def _postfix(self) -> Expr:
        start = self._peek()
        value = self._primary(allow_range=False)
        if self._peek().kind is _Kind.PERCENT:
            percent = self._next()
            if not isinstance(value, Number) or start.kind is not _Kind.NUMBER:
                raise FormulaError(FormulaErrorCode.TYPE, percent.position)
            return Percent(value.value)
        if isinstance(value, RangeRef):
            raise FormulaError(FormulaErrorCode.TYPE, 0)
        return value

    def _primary(self, *, allow_range: bool) -> Expr | RangeRef:
        token = self._next()
        if token.kind is _Kind.NUMBER:
            try:
                return Number(Decimal(token.text))
            except InvalidOperation as exc:  # pragma: no cover - the tokenizer's regex is decimal
                raise FormulaError(FormulaErrorCode.SYNTAX, token.position) from exc
        if token.kind in {_Kind.CELL, _Kind.SHEET}:
            return self._reference(token, allow_range=allow_range)
        if token.kind is _Kind.NAME:
            return self._call(token)
        if token.kind is _Kind.LPAREN:
            self._enter(token.position)
            inner = self._additive()
            self._leave()
            self._expect(_Kind.RPAREN)
            return inner
        raise FormulaError(FormulaErrorCode.SYNTAX, token.position)

    def _cell(self, token: _Token, sheet: str | None) -> CellRef:
        match = re.fullmatch(_CELL, token.text)
        if match is None:
            raise FormulaError(FormulaErrorCode.REF_INVALID, token.position)
        column = column_number(match.group(1))
        row = int(match.group(2))
        if column > MAX_COLUMN or row < 1 or row > MAX_ROW:
            raise FormulaError(FormulaErrorCode.REF_INVALID, token.position)
        return CellRef(sheet, column, row)

    def _reference(self, token: _Token, *, allow_range: bool) -> CellRef | RangeRef:
        sheet: str | None = None
        cell_token = token
        if token.kind is _Kind.SHEET:
            sheet = token.text
            cell_token = self._next()
            if cell_token.kind is not _Kind.CELL:
                raise FormulaError(FormulaErrorCode.REF_INVALID, cell_token.position)
        start = self._cell(cell_token, sheet)
        if self._peek().kind is not _Kind.COLON:
            self.references.append(start)
            return start
        colon = self._next()
        end_token = self._next()
        if end_token.kind is _Kind.SHEET:
            # `A1:'Other'!B2` would span sheets: not addressable.
            raise FormulaError(FormulaErrorCode.REF_INVALID, end_token.position)
        if end_token.kind is not _Kind.CELL:
            raise FormulaError(FormulaErrorCode.REF_INVALID, end_token.position)
        end = self._cell(end_token, sheet)
        if end.column < start.column or end.row < start.row:
            raise FormulaError(FormulaErrorCode.REF_INVALID, end_token.position)
        if not allow_range:
            raise FormulaError(FormulaErrorCode.TYPE, colon.position)
        whole = RangeRef(start, end)
        if len(whole.cells()) > 20_000:
            raise FormulaError(FormulaErrorCode.REF_INVALID, colon.position)
        self.references.extend(whole.cells())
        return whole

    def _call(self, name: _Token) -> Call:
        try:
            function = Function(name.text)
        except ValueError as exc:
            raise FormulaError(FormulaErrorCode.UNSUPPORTED_FUNCTION, name.position) from exc
        self._expect(_Kind.LPAREN)
        self._enter(name.position)
        arguments: list[Expr | RangeRef | Compare] = []
        if self._peek().kind is not _Kind.RPAREN:
            while True:
                arguments.append(self._argument(function, len(arguments)))
                if self._peek().kind is _Kind.COMMA:
                    self._next()
                    continue
                break
        self._expect(_Kind.RPAREN)
        self._leave()
        low, high = _ARITY[function]
        if not low <= len(arguments) <= high:
            raise FormulaError(FormulaErrorCode.UNSUPPORTED_FUNCTION, name.position)
        return Call(function, tuple(arguments))

    def _argument(self, function: Function, index: int) -> Expr | RangeRef | Compare:
        token = self._peek()
        if function is Function.IF and index == 0:
            return self._comparison()
        if function in _RANGE_FUNCTIONS and token.kind in {_Kind.CELL, _Kind.SHEET}:
            # A lone reference or a range; anything after it continues as an expression.
            mark = self._index
            refs_before = len(self.references)
            first = self._reference(self._next(), allow_range=True)
            if isinstance(first, RangeRef):
                following = self._peek()
                if following.kind not in {_Kind.COMMA, _Kind.RPAREN}:
                    raise FormulaError(FormulaErrorCode.TYPE, following.position)
                return first
            self._index = mark
            del self.references[refs_before:]
        expression = self._additive()
        following = self._peek()
        if following.kind is _Kind.OP and following.text in {"=", "<>", "<", "<=", ">", ">="}:
            raise FormulaError(FormulaErrorCode.TYPE, following.position)
        return expression


def parse(text: str) -> Formula:
    """Parse one formula (with or without its leading `=`) into its typed tree.

    Raises `FormulaError` for anything outside the closed grammar; never evaluates anything.
    """
    if len(text) > MAX_FORMULA_LENGTH:
        raise FormulaError(FormulaErrorCode.SYNTAX, MAX_FORMULA_LENGTH)
    body = text.strip()
    offset = len(text) - len(text.lstrip())
    if body.startswith("="):
        body = body[1:]
        offset += 1
    try:
        tokens = _tokens(body)
    except FormulaError as error:
        raise FormulaError(error.code, error.position + offset) from None
    parser = _Parser(tokens)
    try:
        tree = parser.formula()
    except FormulaError as error:
        raise FormulaError(error.code, error.position + offset) from None
    return Formula(tree, tuple(parser.references))


def is_valid(text: str) -> bool:
    try:
        parse(text)
    except FormulaError:
        return False
    return True


# --- rendering --------------------------------------------------------------------------------

_PRECEDENCE: Final = {BinaryOp.ADD: 1, BinaryOp.SUB: 1, BinaryOp.MUL: 2, BinaryOp.DIV: 2}


def render(formula: Formula | Expr, own_sheet: str | None = None) -> str:
    """The canonical text of a tree (ASCII operators), `=`-prefixed, for provenance and Excel.

    `own_sheet` set: references to that sheet drop their prefix; others keep theirs.
    """
    tree = formula.tree if isinstance(formula, Formula) else formula
    return "=" + _render(tree, own_sheet, 0)


def _ref_text(ref: CellRef, own_sheet: str | None) -> str:
    if ref.sheet is None or ref.sheet == own_sheet:
        return ref.a1
    return format_address(ref.sheet, ref.a1)


def _render(node: Expr | RangeRef | Compare, own_sheet: str | None, parent: int) -> str:
    if isinstance(node, Number):
        return format(node.value, "f")
    if isinstance(node, Percent):
        return f"{format(node.value, 'f')}%"
    if isinstance(node, CellRef):
        return _ref_text(node, own_sheet)
    if isinstance(node, RangeRef):
        return f"{_ref_text(node.start, own_sheet)}:{node.end.a1}"
    if isinstance(node, Negate):
        return "-" + _render(node.operand, own_sheet, 3)
    if isinstance(node, Compare):
        return (
            f"{_render(node.left, own_sheet, 0)}{node.op.value}{_render(node.right, own_sheet, 0)}"
        )
    if isinstance(node, Binary):
        level = _PRECEDENCE[node.op]
        right_level = level + 1 if node.op in {BinaryOp.SUB, BinaryOp.DIV} else level
        text = (
            _render(node.left, own_sheet, level)
            + node.op.value
            + _render(node.right, own_sheet, right_level)
        )
        return f"({text})" if level < parent else text
    arguments = ",".join(_render(argument, own_sheet, 0) for argument in node.arguments)
    return f"{node.function.value}({arguments})"
