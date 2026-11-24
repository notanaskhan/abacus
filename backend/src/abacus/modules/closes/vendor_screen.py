"""`close.agent` mode `vendor_screen` (C-02-T34; TASK-8906; C-02 §6; ADR-005, ADR-050, ADR-052,
ADR-167; red).

A person starts the screen for one 1099 vendor (`POST /v1/vendors/{id}/screen`,
`vendor_1099.screen`); code drives one run inline on the capability's run row (A-09-T29's
`start_capability_run`, attributed "<person> via Agent"), as the flux and planner modes do.

- **What the model sees.** Code's facts (the year's payments by method, the W-9 status), the
  closed sets (entity types and the W-9 exemption codes), the W-9's page numbers, and the W-9's
  **masked** text and the vendor's ledger name as untrusted input (ADR-052):
  `evidence.masked_pages`
  masks every detected identifier and scrubs any TIN-shaped run, so no TIN digit reaches the
  gateway (ADR-167). A vendor with no W-9 on file is not screened (409 `w9_not_on_file`): the
  screen asks, it never guesses.
- **What code settles** (`agent.settle_screen`): the entity type is an offered option, an
  exemption a W-9 code, every quote on an offered page, and no output carries four digits in a
  row (`tin_in_output`). Each quote becomes a `document_text` citation code verifies on the W-9
  page; any unverified quote escalates the run and nothing is proposed.
- **What lands.** One P-35 suggestion on `vendor_classification` (entity type, attorney
  flag, exemption) with its verified citations. Nothing changes until a person adopts it; the
  applier writes the vendor in the adopting unit of work (`entity_type_source =
  agent_suggestion_adopted`), and reportability is recomputed by code on the next read.

The three tools (`close.read_vendor_facts`, `close.read_vendor_document`, `close.propose_vendor_
classification`) are the same reads and the same proposal on C17 for a runtime-driven run; the
model never adopts, approves, reveals a TIN or sends a W-9 request (INV-1, C-02 §6).

Synthetic firms only (`ai_gateway.is_synthetic`) behind `closes.vendor_screen`; a shadow run
writes nothing a person sees.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Any, Final, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Row, text

from abacus.kernel._flags import CLOSES_VENDOR_SCREEN
from abacus.kernel.agent_tools import ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.closes import agent as close_agent
from abacus.modules.closes.agent_runs import RunOutcome
from abacus.modules.identity.api import AgentContext, AuthContext, Forbidden, authorise

TARGET: Final = "vendor_classification"
FIELD: Final = "classification"
ENTITY_TYPES: Final[tuple[str, ...]] = (
    "individual", "single_member_llc", "partnership", "c_corporation", "s_corporation",
    "trust_estate", "llc_c", "llc_s", "llc_p", "other",
)  # fmt: skip
Int = classified("internal")
Conf = classified("confidential")
READ: Final = "close.read"
SUGGEST: Final = "suggestion.create"


class W9NotOnFile(DomainConflict):
    """The vendor has no W-9 on file to screen: request one first."""

    code = "w9_not_on_file"


class ScreenNotAvailable(DomainConflict):
    """The vendor screen runs on synthetic firms only until its evals and shadow clear it."""

    code = "agent_not_available"


def _cfg() -> ConfigDict:
    return ConfigDict(extra="forbid", frozen=True)


_VENDOR: Final = text(
    "SELECT v.id, v.client_entity_id, v.display_name, v.entity_type, v.is_attorney, "
    "v.exempt_reason, v.w9_status, v.w9_evidence_version_id, "
    "v.tin_kind IS NOT NULL AS tin_on_file "
    "FROM vendors_1099 v WHERE v.id = :v"
)
_ENGAGEMENT: Final = text(
    "SELECT engagement_id FROM closes WHERE client_entity_id = :e ORDER BY period DESC LIMIT 1"
)
_LATEST_CLOSE: Final = text(
    "SELECT work_item_id FROM closes WHERE client_entity_id = :e ORDER BY period DESC LIMIT 1"
)
_PAYMENTS: Final = text(
    "SELECT tax_year, method, amount, txn_count FROM vendor_payment_rollups WHERE vendor_id = :v "
    "AND tax_year = (SELECT max(tax_year) FROM vendor_payment_rollups WHERE vendor_id = :v) "
    "ORDER BY method"
)


async def vendor_engagement(tenant: TenantContext, vendor_id: UUID) -> UUID | None:
    """The vendor's close engagement (its entity's latest close): who may see it, and where the
    run, its citations and its suggestion live."""
    async with tenant_session(tenant) as session:
        entity = await session.scalar(
            text("SELECT client_entity_id FROM vendors_1099 WHERE id = :v"), {"v": vendor_id}
        )
        if entity is None:
            return None
        return cast(UUID | None, await session.scalar(_ENGAGEMENT, {"e": entity}))


# --- tools (C17) ---------------------------------------------------------------------------------


class _OnRun(BaseModel):
    """A vendor the run may read: its close engagement must be the run's (any other reads 404)."""

    model_config = _cfg()

    vendor_id: Annotated[UUID, Int]

    def tool_targets(self, agent: AgentContext) -> object:
        from abacus.modules.agents.api import ToolTargets  # lazy: closes.api registers these

        return ToolTargets((agent.engagement_id,) if agent.engagement_id is not None else ())


class PaymentFact(BaseModel):
    model_config = _cfg()

    id: Annotated[str, Field(max_length=40), Int]  # `paid_<method>`, the fact id the run uses
    method: Annotated[str, Field(max_length=20), Int]
    amount: Annotated[Decimal, Conf]
    txn_count: Annotated[int, Field(ge=0), Int]


class VendorFactsOut(BaseModel):
    """Masked vendor facts: no TIN, not even its last four; only whether one is on file."""

    model_config = _cfg()

    vendor_id: Annotated[UUID, Int]
    display_name: Annotated[str, Field(max_length=300), Conf]  # untrusted ledger text
    entity_type: Annotated[str, Int]
    is_attorney: Annotated[bool, Int]
    exempt_reason: Annotated[str | None, Int] = None
    w9_status: Annotated[str, Int]
    w9_on_file: Annotated[bool, Int]
    tin_on_file: Annotated[bool, Int]
    tax_year: Annotated[int | None, Int] = None
    payments: Annotated[list[PaymentFact], Field(max_length=10), Int] = []


async def _on_run(
    caller: ToolCaller, vendor_id: UUID
) -> Row[Any]:  # Any: a SQL row of mixed column types
    async with tenant_session(caller.tenant) as session:
        row = (await session.execute(_VENDOR, {"v": vendor_id})).one_or_none()
        engagement = (
            None if row is None else await session.scalar(_ENGAGEMENT, {"e": row.client_entity_id})
        )
    if row is None or engagement != caller.engagement_id:
        raise NotFound("vendor")
    return row


async def read_vendor_facts(caller: ToolCaller, args: _OnRun) -> VendorFactsOut:
    row = await _on_run(caller, args.vendor_id)
    async with tenant_session(caller.tenant) as session:
        payments = (await session.execute(_PAYMENTS, {"v": args.vendor_id})).all()
    return VendorFactsOut(
        vendor_id=args.vendor_id,
        display_name=str(row.display_name),
        entity_type=str(row.entity_type),
        is_attorney=bool(row.is_attorney),
        exempt_reason=row.exempt_reason,
        w9_status=str(row.w9_status),
        w9_on_file=row.w9_evidence_version_id is not None,
        tin_on_file=bool(row.tin_on_file),
        tax_year=payments[0].tax_year if payments else None,
        payments=[
            PaymentFact(
                id=f"paid_{p.method}",
                method=p.method,
                amount=Decimal(p.amount),
                txn_count=int(p.txn_count),
            )
            for p in payments
        ],
    )


class W9PageOut(BaseModel):
    model_config = _cfg()

    id: Annotated[str, Field(max_length=20), Int]  # `page_<n>`
    page: Annotated[int, Int]
    text: Annotated[str, Field(max_length=20000), Conf]  # masked; untrusted


class W9TextOut(BaseModel):
    model_config = _cfg()

    vendor_id: Annotated[UUID, Int]
    evidence_version_id: Annotated[UUID, Int]
    pages: Annotated[list[W9PageOut], Field(max_length=20), Int]


async def w9_pages(tenant: TenantContext, version_id: UUID) -> dict[int, str]:
    """The W-9's scanned pages as masked text (every detected identifier masked, TIN-shaped runs
    scrubbed); a W-9 not yet scanned reads as nothing (fail closed)."""
    from abacus.modules.evidence.api import masked_pages

    found = await masked_pages(tenant, evidence_version_id=version_id)
    return {} if found is None else {p: scrub_digits(t) for p, t in sorted(found.items())}


_RUN: Final = re.compile(r"\d{4,}")


def scrub_digits(page_text: str) -> str:
    """Belt and braces over the evidence scrub: any run of four or more digits is masked, so no
    TIN fragment (a last four included) reaches the gateway."""
    return _RUN.sub(lambda m: "•" * len(m.group(0)), page_text)[:20000]


async def read_vendor_document(caller: ToolCaller, args: _OnRun) -> W9TextOut:
    row = await _on_run(caller, args.vendor_id)
    version = row.w9_evidence_version_id
    if version is None:
        raise W9NotOnFile
    pages = await w9_pages(caller.tenant, cast(UUID, version))
    return W9TextOut(
        vendor_id=args.vendor_id,
        evidence_version_id=cast(UUID, version),
        pages=[W9PageOut(id=f"page_{p}", page=p, text=t) for p, t in pages.items()][:20],
    )


class ProposeClassificationIn(_OnRun):
    entity_type: Annotated[str, Field(max_length=40), Int]
    is_attorney: Annotated[bool, Int]
    exempt_reason: Annotated[str | None, Field(max_length=40), Int] = None
    quotes: Annotated[list[close_agent.W9QuoteOut], Field(min_length=1, max_length=6), Int]
    rationale_ref: Annotated[str | None, Field(max_length=120), Int] = None


class ProposeClassificationOut(BaseModel):
    model_config = _cfg()

    suggestion_id: Annotated[UUID, Int]
    citation_ids: Annotated[list[UUID], Int]


class UnverifiedQuote(DomainConflict):
    """A quote is not on the W-9's page: nothing is proposed."""

    code = "citation_unverified"


async def propose_classification(
    agent: AgentContext,
    vendor_id: UUID,
    proposal: close_agent.VendorScreenOut,
    *,
    shadow: bool = False,
    rationale_ref: str | None = None,
) -> tuple[UUID | None, list[UUID]]:
    """Verify every quote as a `document_text` citation on the W-9, then (outside a shadow run)
    write one suggestion. Any unverified quote raises `UnverifiedQuote` (nothing is written)."""
    from abacus.kernel.uow import uow
    from abacus.modules.agents.api import create_suggestion
    from abacus.modules.evidence.api import CitationAnchor, CitationClaim, record_citations

    if proposal.entity_type not in ENTITY_TYPES or (
        proposal.exempt_reason is not None
        and proposal.exempt_reason not in close_agent.VENDOR_EXEMPTIONS
    ):
        raise close_agent.OutputRefused(facts={"reason": "option_not_offered"})
    async with tenant_session(agent.tenant) as session:
        version = await session.scalar(
            text("SELECT w9_evidence_version_id FROM vendors_1099 WHERE id = :v"),
            {"v": vendor_id},
        )
    if version is None or agent.engagement_id is None:
        raise W9NotOnFile
    claims = [
        CitationClaim(
            "document_text",
            {"evidence_version_id": str(version), "page": q.page},
            quote=q.quote,
        )
        for q in proposal.quotes
    ]
    anchor = CitationAnchor(TARGET, vendor_id, FIELD, None, agent.engagement_id)
    async with uow(agent.tenant) as tx:
        recorded = await record_citations(
            tx, actor=agent, anchor=anchor, claims=claims, shadow=shadow
        )
    if len(recorded) != len(claims) or not all(r.verified for r in recorded):
        raise UnverifiedQuote(facts={"vendor_id": str(vendor_id)})
    cited = [r.id for r in recorded]
    if shadow:
        return None, cited
    suggestion = await create_suggestion(
        agent,
        engagement_id=agent.engagement_id,
        target_type=TARGET,
        target_id=vendor_id,
        field_key=FIELD,
        proposed_value={
            "t": "json",
            "v": {
                "entity_type": proposal.entity_type,
                "is_attorney": proposal.is_attorney,
                "exempt_reason": proposal.exempt_reason,
            },
        },
        citation_ids=cited,
        rationale_ref=rationale_ref,
    )
    return suggestion, cited


async def propose_vendor_classification(
    caller: ToolCaller, args: ProposeClassificationIn
) -> ProposeClassificationOut:
    """A suggestion of the vendor's classification with verified W-9 citations (C-31 Adopt); a
    person adopts it (INV-1)."""
    await _on_run(caller, args.vendor_id)
    suggestion, cited = await propose_classification(
        cast(AgentContext, caller),
        args.vendor_id,
        close_agent.VendorScreenOut(
            entity_type=args.entity_type,
            is_attorney=args.is_attorney,
            exempt_reason=args.exempt_reason,
            quotes=args.quotes,
        ),
        rationale_ref=args.rationale_ref,
    )
    if suggestion is None:  # a tool call is never a shadow run
        raise RuntimeError("propose_classification returned no suggestion outside shadow mode")
    return ProposeClassificationOut(suggestion_id=suggestion, citation_ids=cited)


AGENT_TOOLS: Final = (
    ToolDecl("close.read_vendor_facts", "read", READ, "confidential", _OnRun, VendorFactsOut,
             read_vendor_facts, untrusted=("display_name",), records_read="vendor_1099"),
    ToolDecl("close.read_vendor_document", "read", READ, "confidential", _OnRun, W9TextOut,
             read_vendor_document, untrusted=("pages",), records_read="evidence_page"),
    ToolDecl("close.propose_vendor_classification", "propose", SUGGEST, "confidential",
             ProposeClassificationIn, ProposeClassificationOut, propose_vendor_classification),
)  # fmt: skip


# --- the run a person starts ---------------------------------------------------------------------


async def _available(ctx: AuthContext) -> None:
    from abacus.ai_gateway import is_synthetic

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("vendor_1099.screen", "role")
    if not await flag_enabled(ctx.tenant, CLOSES_VENDOR_SCREEN):
        raise NotFound(CLOSES_VENDOR_SCREEN.name)
    if not await is_synthetic(ctx.tenant):
        raise ScreenNotAvailable(facts={"capability": close_agent.CAPABILITY})


async def screen_vendor(ctx: AuthContext, vendor_id: UUID) -> RunOutcome:
    """`POST /v1/vendors/{id}/screen`: one vendor-screen run. Returns the run's outcome
    (`agent_runs.RunOutcome`): succeeded with a suggestion, escalated with the refusal's reason
    (nothing proposed), or shadow."""
    from abacus.modules.closes.agent_runs import end_run as _end
    from abacus.modules.closes.agent_runs import start_run as _start
    from abacus.modules.engagements.api import get_ref

    await _available(ctx)
    engagement_id = await vendor_engagement(ctx.tenant, vendor_id)
    if engagement_id is None:
        raise NotFound("vendor")
    try:
        engagement = await get_ref(ctx, engagement_id)
        await authorise(ctx, "vendor_1099.screen", engagement.resource())
    except NotFound:
        raise NotFound("vendor") from None
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("vendor") from None
        raise
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_VENDOR, {"v": vendor_id})).one()
        payments = (await session.execute(_PAYMENTS, {"v": vendor_id})).all()
        close_id = await session.scalar(_LATEST_CLOSE, {"e": row.client_entity_id})
    if row.w9_evidence_version_id is None:
        raise W9NotOnFile
    pages = await w9_pages(ctx.tenant, row.w9_evidence_version_id)
    if not pages:
        raise W9NotOnFile(facts={"reason": "w9_not_scanned"})
    given = close_agent.CloseAgentInput(
        mode="vendor_screen",
        close_id=cast(UUID, close_id),
        facts=[
            close_agent.FactIn(
                id=f"paid_{p.method}", kind="money", value=str(Decimal(p.amount)), basis="code"
            )
            for p in payments
        ],
        options=list(ENTITY_TYPES),
        pages=sorted(pages),
        untrusted=[
            f"Vendor name in the ledger: {row.display_name}"[:400],
            *[f"W-9 page {p}: {t}" for p, t in sorted(pages.items())][:20],
        ],
    )
    agent, shadow = await _start(ctx, engagement_id)
    try:
        settled = await close_agent.answer(agent, given)
    except close_agent.OutputRefused as refused:
        return await _end(agent, "escalated", str((refused.facts or {}).get("reason")))
    if settled.screen is None:  # settle_screen requires it
        raise RuntimeError("a settled screen without its screen")
    try:
        suggestion, cited = await propose_classification(
            agent, vendor_id, settled.screen, shadow=shadow
        )
    except UnverifiedQuote:
        return await _end(agent, "escalated", "citation_unverified")
    if shadow:
        return await _end(agent, "shadow", None, citations=len(cited))
    del suggestion
    return await _end(agent, "succeeded", None, citations=len(cited))


# --- the applier (a person adopts in CLS-13) -----------------------------------------------------

_ADOPT: Final = text(
    "UPDATE vendors_1099 SET entity_type = :entity_type, is_attorney = :attorney, "
    "exempt_reason = :exempt, entity_type_source = 'agent_suggestion_adopted', updated_by = :by, "
    "updated_at = abacus_now(), version = version + 1 WHERE id = :v RETURNING version"
)


async def apply_vendor_classification(tx: UnitOfWork, ctx: AuthContext, value: object) -> None:
    """The adopted classification, written as the adopting person in their unit of work
    (`vendor_1099.update` on the vendor's close engagement). An edited value is the person's own
    (`value_source = human`), still from the closed sets."""
    from abacus.modules.agents.api import AdoptedValue
    from abacus.modules.engagements.api import get_ref

    adopted = cast(AdoptedValue, value)
    payload = cast("dict[str, object]", adopted.value.get("v") or {})
    entity_type = str(payload.get("entity_type", ""))
    exempt = payload.get("exempt_reason")
    if (
        adopted.field_key != FIELD
        or entity_type not in ENTITY_TYPES
        or (exempt is not None and exempt not in close_agent.VENDOR_EXEMPTIONS)
    ):
        raise close_agent.OutputRefused(facts={"reason": "option_not_offered"})
    engagement_id = await vendor_engagement(ctx.tenant, adopted.target_id)
    if engagement_id is None:
        raise NotFound("vendor")
    await authorise(ctx, "vendor_1099.update", (await get_ref(ctx, engagement_id)).resource())
    version = await tx.session.scalar(
        _ADOPT,
        {
            "entity_type": entity_type,
            "attorney": bool(payload.get("is_attorney")),
            "exempt": exempt,
            "by": ctx.user_id,
            "v": adopted.target_id,
        },
    )
    if version is None:
        raise NotFound("vendor")
    tx.record(
        "vendor.updated",
        target=Target("vendor", adopted.target_id),
        after=Ref(version=int(version), **(
            {"suggestion_id": adopted.suggestion_id} if adopted.suggestion_id else {}
        )),
        scope=Scope(engagement_id=engagement_id),
    )  # fmt: skip


def register() -> None:
    from abacus.modules.agents.api import register_suggestion_applier

    register_suggestion_applier(
        TARGET,
        apply_vendor_classification,
        engagement_of=vendor_engagement,
    )


__all__ = [
    "AGENT_TOOLS",
    "ENTITY_TYPES",
    "TARGET",
    "ScreenNotAvailable",
    "UnverifiedQuote",
    "W9NotOnFile",
    "apply_vendor_classification",
    "propose_classification",
    "register",
    "screen_vendor",
    "scrub_digits",
    "vendor_engagement",
    "w9_pages",
]
