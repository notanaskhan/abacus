"""The agent's files tools (P-10-T38; SPEC-647 AC-P1 to AC-P6; C17; ADR P-35, ADR-005, ADR-042,
ADR-050; DEC-3402). PROTECTED (agents).

Three tools, one per kind a write passes through:

- `files.build_workbook` (compute, `file.propose`): the run's workbook from sheets the run's own
  steps computed (code computes every figure, ADR-050), built deterministically and stored under
  Object Lock (`evidence.api.store_workbook`), recorded as the run's draft artifact with the
  citations it rests on. Its id is derived from the run and the bytes, so a retried call records
  nothing twice. Nothing is filed.
- `files.propose_save` (propose, `file.propose`): "Save to Files" as a `file_save` proposal on the
  run's engagement (the P-04 review API, `create_proposal`): one row naming the artifact and the
  folder, carrying the artifact's citations, so an approval with an unverified one answers 422
  `uncited_change` (AC-P4). The run's `writes_waiting` counts it.
- `files.save_approved` (approved_write, `file.save`, reached with `file.propose`): files the
  approved copy (`evidence.api.file_approved_copy`). The runtime has already consumed the person's
  grant for exactly this call (`identity.consume_grant`: after `not_before`, unvoided, the approver
  still holding `file.save`), so the copy is recorded "<approver> via Agent" with the grant's id.

The agent never approves, saves on its own, voids or consumes a grant for itself (AC-P6): the
grant is issued in the approving person's unit of work (`proposals.approve_proposal`) and spent
only by the runtime for the call it was issued for (`approved_writes.py`).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated, Final, Literal, cast
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.agent_tools import ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.safe_xlsx import Sheet
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.proposals import ProposedRow, create_proposal
from abacus.modules.engagements.api import client_of
from abacus.modules.evidence.api import file_approved_copy, store_workbook, stored_object
from abacus.modules.identity.api import AgentContext, consumed_grant

Int = classified("internal")
Conf = classified("confidential")
FILE_SAVE: Final = "file_save"  # the proposal kind
PROPOSE: Final = "file.propose"
SAVE: Final = "file.save"
SAVE_TOOL: Final = "files.save_approved"
_ARTIFACTS: Final = UUID("c11f11e5-0b38-5d2a-9e61-3a7c0de0f001")
Folder = Literal["deliverables", "workpapers", "correspondence"]
FOLDER_LABELS: Final = {
    "deliverables": "Deliverables",
    "workpapers": "Workpapers",
    "correspondence": "Correspondence",
}
CellValue = str | int | Decimal | bool | None


def _agent(caller: ToolCaller) -> AgentContext:
    if not isinstance(caller, AgentContext):
        raise NotFound("agent_run")
    return caller


def _engagement(agent: AgentContext) -> UUID:
    if agent.engagement_id is None:  # a firm-level run has no Files to save into (DEC-3402)
        raise DomainInvalid("engagement_required")
    return agent.engagement_id


class SheetIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: Annotated[str, Field(min_length=1, max_length=31), Conf]
    rows: Annotated[list[list[CellValue]], Field(max_length=5_000), classified("restricted")] = (
        Field(default_factory=list)
    )


class BuildWorkbookIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, Field(min_length=1, max_length=120), Conf]
    sheets: Annotated[list[SheetIn], Field(min_length=1, max_length=12), Conf]
    citation_ids: Annotated[list[UUID], Field(max_length=200), Int] = Field(default_factory=list)


class BuildWorkbookOut(BaseModel):
    artifact_id: Annotated[UUID, Int]
    size_bytes: Annotated[int, Field(ge=0), Int]
    sha256: Annotated[str, Int]


class ProposeSaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: Annotated[UUID, Int]
    folder: Annotated[Folder, Int] = "deliverables"

    def tool_targets(self, agent: AgentContext) -> object:
        from abacus.modules.agents.tools.runtime import ToolTargets

        engagement = agent.engagement_id
        return ToolTargets(engagement_ids=(engagement,) if engagement is not None else ())


class ProposeSaveOut(BaseModel):
    proposal_id: Annotated[UUID, Int]


class SaveApprovedIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: Annotated[UUID, Int]

    def tool_targets(self, agent: AgentContext) -> object:
        from abacus.modules.agents.tools.runtime import ToolTargets

        engagement = agent.engagement_id
        return ToolTargets(engagement_ids=(engagement,) if engagement is not None else ())


class SaveApprovedOut(BaseModel):
    evidence_version_id: Annotated[UUID, Int]
    grant_id: Annotated[UUID, Int]


def _xlsx_name(name: str) -> str:
    return name if name.lower().endswith(".xlsx") else f"{name}.xlsx"


async def build_workbook(caller: ToolCaller, args: BuildWorkbookIn) -> BuildWorkbookOut:
    """The run's workbook as its draft artifact (WB-03d "TY2025 Season Progress — by office")."""
    agent = _agent(caller)
    sheets = [Sheet(s.title, [list(r) for r in s.rows]) for s in args.sheets]
    stored = await store_workbook(agent.tenant_id, sheets)
    name = _xlsx_name(args.name)
    artifact = uuid5(_ARTIFACTS, f"{agent.agent_run_id}:{stored.fingerprint}:{name}")
    cites = sorted({str(c) for c in args.citation_ids})
    async with uow(agent.tenant) as tx:
        inserted = (
            await tx.session.execute(
                text(
                    "INSERT INTO run_artifacts (id, tenant_id, run_id, kind, name, size_bytes, "
                    "storage_key, storage_version_id, sha256, cites) VALUES (:id, :t, :run, "
                    "'xlsx', :name, :size, :key, :version, :sha, CAST(:cites AS jsonb)) "
                    "ON CONFLICT (id) DO NOTHING RETURNING id"
                ),
                {
                    "id": artifact,
                    "t": agent.tenant_id,
                    "run": agent.agent_run_id,
                    "name": name,
                    "size": stored.size,
                    "key": stored.key,
                    "version": stored.version_id,
                    "sha": stored.fingerprint,
                    "cites": json.dumps(cites),
                },
            )
        ).first()
        if inserted is not None:
            tx.record(
                "run_artifact.created",
                target=Target("agent_run", agent.agent_run_id),
                after=Ref(artifact=artifact, size=stored.size),
                scope=Scope(engagement_id=agent.engagement_id),
            )
    return BuildWorkbookOut(
        artifact_id=artifact, size_bytes=stored.size, sha256=stored.fingerprint
    )


_ARTIFACT: Final = text(
    "SELECT id, run_id, name, size_bytes, storage_key, storage_version_id, sha256, state, cites "
    "FROM run_artifacts WHERE id = :id AND run_id = :run"
)


async def _artifact(tenant: TenantContext, run_id: UUID, artifact_id: UUID) -> object:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ARTIFACT, {"id": artifact_id, "run": run_id})).first()
    if row is None:
        raise NotFound("run_artifact")
    return row


async def artifact_engagement(tenant: TenantContext, artifact_id: UUID) -> UUID | None:
    """The proposal target's engagement (P-04-T24 M4: every target is the engagement's)."""
    async with tenant_session(tenant) as session:
        return cast(
            UUID | None,
            await session.scalar(
                text(
                    "SELECT r.engagement_id FROM run_artifacts a JOIN agent_runs r "
                    "ON r.id = a.run_id WHERE a.id = :id"
                ),
                {"id": artifact_id},
            ),
        )


async def propose_save(caller: ToolCaller, args: ProposeSaveIn) -> ProposeSaveOut:
    """WB-03d's "Save to Files" card: a `file_save` proposal a person decides."""
    agent = _agent(caller)
    engagement = _engagement(agent)
    row = await _artifact(agent.tenant, agent.agent_run_id, args.artifact_id)
    if row.state != "draft":
        raise DomainInvalid("artifact_not_draft")
    name = cast(str, row.name)
    cites = tuple(UUID(str(c)) for c in cast(list[str], row.cites or []))
    proposal = await create_proposal(
        agent,
        engagement_id=engagement,
        kind=FILE_SAVE,
        title=f"Save to Files: {name}",
        rows=[
            ProposedRow(
                target_type="run_artifact",
                target_id=args.artifact_id,
                field_key="saved_to",
                label="Save to Files",
                before=None,
                after={"t": "text", "v": f"{FOLDER_LABELS[args.folder]} \u203a {name}"},
                cause="file_save",
                citation_ids=cites,
            )
        ],
        set_ref={"artifact_id": str(args.artifact_id), "folder": args.folder},
    )
    async with uow(agent.tenant) as tx:
        await tx.session.execute(
            text("UPDATE agent_runs SET writes_waiting = writes_waiting + 1 WHERE id = :run"),
            {"run": agent.agent_run_id},
        )
        tx.record(
            "agent_run.write_proposed",
            target=Target("agent_run", agent.agent_run_id),
            after=Ref(proposal=proposal),
            scope=Scope(engagement_id=engagement),
        )
    return ProposeSaveOut(proposal_id=proposal)


_PROPOSAL: Final = text(
    "SELECT p.id, p.kind, p.state, p.agent_run_id, p.engagement_id, p.set_ref "
    "FROM proposals p WHERE p.id = :id"
)


async def save_approved(caller: ToolCaller, args: SaveApprovedIn) -> SaveApprovedOut:
    """The approved copy into Files, "<approver> via Agent" (AC-P1). Reached only after the
    runtime consumed the grant for this call."""
    agent = _agent(caller)
    engagement = _engagement(agent)
    async with tenant_session(agent.tenant) as session:
        proposal = (await session.execute(_PROPOSAL, {"id": args.proposal_id})).first()
    if (
        proposal is None
        or proposal.kind != FILE_SAVE
        or proposal.agent_run_id != agent.agent_run_id
        or proposal.engagement_id != engagement
        or proposal.state not in ("approved", "approved_with_edits")
    ):
        raise NotFound("proposal")
    found = await consumed_grant(agent.tenant_id, Target("proposal", args.proposal_id), SAVE)
    if found is None:
        raise NotFound("approval_grant")
    grant_id, approver = found
    ref = cast(dict[str, str], proposal.set_ref or {})
    row = await _artifact(agent.tenant, agent.agent_run_id, UUID(ref["artifact_id"]))
    stored = stored_object(
        agent.tenant_id,
        cast(str, row.storage_key),
        cast(str, row.storage_version_id),
        cast(str, row.sha256),
        int(cast(int, row.size_bytes)),
    )
    client = await client_of(agent.tenant, engagement)
    if client is None:
        raise NotFound("engagement")
    acting = TenantContext(
        agent.tenant_id, "agent", agent.tenant.actor_id, on_behalf_of_user_id=approver
    )
    async with uow(acting) as tx:
        version = await file_approved_copy(
            tx,
            tenant_id=agent.tenant_id,
            engagement_id=engagement,
            client_id=client,
            title=cast(str, row.name),
            folder_kind=ref.get("folder", "deliverables"),
            stored=stored,
            grant_id=grant_id,
            requested_by=approver,
        )
        await tx.session.execute(
            text(
                "UPDATE run_artifacts SET state = 'saved', saved_to = CAST(:to AS jsonb) "
                "WHERE id = :id AND state = 'draft'"
            ),
            {"id": row.id, "to": json.dumps({"evidence_version_id": str(version)})},
        )
        await tx.session.execute(
            text(
                "UPDATE agent_runs SET writes_done = writes_done + 1, "
                "writes_waiting = greatest(writes_waiting - 1, 0) WHERE id = :run"
            ),
            {"run": agent.agent_run_id},
        )
    return SaveApprovedOut(evidence_version_id=version, grant_id=grant_id)


FILE_TOOLS: Final = (
    ToolDecl(
        "files.build_workbook", "compute", PROPOSE, "confidential", BuildWorkbookIn,
        BuildWorkbookOut, build_workbook,
    ),
    ToolDecl(
        "files.propose_save", "propose", PROPOSE, "confidential", ProposeSaveIn, ProposeSaveOut,
        propose_save,
    ),
    ToolDecl(
        SAVE_TOOL, "approved_write", SAVE, "confidential", SaveApprovedIn, SaveApprovedOut,
        save_approved, scope_action=PROPOSE,
    ),
)  # fmt: skip
