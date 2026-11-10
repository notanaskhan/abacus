"""The stamp and the parameters (T-04-T11; DEC-3124)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from functools import cache
from pathlib import Path
from typing import Final, cast

import yaml

ENGINE_VERSION: Final = "1"
_DIR: Final = Path(__file__).resolve().parent / "parameters"
WHOLE: Final = Decimal("1")


@dataclass(frozen=True)
class Stamp:
    engine_name: str
    engine_version: str
    inputs_hash: str


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        items = cast(Mapping[object, object], value).items()
        return {str(k): _plain(v) for k, v in sorted(items, key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in cast(Sequence[object], value)]
    return value


def stamp(engine_name: str, inputs: Mapping[str, object]) -> Stamp:
    body = json.dumps(
        {"engine": engine_name, "version": ENGINE_VERSION, "inputs": _plain(inputs)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return Stamp(engine_name, ENGINE_VERSION, hashlib.sha256(body.encode()).hexdigest())


def whole(value: Decimal) -> Decimal:
    """Whole dollars, half up (the forms' own rounding)."""
    with localcontext() as ctx:
        ctx.prec = 28
        return value.quantize(WHOLE, rounding=ROUND_HALF_UP)


def pct(value: str) -> Decimal:
    return Decimal(value) / Decimal(100)


@cache
def parameters(tax_year: int) -> Mapping[str, object]:
    """`parameters/ty<tax_year>.yaml` (PROTECTED). A year without a file raises `LookupError`."""
    path = _DIR / f"ty{tax_year}.yaml"
    if not path.is_file():
        raise LookupError(f"individual return parameters: ty{tax_year}")
    return cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))


def parameter_table(tax_year: int, key: str) -> Mapping[str, object]:
    return cast(Mapping[str, object], parameters(tax_year)[key])
