"""The working-paper formula engine (SPEC-308 AC-3; ADR-050: code computes).

A cell whose raw text starts with `=` is a formula: decimal arithmetic (`+ - * /`, unary minus,
parentheses), cell references (`B4`), `SUM(B2:B9)`, which counts only numeric cells in the
range, and `TB("1000")` (SPEC-310): an account's net on the engagement's trial balance of record,
end of year, `TB("1000", "BOY")` or `TB("1000", "FINAL")` (after recorded adjustments);
`TB("1000:1099")` sums a code range. Errors are values, as
in a spreadsheet: `#REF!` (a bad reference), `#CYCLE!` (a cell that depends on itself),
`#DIV/0!`, `#TB!` (no trial balance, or an account it doesn't hold) and `#ERR!` (anything that
doesn't parse). No floats anywhere.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Final

_TOKEN: Final = re.compile(
    r'\s*(?:(\d+(?:\.\d+)?)|"([^"]{0,64})"|(SUM|TB)\b|([A-Z]{1,2}[1-9][0-9]{0,3})|(.))'
)
_CELL: Final = re.compile(r"^([A-Z]{1,2})([1-9][0-9]{0,3})$")
_NUMBER: Final = re.compile(r"^\s*\(?-?\$?[0-9,]*\.?[0-9]+\)?\s*$")
MAX_RANGE: Final = 2000

Value = Decimal | str  # a number, plain text, or an error code


@dataclass(frozen=True)
class TbSource:
    """A trial balance's nets by account code (upper case) for the TB() function."""

    eoy: Mapping[str, Decimal]
    boy: Mapping[str, Decimal] | None
    final: Mapping[str, Decimal] | None = None  # SPEC-311: with recorded adjustments

    def total(self, selector: str, column: str) -> Decimal:
        nets = {"EOY": self.eoy, "BOY": self.boy, "FINAL": self.final}[column]
        if nets is None:
            raise FormulaError("#TB!")
        lo, _, hi = selector.strip().upper().partition(":")
        if not hi:
            if lo not in nets:
                raise FormulaError("#TB!")
            return nets[lo]
        codes = [c for c in nets if lo <= c <= hi]
        if not codes:
            raise FormulaError("#TB!")
        return sum((nets[c] for c in codes), Decimal(0))

    def uses(self, raw: str | None) -> bool:
        return raw is not None and raw.startswith("=") and "TB(" in raw.upper().replace(" ", "")


class FormulaError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def column_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def column_letters(index: int) -> str:
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def split_key(key: str) -> tuple[int, int]:
    """`B4` -> (column 2, row 4)."""
    m = _CELL.match(key)
    if m is None:
        raise FormulaError("#REF!")
    return column_index(m.group(1)), int(m.group(2))


def parse_number(raw: str) -> Decimal | None:
    """Plain numbers as auditors type them: `1,250.00`, `-3`, `(400)` for negative, `$12`."""
    if not _NUMBER.match(raw):
        return None
    text = raw.strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "").replace("$", "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if negative else value


class _Parser:
    def __init__(self, text: str, resolve: _Resolver) -> None:
        self.tokens: list[tuple[str, str]] = []
        for m in _TOKEN.finditer(text):
            if m.group(1):
                self.tokens.append(("num", m.group(1)))
            elif m.group(2) is not None:
                self.tokens.append(("str", m.group(2)))
            elif m.group(3):
                self.tokens.append(("fn", m.group(3)))
            elif m.group(4):
                self.tokens.append(("ref", m.group(4)))
            elif m.group(5) and not m.group(5).isspace():
                self.tokens.append(("op", m.group(5)))
        self.pos = 0
        self.resolve = resolve

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self, value: str | None = None) -> tuple[str, str]:
        token = self.peek()
        if token is None or (value is not None and token[1] != value):
            raise FormulaError("#ERR!")
        self.pos += 1
        return token

    def parse(self) -> Decimal:
        result = self.expr()
        if self.peek() is not None:
            raise FormulaError("#ERR!")
        return result

    def expr(self) -> Decimal:
        value = self.term()
        while (t := self.peek()) is not None and t[1] in "+-":
            self.take()
            right = self.term()
            value = value + right if t[1] == "+" else value - right
        return value

    def term(self) -> Decimal:
        value = self.unary()
        while (t := self.peek()) is not None and t[1] in "*/":
            self.take()
            right = self.unary()
            if t[1] == "*":
                value *= right
            else:
                try:
                    value /= right
                except (DivisionByZero, InvalidOperation) as exc:
                    raise FormulaError("#DIV/0!") from exc
        return value

    def unary(self) -> Decimal:
        t = self.peek()
        if t is not None and t[1] == "-":
            self.take()
            return -self.unary()
        if t is not None and t[1] == "+":
            self.take()
            return self.unary()
        return self.atom()

    def atom(self) -> Decimal:
        kind, text = self.take()
        if kind == "num":
            return Decimal(text)
        if kind == "ref":
            return self.number(self.resolve.value(text))
        if kind == "fn" and text == "TB":
            return self.tb()
        if kind == "fn":
            self.take("(")
            start = self.take()
            self.take(":")
            end = self.take()
            self.take(")")
            if start[0] != "ref" or end[0] != "ref":
                raise FormulaError("#REF!")
            return self.total(start[1], end[1])
        if text == "(":
            value = self.expr()
            self.take(")")
            return value
        raise FormulaError("#ERR!")

    def tb(self) -> Decimal:
        self.take("(")
        kind, selector = self.take()
        if kind != "str":
            raise FormulaError("#ERR!")
        column = "EOY"
        if (t := self.peek()) is not None and t[1] == ",":
            self.take(",")
            kind, column = self.take()
            if kind != "str" or column not in ("EOY", "BOY", "FINAL"):
                raise FormulaError("#ERR!")
        self.take(")")
        if self.resolve.tb is None:
            raise FormulaError("#TB!")
        return self.resolve.tb.total(selector, column)

    def total(self, start: str, end: str) -> Decimal:
        (c1, r1), (c2, r2) = split_key(start), split_key(end)
        c1, c2 = sorted((c1, c2))
        r1, r2 = sorted((r1, r2))
        if (c2 - c1 + 1) * (r2 - r1 + 1) > MAX_RANGE:
            raise FormulaError("#REF!")
        total = Decimal(0)
        for c in range(c1, c2 + 1):
            for r in range(r1, r2 + 1):
                value = self.resolve.value(f"{column_letters(c)}{r}")
                if isinstance(value, Decimal):
                    total += value
                elif value.startswith("#"):
                    raise FormulaError(value)
        return total

    @staticmethod
    def number(value: Value) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value.startswith("#"):
            raise FormulaError(value)
        if value == "":
            return Decimal(0)
        raise FormulaError("#ERR!")


class _Resolver:
    def __init__(self, raws: Mapping[str, str | None], tb: TbSource | None = None) -> None:
        self.raws = raws
        self.tb = tb
        self.done: dict[str, Value] = {}
        self.active: set[str] = set()

    def value(self, key: str) -> Value:
        if key in self.done:
            return self.done[key]
        if key in self.active:
            raise FormulaError("#CYCLE!")
        raw = self.raws.get(key) or ""
        if not raw.startswith("="):
            number = parse_number(raw) if raw else None
            result: Value = number if number is not None else raw
        else:
            self.active.add(key)
            try:
                result = _Parser(raw[1:].upper(), self).parse()
            except FormulaError as exc:
                result = exc.code
            finally:
                self.active.discard(key)
        self.done[key] = result
        return result


def evaluate(raws: Mapping[str, str | None], tb: TbSource | None = None) -> dict[str, Value]:
    """Every cell's value, computed from the raw texts of one sheet (and the trial balance)."""
    resolver = _Resolver(raws, tb)
    return {key: resolver.value(key) for key in raws}


def is_formula(raw: str | None) -> bool:
    return raw is not None and raw.startswith("=")
