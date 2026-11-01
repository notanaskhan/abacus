"""The document path of a methodology import (K-01-T21; K-01 §4.2 to §4.4; DEC-1856).

`start_import` hands an import with a Word or PDF file to the Methodology importer through a slot
(`register_document_importer`): the agents module registers `MethodologyImportWorkflow`'s start, so
methodology never imports agents (BOUND-002). With no importer registered, the flag off, or a firm
the importer may not read (not synthetic and the agent not cleared, ADR-112), the start is 409
`importer_not_enabled` and the UI offers the workbook path (AC7.7).

The workflow's activities call back here with identifiers only:

- `import_source` — the import's PDF bytes and its template's name and status, for its run;
- `record_progress` — `pages_done` / `pages_total` after each batch (KNW-02 b's RunCard);
- `finish_document_import` — every batch's steps written as the template's next version in one
  unit of work: programs and steps with `origin = 'importer'`, each step's batch run as
  `proposed_by_run_id` (INV-5), its parse confidence and flag, and its source row (page, quote,
  box, whether code verified the quote on its page); the version lands in Needs review for a
  person to approve (INV-1). Nothing here is mandatory, approved or dated: those are a person's;
- `fail_document_import` — `failed` with a fixed code (`pii_hold`, `source_encrypted`, …).

A cancelled import stays cancelled: every write checks the import is still `parsing` first.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import Actor, AuthContext, Resource, authorise
from abacus.modules.methodology.models import (
    MethodologyImport,
    MethodologySourceFile,
    MethodologySourcePage,
    MethodologyTemplate,
    MethodologyVersion,
    MethodologyVersionEvent,
    Program,
    ProgramStep,
    ProgramStepSource,
)
from abacus.modules.methodology.repository import (
    _land_for_review,  # pyright: ignore[reportPrivateUsage] -- the module's own lifecycle row
    _prior_keys,  # pyright: ignore[reportPrivateUsage] -- the module's own lineage keys
    assign_step_keys,
)
from abacus.modules.methodology.workbook import StepRow
from abacus.modules.platform.api import read_stored

PARSE: Final = "methodology.parse"
SUBJECT: Final = "methodology_import"
CONFIDENCE_FLOOR: Final = Decimal("0.85")
# The level a person sets in review: an imported step starts at testing (the importer never
# sets a level; K-01 §6.1).
IMPORTED_LEVEL: Final = "testing"
_REF: Final = re.compile(r"^(?P<code>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*) step (?P<n>\d{1,3})$")


@dataclass(frozen=True)
class DocumentImporter:
    """`admitted(ctx)`: the importer may read this firm (synthetic, or the agent cleared);
    `start(ctx, import_id)`: dispatch MethodologyImportWorkflow for an import now parsing."""

    admitted: Callable[[AuthContext], Awaitable[bool]]
    start: Callable[[AuthContext, UUID], Awaitable[None]]


_importer: DocumentImporter | None = None


def register_document_importer(importer: DocumentImporter) -> None:
    """The agents module's MethodologyImportWorkflow (once, at its import)."""
    global _importer
    _importer = importer


def document_importer() -> DocumentImporter | None:
    return _importer


class ImportNotParsing(DomainConflict):
    """The import is no longer parsing (cancelled, failed or finished)."""

    code = "import_not_parsing"


@dataclass(frozen=True)
class ImportSource:
    template_name: str
    status: str
    content: bytes
    file_id: UUID


async def _row(session: AsyncSession, import_id: UUID) -> MethodologyImport:
    found = (
        await session.execute(select(MethodologyImport).where(MethodologyImport.id == import_id))
    ).scalar_one_or_none()
    if found is None:
        raise NotFound(SUBJECT)
    return found


async def import_source(agent: Actor, import_id: UUID) -> ImportSource:
    """The import's PDF and its template's name, for the importer's run (`methodology.parse`)."""
    await authorise(agent, PARSE, Resource.firm(agent.tenant_id))
    async with tenant_session(agent.tenant) as session:
        row = await _row(session, import_id)
        template = (
            await session.execute(
                select(MethodologyTemplate.name).where(MethodologyTemplate.id == row.template_id)
            )
        ).scalar_one()
        found = (
            await session.execute(
                select(MethodologySourceFile).where(
                    MethodologySourceFile.import_id == import_id,
                    MethodologySourceFile.role == "document_pdf",
                )
            )
        ).scalar_one_or_none()
    if found is None:
        raise NotFound("methodology_source_file")
    content = await read_stored(
        agent.tenant_id, found.storage_key, found.storage_version_id, found.sha256, found.bytes
    )
    return ImportSource(template, row.status, content, found.id)


async def import_status(tenant: TenantContext, import_id: UUID) -> str:
    async with tenant_session(tenant) as session:
        return (await _row(session, import_id)).status


async def record_progress(
    agent: Actor, import_id: UUID, *, pages_done: int, pages_total: int, run_id: UUID
) -> None:
    """KNW-02 b's progress after a batch; refused once the import is not parsing."""
    await authorise(agent, PARSE, Resource.firm(agent.tenant_id))
    async with uow(agent.tenant) as tx:
        changed = (
            await tx.session.execute(
                update(MethodologyImport)
                .where(MethodologyImport.id == import_id, MethodologyImport.status == "parsing")
                .values(pages_done=pages_done, pages_total=pages_total, agent_run_id=run_id)
                .returning(MethodologyImport.id)
            )
        ).scalar_one_or_none()
        if changed is None:
            raise ImportNotParsing(facts={"import_id": str(import_id)})
        tx.record(
            "methodology_import.progressed",
            target=Target(SUBJECT, import_id),
            after=Ref(pages_done=pages_done, pages_total=pages_total, agent_run_id=run_id),
        )


async def fail_document_import(tenant: TenantContext, import_id: UUID, code: str) -> None:
    """`failed` with a fixed code; a cancelled or finished import is left as it is."""
    async with uow(tenant) as tx:
        await tx.session.execute(
            update(MethodologyImport)
            .where(MethodologyImport.id == import_id, MethodologyImport.status == "parsing")
            .values(status="failed", failure_code=code)
        )
        tx.record("methodology_import.failed", target=Target(SUBJECT, import_id))


# --- the pages -----------------------------------------------------------------------------------

PageWordRow = tuple[str, tuple[float, float, float, float]]


async def store_pages(
    agent: Actor,
    file_id: UUID,
    pages: Sequence[tuple[int, float, float, Sequence[PageWordRow]]],
) -> None:
    """Each page's size and words, once (insert-only; a retried extract finds them stored)."""
    await authorise(agent, PARSE, Resource.firm(agent.tenant_id))
    async with uow(agent.tenant) as tx:
        stored = set(
            (
                await tx.session.execute(
                    select(MethodologySourcePage.page).where(
                        MethodologySourcePage.file_id == file_id
                    )
                )
            ).scalars()
        )
        rows = [
            {
                "tenant_id": agent.tenant_id,
                "file_id": file_id,
                "page": page,
                "width": width,
                "height": height,
                "words": [[text, *box] for text, box in words],
            }
            for page, width, height, words in pages
            if page not in stored
        ]
        if rows:
            await tx.session.execute(insert(MethodologySourcePage), rows)
        tx.record(
            "methodology_source_file.pages_stored",
            target=Target("methodology_source_file", file_id),
            after=Ref(pages=len(rows)),
        )


def _is_word(item: object) -> bool:
    return isinstance(item, list) and len(cast(list[object], item)) == 5


def _word(item: object) -> PageWordRow:
    """A stored word, `[text, x0, top, x1, bottom]`."""
    text, x0, top, x1, bottom = cast(list[object], item)
    return (str(text), (_num(x0), _num(top), _num(x1), _num(bottom)))


def _num(value: object) -> float:
    return float(value) if isinstance(value, (int, float, Decimal, str)) else 0.0


async def stored_pages(
    tenant: TenantContext, file_id: UUID, first: int, last: int
) -> dict[int, list[PageWordRow]]:
    """Pages `first` to `last` as stored: each page's words with their boxes."""
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                select(MethodologySourcePage).where(
                    MethodologySourcePage.file_id == file_id,
                    MethodologySourcePage.page >= first,
                    MethodologySourcePage.page <= last,
                )
            )
        ).scalars()
        out: dict[int, list[PageWordRow]] = {}
        for row in found:
            out[row.page] = [_word(item) for item in row.words if _is_word(item)]
        return out


# --- the parsed steps ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedProgram:
    code: str
    name: str


@dataclass(frozen=True)
class ParsedStep:
    """One step as the importer read it, with code's verification of its quote."""

    program_code: str
    number: int
    text: str
    page: int
    page_to: int
    quote: str
    confidence: Decimal
    run_id: UUID
    verified: bool
    bbox: tuple[float, float, float, float] | None
    refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImportedVersion:
    version_id: UUID
    steps: int
    flags: int
    flag_counts: dict[str, int] = field(default_factory=dict[str, int])


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def flag_of(step: ParsedStep, known: frozenset[tuple[str, int]], gap: bool) -> str | None:
    """The one parse flag a step carries, in order of what a reviewer must check first (K-01
    §4.4): an unverified quote, then a low confidence, a step split across pages, a numbering
    gap before it, a cross-reference to a step that is not in the import."""
    if not step.verified:
        return "unverified_citation"
    if step.confidence < CONFIDENCE_FLOOR:
        return "low_confidence"
    if step.page_to > step.page:
        return "split_across_pages"
    if gap:
        return "numbering_gap"
    for ref in step.refs:
        found = _REF.match(ref)
        if found is None or (found["code"], int(found["n"])) not in known:
            return "cross_reference_missing"
    return None


def assign_flags(kept: Sequence[ParsedStep]) -> list[str | None]:
    """Each kept step's flag (`ordered`'s output): a gap is a number past the previous one + 1."""
    known = frozenset((s.program_code, s.number) for s in kept)
    previous: dict[str, int] = {}
    flags: list[str | None] = []
    for step in kept:
        gap = step.number > previous.get(step.program_code, 0) + 1
        previous[step.program_code] = step.number
        flags.append(flag_of(step, known, gap))
    return flags


def ordered(programs: Sequence[ParsedProgram], steps: Sequence[ParsedStep]) -> list[ParsedStep]:
    """Steps by program (in the order the programs were read) and number. A step read twice (a
    batch's last page, read again as the next batch's context) is kept once: the fuller reading,
    the one that runs to the later page, since the first batch could not see where it ended."""
    position: dict[str, int] = {}
    for p in programs:  # a heading read twice (a batch's context page) keeps its first place
        position.setdefault(p.code, len(position))
    seen: set[tuple[str, int]] = set()
    kept: list[ParsedStep] = []
    for step in sorted(
        steps,
        key=lambda s: (
            position.get(s.program_code, len(position)),
            s.number,
            s.page,
            -s.page_to,
            -len(s.text),
        ),
    ):
        key = (step.program_code, step.number)
        if key in seen:
            continue
        seen.add(key)
        kept.append(step)
    return kept


def _programs_of(
    programs: Sequence[ParsedProgram], steps: Sequence[ParsedStep]
) -> list[ParsedProgram]:
    """Every program a step names, in reading order; one named only by a step takes its code."""
    out: dict[str, ParsedProgram] = {}
    for p in programs:
        out.setdefault(p.code, p)
    for s in steps:
        out.setdefault(s.program_code, ParsedProgram(s.program_code, s.program_code))
    return list(out.values())


async def finish_document_import(
    agent: Actor,
    import_id: UUID,
    programs: Sequence[ParsedProgram],
    steps: Sequence[ParsedStep],
) -> ImportedVersion:
    """Every batch's steps as the template's next version, in Needs review, in one unit of work."""
    await authorise(agent, PARSE, Resource.firm(agent.tenant_id))
    kept = ordered(programs, steps)
    async with uow(agent.tenant) as tx:
        row = await _row(tx.session, import_id)
        if row.status != "parsing":
            raise ImportNotParsing(facts={"import_id": str(import_id)})
        source = (
            await tx.session.execute(
                select(MethodologySourceFile).where(
                    MethodologySourceFile.import_id == import_id,
                    MethodologySourceFile.role == "document_pdf",
                )
            )
        ).scalar_one()
        latest = await tx.session.scalar(
            select(func.max(MethodologyVersion.version)).where(
                MethodologyVersion.template_id == row.template_id
            )
        )
        number = (latest or 0) + 1
        version_id = uuid4()
        fingerprint = hashlib.sha256(source.sha256.encode()).hexdigest()
        await tx.session.execute(
            insert(MethodologyVersion).values(
                id=version_id,
                tenant_id=agent.tenant_id,
                template_id=row.template_id,
                version=number,
                source_fingerprint=fingerprint,
                imported_by=row.started_by,
                label=f"v{number}",
                origin="document_import",
            )
        )
        program_ids: dict[str, UUID] = {}
        for position, program in enumerate(_programs_of(programs, kept)):
            program_ids[program.code] = (
                await tx.session.execute(
                    insert(Program)
                    .values(
                        tenant_id=agent.tenant_id,
                        version_id=version_id,
                        code=program.code,
                        name=program.name[:200],
                        position=position,
                    )
                    .returning(Program.id)
                )
            ).scalar_one()
        keys = assign_step_keys(
            [StepRow(s.program_code, s.number, s.text, IMPORTED_LEVEL) for s in kept],
            await _prior_keys(tx.session, row.template_id, number),
        )
        counts: dict[str, int] = {}
        rows: list[dict[str, object]] = []
        sources: list[dict[str, object]] = []
        for step, key, flag in zip(kept, keys, assign_flags(kept), strict=True):
            if flag is not None:
                counts[flag] = counts.get(flag, 0) + 1
            step_id = uuid4()
            rows.append(
                {
                    "id": step_id,
                    "tenant_id": agent.tenant_id,
                    "version_id": version_id,
                    "program_id": program_ids[step.program_code],
                    "step_key": key,
                    "number": step.number,
                    "text": step.text[:4000],
                    "assertions": [],
                    "standard_refs": [],
                    "level": IMPORTED_LEVEL,
                    "mandatory": False,
                    "prepopulates": [],
                    "depends_on_step_keys": [],
                    "origin": "importer",
                    "proposed_by_run_id": step.run_id,
                    "parse_confidence": step.confidence.quantize(Decimal("0.001")),
                    "parse_flag": flag,
                }
            )
            sources.append(
                {
                    "tenant_id": agent.tenant_id,
                    "step_id": step_id,
                    "source_file_id": source.id,
                    "page_from": step.page,
                    "page_to": step.page_to,
                    "bbox": None if step.bbox is None else list(step.bbox),
                    "quote": step.quote[:400],
                    "verified": step.verified,
                    "verify_reason": None if step.verified else "quote_not_found",
                }
            )
        if rows:
            await tx.session.execute(insert(ProgramStep), rows)
            await tx.session.execute(insert(ProgramStepSource), sources)
        await _land_for_review(
            tx.session,
            agent.tenant_id,
            row.template_id,
            version_id,
            None,  # the importer's session: an event's actor must be the session's (0180)
            "document_import",
        )
        await tx.session.execute(
            update(MethodologyImport)
            .where(MethodologyImport.id == import_id)
            .values(status="needs_review", version_id=version_id)
        )
        await tx.session.execute(
            insert(MethodologyVersionEvent).values(
                tenant_id=agent.tenant_id,
                version_id=version_id,
                kind="import_started",
                actor_user_id=None,
                facts={
                    "import_id": str(import_id),
                    "initiated_by": str(row.started_by),
                    "steps": len(rows),
                    "flags": sum(counts.values()),
                },
            )
        )
        tx.record(
            "methodology_import.needs_review",
            target=Target(SUBJECT, import_id),
            after=Ref(version_id=version_id, steps=len(rows), flags=sum(counts.values())),
        )
    return ImportedVersion(version_id, len(rows), sum(counts.values()), counts)


def verify_quote(
    quote: str, words: Sequence[tuple[str, tuple[float, float, float, float]]]
) -> tuple[bool, tuple[float, float, float, float] | None]:
    """Whether `quote` is printed on the page (whitespace and case aside, NFKC) and the box around
    its words; a quote that is not there is unverified and its citation is never shown (INV-2)."""
    target = _normal(quote).split()
    if not target:
        return False, None
    normal = [(_normal(text), box) for text, box in words]
    tokens = [t for t, _ in normal]
    for start in range(len(tokens) - len(target) + 1):
        if tokens[start : start + len(target)] == target:
            boxes = [b for _, b in normal[start : start + len(target)]]
            return True, (
                min(b[0] for b in boxes),
                min(b[1] for b in boxes),
                max(b[2] for b in boxes),
                max(b[3] for b in boxes),
            )
    return False, None
