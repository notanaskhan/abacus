"""`engagements.season_planner` v1 (T-08-T17; TASK-8840; T-08 §6; SPEC-710; ENG-07 d, e; ADR-005,
ADR-019, ADR-050; DEC-5842). RED: an agent path.

After code builds the season manifest (T-08-T09), the planner phrases the asks code found and
suggests an eligible person for each exception row that needs one. Code has the last word:

- **Inputs** are manifest metadata only (`SeasonPlannerInput`): row ids, exception codes, office,
  segment, the role to fill, and the staff code checked as eligible (active, not walled from the
  client: `season_service.reassign`'s rule). No count, figure, return, TIN or tax return
  information: the capability declares no `tri`, and a context carrying a TRI subject is refused
  by the gateway (C19 condition 6) before any model call.
- **Asks** come from code's ambiguity rules (`ASK_RULES`): two prior binders, a bounced contact,
  a missing confirmation, a changed continuance fact, no signer. The planner recommends one of
  the ask's own options and a phrase from a closed set (`PHRASES`); anything else is dropped.
- **Reassignments** are kept only to a person listed as eligible for that row and role; they are
  stored as asks (`reassign_<role>`) whose options are the eligible people, the planner's pick as
  the recommendation. A person answers every ask (`answer`); a manager approves the cohort.
- **Writes.** The planner has no tools and writes nothing; code writes the kept asks as
  `season_asks` (`source: agent`) once per manifest. Synthetic tenants only until the capability
  is cleared (`client_data: none`).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext, AuthContext

CAPABILITY: Final = "engagements.season_planner"
Int = classified("internal")
Conf = classified("confidential")
Role = Literal["preparer", "reviewer", "signer"]
PHRASES: Final = frozenset(
    {
        "two_binders",
        "contact_bounced",
        "confirmation_missing",
        "continuance_changed",
        "signer_missing",
    }
)
# Code's ambiguity rules: exception code -> (ask code, options, phrase key).
ASK_RULES: Final[dict[str, tuple[str, tuple[str, ...], str]]] = {
    "binder_ambiguous": ("binder_choice", ("use_newer", "use_both", "ask_client"), "two_binders"),
    "contact_bounced": ("contact_update", ("ask_client", "use_portal_only"), "contact_bounced"),
    "confirmation_missing": (
        "confirmation",
        ("request_again", "exclude_row"),
        "confirmation_missing",
    ),
    "continuance_changed": (
        "continuance",
        ("rerun_continuance", "exclude_row"),
        "continuance_changed",
    ),
    "signer_missing": ("signer", ("name_signer", "exclude_row"), "signer_missing"),
}
# Exception codes whose row needs a person, by role.
NEEDS_PERSON: Final[dict[str, Role]] = {
    "assignee_walled_or_departed": "preparer",
    "assignee_seasonal_not_started": "preparer",
    "signer_missing": "signer",
}


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class EligibleRef(BaseModel):
    model_config = _cfg()

    user_ref: Annotated[str, Field(pattern=r"^u[0-9]{1,4}$"), Int]  # opaque: u1, u2 ...
    name: Annotated[str, Field(min_length=1, max_length=120), Conf]


class PlannerRow(BaseModel):
    model_config = _cfg()

    row_id: Annotated[str, Field(pattern=r"^r[0-9]{1,4}$"), Int]
    codes: Annotated[list[str], Field(max_length=10), Int]
    office: Annotated[str, Field(max_length=80), Int]
    segment: Annotated[str, Field(max_length=80), Int]
    role: Annotated[Role | None, Int] = None
    eligible: Annotated[list[EligibleRef], Field(max_length=50), Conf] = []


class PlannerAsk(BaseModel):
    model_config = _cfg()

    ask_code: Annotated[str, Field(max_length=60), Int]
    row_ids: Annotated[list[str], Field(max_length=200), Int]
    options: Annotated[list[str], Field(max_length=10), Int]


class SeasonPlannerInput(BaseModel):
    """Manifest metadata only: no count, figure or TRI field exists here."""

    model_config = _cfg()

    rows: Annotated[list[PlannerRow], Field(min_length=1, max_length=500), Conf]
    asks: Annotated[list[PlannerAsk], Field(max_length=100), Int]


class AskAnswer(BaseModel):
    model_config = _cfg()

    ask_code: Annotated[str, Field(max_length=60), Int]
    recommended_option: Annotated[str | None, Field(max_length=40), Int] = None
    phrase_key: Annotated[str, Field(max_length=40), Int]


class Reassignment(BaseModel):
    model_config = _cfg()

    row_id: Annotated[str, Field(max_length=10), Int]
    role: Annotated[Role, Int]
    user_ref: Annotated[str, Field(max_length=10), Int]


class SeasonPlannerOutput(BaseModel):
    model_config = _cfg()

    asks: Annotated[list[AskAnswer], Field(max_length=100), Int] = []
    reassignments: Annotated[list[Reassignment], Field(max_length=500), Int] = []


@dataclass(frozen=True)
class FlaggedRow:
    row_id: UUID
    client_id: UUID
    codes: tuple[str, ...]
    office: str
    segment: str


@dataclass(frozen=True)
class Given:
    model: SeasonPlannerInput
    rows: dict[str, UUID]  # r1 -> row id
    people: dict[str, UUID]  # u1 -> user id
    ask_rows: dict[str, tuple[UUID, ...]]  # ask code -> row ids


@dataclass(frozen=True)
class KeptAsk:
    question_code: str
    row_ids: tuple[UUID, ...]
    options: tuple[str, ...]
    recommended: str | None
    phrase_key: str


def code_asks(rows: Sequence[FlaggedRow]) -> dict[str, tuple[UUID, ...]]:
    """Code's asks: one per ambiguity rule, over every row it flags."""
    out: dict[str, list[UUID]] = {}
    for r in rows:
        for c in r.codes:
            rule = ASK_RULES.get(c)
            if rule is not None:
                out.setdefault(rule[0], []).append(r.row_id)
    return {k: tuple(v) for k, v in out.items()}


def model_input(
    rows: Sequence[FlaggedRow],
    eligible: dict[UUID, list[tuple[UUID, str]]],
) -> Given:
    """Opaque refs for rows and people; the eligible lists are code's (module docstring)."""
    row_refs = {f"r{i}": r.row_id for i, r in enumerate(rows, start=1)}
    by_id = {v: k for k, v in row_refs.items()}
    people: dict[str, UUID] = {}
    ref_of: dict[UUID, str] = {}
    planner_rows: list[PlannerRow] = []
    for r in rows:
        role = next((NEEDS_PERSON[c] for c in r.codes if c in NEEDS_PERSON), None)
        refs: list[EligibleRef] = []
        for user_id, name in eligible.get(r.row_id, []) if role is not None else []:
            ref = ref_of.setdefault(user_id, f"u{len(ref_of) + 1}")
            people[ref] = user_id
            refs.append(EligibleRef(user_ref=ref, name=name))
        planner_rows.append(
            PlannerRow(
                row_id=by_id[r.row_id],
                codes=list(r.codes),
                office=r.office,
                segment=r.segment,
                role=role,
                eligible=refs,
            )
        )
    asks = code_asks(rows)
    rule_of = {v[0]: v for v in ASK_RULES.values()}
    return Given(
        SeasonPlannerInput(
            rows=planner_rows,
            asks=[
                PlannerAsk(ask_code=k, row_ids=[by_id[x] for x in v], options=list(rule_of[k][1]))
                for k, v in sorted(asks.items())
            ],
        ),
        row_refs,
        people,
        asks,
    )


def settle(answer: SeasonPlannerOutput | None, given: Given) -> list[KeptAsk]:
    """Code's last word: asks only for code's ambiguities with their own options and a closed
    phrase; reassignments only to a person listed eligible for that row and role."""
    rule_of = {v[0]: v for v in ASK_RULES.values()}
    recommended = {a.ask_code: a for a in (answer.asks if answer is not None else [])}
    kept: list[KeptAsk] = []
    for code, rows in sorted(given.ask_rows.items()):
        _c, options, phrase = rule_of[code]
        a = recommended.get(code)
        pick = a.recommended_option if a is not None and a.recommended_option in options else None
        key = a.phrase_key if a is not None and a.phrase_key in PHRASES else phrase
        kept.append(KeptAsk(code, rows, options, pick, key))
    listed = {
        (r.row_id, r.role): {e.user_ref for e in r.eligible}
        for r in given.model.rows
        if r.role is not None
    }
    seen: set[tuple[str, str]] = set()
    for s in answer.reassignments if answer is not None else []:
        if (s.row_id, s.role) in seen or s.user_ref not in listed.get((s.row_id, s.role), set()):
            continue  # an unlisted (walled, departed, ineligible) person is never suggested
        seen.add((s.row_id, s.role))
        options = tuple(str(given.people[u]) for u in sorted(listed[(s.row_id, s.role)]))
        kept.append(
            KeptAsk(
                f"reassign_{s.role}",
                (given.rows[s.row_id],),
                options,
                str(given.people[s.user_ref]),
                "reassign",
            )
        )
    return kept


async def _judge(agent: AgentContext, given: SeasonPlannerInput) -> SeasonPlannerOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    context = ContextBuilder().task(given.model_dump(), untrusted=("rows",)).build()
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=SeasonPlannerOutput,
                budget_usd=spec.limits.max_cost_usd,
                attribution=Attribution(
                    agent.tenant, agent.engagement_id, CAPABILITY, agent.agent_run_id
                ),
                context=context,
                work_class=spec.work_class,
                essential=spec.essential,
                routes=spec.routes,
                cheaper_tiers=spec.cheaper_tiers,
                max_output_tokens=spec.limits.max_output_tokens,
                timeout_seconds=spec.limits.max_seconds,
            )
        )
    except Exception:  # a refused call (boundary, budget, schema): code's asks stand alone
        return None
    return cast(SeasonPlannerOutput, result.output)


async def _eligible(
    tenant: TenantContext, rows: Sequence[FlaggedRow], pool: Sequence[tuple[UUID, str]]
) -> dict[UUID, list[tuple[UUID, str]]]:
    from abacus.modules.identity.api import is_active_member, walled_from

    out: dict[UUID, list[tuple[UUID, str]]] = {}
    walls = {u: await walled_from(tenant, u) for u, _n in pool}
    active = {u: await is_active_member(tenant.tenant_id, u) for u, _n in pool}
    for r in rows:
        out[r.row_id] = [(u, n) for u, n in pool if active[u] and r.client_id not in walls[u]]
    return out


async def plan(person: AuthContext, manifest_id: UUID) -> int:
    """After a build: the planner's kept asks written once (code's asks alone when the call is
    refused or the firm is not synthetic). Answers the asks written."""
    from abacus.ai_gateway import is_synthetic
    from abacus.modules.agents.api import end_capability_run, start_capability_run
    from abacus.modules.identity.api import display_names

    async with tenant_session(person.tenant) as session:
        if await session.scalar(
            text("SELECT count(*) FROM season_asks WHERE manifest_id = :m"), {"m": manifest_id}
        ):
            return 0  # once per manifest
        found = (
            await session.execute(
                text(
                    "SELECT r.id, r.client_id, r.exception_codes, c.office_id, c.segment, "
                    "r.preparer_user_id, r.reviewer_user_id, r.signer_user_id FROM "
                    "season_manifest_rows r JOIN season_cohorts c ON c.id = r.cohort_id "
                    "WHERE c.manifest_id = :m AND r.excluded_at IS NULL ORDER BY r.id"
                ),
                {"m": manifest_id},
            )
        ).all()
    rows = [
        FlaggedRow(
            UUID(str(r.id)),
            UUID(str(r.client_id)),
            tuple(r.exception_codes or ()),
            str(r.office_id),
            str(r.segment),
        )
        for r in found
        if r.exception_codes
    ]
    if not rows:
        return 0
    staff = sorted(
        {u for r in found for u in (r.preparer_user_id, r.reviewer_user_id, r.signer_user_id) if u}
    )
    names = await display_names(list(staff))
    pool = [(UUID(str(u)), names.get(UUID(str(u)), "")) for u in staff]
    given = model_input(rows, await _eligible(person.tenant, rows, pool))
    answer = None
    if await is_synthetic(person.tenant):
        agent = await start_capability_run(person, CAPABILITY, None)
        if agent is not None:
            answer = await _judge(agent, given.model)
            await end_capability_run(
                agent,
                status="succeeded" if answer is not None else "escalated",
                output={"asks": len(given.ask_rows)},
            )
    kept = settle(answer, given)
    source = "agent" if answer is not None else "code"
    async with uow(person.tenant) as tx:
        for k in kept:
            await tx.session.execute(
                text(
                    "INSERT INTO season_asks (tenant_id, manifest_id, row_ids, question_code, "
                    "options, recommended_option, source) VALUES (:t, :m, CAST(:r AS uuid[]), :q, "
                    "CAST(:o AS jsonb), :rec, :s)"
                ),
                {
                    "t": person.tenant_id,
                    "m": manifest_id,
                    "r": [str(x) for x in k.row_ids],
                    "q": k.question_code,
                    "o": json.dumps([{"key": o, "phrase": k.phrase_key} for o in k.options]),
                    "rec": k.recommended,
                    "s": source,
                },
            )
        tx.record(
            "season_asks.opened",
            target=Target("season_manifest", manifest_id),
            after=Ref(asks=len(kept)),
        )
    return len(kept)


async def answer(person: AuthContext, ask_id: UUID, option: str) -> None:
    """A person's answer (the planner never answers, INV-1), once."""
    from abacus.kernel.errors import DomainConflict, NotFound
    from abacus.modules.identity.api import Forbidden

    if person.client or person.tenant.actor_kind != "human" or person.is_support:
        raise Forbidden("season_setup.prepare", "role")
    async with tenant_session(person.tenant) as session:
        row = (
            await session.execute(
                text("SELECT options, answered_option FROM season_asks WHERE id = :a"),
                {"a": ask_id},
            )
        ).first()
    if row is None:
        raise NotFound("season_ask")
    keys = {str(o.get("key")) for o in cast(list[dict[str, object]], row.options or [])}
    if option not in keys or row.answered_option is not None:
        raise DomainConflict(facts={"ask_id": str(ask_id)})
    async with uow(person.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE season_asks SET answered_option = :o, answered_by = :u, "
                "answered_at = clock_timestamp() WHERE id = :a AND answered_option IS NULL"
            ),
            {"o": option, "u": person.user_id, "a": ask_id},
        )
        tx.record(
            "season_ask.answered", target=Target("season_ask", ask_id), after=Ref(option=option)
        )


__all__ = [
    "ASK_RULES",
    "CAPABILITY",
    "PHRASES",
    "SeasonPlannerInput",
    "SeasonPlannerOutput",
    "answer",
    "code_asks",
    "model_input",
    "plan",
    "settle",
]
