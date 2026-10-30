"""Report templates for C11's routes (P-11-T06; P-11 §3 F1; C11 §1, §2, §4, §7; SPEC-520 AC-1 to
AC-5; ADR-320 §2).

The bundle validation lives here because the DocBlock vocabulary does (`contract.py`); storage,
publication and reads are methodology's (`methodology.api`, firm content). Validation is code,
by path, and lists every problem at once (AC-1):

- `markup_not_allowed` (AC-2): any text that carries markup, a URL or a template expression: an
  HTML or XML tag, a scheme (`http:`, `https:`, `ftp:`, `file:`, `data:`, `javascript:`,
  `mailto:`), `www.`, `{{`, `{%`, `${` or `<%`. Firm templates are structured blocks; the only
  expression is a `var` run naming a declared key.
- `unknown_variable`: a `var` run, or a sample-data key, that names no declared variable.
- `unknown_layout`: a layout key outside C11's six code-owned layouts.
- `clause_conflict`: a clause id declared twice, a clause block naming no declared clause, a
  clause placed twice in the body, or a clause library entry that nests another clause.
- `too_large`: body, clauses and variables over 512 KB as canonical JSON.

`unknown_block` cannot reach this code: the frozen request model is a closed union, so an
unknown block type is refused by request validation (422 with its path) before the route runs
(DEC-1350). The content hash is SHA-256 over canonical JSON (sorted keys, no whitespace) of the
layout, body, clauses, variables and sample data.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from typing import Final, cast, get_args
from uuid import UUID

from abacus.kernel._flags import REPORTING_GENERATED_DOCUMENTS
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.methodology.api import (
    ReportTemplateBundle,
    ReportTemplateVersionView,
    import_report_template,
    publish_report_template,
    report_template_version,
    report_templates_in_firm,
)
from abacus.modules.reporting.contract import (
    ClauseBlock,
    DocBlock,
    EnclosuresBlock,
    HeadingBlock,
    ImportErrorCode,
    ImportErrorOut,
    ImportReportOut,
    KvBlock,
    LayoutKey,
    LegendBlock,
    ListBlock,
    ParagraphBlock,
    ReportTemplateOut,
    ReportTemplateVersionOut,
    Run,
    SectionBlock,
    SignatureBlock,
    TableBlock,
    TemplateImportIn,
    TextRun,
    VarRun,
)

MAX_BYTES: Final = 512 * 1024
LAYOUTS: Final = frozenset(get_args(LayoutKey))
# AC-2: markup, a URL or a template expression anywhere in firm wording.
_MARKUP: Final = re.compile(
    r"<\s*/?\s*[a-z!?][^>]*>|<%|\{\{|\{%|\$\{|\b(?:https?|ftp|file|data|javascript|mailto):"
    r"|\bwww\.",
    re.IGNORECASE,
)


def has_markup(text: str) -> bool:
    return _MARKUP.search(text) is not None


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def content_sha256(body: TemplateImportIn) -> str:
    dumped = body.model_dump(mode="json")
    return hashlib.sha256(
        canonical(
            {k: dumped[k] for k in ("layout_key", "body", "clauses", "variables")}
            | {"sample_data": dumped["sample_data"]}
        )
    ).hexdigest()


class _Walk:
    """One pass over the bundle collecting `(path, code)` problems."""

    def __init__(self, declared: frozenset[str], clause_ids: frozenset[str]) -> None:
        self.declared = declared
        self.clause_ids = clause_ids
        self.placed: set[str] = set()
        self.used: set[str] = set()
        self.errors: list[ImportErrorOut] = []

    def add(self, path: str, code: ImportErrorCode) -> None:
        self.errors.append(ImportErrorOut(path=path[:500], code=code))

    def wording(self, path: str, value: str) -> None:
        if has_markup(value):
            self.add(path, "markup_not_allowed")

    def runs(self, path: str, runs: list[Run]) -> None:
        for i, run in enumerate(runs):
            where = f"{path}[{i}]"
            if isinstance(run, TextRun):
                self.wording(f"{where}.text", run.text)
            elif isinstance(run, VarRun):
                self.used.add(run.key)
                if run.key not in self.declared:
                    self.add(f"{where}.key", "unknown_variable")

    def blocks(self, path: str, blocks: list[DocBlock], *, in_library: bool = False) -> None:
        for i, block in enumerate(blocks):
            self.block(f"{path}[{i}]", block, in_library=in_library)

    def block(self, path: str, block: DocBlock, *, in_library: bool) -> None:
        match block:
            case SectionBlock():
                self.wording(f"{path}.title", block.title)
                self.blocks(f"{path}.blocks", block.blocks, in_library=in_library)
            case HeadingBlock():
                self.wording(f"{path}.text", block.text)
            case ParagraphBlock():
                self.runs(f"{path}.runs", block.runs)
            case ClauseBlock():
                if in_library:
                    self.add(path, "clause_conflict")
                elif block.clause_id not in self.clause_ids or block.clause_id in self.placed:
                    self.add(f"{path}.clause_id", "clause_conflict")
                self.placed.add(block.clause_id)
                self.blocks(f"{path}.blocks", block.blocks, in_library=True)
            case ListBlock():
                for j, item in enumerate(block.items):
                    self.runs(f"{path}.items[{j}]", item)
            case TableBlock():
                for j, column in enumerate(block.columns):
                    self.wording(f"{path}.columns[{j}]", column)
                for j, row in enumerate(block.rows):
                    for k, cell in enumerate(row):
                        self.wording(f"{path}.rows[{j}][{k}]", cell)
            case KvBlock():
                for j, row in enumerate(block.rows):
                    self.wording(f"{path}.rows[{j}].key", row.key)
                    self.runs(f"{path}.rows[{j}].value", row.value)
            case SignatureBlock():
                for j, signer in enumerate(block.signers):
                    self.wording(f"{path}.signers[{j}].label", signer.label)
                    self.runs(f"{path}.signers[{j}].name", signer.name)
            case LegendBlock():
                self.wording(f"{path}.text", block.text)
            case EnclosuresBlock():
                for j, item in enumerate(block.items):
                    self.wording(f"{path}.items[{j}]", item)
            case _:
                pass  # image (an asset id, never a URL) and page_break carry no text


def _duplicates(values: list[str]) -> Iterator[int]:
    seen: set[str] = set()
    for i, value in enumerate(values):
        if value in seen:
            yield i
        seen.add(value)


def validate(body: TemplateImportIn) -> tuple[list[ImportErrorOut], list[str]]:
    """Every problem by path (AC-1, AC-2) and the warnings (declared but unused variables)."""
    declared = frozenset(v.key for v in body.variables)
    clause_ids = frozenset(c.clause_id for c in body.clauses)
    walk = _Walk(declared, clause_ids)
    if body.layout_key not in LAYOUTS:
        walk.add("layout_key", "unknown_layout")
    for field, value in (("name", body.name), ("description", body.description)):
        walk.wording(field, value)
    for i in _duplicates([v.key for v in body.variables]):
        walk.add(f"variables[{i}].key", "unknown_variable")
    for i, variable in enumerate(body.variables):
        walk.wording(f"variables[{i}].label", variable.label)
    for i in _duplicates([c.clause_id for c in body.clauses]):
        walk.add(f"clauses[{i}].clause_id", "clause_conflict")
    for i, clause in enumerate(body.clauses):
        walk.wording(f"clauses[{i}].title", clause.title)
        walk.blocks(f"clauses[{i}].standard", clause.standard, in_library=True)
    walk.blocks("body", body.body)
    for key, value in sorted(body.sample_data.items()):
        if key not in declared:
            walk.add(f"sample_data.{key}", "unknown_variable")
        walk.wording(f"sample_data.{key}", value)
    dumped = body.model_dump(mode="json")
    size = len(canonical({k: dumped[k] for k in ("body", "clauses", "variables")}))
    if size > MAX_BYTES:
        walk.add("", "too_large")
    warnings = [
        f"variable {key} is declared but never used" for key in sorted(declared - walk.used)
    ]
    return walk.errors, warnings


async def _gate(ctx: AuthContext, action: str) -> None:
    """C11's order: a client principal 404, the matrix action, then the flag (404 off)."""
    if ctx.client:
        raise NotFound("generated documents")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, REPORTING_GENERATED_DOCUMENTS):
        raise NotFound(REPORTING_GENERATED_DOCUMENTS.name)


async def import_bundle(
    ctx: AuthContext, body: TemplateImportIn, *, dry_run: bool
) -> ImportReportOut:
    """AC-1: the report; with `dry_run=false` and no error, a stored draft version."""
    await _gate(ctx, "report_template.import")
    errors, warnings = validate(body)
    if errors or dry_run:
        return ImportReportOut(
            ok=not errors, errors=errors, warnings=warnings, draft_version_id=None
        )
    dumped = body.model_dump(mode="json")
    stored = await import_report_template(
        ctx,
        ReportTemplateBundle(
            family=body.family,
            name=body.name,
            description=body.description,
            layout_key=body.layout_key,
            body=cast(list[object], dumped["body"]),
            clauses=cast(list[object], dumped["clauses"]),
            variables=cast(list[object], dumped["variables"]),
            sample_data=cast(dict[str, object], dumped["sample_data"]),
            content_sha256=content_sha256(body),
        ),
    )
    if not stored.created:
        warnings = [*warnings, f"unchanged: version {stored.version_no} already has this content"]
    return ImportReportOut(
        ok=True, errors=[], warnings=warnings, draft_version_id=stored.version_id
    )


def _version_out(view: ReportTemplateVersionView) -> ReportTemplateVersionOut:
    """Stored JSON back through the closed DocBlock union (it was validated on import)."""
    return ReportTemplateVersionOut.model_validate(
        {
            "template_id": view.template_id,
            "version_no": view.version_no,
            "layout_key": view.layout_key,
            "body": view.body,
            "clauses": view.clauses,
            "variables": view.variables,
            "publications": [
                {"action": p.action, "by": p.by, "at": p.at} for p in view.publications
            ],
            "content_sha256": view.content_sha256,
        }
    )


async def version(
    ctx: AuthContext, template_id: UUID, version_no: int
) -> ReportTemplateVersionOut:
    await _gate(ctx, "report_template.read")
    return _version_out(await report_template_version(ctx, template_id, version_no))


async def publish(
    ctx: AuthContext, template_id: UUID, version_no: int
) -> ReportTemplateVersionOut:
    """AC-3, AC-4: human only, fresh second factor, four eyes; republishing rolls back."""
    await _gate(ctx, "report_template.publish")
    await publish_report_template(ctx, template_id, version_no)
    return _version_out(await report_template_version(ctx, template_id, version_no))


async def listing(ctx: AuthContext, family: str | None) -> ListPage[ReportTemplateOut]:
    await _gate(ctx, "report_template.read")
    items = [
        ReportTemplateOut.model_validate(
            {
                "id": t.id,
                "family": t.family,
                "name": t.name,
                "description": t.description,
                "current_version": t.current_version,
                "published_at": t.published_at,
            }
        )
        for t in await report_templates_in_firm(ctx, family)
    ]
    return ListPage[ReportTemplateOut](items=items, total=len(items))
