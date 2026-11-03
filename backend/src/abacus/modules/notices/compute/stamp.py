"""The engine stamp every notices result carries (N-04 §4.4)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

ENGINE_NAME: Final = "notices"
ENGINE_VERSION: Final = "1"


@dataclass(frozen=True)
class Stamp:
    engine_name: str
    engine_version: str
    inputs_hash: str


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def stamp(kind: str, inputs: object) -> Stamp:
    """The SHA-256 of the canonical JSON of `inputs` under this engine and `kind`."""
    body = json.dumps(
        {"engine": ENGINE_NAME, "version": ENGINE_VERSION, "kind": kind, "inputs": _plain(inputs)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return Stamp(ENGINE_NAME, ENGINE_VERSION, hashlib.sha256(body.encode("utf-8")).hexdigest())
