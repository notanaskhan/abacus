"""The instrument reader's tools on C17 (T-07-T14; TASK-8040; SPEC-656 AC-1.4, AC-1.5, AC-2.1 to
AC-2.4; ADR-233, ADR-049, ADR-050, ADR-052; §7216).

- `tax.read_instrument_clauses` (read): the current segmentation's clauses, each with its label,
  heading, pages and the masked words inside its regions, wrapped as untrusted.
- `tax.read_trust_facts` (read): the year's distributions and expenses as code facts with ids,
  the trust profile's facts and the prior year's approved determinations.
- `tax.propose_trust_determinations` (propose): the seven determinations as one proposal
  (AgentBlocks: the rationale by reference, numbers by fact id, clause citations).

Every tool carries tax return information (`data_class="tri"`): the runtime refuses a call before
any query when the trust (its `client_entity_id` with the `tax_year`) lacks either §7216 consent
(`consent_required`). No tool adopts, approves, locks or reopens: the reader proposes; a person
adopts in TXT-01 and approves at L3 (INV-1). A proposal is refused whole when a clause citation
does not verify (`unverified_citation`) or a figure in its text is not one of the facts it names
(`number_provenance`, INV-2).

The suggestion applier writes an adopted value as a new determination version (`set_by_kind =
'agent'`, with its suggestion; "<initiator> via Agent") and moves the interpretation to adopted;
a proposal moves it to proposed and, for `principal_invaded = yes`, to the principal-invaded
scenario.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.agents.api import (
    AdoptedValue,
    ProposedRow,
    ToolTargets,
    agent_tool,
    create_proposal,
    register_suggestion_applier,
)
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    masked_region_text,
    record_citations,
)
from abacus.modules.identity.api import AgentContext, AuthContext
from abacus.modules.organisations.api import TriSubject
from abacus.modules.tax.fiduciary_contract import CLAUSE_GOVERNED, DeterminationKey
from abacus.modules.tax.instrument_citations import KIND as CLAUSE_KIND
from abacus.modules.tax.tools import (
    ProposedOut,
    ReturnIn,
    _return_of,  # pyright: ignore[reportPrivateUsage]  # same module (tax)
)

Int = classified("internal")
Tri = classified("restricted", tri=True)
MAX: Final = 200
TARGET: Final = "instrument_determination"
PROPOSAL_KIND: Final = "instrument_determinations"
_VALUE_AAD: Final = "tax.instrument_determination.value"
_NUMBER: Final = re.compile(r"(?<![A-Za-z])\$?\d[\d,]*(?:\.\d+)?%?")
# Clause labels and statute references are not figures (Art. III(a), §663(b), 1041).
_NOT_FIGURE: Final = re.compile(
    r"(Art\.\s*[IVXLC]+|§\s*\d+[a-z()0-9]*|Form\s+\d+|\b(19|20)\d{2}\b)"
)


def _cfg() -> ConfigDict:
    return ConfigDict(extra="forbid", frozen=True)


class _Trust(ReturnIn):
    def tool_targets(self, agent: AgentContext) -> ToolTargets:
        engagements = (agent.engagement_id,) if agent.engagement_id is not None else ()
        return ToolTargets(engagements, (), (TriSubject(self.client_entity_id, self.tax_year),))


# --- tax.read_instrument_clauses ----------------------------------------------------------------


class ClauseRow(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Int]  # the clause id (rows carry an id, ADR-049)
    label: Annotated[str, Int]
    heading: Annotated[str | None, Tri]
    page_from: Annotated[int, Int]
    page_to: Annotated[int, Int]
    text: Annotated[str | None, Tri]  # masked; None where a page was not scanned


class ClausesOut(BaseModel):
    model_config = _cfg()

    instrument_id: Annotated[UUID, Int]
    segmentation_id: Annotated[UUID, Int]
    status: Annotated[str, Int]
    clauses: Annotated[list[ClauseRow], Int]


_CURRENT: Final = text(
    "SELECT i.instrument_id, i.segmentation_id, s.status, g.evidence_version_id "
    "FROM instrument_interpretations i "
    "JOIN instrument_segmentations s ON s.id = i.segmentation_id "
    "JOIN governing_instruments g ON g.id = i.instrument_id "
    "WHERE i.work_item_id = :w AND i.superseded_at IS NULL"
)
_CLAUSES: Final = text(
    "SELECT id, label, heading, page_from, page_to, regions FROM instrument_clauses "
    "WHERE segmentation_id = :s ORDER BY ordinal LIMIT :n"
)


@agent_tool(
    name="tax.read_instrument_clauses", kind="read", action="instrument.read", data_class="tri",
    input_model=_Trust, output_model=ClausesOut, untrusted=("clauses",),
    records_read="instrument_clause",
)  # fmt: skip
async def read_instrument_clauses(agent: AgentContext, args: _Trust) -> ClausesOut:
    _, work_item = await _return_of(agent, args)
    async with tenant_session(agent.tenant) as session:
        current = (await session.execute(_CURRENT, {"w": work_item})).first()
        if current is None:
            raise NotFound("instrument_interpretation")
        rows = list(
            (await session.execute(_CLAUSES, {"s": current.segmentation_id, "n": MAX})).all()
        )
    out: list[ClauseRow] = []
    for r in rows:
        held: object = r.regions
        stored = cast(
            list[dict[str, object]], held if isinstance(held, list) else json.loads(str(held))
        )
        regions: list[tuple[int, tuple[float, float, float, float]]] = [
            (
                cast(int, g["page"]),
                cast(tuple[float, float, float, float], tuple(cast(list[float], g["bbox"]))),
            )
            for g in stored
        ]
        texts = await masked_region_text(agent.tenant, current.evidence_version_id, regions)
        known = [t for t in texts if t is not None]
        out.append(
            ClauseRow(
                id=r.id, label=r.label, heading=r.heading, page_from=r.page_from,
                page_to=r.page_to, text=" ".join(known) if len(known) == len(texts) else None,
            )
        )  # fmt: skip
    return ClausesOut(
        instrument_id=current.instrument_id,
        segmentation_id=current.segmentation_id,
        status=current.status,
        clauses=out,
    )


# --- tax.read_trust_facts -----------------------------------------------------------------------


class Fact(BaseModel):
    """A code fact the proposal may name a figure by (number provenance, INV-2)."""

    model_config = _cfg()

    id: Annotated[str, Int]  # the fact id: "distribution:<id>", "expense:<id>"
    label: Annotated[str, Tri]
    amount: Annotated[Decimal, Tri]
    detail: Annotated[str | None, Tri] = None  # source, charged to, the clause it cites


class TrustFactsOut(BaseModel):
    model_config = _cfg()

    fiduciary_kind: Annotated[str, Int]
    revocable: Annotated[bool, Tri]
    settlor_died_year: Annotated[int | None, Tri]
    distributions: Annotated[list[Fact], Int]
    expenses: Annotated[list[Fact], Int]
    prior_year: Annotated[dict[str, str], Tri]  # key → value code of the approved prior reading


_PROFILE: Final = text(
    "SELECT fiduciary_kind, revocable, settlor_died_year FROM trust_profiles "
    "WHERE client_entity_id = :e"
)
_DISTRIBUTIONS: Final = text(
    "SELECT d.id, v.amount, v.source, v.paid_on FROM trust_distributions d JOIN LATERAL ("
    "SELECT * FROM trust_distribution_versions x WHERE x.distribution_id = d.id ORDER BY x.seq "
    "DESC LIMIT 1) v ON true WHERE d.work_item_id = :w ORDER BY v.paid_on, d.id LIMIT :n"
)
_EXPENSES: Final = text(
    "SELECT e.id, v.amount, e.kind, v.charged_to FROM trust_expenses e JOIN LATERAL ("
    "SELECT * FROM trust_expense_versions x WHERE x.expense_id = e.id ORDER BY x.seq DESC "
    "LIMIT 1) v ON true WHERE e.work_item_id = :w ORDER BY e.id LIMIT :n"
)
_PRIOR: Final = text(
    "SELECT d.key, v.value_code FROM tax_returns r JOIN instrument_interpretations i "
    "ON i.work_item_id = r.work_item_id AND i.status = 'approved' "
    "JOIN instrument_determinations d ON d.interpretation_id = i.id JOIN LATERAL (SELECT * FROM "
    "instrument_determination_versions x WHERE x.determination_id = d.id ORDER BY x.seq DESC "
    "LIMIT 1) v ON true WHERE r.client_entity_id = :e AND r.tax_year = :y"
)


@agent_tool(
    name="tax.read_trust_facts", kind="read", action="instrument.read", data_class="tri",
    input_model=_Trust, output_model=TrustFactsOut, records_read="trust_distribution",
)  # fmt: skip
async def read_trust_facts(agent: AgentContext, args: _Trust) -> TrustFactsOut:
    _, work_item = await _return_of(agent, args)
    async with tenant_session(agent.tenant) as session:
        profile = (await session.execute(_PROFILE, {"e": args.client_entity_id})).first()
        distributions = (await session.execute(_DISTRIBUTIONS, {"w": work_item, "n": MAX})).all()
        expenses = (await session.execute(_EXPENSES, {"w": work_item, "n": MAX})).all()
        prior = (
            await session.execute(_PRIOR, {"e": args.client_entity_id, "y": args.tax_year - 1})
        ).all()
    return TrustFactsOut(
        fiduciary_kind=profile.fiduciary_kind if profile is not None else "trust",
        revocable=bool(profile.revocable) if profile is not None else False,
        settlor_died_year=profile.settlor_died_year if profile is not None else None,
        distributions=[
            Fact(
                id=f"distribution:{d.id}",
                label=f"Distribution {d.paid_on.isoformat()}",
                amount=d.amount,
                detail=d.source,
            )
            for d in distributions
        ],
        expenses=[
            Fact(id=f"expense:{e.id}", label=e.kind, amount=e.amount, detail=e.charged_to)
            for e in expenses
        ],
        prior_year={p.key: p.value_code for p in prior},
    )


# --- tax.propose_trust_determinations -----------------------------------------------------------


class ClauseCite(BaseModel):
    model_config = _cfg()

    clause_id: Annotated[UUID, Int]
    quote: Annotated[str, Field(min_length=1, max_length=2000), Tri]


class ProposedDetermination(BaseModel):
    model_config = _cfg()

    key: Annotated[DeterminationKey, Int]
    value_code: Annotated[str, Field(min_length=1, max_length=60), Tri]
    value_text: Annotated[str, Field(min_length=1, max_length=300), Tri]
    rationale_ref: Annotated[str | None, Field(max_length=120), Int] = None  # an AgentText block
    clauses: Annotated[list[ClauseCite], Field(max_length=5), Int] = []
    fact_ids: Annotated[list[str], Field(max_length=20), Int] = []  # numbers by reference


class DeterminationsIn(_Trust):
    determinations: Annotated[list[ProposedDetermination], Field(min_length=1, max_length=7), Int]


class UnverifiedCitation(DomainInvalid):
    """A clause citation the verifier refused: the proposal is rejected whole (INV-2)."""

    code = "unverified_citation"


class NumberProvenance(DomainInvalid):
    """A figure in the proposed text that is none of the facts it names (INV-2)."""

    code = "number_provenance"


def _figures(text_: str) -> list[Decimal]:
    out: list[Decimal] = []
    for token in _NUMBER.findall(_NOT_FIGURE.sub(" ", text_)):
        raw = token.strip("$%").replace(",", "")
        try:
            out.append(Decimal(raw))
        except InvalidOperation:
            continue
    return out


async def _facts(agent: AgentContext, args: _Trust) -> dict[str, Decimal]:
    facts = await read_trust_facts(agent, args)
    return {f.id: f.amount for f in (*facts.distributions, *facts.expenses)}


_INTERPRETATION: Final = text(
    "SELECT id, engagement_id, work_item_id, instrument_id, segmentation_id, status "
    "FROM instrument_interpretations WHERE work_item_id = :w AND superseded_at IS NULL"
)
_DETERMINATION_ID: Final = text(
    "SELECT id FROM instrument_determinations WHERE interpretation_id = :i AND key = :k"
)
_INSERT_DETERMINATION: Final = text(
    "INSERT INTO instrument_determinations (tenant_id, interpretation_id, key) "
    "VALUES (:t, :i, :k) ON CONFLICT (interpretation_id, key) DO NOTHING"
)
_PROPOSED: Final = text(
    "UPDATE instrument_interpretations SET status = 'proposed', read_run_id = :run, "
    "scenario = :scenario, row_version = row_version + 1 WHERE id = :i AND status IN "
    "('unread', 'reading', 'reopened', 'proposed')"
)


@agent_tool(
    name="tax.propose_trust_determinations", kind="propose", action="proposal.create",
    data_class="tri", input_model=DeterminationsIn, output_model=ProposedOut,
)  # fmt: skip
async def propose_trust_determinations(agent: AgentContext, args: DeterminationsIn) -> ProposedOut:
    engagement, work_item = await _return_of(agent, args)
    facts = await _facts(agent, args)
    # Number provenance first: nothing is written for a proposal with an unsourced figure.
    for d in args.determinations:
        named = {facts[f] for f in d.fact_ids if f in facts}
        if set(d.fact_ids) - facts.keys() or any(n not in named for n in _figures(d.value_text)):
            raise NumberProvenance(facts={"key": d.key})
        if d.key in CLAUSE_GOVERNED and not d.clauses:
            raise UnverifiedCitation(facts={"key": d.key})
    async with tenant_session(agent.tenant) as session:
        interp = (await session.execute(_INTERPRETATION, {"w": work_item})).first()
    if interp is None:
        raise NotFound("instrument_interpretation")
    rows: list[ProposedRow] = []
    async with uow(agent.tenant) as tx:
        for d in args.determinations:
            await tx.session.execute(
                _INSERT_DETERMINATION, {"t": agent.tenant.tenant_id, "i": interp.id, "k": d.key}
            )
            determination = cast(
                UUID, await tx.session.scalar(_DETERMINATION_ID, {"i": interp.id, "k": d.key})
            )
            recorded = await record_citations(
                tx,
                actor=agent,
                anchor=CitationAnchor(
                    type=TARGET,
                    id=determination,
                    ref=d.key,
                    engagement_id=engagement,
                    work_item_id=work_item,
                ),
                claims=[
                    CitationClaim(
                        CLAUSE_KIND,
                        {
                            "instrument_id": str(interp.instrument_id),
                            "segmentation_id": str(interp.segmentation_id),
                            "clause_id": str(c.clause_id),
                        },
                        quote=c.quote,
                    )
                    for c in d.clauses
                ],
            )
            if not all(r.verified for r in recorded):
                raise UnverifiedCitation(facts={"key": d.key})
            rows.append(
                ProposedRow(
                    target_type=TARGET,
                    target_id=determination,
                    field_key=f"{d.key}:{d.value_code}",
                    label=d.value_text,
                    before=None,
                    after={"t": "text", "v": d.value_text},
                    cause="agent_proposal",
                    citation_ids=tuple(r.id for r in recorded),
                    rationale_ref=d.rationale_ref,
                )
            )
        invaded = any(
            d.key == "principal_invaded" and d.value_code.startswith("yes")
            for d in args.determinations
        )
        await tx.session.execute(
            _PROPOSED,
            {"i": interp.id, "run": agent.agent_run_id,
             "scenario": "principal_invaded" if invaded else "base"},
        )  # fmt: skip
        tx.record(
            "instrument_interpretation.proposed",
            target=Target("instrument_interpretation", interp.id),
        )
    proposal = await create_proposal(
        agent, engagement_id=engagement, kind=PROPOSAL_KIND, title="Proposed instrument reading",
        rows=rows,
    )  # fmt: skip
    return ProposedOut(proposal_id=proposal, state="pending", row_count=len(rows))


# --- the applier (a person adopts in TXT-01) ----------------------------------------------------

_LATEST: Final = text(
    "SELECT d.interpretation_id, d.key, coalesce(max(v.seq), 0) AS seq, i.status "
    "FROM instrument_determinations d JOIN instrument_interpretations i ON i.id = "
    "d.interpretation_id LEFT JOIN instrument_determination_versions v ON v.determination_id = "
    "d.id WHERE d.id = :d GROUP BY d.interpretation_id, d.key, i.status"
)
_NEW_VERSION: Final = text(
    "INSERT INTO instrument_determination_versions (tenant_id, determination_id, key, seq, "
    "value_code, value_text_sealed, rationale_ref, citation_ids, set_by_kind, set_by_id, "
    "suggestion_id) VALUES (:t, :d, :k, :seq, :code, :value, NULL, :citations, 'agent', :u, :s)"
)
_ADOPTED: Final = text(
    "UPDATE instrument_interpretations SET status = 'adopted', version_no = version_no + 1, "
    "row_version = row_version + 1 WHERE id = :i AND status IN ('proposed', 'adopted')"
)
_ENGAGEMENT_OF: Final = text(
    "SELECT i.engagement_id FROM instrument_determinations d JOIN instrument_interpretations i "
    "ON i.id = d.interpretation_id WHERE d.id = :d"
)


async def determination_engagement(tenant: TenantContext, target_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        return cast(UUID | None, await session.scalar(_ENGAGEMENT_OF, {"d": target_id}))


async def apply_determination(tx: UnitOfWork, ctx: AuthContext, value: AdoptedValue) -> None:
    """The adopted value as a new version (agent-set, with its suggestion), in the adopting unit
    of work; a locked interpretation refuses (`interpretation_locked`)."""
    from abacus.modules.tax.fiduciary_contract import InterpretationLocked

    row = (await tx.session.execute(_LATEST, {"d": value.target_id})).first()
    if row is None:
        raise NotFound(TARGET)
    if row.status == "approved":
        raise InterpretationLocked(facts={"interpretation_id": str(row.interpretation_id)})
    key, _, code = value.field_key.partition(":")
    if key != row.key or not code:
        raise DomainInvalid(facts={"field": "field_key"})
    shown = str(value.value.get("v", ""))
    await tx.session.execute(
        _NEW_VERSION,
        {"t": ctx.tenant_id, "d": value.target_id, "k": key, "seq": int(row.seq) + 1,
         "code": code, "value": await seal(ctx.tenant_id, shown.encode(), _VALUE_AAD),
         "citations": list(value.citation_ids), "u": ctx.user_id, "s": value.suggestion_id},
    )  # fmt: skip
    await tx.session.execute(_ADOPTED, {"i": row.interpretation_id})
    tx.record(
        "instrument_determination.adopted",
        target=Target(TARGET, value.target_id),
        after=Ref(key=key, seq=int(row.seq) + 1),
    )


def register() -> None:
    register_suggestion_applier(
        TARGET, apply_determination, engagement_of=determination_engagement
    )


__all__ = [
    "apply_determination",
    "propose_trust_determinations",
    "read_instrument_clauses",
    "read_trust_facts",
    "register",
]
