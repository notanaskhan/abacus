"""Trust agreement (A-05-T39; A-05 §4.4 `trust_agreement`; EBP-06; DEC-2305): pure functions.

Each certified trust line agrees to the plan TB line of the same name for both dates. Level 1 and
NAV foot the certified investments, and a line marked `not_certified` (notes receivable) sits below
them and never counts as certified. Decimal only; the service passes the TB at the chosen layer.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

ENGINE_NAME: Final = "ebp_trust_agreement"
ENGINE_VERSION: Final = "1"
_ZERO: Final = Decimal(0)


@dataclass(frozen=True)
class TrustLine:
    line_key: str
    fund_name: str
    boy: Decimal | None
    eoy: Decimal | None
    level: str  # level1, nav, not_certified


@dataclass(frozen=True)
class TbFigure:
    name: str
    boy: Decimal | None
    eoy: Decimal


@dataclass(frozen=True)
class Agreed:
    line_key: str
    fund_name: str
    level: str
    trust_boy: Decimal | None
    trust_eoy: Decimal | None
    tb_boy: Decimal | None
    tb_eoy: Decimal | None
    ties: bool
    off_by: Decimal


@dataclass(frozen=True)
class Agreement:
    lines: tuple[Agreed, ...]
    investments_eoy: Decimal
    investments_boy: Decimal
    level1_eoy: Decimal
    nav_eoy: Decimal
    below_eoy: Decimal
    below_boy: Decimal
    py_ties: bool
    inputs_hash: str
    engine_version: str = ENGINE_VERSION


def normalised(name: str) -> str:
    return " ".join(name.lower().split())


def _hash(trust: Sequence[TrustLine], tb: Mapping[str, TbFigure]) -> str:
    body = {
        "trust": sorted(f"{t.line_key}|{t.boy}|{t.eoy}|{t.level}" for t in trust),
        "tb": sorted(f"{k}|{v.boy}|{v.eoy}" for k, v in tb.items()),
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def agree(trust: Sequence[TrustLine], tb_lines: Sequence[TbFigure]) -> Agreement:
    """Line by line against the TB at the chosen layer; the certified footing by level."""
    tb = {normalised(f.name): f for f in tb_lines}
    agreed: list[Agreed] = []
    investments_eoy = investments_boy = level1 = nav = below_eoy = below_boy = _ZERO
    py_ties = True
    for line in trust:
        found = tb.get(normalised(line.fund_name))
        tb_eoy = found.eoy if found else None
        tb_boy = found.boy if found else None
        eoy_off = (line.eoy or _ZERO) - (tb_eoy or _ZERO)
        boy_off = (line.boy or _ZERO) - (tb_boy or _ZERO)
        py_ties = py_ties and boy_off == _ZERO
        agreed.append(
            Agreed(
                line.line_key, line.fund_name, line.level, line.boy, line.eoy, tb_boy, tb_eoy,
                found is not None and eoy_off == _ZERO and boy_off == _ZERO, eoy_off,
            )  # fmt: skip
        )
        if line.level == "not_certified":
            below_eoy += line.eoy or _ZERO
            below_boy += line.boy or _ZERO
            continue
        investments_eoy += line.eoy or _ZERO
        investments_boy += line.boy or _ZERO
        if line.level == "level1":
            level1 += line.eoy or _ZERO
        elif line.level == "nav":
            nav += line.eoy or _ZERO
    return Agreement(
        tuple(agreed), investments_eoy, investments_boy, level1, nav, below_eoy, below_boy,
        py_ties, _hash(trust, tb),
    )  # fmt: skip
