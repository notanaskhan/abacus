"""NetSuite's "TB by subsidiary" CSV split into one trial balance per subsidiary (A-09-T18;
SPEC-658; AUD-32 bulk upload). Pure: no I/O. Client content is untrusted: cells are text, never
formulas; amounts are parsed, never evaluated; each subsidiary must balance or it is refused."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, cast

CENT: Final = Decimal("0.01")
HEADERS: Final = ("subsidiary", "account", "account name", "debit", "credit")
MAX_ROWS: Final = 50_000


class SplitRefused(ValueError):
    code = "tb_split_refused"


@dataclass(frozen=True)
class SplitLine:
    account: str
    name: str
    debit: Decimal
    credit: Decimal


def _amount(raw: str) -> Decimal:
    text = raw.strip().replace(",", "").replace("$", "")
    if not text:
        return Decimal("0.00")
    negative = text.startswith("(") and text.endswith(")")
    try:
        value = Decimal(text.strip("()")).quantize(CENT)
    except InvalidOperation:
        raise SplitRefused("amount") from None
    return -value if negative else value


def split(data: bytes) -> Mapping[str, tuple[SplitLine, ...]]:
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
    first: list[str] = next(reader, cast("list[str]", []))
    header = [h.strip().casefold() for h in first]
    if any(h not in header for h in HEADERS):
        raise SplitRefused("header")
    at = {h: header.index(h) for h in HEADERS}
    out: dict[str, list[SplitLine]] = {}
    for n, row in enumerate(reader):
        if n >= MAX_ROWS:
            raise SplitRefused("too_many_rows")
        if not any(cell.strip() for cell in row):
            continue
        sub = row[at["subsidiary"]].strip()[:200]
        if not sub:
            raise SplitRefused("subsidiary")
        out.setdefault(sub, []).append(
            SplitLine(
                row[at["account"]].strip()[:64],
                row[at["account name"]].strip()[:200],
                _amount(row[at["debit"]]),
                _amount(row[at["credit"]]),
            )
        )
    for sub, lines in out.items():
        if sum((ln.debit for ln in lines), Decimal(0)) != sum(
            (ln.credit for ln in lines), Decimal(0)
        ):
            raise SplitRefused(f"unbalanced:{len(sub)}")
    return {k: tuple(v) for k, v in out.items()}
