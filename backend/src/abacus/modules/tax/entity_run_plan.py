"""The entity return's workbook run plan, `tax.entity_workbook` (T-05-T31; T-05 F2, §4.5; TXP-00;
ADR-050, ADR-005; DEC-4616). Code plans, no model: the run is P-10's engagement run with this
provider's ten steps instead of the methodology's.

Ten step keys in six groups, a DAG (a step depends only on steps of earlier groups):

    1 import       import_trial_balance
    2 map          map_lines                                      ← import
    3 compute      depreciation_register · bonus_eligibility · contributions_distributions ← map
    4 capital      interim_closing_706d · capital_m2              ← compute (capital_m2 ← 706(d))
    5 apportion    apportionment_ptet                             ← map
    6 k1s          federal_k1s · state_k1s_k3s                    ← capital, apportion

- **Scopes.** `all` runs the ten. `group` names groups and `task` names steps: each runs with its
  dependants (downstream), never its dependencies, whose last results stand. So re-running the
  capital group runs `interim_closing_706d`, `capital_m2`, `federal_k1s` and `state_k1s_k3s`, and
  nothing else (the row's acceptance).
- **Human cells are kept.** Every step carries `keep_human: true`; its handler writes a cell only
  where `engine_may_write` allows (never over a person's value), T-05-T32.
- **Consent.** A step that sends tax return information to a model (`map_lines`' mapper
  suggestions, `interim_closing_706d`'s agreement reading) becomes a question step
  `consent_7216` when the partnership lacks either §7216 consent for the year, so its branch waits
  on inputs (`waiting_on_inputs`) and no model is called; the code-only steps still run.
- At most 3 steps run at once (CLS-02 "3 at once"; the run's `max_parallel_steps`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel import clock
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid
from abacus.modules.agents.api import PlanRequest, PlanStep, register_plan_provider
from abacus.modules.engagements.api import work_item_tri_subject
from abacus.modules.organisations.api import tri_consent_verdict

PROVIDER: Final = "tax.entity_workbook"
RUN_STEP: Final = "run_step."


@dataclass(frozen=True)
class EntityStep:
    key: str
    group: str
    label: str
    depends_on: tuple[str, ...] = ()
    model: bool = False  # sends TRI to a model: waits on consent without it


STEPS: Final[tuple[EntityStep, ...]] = (
    EntityStep("import_trial_balance", "import", "Import the trial balance"),
    EntityStep("map_lines", "map", "Map accounts to form lines", ("import_trial_balance",), True),
    EntityStep("depreciation_register", "compute", "Depreciation register", ("map_lines",)),
    EntityStep("bonus_eligibility", "compute", "Bonus depreciation eligibility", ("map_lines",)),
    EntityStep(
        "contributions_distributions", "compute", "Contributions and distributions", ("map_lines",)
    ),
    EntityStep(
        "interim_closing_706d",
        "capital",
        "§706(d) interim closing",
        ("contributions_distributions",),
        True,
    ),
    EntityStep(
        "capital_m2",
        "capital",
        "Capital accounts and M-2",
        ("contributions_distributions", "depreciation_register", "interim_closing_706d"),
    ),
    EntityStep(
        "apportionment_ptet", "apportionment", "State apportionment and PTET", ("map_lines",)
    ),
    EntityStep("federal_k1s", "k1s", "Federal K-1s", ("capital_m2", "apportionment_ptet")),
    EntityStep(
        "state_k1s_k3s", "k1s", "State K-1s and K-3s", ("capital_m2", "apportionment_ptet")
    ),
)
GROUPS: Final[tuple[str, ...]] = ("import", "map", "compute", "capital", "apportionment", "k1s")
LEVEL: Final = {group: n for n, group in enumerate(GROUPS, start=1)}
_BY_KEY: Final = {s.key: s for s in STEPS}


class RunKeysInvalid(DomainInvalid):
    """A group or step key the plan does not have, or a scope without keys."""

    code = "run_keys_invalid"


def dependants(keys: Iterable[str]) -> set[str]:
    """`keys` and every step downstream of them."""
    chosen = set(keys)
    grew = True
    while grew:
        grew = False
        for step in STEPS:
            if step.key not in chosen and any(d in chosen for d in step.depends_on):
                chosen.add(step.key)
                grew = True
    return chosen


def selected(scope: str, keys: Sequence[str]) -> list[EntityStep]:
    """The steps a scope runs, in plan order."""
    if scope == "all":
        return list(STEPS)
    if not keys:
        raise RunKeysInvalid(facts={"scope": scope})
    if scope == "group":
        unknown = [k for k in keys if k not in LEVEL]
        if unknown:
            raise RunKeysInvalid(facts={"key": unknown[0]})
        roots = {s.key for s in STEPS if s.group in keys}
    elif scope == "task":
        unknown = [k for k in keys if k not in _BY_KEY]
        if unknown:
            raise RunKeysInvalid(facts={"key": unknown[0]})
        roots = set(keys)
    else:
        raise RunKeysInvalid(facts={"scope": scope})
    chosen = dependants(roots)
    return [s for s in STEPS if s.key in chosen]


def plan_steps(chosen: Sequence[EntityStep], *, consent: bool) -> list[PlanStep]:
    """The run's plan: dependencies outside the chosen set are dropped (their results stand)."""
    keys = {s.key for s in chosen}
    out: list[PlanStep] = []
    for step in chosen:
        depends = tuple(d for d in step.depends_on if d in keys)
        if step.model and not consent:
            out.append(
                PlanStep(
                    key=step.key,
                    label=step.label,
                    level=LEVEL[step.group],
                    kind="question",
                    arguments={
                        "question_key": "consent_7216",
                        "options": [{"key": "recorded", "title": "Consent is on file"}],
                        "group": step.group,
                    },
                    depends_on=depends,
                )
            )
            continue
        out.append(
            PlanStep(
                key=step.key,
                label=step.label,
                level=LEVEL[step.group],
                kind="compute",
                tool=f"{RUN_STEP}{step.key}",
                arguments={"group": step.group, "keep_human": True},
                depends_on=depends,
            )
        )
    return out


async def consent_in_force(tenant: TenantContext, work_item_id: UUID) -> bool:
    """Both §7216 consents of the partnership for the return's year (C19; fail closed)."""
    subject = await work_item_tri_subject(tenant, work_item_id)
    if subject is None or subject.entity_id is None:
        return False
    verdict = await tri_consent_verdict(
        tenant, [subject.entity_id], await clock.now(tenant), tax_year=subject.tax_year
    )
    return verdict.valid


async def entity_workbook_plan(
    tenant: TenantContext, engagement_id: UUID, request: PlanRequest
) -> list[PlanStep]:
    del engagement_id  # the work item names the return; the engagement was authorised already
    chosen = selected(request.scope, request.keys)
    consent = await consent_in_force(tenant, request.work_item_id)
    return plan_steps(chosen, consent=consent)


register_plan_provider(PROVIDER, entity_workbook_plan)

__all__ = [
    "GROUPS",
    "PROVIDER",
    "STEPS",
    "RunKeysInvalid",
    "dependants",
    "entity_workbook_plan",
    "plan_steps",
    "selected",
]
