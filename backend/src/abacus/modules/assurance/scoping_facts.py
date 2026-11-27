"""Assurance's scoping sources (K-03-T18; TASK-9011; SHT-03 a, b, d; DEC-6017).

Registered as methodology's `assurance` scoping-source provider, over the engagement's own
rows (code reads them; no model):

- `group_scoping.components.performed_by` — "Group scoping > Components > Performed by": the
  set of performers across the engagement's components (`group_team`, `component_auditor`);
  unanswered without components.
- `risk_register.<area>.significant` — "Scoping > Audit areas > <Area> · Significant": `yes` when
  a register row of the area is a significant risk (mandatory or approved), `no` when the area
  has rows and none is; unanswered when the area has no row yet (Harlow & Pike's inventory).
- `risk_register.<area>.assertion` — "Risk register > <Area> > Assertion": the assertions of the
  area's rows; `risk_register.<area>.rmm` — "… > RMM": the highest RMM among them.

The catalogue lists the firm's areas from its register rows (firm data, never a constant). The
reader is authorised on the engagement by the engagements provider (`scoping.read`); this one
reads only after that, on the same engagement.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final, get_args
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.modules.assurance.planning_contract import Assertion
from abacus.modules.engagements.api import authorise_scoping_reader
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology.api import scoping_rules as sr

_SEP: Final = " \u203a "  # the menus' separator (SHT-03)

PERFORMED_BY: Final = "group_scoping.components.performed_by"
_AREA_KEY: Final = re.compile(
    r"^risk_register\.([a-z][a-z0-9_]{0,63})\.(significant|assertion|rmm)$"
)
_SIGNIFICANT: Final = frozenset({"mandatory", "approved"})
_RMM_ORDER: Final = {"low": 0, "moderate": 1, "high": 2}
_ASSERTIONS: Final = get_args(Assertion)  # planning's codes

_AREAS: Final = text(
    "SELECT DISTINCT ON (area_key) area_key, area_label FROM risk_register_rows "
    "ORDER BY area_key, created_at"
)
_PERFORMERS: Final = text("SELECT DISTINCT performed_by FROM components WHERE engagement_id = :e")
_REGISTER: Final = text(
    "SELECT area_key, level, assertions, rmm, significance FROM risk_register_rows "
    "WHERE engagement_id = :e"
)


class AssuranceFacts:
    def knows(self, key: str) -> bool:
        return key == PERFORMED_BY or _AREA_KEY.fullmatch(key) is not None

    async def catalogue(self, ctx: AuthContext) -> Sequence[sr.Source]:
        out = [
            sr.Source(
                PERFORMED_BY,
                _SEP.join(("Group scoping", "Components", "Performed by")),
                "planning_form",
                ("group_team", "component_auditor"),
            ),
        ]
        async with tenant_session(ctx.tenant) as session:
            areas = list(await session.execute(_AREAS))
        for a in areas:
            key, label = str(a.area_key), str(a.area_label)
            out += [
                sr.Source(
                    f"risk_register.{key}.significant",
                    _SEP.join(("Scoping", "Audit areas", f"{label} · Significant")),
                    "risk",
                    ("yes", "no"),
                ),
                sr.Source(
                    f"risk_register.{key}.assertion",
                    _SEP.join(("Risk register", f"{label}", "Assertion")),
                    "assertion",
                    _ASSERTIONS,
                ),
                sr.Source(
                    f"risk_register.{key}.rmm",
                    _SEP.join(("Risk register", f"{label}", "RMM")),
                    "risk",
                    ("low", "moderate", "high"),
                ),
            ]
        return out

    async def answers(
        self, ctx: AuthContext, engagement_id: UUID
    ) -> Mapping[str, str | frozenset[str] | None]:
        await authorise_scoping_reader(ctx, engagement_id)
        async with tenant_session(ctx.tenant) as session:
            performers = frozenset(
                str(r.performed_by)
                for r in await session.execute(_PERFORMERS, {"e": engagement_id})
            )
            register = list(await session.execute(_REGISTER, {"e": engagement_id}))
        found: dict[str, str | frozenset[str] | None] = {PERFORMED_BY: performers or None}
        by_area: dict[str, list[tuple[str, tuple[str, ...], str]]] = {}
        for r in register:
            by_area.setdefault(str(r.area_key), []).append(
                (str(r.significance), tuple(r.assertions or ()), str(r.rmm))
            )
        for area, rows in by_area.items():
            significant = any(sig in _SIGNIFICANT for sig, _, _ in rows)
            assertions = frozenset(a for _, found_in, _ in rows for a in found_in)
            rmm = max((v for _, _, v in rows), key=lambda v: _RMM_ORDER.get(v, -1))
            found[f"risk_register.{area}.significant"] = "yes" if significant else "no"
            found[f"risk_register.{area}.assertion"] = assertions or None
            found[f"risk_register.{area}.rmm"] = rmm
        return found


def register() -> None:
    sr.register_scoping_source("assurance", AssuranceFacts())


__all__ = ["PERFORMED_BY", "AssuranceFacts", "register"]
