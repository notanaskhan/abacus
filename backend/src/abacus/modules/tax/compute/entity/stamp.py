"""The entity engines' output stamp (T-05-T09; T-05 §4.4; DEC-77, DEC-3408): `engine_name`,
`engine_version` and the SHA-256 of the canonical inputs on every output, so a figure can always be
traced to the engine and the inputs that made it. Independent of `tax.compute.individual`."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast

ENGINE_VERSION: Final = "1"


@dataclass(frozen=True, slots=True)
class Stamp:
    engine_name: str
    engine_version: str
    inputs_hash: str


def plain(value: object) -> object:
    """A JSON-ready canonical form: Decimals as fixed-point text, mappings sorted."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        items = cast(Mapping[object, object], value).items()
        return {str(k): plain(v) for k, v in sorted(items, key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in cast(Sequence[object], value)]
    return value


def stamp(engine_name: str, inputs: object) -> Stamp:
    body = json.dumps(
        {"engine": engine_name, "version": ENGINE_VERSION, "inputs": plain(inputs)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return Stamp(engine_name, ENGINE_VERSION, hashlib.sha256(body.encode()).hexdigest())
