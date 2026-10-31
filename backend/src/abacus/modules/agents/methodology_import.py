"""The Methodology importer (K-01-T21; K-01 §4.4, §6; DEC-1856). PROTECTED.

`POST /v1/methodology/imports/{id}/start` with a PDF hands the import to this capability through
methodology's document-importer slot (registered below): the firm must be one the importer may
read (synthetic, or the agent cleared for client data, ADR-112; else 409 `importer_not_enabled`),
then `MethodologyImportWorkflow` (`methodology-import-v1`, background class) runs:

1. `extract_pages`: the import's own run reads every page in `kernel.pdf_pages`' isolated child
   (methodology's `extract_source`), stores each page's size and words (`methodology_source_pages`)
   and applies the PII hold: an unmasked SSN, ITIN or EIN anywhere fails the import `pii_hold`
   before any model call. An encrypted or malformed file fails it with its code.
2. `parse_batch` once per eight pages: a run each, through `ai_gateway` with the registered prompt
   `methodology.import_parse@v1`; the pages go in one `<untrusted name="document">` block (ADR-052)
   and the answer must be `ImportBatchOutput` (no mandatory, approval, level or date field). The
   output is kept on the batch's run; progress is written after each batch. A cancelled import
   stops the loop; a budget or boundary refusal fails it.
3. `finish`: code verifies every quote on its page (the box is the quote's words' boxes), sets each
   step's flag and writes the template's next version, in Needs review, through `methodology.api`
   with each step's batch run as its proposer (INV-1, INV-2, INV-5).

The importer proposes; a person reviews the flags and approves the version (KNW-02).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from contextlib import suppress
from decimal import Decimal
from typing import Final, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.ai_gateway import (
    AssembledContext,
    Attribution,
    ContextBuilder,
    GatewayCall,
    ModelRequest,
    call,
    is_synthetic,
)
from abacus.kernel.db import tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.handoff import ImportBatchOutput, ImportedStep
from abacus.modules.agents.repository import finish_run, get_run, insert_run
from abacus.modules.agents.service import (
    _reader,  # pyright: ignore[reportPrivateUsage] -- the module's own system reader
    fail_run,
    load_agent_context,
)
from abacus.modules.agents.spec import cleared_for_client_data, spec
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.agents.upload_review import TERMINAL
from abacus.modules.agents.workflow_types import (
    ImportBatchInput,
    ImportBatchOutcome,
    ImportFailInput,
    ImportFinishInput,
    ImportPagesOutcome,
    MethodologyImportInput,
)
from abacus.modules.identity.api import AgentContext, AuthContext
from abacus.modules.methodology.api import (
    DocumentImporter,
    ParsedProgram,
    ParsedStep,
    extract_source,
    fail_document_import,
    finish_document_import,
    import_source,
    import_status,
    record_progress,
    register_document_importer,
    store_pages,
    stored_pages,
    verify_quote,
)

IMPORTER: Final = "methodology.importer"
PROMPT: Final = "methodology.import_parse@v1"
BATCH_PAGES: Final = 8
UNTRUSTED_DOCUMENT: Final = '<untrusted name="document">'


def batches(page_count: int, size: int = BATCH_PAGES) -> list[tuple[int, int]]:
    """Pages 1 to `page_count` in runs of `size`: (1, 8), (9, 16), …"""
    return [(first, min(first + size - 1, page_count)) for first in range(1, page_count + 1, size)]


def page_lines(words: Sequence[tuple[str, tuple[float, float, float, float]]]) -> str:
    """A page's text in reading order: words on one top are a line, lines top to bottom."""
    rows: dict[int, list[tuple[float, str]]] = {}
    for text, box in words:
        rows.setdefault(round(box[1] * 1000), []).append((box[0], text))
    return "\n".join(" ".join(t for _, t in sorted(row)) for _, row in sorted(rows.items()))


# --- admission and start (methodology's slot) ---------------------------------------------------


async def admitted(ctx: AuthContext) -> bool:
    """The importer may read this firm: synthetic, or the agent cleared for client data (its spec
    says `none` today, so real firms wait for clearance; ADR-112)."""
    return await is_synthetic(ctx.tenant) or cleared_for_client_data(IMPORTER)


def workflow_id(tenant_id: UUID, import_id: UUID) -> str:
    return f"methodology-import:{tenant_id}:{import_id}"


async def start(ctx: AuthContext, import_id: UUID) -> None:
    from abacus.modules.agents.methodology_import_workflow import MethodologyImportWorkflow

    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            MethodologyImportWorkflow,
            MethodologyImportInput(str(ctx.tenant_id), str(import_id), str(ctx.user_id)),
            id=workflow_id(ctx.tenant_id, import_id),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


register_document_importer(DocumentImporter(admitted, start))


# --- runs ----------------------------------------------------------------------------------------


async def _run_for(tenant_id: UUID, requested_by: UUID, key: str) -> UUID:
    """The importer's run for this import step, once (a retried activity finds it)."""
    importer = spec(IMPORTER)
    reader = _reader(tenant_id, f"agents:{importer.id}")
    event = uuid5(NAMESPACE_URL, f"abacus:methodology-import:{key}")
    try:
        async with uow(reader) as tx:
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=importer.id,
                shadow=await starts_in_shadow(tx.session, reader, importer.id),
                spec_version=importer.version,
                engagement_id=None,
                evidence_version_id=None,
                initiator_user_id=requested_by,
                source_event_id=event,
                task_scope=sorted(importer.task_scope),
            )
            if run_id is not None:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(initiator=requested_by),
                )
                return run_id
    except MissingAuditEvent:
        pass
    from abacus.modules.agents.repository import run_for_event

    async with tenant_session(reader) as session:
        found = await run_for_event(session, importer.id, event)
    if found is None:
        raise RuntimeError("the importer's run could not be created")
    return found.id


async def _end(tenant_id: UUID, run_id: UUID, output: dict[str, object] | None = None) -> None:
    try:
        async with uow(_reader(tenant_id, f"agent-run:{run_id}")) as tx:
            if await finish_run(tx.session, run_id, status="completed", output=output):
                tx.record("agent_run.completed", target=Target("agent_run", run_id))
    except MissingAuditEvent:
        pass


# --- 1. extract ----------------------------------------------------------------------------------


async def extract_pages(input: MethodologyImportInput) -> ImportPagesOutcome:
    tenant_id, import_id = UUID(input.tenant_id), UUID(input.import_id)
    run_id = await _run_for(tenant_id, UUID(input.requested_by), f"{import_id}:extract")
    agent = await load_agent_context(tenant_id, run_id)
    source = await import_source(agent, import_id)
    try:
        found = await extract_source(source.content)
    except DomainInvalid as exc:
        await fail_document_import(agent.tenant, import_id, exc.code)
        await fail_run(tenant_id, run_id, exc.code)
        return ImportPagesOutcome(0, held=True)
    if found.hold.held:  # before any model call (K-01-T20)
        await fail_document_import(agent.tenant, import_id, "pii_hold")
        await fail_run(tenant_id, run_id, "pii_hold")
        return ImportPagesOutcome(found.page_count, held=True)
    await store_pages(
        agent,
        source.file_id,
        [(p.page, p.width, p.height, [(w.text, w.box) for w in p.words]) for p in found.pages],
    )
    await record_progress(
        agent, import_id, pages_done=0, pages_total=found.page_count, run_id=run_id
    )
    await _end(tenant_id, run_id)
    return ImportPagesOutcome(found.page_count, held=False)


# --- 2. parse one batch --------------------------------------------------------------------------


def build_context(
    template: str, first: int, last: int, count: int, pages: dict[int, str]
) -> AssembledContext:
    return (
        ContextBuilder()
        .text(
            "engagement", f"Methodology template {template}. Pages {first} to {last} of {count}."
        )
        .task(
            {"document": [{"page": n, "text": pages[n]} for n in sorted(pages)]},
            untrusted=["document"],
        )
        .build()
    )


async def parse_batch(input: ImportBatchInput) -> ImportBatchOutcome:
    tenant_id, import_id = UUID(input.tenant_id), UUID(input.import_id)
    if await import_status(_reader(tenant_id, "agents:importer"), import_id) != "parsing":
        return ImportBatchOutcome(None, stop=True)  # cancelled, failed or finished
    key = f"{import_id}:batch:{input.first_page}"
    run_id = await _run_for(tenant_id, UUID(input.requested_by), key)
    agent = await load_agent_context(tenant_id, run_id)
    importer = spec(IMPORTER)
    source = await import_source(agent, import_id)
    words = await stored_pages(agent.tenant, source.file_id, input.first_page, input.last_page)
    total = max(words) if words else input.last_page
    context = build_context(
        source.template_name,
        input.first_page,
        input.last_page,
        total,
        {n: page_lines(w) for n, w in words.items()},
    )
    try:
        result = await call(
            GatewayCall(
                purpose=importer.purpose,
                prompt=importer.prompt,
                tier=importer.tier,
                output_schema=ImportBatchOutput,
                budget_usd=importer.limits.max_cost_usd,
                attribution=Attribution(agent.tenant, None, importer.id, run_id),
                context=context,
                work_class=importer.work_class,
                essential=importer.essential,
                routes=importer.routes,
                cheaper_tiers=importer.cheaper_tiers,
                max_output_tokens=importer.limits.max_output_tokens,
                timeout_seconds=importer.limits.max_seconds,
            )
        )
    except tuple(TERMINAL) as exc:
        code = next(c for kind, c in TERMINAL.items() if isinstance(exc, kind))
        await fail_run(tenant_id, run_id, code)
        await fail_document_import(agent.tenant, import_id, code)
        return ImportBatchOutcome(str(run_id), stop=True)
    output = result.output
    await _end(tenant_id, run_id, None if output is None else output.model_dump(mode="json"))
    await record_progress(
        agent, import_id, pages_done=input.last_page, pages_total=total, run_id=run_id
    )
    return ImportBatchOutcome(str(run_id), stop=False)


# --- 3. verify and finish ------------------------------------------------------------------------


async def finish(input: ImportFinishInput) -> str:
    """Code verifies every quote on its page, then the version is written in Needs review."""
    tenant_id, import_id = UUID(input.tenant_id), UUID(input.import_id)
    reader = _reader(tenant_id, "agents:importer")
    outputs: list[tuple[UUID, ImportBatchOutput]] = []
    async with tenant_session(reader) as session:
        for raw in input.run_ids:
            run = await get_run(session, UUID(raw))
            if run is not None and run.agent_id == IMPORTER and run.output is not None:
                outputs.append((run.id, ImportBatchOutput.model_validate(run.output)))
    if not outputs:
        await fail_document_import(reader, import_id, "nothing_parsed")
        return "failed"
    first_run = outputs[0][0]
    agent = await _finishing_context(tenant_id, import_id, first_run)
    source = await import_source(agent, import_id)
    pages = await stored_pages(agent.tenant, source.file_id, 1, 10_000)
    programs: list[ParsedProgram] = []
    steps: list[ParsedStep] = []
    for run_id, output in outputs:
        programs += [ParsedProgram(p.code, p.name) for p in output.programs]
        steps += [_parsed(s, run_id, pages) for s in output.steps]
    done = await finish_document_import(agent, import_id, programs, steps)
    await _end(
        tenant_id,
        agent.agent_run_id,
        {"version_id": str(done.version_id), "steps": done.steps, "flags": done.flags},
    )
    return "needs_review"


async def _finishing_context(tenant_id: UUID, import_id: UUID, after: UUID) -> AgentContext:
    """The finish step's own run, attributed to the import's initiator (from a batch run)."""
    async with tenant_session(_reader(tenant_id, "agents:importer")) as session:
        batch = await get_run(session, after)
    if batch is None:
        raise RuntimeError("the batch run is gone")
    run_id = await _run_for(tenant_id, batch.initiator_user_id, f"{import_id}:finish")
    return await load_agent_context(tenant_id, run_id)


def _parsed(
    step: ImportedStep,
    run_id: UUID,
    pages: dict[int, list[tuple[str, tuple[float, float, float, float]]]],
) -> ParsedStep:
    verified, bbox = verify_quote(step.quote, pages.get(step.page, []))
    return ParsedStep(
        program_code=step.program_code,
        number=step.number,
        text=step.text,
        page=step.page,
        page_to=max(step.page_to or step.page, step.page),
        quote=step.quote,
        confidence=Decimal(str(step.confidence)),
        run_id=run_id,
        verified=verified,
        bbox=bbox,
        refs=tuple(step.refs),
    )


async def fail(input: ImportFailInput) -> None:
    await fail_document_import(
        _reader(UUID(input.tenant_id), "agents:importer"), UUID(input.import_id), input.code
    )


# --- the fake model's answer (local runs and tests only) -----------------------------------------

_HEADING: Final = re.compile(r"^(?P<code>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{2,4})\s+(?P<name>\S.*)$")
_STEP: Final = re.compile(r"^(?P<n>\d{1,3})\.\s+(?P<text>\S.*)$")
_REFS: Final = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{2,4} step \d{1,3}")
_UNSURE: Final = "(as applicable)"


def fake_parse(request: ModelRequest) -> str:
    """Reads the document block the way a careful importer would: headings `BH-EBP-110 Name`,
    steps `7. Text`, a step's following lines (onto the next page too) as its text, the first six
    words as the quote, low confidence where the text says "(as applicable)"."""
    block = request.user.split(UNTRUSTED_DOCUMENT, 1)[1].split("</untrusted>", 1)[0]
    pages = cast(list[dict[str, object]], json.loads(block))
    programs: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    program: str | None = None
    current: dict[str, object] | None = None
    for entry in pages:
        number = cast(int, entry["page"])
        for line in str(entry["text"]).splitlines():
            line = line.strip()
            heading = _HEADING.match(line)
            step = _STEP.match(line)
            if heading is not None:
                program = heading["code"]
                programs.append({"code": program, "name": heading["name"]})
                current = None
            elif step is not None and program is not None:
                current = {
                    "program_code": program,
                    "number": int(step["n"]),
                    "text": step["text"],
                    "page": number,
                    "quote": " ".join(step["text"].split()[:6]),
                    "confidence": 0.97,
                    "refs": [],
                }
                steps.append(current)
            elif current is not None and line:
                current["text"] = f"{current['text']} {line}"
                if number != current["page"]:
                    current["page_to"] = number
    for s in steps:
        text = str(s["text"])
        s["refs"] = _REFS.findall(text)
        if _UNSURE in text:
            s["confidence"] = 0.6
    return json.dumps({"programs": programs, "steps": steps})
