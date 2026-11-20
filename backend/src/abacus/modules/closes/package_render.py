"""CLS-08's package assembly and render (C-02-T28; SPEC-701 F7 US-7.1, US-7.2; ADR-152, ADR-320;
DEC-5819).

- **A deterministic run.** Generate (`close_package.generate`, a person) opens a DET run
  (`close.package_assembler`, no model call) for the Drafting state, writes a new deliverable
  version that keeps the commentary the person edited, and asks C11 for a DRAFT render of kind
  `close_package`; `PackageAssemblyWorkflow` waits for the render job and ends the run.
- **The document** is composed by code (`compose_package`), never from a firm template's prose: the
  entity, "Balance Sheet" and "Income Statement" tables from the package's computed lines (posted
  or recorded entries only, C-02-T21), the commentary as the person left it, the legend "No
  assurance is provided." on every page for an AR-C 70 preparation route and none for a CAS
  by-product (December), page numbers when the toggles say so. C11 draws DRAFT on every draft page.
- **Deterministic.** The same posted TB and the same toggles give the same blocks, so the snapshot
  and the bytes are the same on every render (DEC-44); the XLSX is `safe_xlsx`'s byte-stable book.
- **Pages.** `page_url` names P-03's page route for the render's PDF version.
"""

from __future__ import annotations

import contextvars
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.closes.delivery_contract import DeliveryPackageOut, DeliveryStatementLineOut
from abacus.modules.identity.api import AuthContext, authorise

KIND: Final = "close_package"
OWNER: Final = "close_deliverable_version"
AGENT: Final = "close.package_assembler"
RECORD_TYPE: Final = "derived_rendering"
NO_ASSURANCE: Final = "No assurance is provided."
ASSEMBLE: Final = "closes.assemble_package"
FINISH: Final = "closes.finish_package_assembly"
_TITLES: Final = {"balance_sheet": "Balance Sheet", "income_statement": "Income Statement"}

# The blocks the person's generate computed, handed to C11's body provider inside the same render
# call (the provider sees a tenant only; the package read needs the person's authorisation).
_BODY: contextvars.ContextVar[list[object] | None] = contextvars.ContextVar(
    "close_package_body", default=None
)


def _money(value: Decimal) -> str:
    text_ = f"{abs(value):,.2f}"
    return f"({text_})" if value < 0 else text_


def _table(lines: Sequence[DeliveryStatementLineOut], *, prior: bool) -> dict[str, object]:
    columns = ["", "Current"] + (["Prior"] if prior else [])
    rows = [
        [ln.label, _money(ln.amount)] + ([_money(ln.prior) if ln.prior is not None else ""] if prior else [])
        for ln in lines
    ]
    return {"type": "table", "columns": columns, "rows": rows}


def compose_package(
    package: DeliveryPackageOut, entity_name: str, period_label: str, *, page_numbers: bool
) -> list[object]:
    """The package's DocBlocks (pure): heading, legend when the route carries one, one table per
    statement, the commentary, page numbers on request."""
    blocks: list[object] = [{"type": "heading", "level": 1, "text": entity_name}]
    if package.legend:
        blocks.append({"type": "legend", "text": package.legend})
    first = True
    for key in ("balance_sheet", "income_statement"):
        lines = package.balance_sheet if key == "balance_sheet" else package.income_statement
        if key not in package.sections or not lines:
            continue
        if not first:
            blocks.append({"type": "page_break"})
        first = False
        blocks.append({"type": "heading", "level": 2, "text": _TITLES[key]})
        blocks.append(
            {"type": "paragraph", "runs": [{"type": "text", "text": period_label}]}
        )
        blocks.append(_table(lines, prior=key == "income_statement"))
    if package.commentary and "commentary" in package.sections:
        blocks.append({"type": "page_break"})
        blocks.append({"type": "heading", "level": 2, "text": "Commentary"})
        for para in (p.strip() for p in package.commentary.split("\n\n")):
            if para:
                blocks.append({"type": "paragraph", "runs": [{"type": "text", "text": para}]})
    _ = page_numbers  # C11's financial_statements layout numbers every page (P-11-T07)
    return blocks


def package_workbook(package: DeliveryPackageOut, entity_name: str) -> bytes:
    """The XLSX: the same lines and figures, byte-stable (safe_xlsx)."""
    sheets: list[Sheet] = []
    for key in ("balance_sheet", "income_statement"):
        lines = package.balance_sheet if key == "balance_sheet" else package.income_statement
        if key in package.sections and lines:
            rows: list[list[str]] = [[entity_name, ""], ["Line", "Amount"]]
            rows += [[ln.label, f"{ln.amount:.2f}"] for ln in lines]
            if package.legend:
                rows.append([package.legend, ""])
            sheets.append(Sheet(_TITLES[key], rows))
    return workbook(sheets)


async def _body(_tenant: TenantContext, owner: object, _scope: object) -> Sequence[object]:
    found = _BODY.get()
    return [] if found is None else found


async def _no_values(_owner: object, _scope: object) -> dict[str, str]:
    return {}


async def _release_approval(ref: object) -> tuple[UUID, str] | None:
    """The final render is C-02-T29's release only, with the partner's approval."""
    from abacus.modules.closes.release import release_approval

    return await release_approval(ref)


def ensure_kind() -> None:
    from abacus.modules.reporting import api as c11

    try:
        c11.document_kind(KIND)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=KIND,
                layout="financial_statements",
                variables_provider=_no_values,
                approval_provider=_release_approval,
                retention_record_type=RECORD_TYPE,
                formats=("pdf",),
                body_provider=_body,
            )
        )


_LABEL = text(
    "SELECT c.engagement_id, c.period, c.client_entity_id FROM closes c WHERE c.work_item_id = :c"
)


def period_label(period: str) -> str:
    from datetime import date

    year, month = (int(p) for p in period.split("-"))
    end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return f"As of and for the month ended {end:%B} {end.day}, {end.year}"


async def generate(ctx: AuthContext, close_id: UUID) -> tuple[UUID, int, UUID]:
    """Generate (or regenerate, keeping commentary edits): a DET run, a new version, a DRAFT render.
    Answers (run id, version number, generated document id)."""
    from abacus.modules.agents.api import open_deterministic_run
    from abacus.modules.closes.package_service import edit_commentary, get_package
    from abacus.modules.engagements.api import engagement_hold_facts, engagement_label, get_ref
    from abacus.modules.reporting import api as c11

    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_LABEL, {"c": close_id})).first()
    if row is None:
        raise NotFound("close")
    ref = await get_ref(ctx, row.engagement_id)
    await authorise(ctx, "close_package.generate", ref.resource())
    current = await get_package(ctx, close_id)
    # A new version carrying the commentary exactly as it stands (edited text kept).
    package = await edit_commentary(ctx, close_id, current.commentary or "", current.version)
    label = await engagement_label(ctx.tenant, row.engagement_id)
    facts = await engagement_hold_facts(ctx.tenant, row.engagement_id)
    if label is None or facts is None:
        raise NotFound("engagement")
    entity = label.client_entity_name or label.client_name
    ensure_kind()
    blocks = compose_package(package, entity, period_label(str(row.period)), page_numbers=True)
    token = _BODY.set(blocks)
    try:
        async with uow(ctx.tenant) as tx:
            run_id = await open_deterministic_run(
                tx, tenant_id=ctx.tenant_id, agent_id=AGENT, engagement_id=row.engagement_id,
                initiator=ctx.user_id, task_scope=("close_package.read",),
            )  # fmt: skip
            ticket = await c11.render(
                tx,
                c11.RenderRequest(
                    kind=KIND,
                    owner_ref=c11.OwnerRef(OWNER, close_id),
                    scope=c11.RenderScope(
                        client_id=facts.client_id,
                        engagement_id=row.engagement_id,
                        work_item_id=close_id,
                    ),
                    template_version_id=None,
                    requested_by=c11.Requester("human", user_id=ctx.user_id),
                    formats=("pdf",),
                ),
            )
            await tx.session.execute(
                text(
                    "UPDATE close_deliverables SET status = 'drafting' WHERE close_id = :c "
                    "AND status IN ('draft', 'drafting')"
                ),
                {"c": close_id},
            )
            tx.record(
                "close_package.generated",
                target=Target("close", close_id),
                after=Ref(version=package.version, document=ticket.generated_document_id),
            )
    finally:
        _BODY.reset(token)
    return run_id, package.version, ticket.generated_document_id


async def finish(tenant_id: UUID, close_id: UUID, run_id: UUID, document_id: UUID, version_no: int) -> str:
    """The workflow's second step: once the render job has succeeded (or failed), end the DET run
    and leave the deliverable Draft (or fail the run with the render's code)."""
    from abacus.modules.agents.api import close_deterministic_run
    from abacus.modules.reporting.api import render_outcome

    tenant = TenantContext(tenant_id, "system", f"close_package:{close_id}")
    outcome = await render_outcome(tenant, document_id, version_no)
    if outcome.status in ("queued", "running"):
        raise RuntimeError("render_pending")  # retried by the activity's policy
    async with uow(tenant) as tx:
        await close_deterministic_run(
            tx, run_id,
            output={"generated_document_id": str(document_id), "version_no": version_no},
            failure_code=None if outcome.status == "succeeded" else (outcome.failure_code or "render_failed"),
        )  # fmt: skip
        await tx.session.execute(
            text("UPDATE close_deliverables SET status = 'draft' WHERE close_id = :c AND status = 'drafting'"),
            {"c": close_id},
        )
        tx.record("close_package.assembled", target=Target("close", close_id), after=Ref(ok=int(outcome.status == "succeeded")))
    return outcome.status


async def document_of(tenant: TenantContext, close_id: UUID) -> UUID | None:
    from abacus.modules.reporting.api import OwnerRef, document_of_owner

    return await document_of_owner(tenant, OwnerRef(OWNER, close_id), KIND)


async def page_url(ctx: AuthContext, close_id: UUID, page_no: int) -> tuple[str, int]:
    """P-03's page route for the latest render's PDF (the evidence version the job filed)."""
    from abacus.modules.closes.package_service import get_package
    from abacus.modules.reporting.api import latest_document_version, render_outcome

    await get_package(ctx, close_id)  # authorises close_package.read
    document = await document_of(ctx.tenant, close_id)
    if document is None:
        raise NotFound("close_package_render")
    async with tenant_session(ctx.tenant) as session:
        version_no = await session.scalar(
            text("SELECT max(version_no) FROM generated_document_versions WHERE generated_document_id = :d"),
            {"d": document},
        )
    if version_no is None or await latest_document_version(ctx.tenant, document) is None:
        raise NotFound("close_package_render")
    outcome = await render_outcome(ctx.tenant, document, int(version_no))
    if outcome.evidence_version_id is None or outcome.page_count is None:
        raise NotFound("close_package_render")
    if not 1 <= page_no <= outcome.page_count:
        raise NotFound("close_package_page")
    return f"/v1/evidence-versions/{outcome.evidence_version_id}/pages/{page_no}", outcome.page_count


async def export_xlsx(ctx: AuthContext, close_id: UUID) -> bytes:
    from abacus.modules.closes.package_service import get_package
    from abacus.modules.engagements.api import engagement_label

    package = await get_package(ctx, close_id)
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_LABEL, {"c": close_id})).first()
    label = None if row is None else await engagement_label(ctx.tenant, row.engagement_id)
    entity = "" if label is None else (label.client_entity_name or label.client_name)
    async with uow(ctx.tenant) as tx:
        tx.record("close_package.exported", target=Target("close", close_id), after=Ref(fmt=1))
    return package_workbook(package, entity)


# --- PackageAssemblyWorkflow ---------------------------------------------------------------------


@activity.defn(name=FINISH)
async def finish_activity(given: list[str]) -> str:
    """Draft: end the DET run. Release (C-02-T29, a sixth item "release"): end the run, then
    publish, open the C18 item, send the email and deliver."""
    tenant_id, close_id, run_id, document_id, version_no = given[:5]
    status = await finish(UUID(tenant_id), UUID(close_id), UUID(run_id), UUID(document_id), int(version_no))
    if len(given) > 5 and given[5] == "release" and status == "succeeded":
        from abacus.modules.closes.release import deliver

        return await deliver(UUID(tenant_id), UUID(close_id), UUID(document_id), int(version_no))
    return status


@workflow.defn(name="PackageAssemblyWorkflow")
class PackageAssemblyWorkflow:
    """`close_package:<tenant>:<close>:<version>`: wait for the render job, then end the DET run.
    The generate itself ran in the request (a person's act); this only finishes."""

    @workflow.run
    async def run(self, given: list[str]) -> str:
        return cast(
            str,
            await workflow.execute_activity(
                FINISH,
                given,
                result_type=str,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=1.5,
                    maximum_interval=timedelta(seconds=20),
                    maximum_attempts=30,
                    non_retryable_error_types=["NotFound"],
                ),
            ),
        )


async def start_assembly(
    tenant_id: UUID, close_id: UUID, run_id: UUID, document_id: UUID, version_no: int,
    *, mode: str = "draft",
) -> None:
    from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

    from abacus.kernel.dispatch import dispatch

    await dispatch(
        PackageAssemblyWorkflow,
        [str(tenant_id), str(close_id), str(run_id), str(document_id), str(version_no)]
        + (["release"] if mode == "release" else []),
        id=f"close_package:{tenant_id}:{close_id}:{version_no}:{mode}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


ACTIVITIES: tuple[object, ...] = (finish_activity,)

__all__ = [
    "ACTIVITIES",
    "KIND",
    "PackageAssemblyWorkflow",
    "compose_package",
    "document_of",
    "ensure_kind",
    "export_xlsx",
    "finish",
    "generate",
    "package_workbook",
    "page_url",
    "period_label",
    "start_assembly",
]

