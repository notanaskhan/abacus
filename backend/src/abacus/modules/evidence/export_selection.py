"""What an engagement export holds (A-01-T19; SPEC-344 §6, §7.2, §7.3; DEC-379, DEC-433).
PROTECTED.

The selection is read as the requester, never as the system: the scope's asked PBC binders'
requests through `requests.api.source_documents` (`visible()`, walls, independence), and each
request's live files with their effective review decision (a withdrawn or voided version is
never read). By default only accepted files go in; with `include_unaccepted` a file nobody has
decided goes in too and its row reads "Uploaded, needs review (not accepted)". Rejected and sent
back files never do.

Archive paths (`evidence/NN Category/NN Request/vN__file`) are built from hostile names: each
segment NFC, separators, control and format characters replaced, `.` and `..` impossible, TIN
forms masked, trimmed so the path stays within 180 characters, and duplicates (compared without
case) de-duplicated with `~2`, `~3`. Every path passes `archive_path_problem` or the build stops.

Code computes everything here; nothing calls a model.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.tin_patterns import scrub_tins
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.export_manifest import EVIDENCE_DIR, MAX_PATH, archive_path_problem
from abacus.modules.evidence.export_package import ExportSectionInvalid, SectionRequest
from abacus.modules.evidence.repository import item_versions_with_decisions
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, firm_time_zone, names_of
from abacus.modules.requests.api import read_item_versions, source_documents

ReviewState = Literal["accepted", "needs_review"]
# The request's status words (docs/product/status-vocabulary.yaml `request`, placeholders left
# out: an index cell is a fact, the date and reason are columns or decisions of their own).
STATUS_LABELS: Final = {
    "draft": "Draft",
    "requested": "Requested",
    "uploaded": "Uploaded \u2013 needs review",
    "received": "Received ✓",
    "returned": "Returned",
    "not_applicable": "Not applicable",
}
NEEDS_REVIEW_LABEL: Final = "Uploaded \u2013 needs review (not accepted)"
_CATEGORY_CHARS: Final = 36
_REQUEST_CHARS: Final = 56
_FILE_CHARS: Final = 60
_EXTENSION_CHARS: Final = 10
_REPLACED: Final = frozenset("/\\:")


@dataclass(frozen=True)
class PlannedFile:
    path: str
    evidence_version_id: UUID
    request_item_id: UUID
    binder_id: UUID
    version_no: int
    review_state: ReviewState
    media_type: str
    fingerprint: str
    size_bytes: int
    storage_key: str
    storage_version_id: str
    decided_by: UUID | None
    decided_at: datetime | None


@dataclass(frozen=True)
class PlannedRequest:
    request_item_id: UUID
    binder_id: UUID
    category_no: int
    category: str
    request_no: int
    title: str
    status: str
    status_label: str
    owed_by: str
    requested_on: date | None
    due_on: date | None
    files: tuple[PlannedFile, ...]
    reviewed_by: str
    reviewed_on: date | None


@dataclass(frozen=True)
class Plan:
    export_id: UUID
    requests: tuple[PlannedRequest, ...]

    @property
    def files(self) -> tuple[PlannedFile, ...]:
        return tuple(sorted((f for r in self.requests for f in r.files), key=lambda f: f.path))

    @property
    def version_ids(self) -> frozenset[UUID]:
        return frozenset(f.evidence_version_id for f in self.files)


# The plan of the export being built, so every provider of one build reads the same selection.
_current: ContextVar[Plan | None] = ContextVar("abacus_export_plan", default=None)


@contextmanager
def plan_in_use(plan: Plan) -> Generator[Plan]:
    """Inside the block, `plan` is the one providers of its export read (the package
    activity), so every section of one build agrees with the files."""
    token = _current.set(plan)
    try:
        yield plan
    finally:
        _current.reset(token)


def current_plan(export_id: UUID) -> Plan | None:
    plan = _current.get()
    return plan if plan is not None and plan.export_id == export_id else None


# --- names -------------------------------------------------------------------------------------


def _clean(text: str) -> str:
    """NFC, TIN forms masked, separators and control or format characters replaced, whitespace
    collapsed, no leading or trailing dots or spaces (so never `.` or `..`)."""
    value = unicodedata.normalize("NFC", scrub_tins(text))
    value = "".join(
        "_" if c in _REPLACED or unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c
        for c in value
    )
    return " ".join(value.split()).strip(" .")


def _cut(value: str, limit: int) -> str:
    cut = unicodedata.normalize("NFC", value[:limit]).strip(" .")
    return cut or "_"


def segment(text: str, limit: int) -> str:
    return _cut(_clean(text) or "_", limit)


def _split_extension(name: str) -> tuple[str, str]:
    stem, dot, extension = name.rpartition(".")
    if dot and stem and 0 < len(extension) <= _EXTENSION_CHARS and extension.isalnum():
        return stem, f".{extension}"
    return name, ""


def file_segment(name: str, version_no: int, limit: int = _FILE_CHARS) -> str:
    stem, extension = _split_extension(_clean(name) or "_")
    return f"v{version_no}__{_cut(stem, max(1, limit - len(extension)))}{extension}"


def _with_suffix(path: str, n: int) -> str:
    head, _, last = path.rpartition("/")
    stem, extension = _split_extension(last)
    return f"{head}/{stem}~{n}{extension}"


def _fit(path: str) -> str:
    """Shorten the file name until the path is within MAX_PATH (room kept for `~NN`)."""
    over = len(path) + 3 - MAX_PATH
    if over <= 0:
        return path
    head, _, last = path.rpartition("/")
    stem, extension = _split_extension(last)
    return f"{head}/{_cut(stem, max(1, len(stem) - over))}{extension}"


def deduplicated(paths: Sequence[str]) -> list[str]:
    """The paths in their order, a repeat (compared without case) suffixed `~2`, `~3`."""
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        candidate, n = path, 1
        while candidate.casefold() in seen:
            n += 1
            candidate = _with_suffix(path, n)
        seen.add(candidate.casefold())
        problem = archive_path_problem(candidate)
        if problem is not None:
            raise ExportSectionInvalid(f"an archive path was unsafe ({problem})")
        out.append(candidate)
    return out


# --- the plan ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    request_item_id: UUID
    binder_id: UUID
    title: str
    status: str
    owed_by: str
    requested_at: datetime | None
    due_on: date | None


def _row_order(row: _Row) -> tuple[bool, str, str]:
    """Requests in the order they were asked; never asked last; ties by id."""
    at = row.requested_at.isoformat() if row.requested_at is not None else ""
    return (row.requested_at is None, at, str(row.request_item_id))


async def _files_of(
    ctx: AuthContext, item_id: UUID, binder_id: UUID, include_unaccepted: bool
) -> list[PlannedFile]:
    versions = await read_item_versions(ctx.tenant, item_id)
    async with tenant_session(ctx.tenant) as session:
        rows = await item_versions_with_decisions(session, item_id, versions)
    out: list[PlannedFile] = []
    for version, item, decision in sorted(rows, key=lambda r: (r[0].created_at, r[0].id)):
        if decision is not None and decision.decision == "accept":
            state: ReviewState = "accepted"
        elif decision is None and include_unaccepted:
            state = "needs_review"
        else:
            continue
        decided_by: UUID | None = None
        if decision is not None and decision.actor_kind == "human":
            decided_by = UUID(decision.actor_id)
        out.append(
            PlannedFile(
                path=file_segment(item.title, version.version_no),  # the last segment, for now
                evidence_version_id=version.id,
                request_item_id=item_id,
                binder_id=binder_id,
                version_no=version.version_no,
                review_state=state,
                media_type=version.media_type,
                fingerprint=version.fingerprint,
                size_bytes=version.size_bytes,
                storage_key=version.storage_key,
                storage_version_id=version.storage_version_id,
                decided_by=decided_by,
                decided_at=decision.created_at if decision is not None else None,
            )
        )
    return out


async def plan_selection(
    ctx: AuthContext, request: SectionRequest, *, only: frozenset[UUID] | None = None
) -> Plan:
    """The export's requests and files as `ctx` (the requester) may read them now. `only`
    restricts files to the versions snapshot in `engagement_export_contents`. The requester
    must still read the engagement's evidence (a wall, a role or independence lost since the
    request refuses the build), before `visible()` narrows each read."""
    try:
        engagement = await get_ref(ctx, request.engagement_id)
        await authorise(ctx, "evidence.read", engagement.resource())
    except (Forbidden, NotFound):
        raise ExportSectionInvalid("the requester may no longer read the evidence") from None
    zone = ZoneInfo(await firm_time_zone(ctx.tenant))
    categories: list[tuple[str, list[_Row]]] = []
    for binder_id in request.binder_ids:
        found = await source_documents(ctx, request.work_item_id, binder_id=binder_id)
        for group in found.groups:
            rows = [
                _Row(
                    r.request_item_id,
                    r.binder_id,
                    r.title,
                    r.status,
                    r.owed_by.display if r.owed_by is not None else "",
                    r.requested_at,
                    r.due_on,
                )
                for r in group.rows
            ]
            rows.sort(key=_row_order)
            categories.append((group.label, rows))
    planned: list[PlannedRequest] = []
    for category_no, (label, rows) in enumerate(categories, start=1):
        category_dir = f"{category_no:02d} {segment(label, _CATEGORY_CHARS)}"
        for request_no, row in enumerate(rows, start=1):
            request_dir = f"{request_no:02d} {segment(row.title, _REQUEST_CHARS)}"
            files = [
                f
                for f in await _files_of(
                    ctx, row.request_item_id, row.binder_id, request.include_unaccepted
                )
                if only is None or f.evidence_version_id in only
            ]
            files = [
                replace(f, path=_fit(f"{EVIDENCE_DIR}{category_dir}/{request_dir}/{f.path}"))
                for f in files
            ]
            planned.append(
                PlannedRequest(
                    request_item_id=row.request_item_id,
                    binder_id=row.binder_id,
                    category_no=category_no,
                    category=label,
                    request_no=request_no,
                    title=row.title,
                    status=row.status,
                    status_label=STATUS_LABELS.get(row.status, row.status),
                    owed_by=row.owed_by,
                    requested_on=row.requested_at.astimezone(zone).date()
                    if row.requested_at is not None
                    else None,
                    due_on=row.due_on,
                    files=tuple(files),
                    reviewed_by="",
                    reviewed_on=None,
                )
            )
    return await _finished(Plan(request.export_id, tuple(planned)), zone)


async def _finished(plan: Plan, zone: ZoneInfo) -> Plan:
    """Unique paths across the package, the needs-review label, and who reviewed each row."""
    ordered = sorted(
        (f.path, r.request_item_id, f.evidence_version_id) for r in plan.requests for f in r.files
    )
    unique = dict(
        zip(
            ((item, version) for _, item, version in ordered),
            deduplicated([p for p, _, _ in ordered]),
            strict=True,
        )
    )
    deciders = sorted({f.decided_by for r in plan.requests for f in r.files if f.decided_by})
    names = await names_of(deciders) if deciders else {}
    requests: list[PlannedRequest] = []
    for r in plan.requests:
        files = tuple(
            replace(f, path=unique[(r.request_item_id, f.evidence_version_id)]) for f in r.files
        )
        accepted = [f for f in files if f.review_state == "accepted" and f.decided_at]
        last = max(
            accepted, key=lambda f: (f.decided_at, str(f.evidence_version_id)), default=None
        )
        label = (
            NEEDS_REVIEW_LABEL
            if any(f.review_state == "needs_review" for f in files)
            else r.status_label
        )
        requests.append(
            replace(
                r,
                files=files,
                status_label=label,
                reviewed_by=names.get(last.decided_by, "") if last and last.decided_by else "",
                reviewed_on=last.decided_at.astimezone(zone).date()
                if last and last.decided_at
                else None,
            )
        )
    return Plan(plan.export_id, tuple(requests))
