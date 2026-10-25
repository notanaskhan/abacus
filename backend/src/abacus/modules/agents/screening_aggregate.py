"""The screening aggregate of a request batch (P-06-T20; DEC-48, DEC-324; P-06 §3.5, §4.5).

Code composes the SHL-20 card from what is already recorded. Nothing here calls a model, and
nothing here writes a request's status or a review decision: the agent proposes, and a person
decides (ADR-005).

**The files.** The batch is the item's live fulfilments. A version the client withdrew is left
out (DEC-298, DEC-299), so are versions evidence no longer reads.

**Check 1, "Does this answer the request?"** (`right_document`, model): a file is flagged when its
latest completed upload review shows an `irrelevant` flag. Shown means a code-verified quote and
enough confidence (SPEC-030 Q3; INV-2). A file passes when a review or a per-version screening
completed without one. Otherwise it was not run.

**Check 2, "Is it inside the expected period?"** (`right_period`, code only; ADR-050, DV-2): the
document's own dates, as extraction read them, against the request's `period_start/end`. A file
flags when its dates fall wholly outside. Without a request period, the upload check
`wrong_period` (against the year end) decides. Without dates, the file was not run. No model
output is read here.

**The rule.** A check flags when any file flags, and passes when every file passes. Otherwise it
was not run. The verdict is flagged when any check flags, and passed when both pass. Otherwise
the batch is not screened.

**Tax-return work items at a real firm** (`tri_gate`): no model output is used, and the model
check stays not run.

Each change composes a new `request_batch` row that supersedes the item's previous one (0154). An
unchanged composition writes nothing, so redelivered events are harmless.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.agents.models import ScreeningResult
from abacus.modules.agents.repository import (
    ReviewRunFacts,
    aggregate_head,
    insert_aggregate,
    items_screened_with,
    review_runs_of_versions,
    shown_flags_of_reviews,
    version_results_of,
)
from abacus.modules.agents.tri_gate import model_blocked
from abacus.modules.agents.upload_review import REVIEWER
from abacus.modules.evidence.api import (
    ScreeningFacts,
    screening_facts,
    verified_citation_ids,
    withdrawn_among,
)
from abacus.modules.requests.api import items_of_version, read_item_versions, screening_subject

CheckVerdict = Literal["pass", "flag", "not_run"]
Verdict = Literal["passed", "flagged", "not_screened"]
RIGHT_DOCUMENT: Final = "right_document"
RIGHT_PERIOD: Final = "right_period"
WRONG_DOCUMENT: Final = "wrong_document"
WRONG_YEAR: Final = "wrong_year"
_COMPOSER: Final = "agents.screening_aggregate"
_ATTEMPTS: Final = 3
_log = get_logger(__name__)


@dataclass(frozen=True)
class VersionInput:
    """One file's facts. Code's: dates and the `wrong_period` check outcome. The model's: whether
    a review completed, and the verified citations of a shown `irrelevant` flag (None when there
    is no such flag)."""

    evidence_version_id: UUID
    period_start: date | None = None
    period_end: date | None = None
    as_of: date | None = None
    period_check: str | None = None
    reviewed: bool = False
    wrong_document: tuple[UUID, ...] | None = None


@dataclass(frozen=True)
class CheckOutcome:
    key: str
    verdict: CheckVerdict
    source: Literal["model", "code"]
    citation_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class FileFlag:
    evidence_version_id: UUID
    reason_code: str
    region_ref: str | None


@dataclass(frozen=True)
class Composition:
    evidence_version_ids: tuple[UUID, ...]
    checks: tuple[CheckOutcome, CheckOutcome]
    file_flags: tuple[FileFlag, ...]
    verdict: Verdict


def document_verdict(v: VersionInput) -> CheckVerdict:
    if v.wrong_document is not None:
        return "flag"
    return "pass" if v.reviewed else "not_run"


def period_verdict(
    expected_start: date | None, expected_end: date | None, v: VersionInput
) -> CheckVerdict:
    """Code only: the request's period against the document's dates, else the period check."""
    starts = v.period_start or v.as_of or v.period_end
    ends = v.period_end or v.as_of or v.period_start
    if expected_start is not None or expected_end is not None:
        if starts is None or ends is None:
            return "not_run"
        outside = (expected_start is not None and ends < expected_start) or (
            expected_end is not None and starts > expected_end
        )
        return "flag" if outside else "pass"
    if v.period_check == "problem":
        return "flag"
    return "pass" if v.period_check == "passed" else "not_run"


def combine(verdicts: Iterable[CheckVerdict]) -> CheckVerdict:
    seen = list(verdicts)
    if not seen:
        return "not_run"
    if "flag" in seen:
        return "flag"
    return "pass" if all(v == "pass" for v in seen) else "not_run"


def overall(checks: Sequence[CheckOutcome]) -> Verdict:
    if any(c.verdict == "flag" for c in checks):
        return "flagged"
    return "passed" if checks and all(c.verdict == "pass" for c in checks) else "not_screened"


def compose(
    expected_start: date | None, expected_end: date | None, files: Sequence[VersionInput]
) -> Composition:
    """The aggregate of these files (the rule above). Pure: same inputs, same composition."""
    documents: list[CheckVerdict] = [document_verdict(v) for v in files]
    periods: list[CheckVerdict] = [period_verdict(expected_start, expected_end, v) for v in files]
    cited = tuple(c for v in files for c in (v.wrong_document or ()))
    checks = (
        CheckOutcome(RIGHT_DOCUMENT, combine(documents), "model", cited),
        CheckOutcome(RIGHT_PERIOD, combine(periods), "code"),
    )
    flags: list[FileFlag] = []
    for v, document, period in zip(files, documents, periods, strict=True):
        if document == "flag":
            first = (v.wrong_document or (None,))[0]
            flags.append(
                FileFlag(v.evidence_version_id, WRONG_DOCUMENT, str(first) if first else None)
            )
        if period == "flag":
            flags.append(FileFlag(v.evidence_version_id, WRONG_YEAR, None))
    return Composition(
        tuple(v.evidence_version_id for v in files), checks, tuple(flags), overall(checks)
    )


def checks_json(item_id: UUID, checks: Sequence[CheckOutcome]) -> list[dict[str, object]]:
    return [
        {
            "key": c.key,
            "verdict": c.verdict,
            "source": c.source,
            "answer_ref": str(item_id),
            "citation_ids": [str(i) for i in c.citation_ids],
        }
        for c in checks
    ]


def flags_json(flags: Sequence[FileFlag]) -> list[dict[str, object]]:
    return [
        {
            "evidence_version_id": str(f.evidence_version_id),
            "reason_code": f.reason_code,
            "region_ref": f.region_ref,
        }
        for f in flags
    ]


def latest_reviews(runs: Sequence[ReviewRunFacts]) -> dict[UUID, ReviewRunFacts]:
    """Each version's newest completed review (runs come oldest first)."""
    found: dict[UUID, ReviewRunFacts] = {}
    for run in runs:
        if run.status == "completed" and run.review_id is not None:
            found[run.evidence_version_id] = run
    return found


def _review_id(run: ReviewRunFacts | None) -> UUID | None:
    return run.review_id if run is not None else None


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", _COMPOSER)


@dataclass(frozen=True)
class _Inputs:
    composition: Composition
    result_ids: tuple[UUID, ...]
    review_ids: tuple[UUID, ...]
    engagement_id: UUID


async def _inputs(tenant: TenantContext, item_id: UUID) -> _Inputs | None:
    subject = await screening_subject(tenant, item_id)
    if subject is None:
        return None
    live = await read_item_versions(tenant, item_id)
    hidden = await withdrawn_among(tenant, live)
    facts: dict[UUID, ScreeningFacts] = await screening_facts(
        tenant, [v for v in live if v not in hidden]
    )
    versions = [v for v in live if v in facts]
    blocked = await model_blocked(tenant, [item_id])
    reviews: dict[UUID, ReviewRunFacts] = {}
    results: dict[UUID, UUID] = {}
    flags: list[tuple[UUID, int, str]] = []
    if not blocked:
        async with tenant_session(tenant) as session:
            reviews = latest_reviews(await review_runs_of_versions(session, REVIEWER, versions))
            results = await version_results_of(session, versions)
            flags = await shown_flags_of_reviews(
                session, [r.review_id for r in reviews.values() if r.review_id is not None]
            )
    review_ids = [r.review_id for r in reviews.values() if r.review_id is not None]
    citations = await verified_citation_ids(tenant, "upload_review", review_ids) if flags else {}
    irrelevant: dict[UUID, list[UUID]] = {}
    for review_id, position, category in flags:
        if category == "irrelevant":
            irrelevant.setdefault(review_id, []).extend(
                citations.get((review_id, f"F{position}"), [])
            )
    files: list[VersionInput] = []
    for version in versions:
        fact = facts[version]
        review = reviews.get(version)
        period_check = next((o for code, o in fact.checks if code == "wrong_period"), None)
        review_id = review.review_id if review is not None else None
        wrong = (
            tuple(irrelevant[review_id])
            if review_id is not None and review_id in irrelevant
            else None
        )
        files.append(
            VersionInput(
                version,
                fact.period_start,
                fact.period_end,
                fact.as_of,
                period_check,
                reviewed=review is not None or version in results,
                wrong_document=wrong,
            )
        )
    return _Inputs(
        compose(subject.period_start, subject.period_end, files),
        tuple(results[v] for v in versions if v in results),
        tuple(r for v in versions if (r := _review_id(reviews.get(v))) is not None),
        subject.engagement_id,
    )


def _unchanged(head: ScreeningResult, found: _Inputs, item_id: UUID) -> bool:
    c = found.composition
    return (
        list(head.evidence_version_ids or []) == list(c.evidence_version_ids)
        and list(head.source_result_ids or []) == list(found.result_ids)
        and list(head.source_review_ids or []) == list(found.review_ids)
        and head.checks == checks_json(item_id, c.checks)
        and head.file_flags == flags_json(c.file_flags)
        and head.verdict == c.verdict
    )


async def compose_for_item(tenant_id: UUID, item_id: UUID) -> UUID | None:
    """Compose the item's aggregate; the new row's id, or None when nothing changed (or the item
    is gone). A concurrent composer that wins the chain makes this one start again."""
    tenant = _system(tenant_id)
    for _ in range(_ATTEMPTS):
        found = await _inputs(tenant, item_id)
        if found is None:
            return None
        c = found.composition
        async with tenant_session(tenant) as session:
            head = await aggregate_head(session, item_id)
        if head is not None and _unchanged(head, found, item_id):
            return None
        try:  # the insert guard refuses it if another composer moved the head meanwhile
            async with uow(tenant) as tx:
                result_id = await insert_aggregate(
                    tx.session,
                    values={
                        "tenant_id": tenant_id,
                        "engagement_id": found.engagement_id,
                        "request_item_id": item_id,
                        "batch_no": (head.batch_no or 0) + 1 if head is not None else 1,
                        "supersedes_id": head.id if head is not None else None,
                        "source_result_ids": list(found.result_ids),
                        "source_review_ids": list(found.review_ids),
                        "evidence_version_ids": list(c.evidence_version_ids),
                        "checks": checks_json(item_id, c.checks),
                        "file_flags": flags_json(c.file_flags),
                        "verdict": c.verdict,
                        "citations": [],
                        "unverified": [],
                    },
                )
                tx.record(
                    "screening.completed",
                    target=Target("screening_result", result_id),
                    after=Ref(
                        request_item_id=item_id,
                        files=len(c.evidence_version_ids),
                        flagged=len({f.evidence_version_id for f in c.file_flags}),
                    ),
                )
            return result_id
        except IntegrityError:
            _log.info("screening.recompose", tenant_id=tenant_id, request_item_id=item_id)
    return None


async def compose_for_version(tenant_id: UUID, version_id: UUID) -> list[UUID]:
    """Recompose every item the version fulfils (or fulfilled, for a withdrawal: the item's live
    versions no longer include it)."""
    items = await items_of_version(_system(tenant_id), version_id)
    composed: list[UUID] = []
    for item in items:
        found = await compose_for_item(tenant_id, item.id)
        if found is not None:
            composed.append(found)
    return composed


async def on_version_event(event: OutboxEvent) -> None:
    """`upload_checks.recorded` and `upload_review.recorded`: the version's items recompose."""
    await compose_for_version(event.tenant_id, UUID(str(event.payload["evidence_version_id"])))


async def on_version_withdrawn(event: OutboxEvent) -> None:
    """`evidence_version.withdrawn`: its fulfilments are void, so `items_of_version` no longer
    finds the items. The item the upload was made to and every item an aggregate composed it
    for recompose without it."""
    version = UUID(str(event.payload["evidence_version_id"]))
    named = event.payload.get("request_item_id")
    async with tenant_session(_system(event.tenant_id)) as session:
        items = await items_screened_with(session, version)
    targets: list[UUID] = [UUID(str(named))] if named is not None else []
    for item in dict.fromkeys([*targets, *items]):
        await compose_for_item(event.tenant_id, item)
