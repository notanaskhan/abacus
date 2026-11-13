"""The entity return's workbook run plan, `tax.entity_workbook` (T-05-T31; T-05 F2, §4.5; TXP-00;
ADR-050, ADR-005; DEC-4616). Code plans, no model: the run is P-10's engagement run with this
provider's ten steps instead of the methodology's.

Ten step keys in six groups, a DAG. A step's plan level is its dependency depth (`DEPTH`), so
every dependency sits on a lower level, as P-10's `validate_plan` requires:

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

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
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


def _depths() -> dict[str, int]:
    """Each step's plan level: one more than its deepest dependency's (P-10's `validate_plan`
    refuses a dependency at the same or a later level, so `capital_m2` sits after
    `interim_closing_706d` though both are in the capital group). The group stays in the step's
    arguments for TXP-00's six headings."""
    depth: dict[str, int] = {}
    for step in STEPS:  # STEPS lists every dependency before its dependants
        depth[step.key] = 1 + max((depth[d] for d in step.depends_on), default=0)
    return depth


DEPTH: Final = _depths()


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


QUESTION_706D: Final = "convention_706d"
CONVENTIONS: Final = ("calendar_day", "semi_monthly", "monthly")
_TITLES: Final = {
    "calendar_day": "Calendar day",
    "semi_monthly": "Semi-monthly",
    "monthly": "Monthly",
}


@dataclass(frozen=True)
class ConventionQuestion:
    """T-05-T40 (DEC-4704): the §706(d) convention is not settled for the return, so the run asks
    it before `interim_closing_706d` (options and the recommendation computed by code)."""

    options: tuple[dict[str, str], ...]
    recommended: str
    reason: str


def convention_question(transfers: Sequence[date], proposed: str | None) -> ConventionQuestion:
    """The three conventions of Reg. §1.706-4(c), each with the day each transfer is treated as
    happening at the end of; the reader's proposed convention is recommended, else calendar day."""
    from abacus.modules.tax.compute.entity.allocation import boundary

    options: list[dict[str, str]] = []
    for key in CONVENTIONS:
        ends = [boundary(t, key) for t in transfers]
        days = ", ".join(f"{d:%b} {d.day}, {d.year}" for d in ends)
        detail = f" (books close {days})" if days else ""
        options.append({"key": key, "title": f"{_TITLES[key]}{detail}"})
    if proposed in CONVENTIONS:
        return ConventionQuestion(
            tuple(options),
            str(proposed),
            "The agreement reader's proposal names this convention; a person confirms it.",
        )
    return ConventionQuestion(
        tuple(options),
        "calendar_day",
        "The agreement names no convention; the calendar-day convention closes the books on the "
        "transfer date (Reg. §1.706-4(c)).",
    )


def _levels(chosen: Sequence[EntityStep], extra: Mapping[str, tuple[str, ...]]) -> dict[str, int]:
    """Plan levels as dependency depth, with `extra` edges (a question before its step)."""
    keys = {s.key for s in chosen} | set(extra)
    depth: dict[str, int] = {}
    for key, deps in extra.items():
        if key not in _BY_KEY:
            depth[key] = 1 + max((depth.get(d, DEPTH.get(d, 0)) for d in deps), default=0)
    for step in chosen:
        deps = tuple(d for d in step.depends_on if d in keys) + extra.get(step.key, ())
        depth[step.key] = 1 + max((depth[d] for d in deps if d in depth), default=0)
    return depth


def plan_steps(
    chosen: Sequence[EntityStep],
    *,
    consent: bool,
    return_id: UUID | None = None,
    convention: ConventionQuestion | None = None,
) -> list[PlanStep]:
    """The run's plan: dependencies outside the chosen set are dropped (their results stand).
    With `convention` (the §706(d) convention unsettled) and `interim_closing_706d` chosen, a
    question step `convention_706d` comes first and the step waits on it (T-05-T40)."""
    keys = {s.key for s in chosen}
    extra: dict[str, tuple[str, ...]] = {}
    out: list[PlanStep] = []
    ask = convention is not None and "interim_closing_706d" in keys and consent
    if ask:
        interim = _BY_KEY["interim_closing_706d"]
        extra[QUESTION_706D] = tuple(d for d in interim.depends_on if d in keys)
        extra["interim_closing_706d"] = (QUESTION_706D,)
    level = _levels(chosen, extra)
    if ask and convention is not None:
        out.append(
            PlanStep(
                key=QUESTION_706D,
                label="Which §706(d) convention applies to the interest transfer?",
                level=level[QUESTION_706D],
                kind="question",
                arguments={
                    "question_key": QUESTION_706D,
                    "options": [dict(o) for o in convention.options],
                    "recommended": convention.recommended,
                    "reason": convention.reason,
                    "group": "capital",
                },
                depends_on=extra[QUESTION_706D],
            )
        )
    for step in chosen:
        depends = tuple(d for d in step.depends_on if d in keys) + extra.get(step.key, ())
        if step.model and not consent:
            out.append(
                PlanStep(
                    key=step.key,
                    label=step.label,
                    level=level[step.key],
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
                level=level[step.key],
                kind="compute",
                tool=f"{RUN_STEP}{step.key}",
                arguments={
                    "group": step.group,
                    "keep_human": True,
                    **({} if return_id is None else {"return_id": str(return_id)}),
                },
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


async def settled_convention(tenant: TenantContext, return_id: UUID) -> tuple[bool, str | None]:
    """Whether a person settled the §706(d) convention (the newest structure version is approved
    or a person's own draft), and the convention the newest version names (T-05-T40)."""
    from abacus.modules.tax.allocation_structure import versions

    found = await versions(tenant, return_id)
    if not found:
        return False, None
    newest = found[0]
    settled = newest.status == "approved" or newest.proposed_by_kind == "human"
    return settled, newest.convention


async def transfer_dates(tenant: TenantContext, return_id: UUID) -> list[date]:
    from abacus.modules.tax.allocation_structure import ownership_of

    return (await ownership_of(tenant, return_id))[1]


async def entity_workbook_plan(
    tenant: TenantContext, engagement_id: UUID, request: PlanRequest
) -> list[PlanStep]:
    del engagement_id  # the work item names the return; the engagement was authorised already
    chosen = selected(request.scope, request.keys)
    consent = await consent_in_force(tenant, request.work_item_id)
    question: ConventionQuestion | None = None
    if any(s.key == "interim_closing_706d" for s in chosen):
        settled, proposed = await settled_convention(tenant, request.work_item_id)
        if not settled:
            question = convention_question(
                await transfer_dates(tenant, request.work_item_id), proposed
            )
    return plan_steps(chosen, consent=consent, return_id=request.work_item_id, convention=question)


register_plan_provider(PROVIDER, entity_workbook_plan)

__all__ = [
    "DEPTH",
    "GROUPS",
    "PROVIDER",
    "QUESTION_706D",
    "STEPS",
    "ConventionQuestion",
    "RunKeysInvalid",
    "convention_question",
    "dependants",
    "entity_workbook_plan",
    "plan_steps",
    "selected",
    "settled_convention",
]
