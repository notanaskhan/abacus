"""The tax tools on C17 (T-04-T19; SPEC-649; ADR-233, ADR-049, ADR-050; §7216; DEC-3211).

Read and compute tools carry tax return information (`data_class="tri"`): the runtime refuses a
call before any query when the taxpayer (the `client_entity_id` with its `tax_year`) lacks either
§7216 consent in force for that year (`consent_required`), scrubs every unmasked TIN from the
result, and pins the run's client scope. Propose tools create a proposal through
`agents.api.create_proposal` and answer its identifiers only: never a value (the agent proposes; a
person approves through SHL-10, and T-04-T15's appliers write). C17's names hold no digits, so the
K-1 tools read "pass-through" (`tax.read_pass_through_activity`, …).

| Tool | Kind | Reads |
|---|---|---|
| `tax.read_return` | read | the return's form, year, status and worksheet count |
| `tax.list_documents` | read | the return's documents (current versions) |
| `tax.read_worksheet` | read | one worksheet's fields by its key |
| `tax.read_pass_through_activity` | read | the K-1 activities and their states |
| `tax.read_prior_year` | read | the K-1 treatments' prior-year values |
| `tax.compare_years` | compute | current vs prior per treatment, changed or not |
| `tax.compute_pass_through_facts` | compute | §199A QBI and outside basis by code |
| `tax.compute_residency_facts` | compute | the NYS/NYC residency rules' recommendation |
| `tax.compute_state_allocation` | compute | whole-dollar sourcing by largest remainder |
| `tax.propose_field_changes` | propose | `return_field_changes` on worksheet fields |
| `tax.propose_pass_through_treatments` | propose | `pass_through_treatments` |
| `tax.propose_residency` | propose | `residency` |
| `tax.propose_account_mappings` | propose | `tax_account_mapping` on an entity return (T-05-T23) |
| `tax.propose_allocation_structure` | propose | `allocation_structure` on a return (T-05-T36) |
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Final, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import ProposedRow, ToolTargets, agent_tool, create_proposal
from abacus.modules.engagements.api import entity_of
from abacus.modules.evidence.api import engagement_documents
from abacus.modules.identity.api import AgentContext
from abacus.modules.organisations.api import TriSubject
from abacus.modules.tax.compute.individual.k1 import outside_basis, qbi_199a, state_sourcing
from abacus.modules.tax.compute.individual.residency import ResidencyFacts, residency_rules

Int = classified("internal")
Tri = classified("restricted", tri=True)
MAX: Final = 200


def _cfg() -> ConfigDict:
    return ConfigDict(extra="forbid", frozen=True)


class ReturnIn(BaseModel):
    """A taxpayer's return: the client entity and the tax year (the §7216 subject)."""

    model_config = _cfg()

    client_entity_id: Annotated[UUID, Int]
    tax_year: Annotated[int, Field(ge=2000, le=2100), Int]


async def _return_of(agent: AgentContext, args: ReturnIn) -> tuple[UUID, UUID]:
    """(engagement, return work item) of the taxpayer and year, on the run's engagement only."""
    if agent.engagement_id is None:
        raise NotFound("tax_return")
    if await entity_of(agent.tenant, agent.engagement_id) != args.client_entity_id:
        raise NotFound("tax_return")  # another taxpayer than the run's engagement
    async with tenant_session(agent.tenant) as session:
        found = await session.scalar(
            text(
                "SELECT work_item_id FROM tax_returns WHERE engagement_id = :e "
                "AND tax_year = :y ORDER BY work_item_id LIMIT 1"
            ),
            {"e": agent.engagement_id, "y": args.tax_year},
        )
    if found is None:
        raise NotFound("tax_return")
    return agent.engagement_id, cast(UUID, found)


# --- reads ---------------------------------------------------------------------------------------


class ReturnOut(BaseModel):
    id: Annotated[UUID, Int]
    form: Annotated[str, Int]
    tax_year: Annotated[int, Int]
    status: Annotated[str, Int]
    worksheets: Annotated[int, Field(ge=0), Int]


@agent_tool(
    name="tax.read_return", kind="read", action="tax_return.read", data_class="tri",
    input_model=ReturnIn, output_model=ReturnOut, records_read="tax_return",
)  # fmt: skip
async def read_return(agent: AgentContext, args: ReturnIn) -> ReturnOut:
    _, work_item = await _return_of(agent, args)
    async with tenant_session(agent.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT r.form, r.tax_year, r.status, (SELECT count(*) FROM return_worksheets "
                    "w WHERE w.tax_return_id = r.work_item_id AND w.active) AS sheets "
                    "FROM tax_returns r WHERE r.work_item_id = :r"
                ),
                {"r": work_item},
            )
        ).one()
    return ReturnOut(
        id=work_item, form=str(row.form), tax_year=row.tax_year, status=str(row.status),
        worksheets=int(row.sheets),
    )  # fmt: skip


class DocRow(BaseModel):
    id: Annotated[UUID, Int]  # the evidence version
    title: Annotated[str, Tri]
    category: Annotated[str, Int]
    version: Annotated[int, Int]


class DocsOut(BaseModel):
    documents: Annotated[list[DocRow], Field(max_length=MAX), Int]
    total: Annotated[int, Field(ge=0), Int]


@agent_tool(
    name="tax.list_documents", kind="read", action="tax_return.read", data_class="tri",
    input_model=ReturnIn, output_model=DocsOut, untrusted=("documents",),
    records_read="evidence_version",
)  # fmt: skip
async def list_documents(agent: AgentContext, args: ReturnIn) -> DocsOut:
    engagement, _ = await _return_of(agent, args)
    rows = [
        DocRow(id=v, title=t, category=f, version=n)
        for v, _i, t, f, n, latest in await engagement_documents(agent.tenant, engagement)
        if latest
    ]
    return DocsOut(documents=rows[:MAX], total=len(rows))


class WorksheetIn(ReturnIn):
    worksheet_key: Annotated[str, Field(min_length=1, max_length=80), Int]


class FieldRow(BaseModel):
    id: Annotated[UUID, Int]
    field_key: Annotated[str, Int]
    label: Annotated[str, Int]
    line_ref: Annotated[str | None, Int] = None
    value: Annotated[Decimal | None, Tri] = None
    derivation: Annotated[str, Int]


class WorksheetOut(BaseModel):
    worksheet_id: Annotated[UUID, Int]
    fields: Annotated[list[FieldRow], Field(max_length=MAX), Int]
    total: Annotated[int, Field(ge=0), Int]


def _money(value: object) -> Decimal | None:
    if isinstance(value, dict):
        raw = cast(dict[str, object], value).get("v")
        try:
            return None if raw is None else Decimal(str(raw))
        except ArithmeticError:
            return None
    return None


@agent_tool(
    name="tax.read_worksheet", kind="read", action="return_worksheet.read", data_class="tri",
    input_model=WorksheetIn, output_model=WorksheetOut, records_read="return_field",
)  # fmt: skip
async def read_worksheet(agent: AgentContext, args: WorksheetIn) -> WorksheetOut:
    _, work_item = await _return_of(agent, args)
    async with tenant_session(agent.tenant) as session:
        sheet = await session.scalar(
            text("SELECT id FROM return_worksheets WHERE tax_return_id = :r AND key = :k"),
            {"r": work_item, "k": args.worksheet_key},
        )
        if sheet is None:
            raise NotFound("return_worksheet")
        rows = (
            await session.execute(
                text(
                    "SELECT id, field_key, label, line_ref, current_value, derivation "
                    "FROM return_fields WHERE worksheet_id = :w ORDER BY sort_order, field_key"
                ),
                {"w": sheet},
            )
        ).all()
    found = [
        FieldRow(
            id=r.id, field_key=r.field_key, label=r.label, line_ref=r.line_ref,
            value=_money(r.current_value), derivation=r.derivation,
        )
        for r in rows
    ]  # fmt: skip
    return WorksheetOut(worksheet_id=cast(UUID, sheet), fields=found[:MAX], total=len(found))


class ActivityRow(BaseModel):
    id: Annotated[UUID, Int]
    issuer_name: Annotated[str, Tri]
    issuer_form: Annotated[str, Int]
    state: Annotated[str, Int]
    released_on: Annotated[date | None, Int] = None


class ActivitiesOut(BaseModel):
    activities: Annotated[list[ActivityRow], Field(max_length=MAX), Int]
    total: Annotated[int, Field(ge=0), Int]
    drafts: Annotated[int, Field(ge=0), Int]


@agent_tool(
    name="tax.read_pass_through_activity", kind="read", action="k1_treatment.read",
    data_class="tri", input_model=ReturnIn, output_model=ActivitiesOut,
    untrusted=("activities",), records_read="k1_activity",
)  # fmt: skip
async def read_pass_through_activity(agent: AgentContext, args: ReturnIn) -> ActivitiesOut:
    _, work_item = await _return_of(agent, args)
    async with tenant_session(agent.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, issuer_name, issuer_form, k1_state, released_at "
                    "FROM k1_activities WHERE tax_return_id = :r ORDER BY issuer_name, id"
                ),
                {"r": work_item},
            )
        ).all()
    found = [
        ActivityRow(
            id=r.id, issuer_name=r.issuer_name, issuer_form=r.issuer_form, state=r.k1_state,
            released_on=r.released_at.date() if r.released_at else None,
        )
        for r in rows
    ]  # fmt: skip
    drafts = sum(1 for a in found if a.state == "draft_pre_release")
    return ActivitiesOut(activities=found[:MAX], total=len(found), drafts=drafts)


class TreatmentRow(BaseModel):
    id: Annotated[UUID, Int]
    kind: Annotated[str, Int]
    status: Annotated[str, Int]
    current: Annotated[Decimal | None, Tri] = None
    prior_year: Annotated[Decimal | None, Tri] = None
    changed: Annotated[bool, Int] = False
    # T-04-T38 (additive): code's resolved words ("Passive", "IL 7,011 · CO 4,268 · NY 4,746").
    resolved_text: Annotated[str | None, Tri] = None
    prior_text: Annotated[str | None, Tri] = None


def _text(value: object) -> str | None:
    if isinstance(value, dict):
        raw = cast(dict[str, object], value).get("v")
        return None if raw is None else str(raw)[:200]
    return None


class TreatmentsOut(BaseModel):
    treatments: Annotated[list[TreatmentRow], Field(max_length=MAX), Int]
    total: Annotated[int, Field(ge=0), Int]
    changed: Annotated[int, Field(ge=0), Int]


async def _treatments(agent: AgentContext, args: ReturnIn) -> list[TreatmentRow]:
    _, work_item = await _return_of(agent, args)
    async with tenant_session(agent.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, kind, status, resolved, prior_year, changed_vs_prior "
                    "FROM k1_treatments WHERE tax_return_id = :r ORDER BY kind, id"
                ),
                {"r": work_item},
            )
        ).all()
    out: list[TreatmentRow] = []
    for r in rows:
        current, prior = _money(r.resolved), _money(r.prior_year)
        out.append(
            TreatmentRow(
                id=r.id, kind=r.kind, status=r.status, current=current, prior_year=prior,
                changed=bool(r.changed_vs_prior) or current != prior,
                resolved_text=_text(r.resolved), prior_text=_text(r.prior_year),
            )
        )  # fmt: skip
    return out


@agent_tool(
    name="tax.read_prior_year", kind="read", action="k1_treatment.read", data_class="tri",
    input_model=ReturnIn, output_model=TreatmentsOut, records_read="k1_treatment",
)  # fmt: skip
async def read_prior_year(agent: AgentContext, args: ReturnIn) -> TreatmentsOut:
    rows = await _treatments(agent, args)
    return TreatmentsOut(
        treatments=rows[:MAX], total=len(rows), changed=sum(1 for r in rows if r.changed)
    )


# --- computes ------------------------------------------------------------------------------------


@agent_tool(
    name="tax.compare_years", kind="compute", action="k1_treatment.read", data_class="tri",
    input_model=ReturnIn, output_model=TreatmentsOut, records_read="k1_treatment",
)  # fmt: skip
async def compare_years(agent: AgentContext, args: ReturnIn) -> TreatmentsOut:
    rows = [r for r in await _treatments(agent, args) if r.changed]
    return TreatmentsOut(treatments=rows[:MAX], total=len(rows), changed=len(rows))


class PassThroughIn(ReturnIn):
    qbi: Annotated[Decimal, Tri]
    w2_wages: Annotated[Decimal, Tri]
    ubia: Annotated[Decimal, Tri]
    tax_capital: Annotated[Decimal, Tri]
    liability_share_752: Annotated[Decimal, Tri]


class PassThroughOut(BaseModel):
    qbi_deduction: Annotated[Decimal, Tri]
    outside_basis: Annotated[Decimal, Tri]
    inputs_hash: Annotated[str, Int]


@agent_tool(
    name="tax.compute_pass_through_facts", kind="compute", action="k1_treatment.read",
    data_class="tri", input_model=PassThroughIn, output_model=PassThroughOut,
)  # fmt: skip
async def compute_pass_through_facts(agent: AgentContext, args: PassThroughIn) -> PassThroughOut:
    await _return_of(agent, args)
    q = qbi_199a(args.qbi, args.w2_wages, args.ubia, args.tax_year)
    basis = outside_basis(args.tax_capital, args.liability_share_752)
    return PassThroughOut(
        qbi_deduction=q.deduction, outside_basis=basis.total, inputs_hash=q.stamp.inputs_hash
    )


class ResidencyIn(ReturnIn):
    nyc_days: Annotated[int, Field(ge=0, le=366), Tri]
    has_nyc_abode: Annotated[bool, Tri]
    main_home_outside_nyc: Annotated[bool, Tri]


class ResidencyOut(BaseModel):
    recommended: Annotated[str, Int]
    conflict: Annotated[bool, Int]
    inputs_hash: Annotated[str, Int]


@agent_tool(
    name="tax.compute_residency_facts", kind="compute", action="residency.read",
    data_class="tri", input_model=ResidencyIn, output_model=ResidencyOut,
)  # fmt: skip
async def compute_residency_facts(agent: AgentContext, args: ResidencyIn) -> ResidencyOut:
    await _return_of(agent, args)
    found = residency_rules(
        ResidencyFacts(args.nyc_days, args.has_nyc_abode, args.main_home_outside_nyc),
        args.tax_year,
    )
    return ResidencyOut(
        recommended=found.recommended, conflict=found.conflict,
        inputs_hash=found.stamp.inputs_hash,
    )  # fmt: skip


class AllocationIn(ReturnIn):
    amount: Annotated[Decimal, Tri]
    by_state: Annotated[
        list[tuple[Annotated[str, Field(pattern=r"^[A-Z]{2}$")], Decimal]],
        Field(min_length=1, max_length=60),
        Int,
    ]


class StateShare(BaseModel):
    id: Annotated[str, Int]  # the state code
    amount: Annotated[Decimal, Tri]


class AllocationOut(BaseModel):
    shares: Annotated[list[StateShare], Field(max_length=MAX), Int]
    total: Annotated[Decimal, Tri]


@agent_tool(
    name="tax.compute_state_allocation", kind="compute", action="residency.read",
    data_class="tri", input_model=AllocationIn, output_model=AllocationOut,
)  # fmt: skip
async def compute_state_allocation(agent: AgentContext, args: AllocationIn) -> AllocationOut:
    await _return_of(agent, args)
    found = state_sourcing(args.amount, args.by_state)
    shares = [StateShare(id=s, amount=v) for s, v in found.shares]
    return AllocationOut(shares=shares, total=sum((s.amount for s in shares), Decimal(0)))


# --- proposes ------------------------------------------------------------------------------------


class ProposedOut(BaseModel):
    proposal_id: Annotated[UUID, Int]
    state: Annotated[str, Int]
    row_count: Annotated[int, Int]


class FieldChange(BaseModel):
    model_config = _cfg()

    worksheet_id: Annotated[UUID, Int]
    field_key: Annotated[str, Field(min_length=1, max_length=100), Int]
    after: Annotated[Decimal, Tri]
    citation_ids: Annotated[list[UUID], Field(max_length=20), Int] = Field(
        default_factory=list[UUID]
    )


class _Targeted(ReturnIn):
    def tool_targets(self, agent: AgentContext) -> ToolTargets:
        """The run's engagement, and the taxpayer and year for §7216 (the rows' records are
        checked on the engagement by `create_proposal`)."""
        engagements = (agent.engagement_id,) if agent.engagement_id is not None else ()
        return ToolTargets(engagements, (), (TriSubject(self.client_entity_id, self.tax_year),))


class FieldChangesIn(_Targeted):
    changes: Annotated[list[FieldChange], Field(min_length=1, max_length=50), Int]


async def _propose(
    agent: AgentContext, kind: str, title: str, rows: list[ProposedRow]
) -> ProposedOut:
    if agent.engagement_id is None:
        raise NotFound("tax_return")
    proposal = await create_proposal(
        agent, engagement_id=agent.engagement_id, kind=kind, title=title, rows=rows
    )
    return ProposedOut(proposal_id=proposal, state="pending", row_count=len(rows))


@agent_tool(
    name="tax.propose_field_changes", kind="propose", action="proposal.create",
    data_class="tri", input_model=FieldChangesIn, output_model=ProposedOut,
)  # fmt: skip
async def propose_field_changes(agent: AgentContext, args: FieldChangesIn) -> ProposedOut:
    await _return_of(agent, args)
    rows = [
        ProposedRow(
            target_type="return_worksheet", target_id=c.worksheet_id, field_key=c.field_key,
            label=c.field_key, before=None, after={"t": "decimal", "v": str(c.after)},
            cause="agent_proposal", citation_ids=tuple(c.citation_ids),
        )
        for c in args.changes
    ]  # fmt: skip
    return await _propose(agent, "return_field_changes", "Proposed return field changes", rows)


class TreatmentChange(BaseModel):
    model_config = _cfg()

    treatment_id: Annotated[UUID, Int]
    treatment: Annotated[str, Field(min_length=1, max_length=60), Int]  # "Passive", …


class TreatmentsIn(_Targeted):
    changes: Annotated[list[TreatmentChange], Field(min_length=1, max_length=50), Int]


@agent_tool(
    name="tax.propose_pass_through_treatments", kind="propose", action="proposal.create",
    data_class="tri", input_model=TreatmentsIn, output_model=ProposedOut,
)  # fmt: skip
async def propose_pass_through_treatments(agent: AgentContext, args: TreatmentsIn) -> ProposedOut:
    await _return_of(agent, args)
    rows = [
        ProposedRow(
            target_type="pass_through_treatment", target_id=c.treatment_id, field_key="treatment",
            label="treatment", before=None, after={"t": "text", "v": c.treatment},
            cause="agent_proposal",
        )
        for c in args.changes
    ]  # fmt: skip
    return await _propose(agent, "pass_through_treatments", "Proposed K-1 treatments", rows)


class ResidencyProposalIn(_Targeted):
    determination_id: Annotated[UUID, Int]
    option: Annotated[str, Field(min_length=1, max_length=40), Int]


@agent_tool(
    name="tax.propose_residency", kind="propose", action="proposal.create",
    data_class="tri", input_model=ResidencyProposalIn, output_model=ProposedOut,
)  # fmt: skip
async def propose_residency(agent: AgentContext, args: ResidencyProposalIn) -> ProposedOut:
    from abacus.modules.tax.residency_service import fact_citations

    await _return_of(agent, args)
    # S38 end pass (TASK-7426): the row carries the determination's facts' citations (code's),
    # never the model's; SHL-10 refuses an uncited change.
    cited = await fact_citations(agent.tenant, args.determination_id)
    row = ProposedRow(
        target_type="residency_determination", target_id=args.determination_id,
        field_key="proposed_option", label="proposed option", before=None,
        after={"t": "text", "v": args.option}, cause="agent_proposal", citation_ids=cited,
    )  # fmt: skip
    return await _propose(agent, "residency", "Proposed residency", [row])


# --- T-05-T23 (DEC-4406): an entity return's account mappings ------------------------------------

ACCOUNT_MAPPING: Final = "tax_account_mapping"


class AccountMappingChange(BaseModel):
    model_config = _cfg()

    account_code: Annotated[str, Field(min_length=1, max_length=40), Tri]
    form_line_key: Annotated[str, Field(min_length=1, max_length=40), Int]
    confidence: Annotated[float, Field(ge=0, le=1), Int]


class AccountMappingsIn(_Targeted):
    return_id: Annotated[UUID, Int]
    mappings: Annotated[list[AccountMappingChange], Field(min_length=1, max_length=MAX), Int]


@agent_tool(
    name="tax.propose_account_mappings", kind="propose", action="proposal.create",
    data_class="tri", input_model=AccountMappingsIn, output_model=ProposedOut,
)  # fmt: skip
async def propose_account_mappings(agent: AgentContext, args: AccountMappingsIn) -> ProposedOut:
    """One proposal row per account: the return (the target), `account:<code>` and the key. The
    return must be the run's taxpayer's entity return for the year; codes are not repeated."""
    _, work_item = await _return_of(agent, args)
    if work_item != args.return_id:
        raise NotFound("tax_return")
    codes = [m.account_code for m in args.mappings]
    if len(set(codes)) != len(codes):
        raise NotFound("tax_return")  # a repeated account is no proposal (fail closed)
    rows = [
        ProposedRow(
            target_type=ACCOUNT_MAPPING, target_id=args.return_id,
            field_key=f"account:{m.account_code}", label=f"Account {m.account_code}",
            before=None, after={"t": "text", "v": m.form_line_key}, cause="agent_proposal",
        )
        for m in args.mappings
    ]  # fmt: skip
    return await _propose(agent, ACCOUNT_MAPPING, "Proposed account mappings", rows)


# --- T-05-T36 (DEC-4621): the agreement reader's allocation structure -------------------------

ALLOCATION_STRUCTURE: Final = "allocation_structure"


class StructureParameter(BaseModel):
    """One verified parameter: code checked the quote is in the cited clause before this call."""

    model_config = _cfg()

    parameter: Annotated[str, Field(pattern=r"^(kind|method|convention|rungs|transfers)$"), Int]
    value: Annotated[str | list[dict[str, str]], Tri]
    clause: Annotated[str, Field(min_length=1, max_length=40), Int]
    quote: Annotated[str, Field(min_length=1, max_length=400), Tri]


class AllocationStructureIn(_Targeted):
    return_id: Annotated[UUID, Int]
    parameters: Annotated[list[StructureParameter], Field(max_length=5), Tri]
    question: Annotated[str | None, Field(pattern=r"^convention$"), Int] = None


@agent_tool(
    name="tax.propose_allocation_structure", kind="propose", action="proposal.create",
    data_class="tri", input_model=AllocationStructureIn, output_model=ProposedOut,
)  # fmt: skip
async def propose_allocation_structure(
    agent: AgentContext, args: AllocationStructureIn
) -> ProposedOut:
    """One row per verified parameter on the return (`structure:<parameter>`), its cited
    clause as the row's rationale (code verified the quote in it before this call); the open
    §706(d) question is a row of its own. A manager approves the structure at L3 (T-05-T41);
    nothing is allocated here."""
    import json

    _, work_item = await _return_of(agent, args)
    if work_item != args.return_id:
        raise NotFound("tax_return")
    names = [p.parameter for p in args.parameters]
    if len(set(names)) != len(names) or (not names and args.question is None):
        raise NotFound("tax_return")  # a repeated or empty structure is no proposal (fail closed)
    rows = [
        ProposedRow(
            target_type=ALLOCATION_STRUCTURE, target_id=args.return_id,
            field_key=f"structure:{p.parameter}", label=p.parameter.capitalize(), before=None,
            after={
                "t": "text",
                "v": p.value if isinstance(p.value, str) else json.dumps(p.value, sort_keys=True),
            },
            cause="agent_proposal", rationale_ref=f"clause:{p.clause}",
        )
        for p in args.parameters
    ]  # fmt: skip
    if args.question is not None:
        rows.append(
            ProposedRow(
                target_type=ALLOCATION_STRUCTURE, target_id=args.return_id,
                field_key="structure:convention_question", label="Convention question",
                before=None, after={"t": "text", "v": args.question}, cause="agent_proposal",
            )
        )  # fmt: skip
    return await _propose(agent, ALLOCATION_STRUCTURE, "Proposed allocation structure", rows)
