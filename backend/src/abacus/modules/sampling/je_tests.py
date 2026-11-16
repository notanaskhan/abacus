"""JE testing (A-08-T12; SPEC-657 F1, F3; ADR-400 P-58; ADR P-57; ADR-050): the service behind
`fieldwork_contract`'s JE routes (AUD-12, JE variant).

- **Population.** A test names a GL snapshot of the engagement's entity, which A-03's
  `general_ledger` path stored only once `validate_gl` proved it (opening TB + JE activity =
  closing TB for every account). The tie is re-read from the snapshot's balances on every view.
- **Criteria.** A person configures the firm's `je_risk_criteria` policy version (firm content,
  `methodology.api`), with overrides; each configuration is a new insert-only version of the
  test's criteria. `post_close` without a `through` takes the test's post-close date.
- **Posting user roles.** A person sets each posting user's role class with its citation; names
  are sealed and matched by SHA-256 of the case-folded name, never logged.
- **Scoring.** `JeScoringWorkflow` (batch queue) scores the whole population with the frozen
  engine (`compute.je_scoring`) in one activity and stores a run (engine version, inputs hash,
  unique flagged, hits) and every entry's score with its reason codes, insert-only.
- **Selection.** A person draws a selection: the frozen `je_score_selection` version picks the
  entries by score and the seeded unpredictable picks; the selection is a sample-set version
  over a population of the scored entries, drawn by `SampleDrawWorkflow` like every other.

Every route authorised the action on the test's engagement (walls 404, independence 403).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID, uuid4

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel._statuses import JeCriterionStatus
from abacus.kernel.clock import now
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, names_of
from abacus.modules.ledger.api import (
    GlSnapshotView,
    JournalEntry,
    gl_snapshot_view,
    je_fields_available,
    journal_entries,
)
from abacus.modules.methodology.api import je_risk_criteria_version
from abacus.modules.platform.api import references_in_effect
from abacus.modules.sampling import je_repository as repo
from abacus.modules.sampling import population_repository as population_repo
from abacus.modules.sampling import sample_set_repository as set_repo
from abacus.modules.sampling.compute import Record, canonical, je_scoring, je_selection
from abacus.modules.sampling.draw_types import SampleDrawInput
from abacus.modules.sampling.fieldwork_contract import (
    CriteriaIn,
    CriterionKey,
    CriterionOut,
    JeTestCreateIn,
    JeTestOut,
    PopulationNotTied,
    PostingUserRolesIn,
    ScoredEntriesOut,
    ScoredEntryOut,
    ScoreRunOut,
    SelectionIn,
    SelectionOut,
    TieOut,
)
from abacus.modules.sampling.je_scoring_types import JeScoringInput

ACTOR: Final = "je_scoring"
NAME_AAD: Final = "sampling.je_posting_user"
PAGE: Final = 50
TIE_LABEL: Final = "Opening TB + JE activity = closing TB"
TIE_ENGINE: Final = "je-tie-1"
AllowedAction = Literal["je_test.configure", "je_test.score", "sample_set.create"]
_CURSOR: Final = re.compile(r"^[A-Za-z0-9_-]{1,400}={0,2}$")
_ACTIONS: Final[tuple[AllowedAction, ...]] = (
    "je_test.configure",
    "je_test.score",
    "sample_set.create",
)
Row = dict[str, Any]  # Any: database rows of mixed column types


class PeriodOutsideLedger(DomainInvalid):
    """The test's period and post-close window must lie within the GL snapshot's period."""

    code = "period_outside_ledger"


class CriteriaInvalid(DomainInvalid):
    """The policy's criteria, with the overrides, cannot be evaluated."""

    code = "criteria_invalid"


class CriteriaRequired(DomainConflict):
    """Scoring waits for a person to configure the criteria."""

    code = "criteria_required"


class JeTestBusy(DomainConflict):
    """A scoring run is in progress: configure or score again when it finishes."""

    code = "je_test_busy"


class JeTestNotScored(DomainConflict):
    """A selection needs a finished scoring run."""

    code = "je_test_not_scored"


class SelectionInvalid(DomainInvalid):
    """Neither a score floor nor a count, or more unpredictable picks than entries left."""

    code = "selection_invalid"


@dataclass(frozen=True)
class _Found:
    row: Row
    engagement_id: UUID
    resource: Resource


# --- pure helpers --------------------------------------------------------------------------------


def tie_of(snapshot: GlSnapshotView) -> TieOut:
    """Code's completeness tie from the snapshot's balances (closing vs the trial balance)."""
    tied, difference = 0, Decimal(0)
    for b in snapshot.balances:
        gap = b.closing - b.tb_closing
        difference += gap
        tied += 1 if gap == 0 else 0
    total = len(snapshot.balances)
    result: Literal["tie", "difference"] = (
        "tie" if tied == total and difference == 0 else "difference"
    )
    return TieOut(accounts_tied=tied, accounts_total=total, difference=difference, result=result)


def posting_user_key(name: str) -> bytes:
    return hashlib.sha256(name.strip().casefold().encode("utf-8")).digest()


def _last4(code: str) -> str | None:
    digits = "".join(ch for ch in code if ch.isdigit())
    return digits[-4:] if len(digits) >= 4 else None


def entry_refs(entries: Sequence[JournalEntry]) -> list[str]:
    """Each entry's reference; an entry without one, or a repeated one, gets its date and a
    counter so every reference names one entry."""
    seen: dict[str, int] = {}
    refs: list[str] = []
    for e in entries:
        base = (e.reference or f"JE {e.posted_on.isoformat()}").strip()[:100] or "JE"
        n = seen.get(base, 0)
        seen[base] = n + 1
        refs.append(base if n == 0 else f"{base} #{n + 1}")
    return refs


def to_engine(entry: JournalEntry, ref: str) -> je_scoring.JeEntry:
    return je_scoring.JeEntry(
        ref=ref,
        posted_on=entry.posted_on,
        amount=entry.total_debit,
        descriptions=tuple(x.description for x in entry.lines if x.description),
        posted_by=entry.posted_by,
        entered_at=entry.entered_at,
        source=entry.source,
    )


def merged_criteria(
    policy: Sequence[tuple[CriterionKey, int, Mapping[str, str]]],
    overrides: Mapping[CriterionKey, Mapping[str, str]],
    post_close_through: date,
) -> list[je_scoring.Criterion]:
    keys = {k for k, _, _ in policy}
    if any(k not in keys for k in overrides):
        raise CriteriaInvalid(facts={"field": "overrides"})
    out: list[je_scoring.Criterion] = []
    for key, weight, params in policy:
        merged = {**params, **overrides.get(key, {})}
        if key == "post_close":
            merged.setdefault("through", post_close_through.isoformat())
        out.append(je_scoring.Criterion(key, weight, merged))
    _validate(out)
    return out


def _validate(criteria: Sequence[je_scoring.Criterion]) -> None:
    probe = je_scoring.JeEntry("probe", date(2000, 1, 3), Decimal(1), ("probe",))
    inputs = je_scoring.Inputs(
        tuple(criteria), je_scoring.HolidaySet("probe", frozenset()), date(2000, 1, 1)
    )
    try:
        je_scoring.score(inputs, [probe])
    except je_scoring.InvalidCriteria as exc:
        raise CriteriaInvalid(facts={"field": str(exc) or "criteria"}) from None


def encode_cursor(score: int, ref: str) -> str:
    return base64.urlsafe_b64encode(json.dumps([score, ref]).encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> tuple[int, str] | None:
    if cursor is None:
        return None
    try:
        if not _CURSOR.fullmatch(cursor):
            raise ValueError("cursor")
        score, ref = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return int(score), str(ref)
    except (ValueError, TypeError, binascii.Error):
        raise DomainInvalid(facts={"field": "cursor"}) from None


# --- access --------------------------------------------------------------------------------------


async def _find(ctx: AuthContext, je_test_id: UUID, action: str) -> _Found:
    async with tenant_session(ctx.tenant) as session:
        row = await repo.test(session, je_test_id)
    if row is None:
        raise NotFound("je_test")
    engagement_id = cast(UUID, row["engagement_id"])
    ref = await get_ref(ctx, engagement_id)
    resource = ref.resource()
    await authorise(ctx, action, resource)
    return _Found(row, engagement_id, resource)


async def _may(ctx: AuthContext, action: str, resource: Resource) -> bool:
    try:
        await authorise(ctx, action, resource)
    except Forbidden:
        return False
    return True


# --- create --------------------------------------------------------------------------------------


async def create_je_test(ctx: AuthContext, work_item_id: UUID, body: JeTestCreateIn) -> JeTestOut:
    """The population (a proved GL snapshot of the engagement's entity) and a draft test; a
    second create for the same snapshot answers the first. The route authorised the work item."""
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    snapshot = await gl_snapshot_view(ctx.tenant, body.gl_snapshot_id)
    if snapshot.client_entity_id != ref.client_entity_id or snapshot.kind != "year":
        raise NotFound("gl_snapshot")
    # The post-close window may run past the snapshot: its entries are those the export carried.
    inside = snapshot.period_start <= body.period_start <= body.period_end <= snapshot.period_end
    if not inside or body.post_close_through < body.period_end:
        raise PeriodOutsideLedger
    async with uow(ctx.tenant) as tx:
        je_test_id = await repo.insert_test(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "work_item_id": work_item_id,
                "gl_snapshot_id": body.gl_snapshot_id,
                "period_start": body.period_start,
                "period_end": body.period_end,
                "post_close_through": body.post_close_through,
                "created_by": ctx.user_id,
            },
        )
        tx.record(
            "je_test.created",
            target=Target("je_test", je_test_id),
            after=Ref(engagement=engagement_id, gl_snapshot=body.gl_snapshot_id),
        )
    return await je_test_view(ctx, je_test_id)


# --- configure -----------------------------------------------------------------------------------


async def put_criteria(ctx: AuthContext, je_test_id: UUID, body: CriteriaIn) -> JeTestOut:
    found = await _find(ctx, je_test_id, "je_test.configure")
    if found.row["status"] == "scoring":
        raise JeTestBusy
    policy = await je_risk_criteria_version(ctx.tenant_id, body.policy_version_id)
    if policy is None:
        raise NotFound("threshold_policy_version")
    _, payload = policy
    criteria = merged_criteria(
        [(c.key, c.weight, c.params) for c in payload.criteria],
        body.overrides,
        cast(date, found.row["post_close_through"]),
    )
    async with uow(ctx.tenant) as tx:
        version = await repo.next_configured_version(tx.session, je_test_id)
        await repo.insert_criteria(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "je_test_id": je_test_id,
                    "configured_version": version,
                    "position": n,
                    "key": c.key,
                    "weight": c.weight,
                    "params": dict(c.params),
                    "set_by": ctx.user_id,
                }
                for n, c in enumerate(criteria, start=1)
            ],
        )
        await repo.set_policy(tx.session, je_test_id, body.policy_version_id)
        tx.record(
            "je_test.configured",
            target=Target("je_test", je_test_id),
            after=Ref(policy_version=body.policy_version_id, configured=version),
        )
    return await je_test_view(ctx, je_test_id)


async def put_posting_user_roles(
    ctx: AuthContext, je_test_id: UUID, body: PostingUserRolesIn
) -> JeTestOut:
    found = await _find(ctx, je_test_id, "je_test.configure")
    if found.row["status"] == "scoring":
        raise JeTestBusy
    rows: list[dict[str, object]] = []
    for role in body.roles:
        name = role.posting_user.strip()
        rows.append(
            {
                "tenant_id": ctx.tenant_id,
                "je_test_id": je_test_id,
                "posting_user_sha256": posting_user_key(name),
                "posting_user_sealed": await seal(ctx.tenant_id, name.encode("utf-8"), NAME_AAD),
                "role_class": role.role_class,
                "citation_id": role.citation_id,
                "set_by": ctx.user_id,
            }
        )
    async with uow(ctx.tenant) as tx:
        await repo.insert_roles(tx.session, rows)
        tx.record(
            "je_test.roles_set", target=Target("je_test", je_test_id), after=Ref(roles=len(rows))
        )
    return await je_test_view(ctx, je_test_id)


# --- score ---------------------------------------------------------------------------------------


def _scoring_workflow() -> type:
    from abacus.modules.sampling.je_scoring_workflow import JeScoringWorkflow

    return JeScoringWorkflow


async def start_scoring(ctx: AuthContext, je_test_id: UUID, idempotency_key: str) -> ScoreRunOut:
    """202: a scoring run on the batch queue; refused until the tie reads `tie` and a person has
    configured the criteria. A replay of the same key answers the first run."""
    found = await _find(ctx, je_test_id, "je_test.score")

    async def run() -> tuple[int, dict[str, object]]:
        snapshot = await gl_snapshot_view(ctx.tenant, cast(UUID, found.row["gl_snapshot_id"]))
        if tie_of(snapshot).result != "tie":
            raise PopulationNotTied
        async with tenant_session(ctx.tenant) as session:
            if not await repo.criteria(session, je_test_id):
                raise CriteriaRequired
        async with uow(ctx.tenant) as tx:
            locked = await repo.test(tx.session, je_test_id, lock=True)
            if locked is None or locked["status"] == "scoring":
                raise JeTestBusy
            version = int(locked["score_version"]) + 1
            await repo.set_status(
                tx.session, je_test_id, "scoring", expect=("draft", "scored", "failed")
            )
            tx.record(
                "je_test.scoring_started",
                target=Target("je_test", je_test_id),
                after=Ref(score_version=version),
            )
        workflow_id = f"je_scoring:{ctx.tenant_id}:{je_test_id}:{version}"
        given = JeScoringInput(str(ctx.tenant_id), str(je_test_id), version, str(ctx.user_id))
        try:
            await dispatch(
                _scoring_workflow(),
                given,
                id=workflow_id,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            )
        except Exception:
            await fail_scoring(ctx.tenant_id, je_test_id, "dispatch_failed")
            raise
        return 202, {"score_version": version, "workflow_id": workflow_id}

    stored = await idempotent(
        ctx.tenant,
        route="je_test.score",
        key=idempotency_key,
        body={"je_test_id": str(je_test_id)},
        run=run,
    )
    return ScoreRunOut(
        je_test_id=je_test_id,
        score_version=int(cast(int, stored.body["score_version"])),
        workflow_id=str(stored.body["workflow_id"]),
    )


def _system(tenant_id: UUID, je_test_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"{ACTOR}:{je_test_id}")


async def holiday_set(as_of: date) -> je_scoring.HolidaySet:
    """The published federal `legal_holidays` sets in effect on `as_of` (K-02-T05), with the
    versions that enter the inputs hash."""
    found = await references_in_effect("legal_holidays", as_of)
    dates: set[date] = set()
    versions: list[str] = []
    for ref in found:
        versions.append(f"{ref.key}@{ref.version}")
        rows = cast(Sequence[Any], getattr(ref.payload, "rows", ()))  # Any: the payload's rows
        dates.update(r.date for r in rows if r.jurisdiction == "US")
    return je_scoring.HolidaySet(",".join(sorted(versions)) or "none", frozenset(dates))


async def run_scoring(tenant_id: UUID, je_test_id: UUID, score_version: int) -> str:
    """The activity's work: score the population and store the run; the test's status after."""
    tenant = _system(tenant_id, je_test_id)
    async with tenant_session(tenant) as session:
        row = await repo.test(session, je_test_id)
        if row is None or row["status"] != "scoring":
            return "missing" if row is None else str(row["status"])
        criteria_rows = await repo.criteria(session, je_test_id)
        roles = await repo.roles(session, je_test_id)
    snapshot_id = cast(UUID, row["gl_snapshot_id"])
    facts = await je_fields_available(tenant, snapshot_id)
    start, through = cast(date, row["period_start"]), cast(date, row["post_close_through"])
    entries = [
        e for e in await journal_entries(tenant, snapshot_id) if start <= e.posted_on <= through
    ]
    refs = entry_refs(entries)
    role_map: dict[str, je_scoring.RoleClass] = {}
    for e in entries:
        if e.posted_by and e.posted_by not in role_map:
            role = roles.get(posting_user_key(e.posted_by))
            if role is not None:
                role_map[e.posted_by] = cast(je_scoring.RoleClass, role)
    inputs = je_scoring.Inputs(
        criteria=tuple(
            je_scoring.Criterion(
                cast(CriterionKey, c["key"]),
                int(c["weight"]),
                dict(cast(Mapping[str, str], c["params"])),
            )
            for c in criteria_rows
        ),
        holidays=await holiday_set(cast(date, row["period_end"])),
        period_end=cast(date, row["period_end"]),
        roles=role_map,
        fields_available=facts.available,
    )
    engine_entries = [to_engine(e, ref) for e, ref in zip(entries, refs, strict=True)]
    scored = je_scoring.score(inputs, engine_entries)
    by_ref = {ref: e for e, ref in zip(entries, refs, strict=True)}
    hits = {c.key: c.hit_count for c in scored.criteria}
    async with uow(tenant) as tx:
        run_id = await repo.insert_run(
            tx.session,
            {
                "tenant_id": tenant_id,
                "je_test_id": je_test_id,
                "score_version": score_version,
                "engine_version": scored.engine_version,
                "inputs_hash": scored.inputs_hash,
                "entries_count": len(engine_entries),
                "unique_flagged": scored.unique_flagged,
                "hits": hits,
            },
        )
        if run_id.int != 0:
            await repo.insert_scores(
                tx.session,
                [
                    {
                        "tenant_id": tenant_id,
                        "run_id": run_id,
                        "entry_ref": s.entry_ref,
                        "score": s.score,
                        "reason_codes": list(s.reason_codes),
                        "criteria_mask": s.criteria_mask,
                        "posted_on": by_ref[s.entry_ref].posted_on,
                        "amount": by_ref[s.entry_ref].total_debit,
                        "account_last4": _account(by_ref[s.entry_ref]),
                        "description": _description(by_ref[s.entry_ref]),
                    }
                    for s in scored.scores
                ],
            )
        if not await repo.set_status(
            tx.session, je_test_id, "scored", expect=("scoring",), score_version=score_version
        ):
            return "superseded"
        tx.record(
            "je_test.scored",
            target=Target("je_test", je_test_id),
            after=Ref(
                score_version=score_version,
                entries=len(engine_entries),
                flagged=scored.unique_flagged,
                inputs=scored.inputs_hash,
            ),
        )
    return "scored"


def _account(entry: JournalEntry) -> str | None:
    debit = max(entry.lines, key=lambda x: (x.debit, -x.line_no), default=None)
    return None if debit is None else _last4(debit.account_code)


def _description(entry: JournalEntry) -> str:
    return next((x.description for x in entry.lines if x.description), "")[:500]


async def fail_scoring(tenant_id: UUID, je_test_id: UUID, code: str = "scoring_failed") -> str:
    tenant = _system(tenant_id, je_test_id)
    async with uow(tenant) as tx:
        if await repo.set_status(
            tx.session, je_test_id, "failed", expect=("scoring",), failure_code=code
        ):
            tx.record("je_test.scoring_failed", target=Target("je_test", je_test_id))
    return "failed"


# --- entries -------------------------------------------------------------------------------------


async def _selected_refs(tenant: TenantContext, sample_set_id: UUID | None) -> list[str] | None:
    if sample_set_id is None:
        return None
    async with tenant_session(tenant) as session:
        versions = [
            v for v in await set_repo.versions(session, [sample_set_id]) if v["status"] != "failed"
        ]
        if not versions:
            return None
        items = await set_repo.items(session, cast(UUID, versions[-1]["id"]))
    return [str(i["record_key"]) for i in items]


async def list_entries(
    ctx: AuthContext,
    je_test_id: UUID,
    *,
    criterion: CriterionKey | None,
    selected: bool | None,
    cursor: str | None,
) -> ScoredEntriesOut:
    found = await _find(ctx, je_test_id, "je_test.read")
    after = decode_cursor(cursor)
    score_version = int(found.row["score_version"])
    if score_version == 0:
        return ScoredEntriesOut(items=[], next_cursor=None)
    chosen = await _selected_refs(ctx.tenant, cast(UUID | None, found.row["sample_set_id"]))
    async with tenant_session(ctx.tenant) as session:
        run = await repo.run_of(session, je_test_id, score_version)
        if run is None:
            return ScoredEntriesOut(items=[], next_cursor=None)
        if selected is not None and chosen is None:
            chosen = []
        rows = await repo.scores_page(
            session,
            cast(UUID, run["id"]),
            mask_bit=None if criterion is None else je_scoring.CRITERIA_ORDER.index(criterion),
            refs=None if selected is None else chosen,
            in_refs=bool(selected),
            after=after,
            limit=PAGE + 1,
        )
    picked = set(chosen or ())
    items = [
        ScoredEntryOut(
            entry_ref=str(r["entry_ref"]),
            posted_on=cast(date, r["posted_on"]),
            amount=cast(Decimal, r["amount"]),
            account_last4=cast(str | None, r["account_last4"]),
            description=str(r["description"]),
            score=int(r["score"]),
            reason_codes=list(r["reason_codes"]),
            selected=str(r["entry_ref"]) in picked,
        )
        for r in rows[:PAGE]
    ]
    last = rows[PAGE - 1] if len(rows) > PAGE else None
    return ScoredEntriesOut(
        items=items,
        next_cursor=None
        if last is None
        else encode_cursor(int(last["score"]), str(last["entry_ref"])),
    )


# --- selection -----------------------------------------------------------------------------------


def _draw_workflow() -> type:
    from abacus.modules.sampling.draw_workflow import SampleDrawWorkflow

    return SampleDrawWorkflow


async def draw_selection(
    ctx: AuthContext, je_test_id: UUID, body: SelectionIn, idempotency_key: str
) -> SelectionOut:
    """A sample-set version, method `je_score_selection`, drawn by `SampleDrawWorkflow`; a
    replay of the same key and body answers the first version."""
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("sample_set.create", "role")
    found = await _find(ctx, je_test_id, "sample_set.create")

    async def run() -> tuple[int, dict[str, object]]:
        version_id = await _draw(ctx, found, body)
        return 201, {"version_id": str(version_id)}

    await idempotent(
        ctx.tenant,
        route="je_test.selection",
        key=idempotency_key,
        body={"je_test_id": str(je_test_id), **body.model_dump(mode="json")},
        run=run,
    )
    view = await je_test_view(ctx, je_test_id)
    if view.selection is None:
        raise NotFound("sample_set")
    return view.selection


async def _draw(ctx: AuthContext, found: _Found, body: SelectionIn) -> UUID:
    row = found.row
    je_test_id = cast(UUID, row["id"])
    if row["status"] != "scored":
        raise JeTestNotScored
    snapshot = await gl_snapshot_view(ctx.tenant, cast(UUID, row["gl_snapshot_id"]))
    tie = tie_of(snapshot)
    if tie.result != "tie":
        raise PopulationNotTied
    if body.score_min is None and body.top_n is None:
        raise SelectionInvalid(facts={"field": "score_min"})
    async with tenant_session(ctx.tenant) as session:
        run = await repo.run_of(session, je_test_id, int(row["score_version"]))
        if run is None:
            raise JeTestNotScored
        scores = await repo.all_scores(session, cast(UUID, run["id"]))
    seed = secrets.randbits(24)
    try:
        selection = je_selection.select(
            [je_selection.Scored(ref, score) for ref, score, _ in scores],
            score_min=body.score_min,
            top_n=body.top_n,
            unpredictable_n=body.unpredictable_n,
            seed=seed,
        )
    except je_selection.SelectionInvalid as exc:
        raise SelectionInvalid(facts={"field": str(exc)}) from None
    if not selection.picks:
        raise SelectionInvalid(facts={"field": "score_min"})
    population = canonical(
        Record(ref, amount if isinstance(amount, Decimal) else None) for ref, _, amount in scores
    )
    by_ref = {ref: score for ref, score, _ in scores}
    population_id, version_id = uuid4(), uuid4()
    sample_set_id = cast(UUID | None, row["sample_set_id"]) or uuid4()
    tie_inputs = hashlib.sha256(
        json.dumps(
            {
                "engine_version": TIE_ENGINE,
                "population": population.population_hash,
                "label": TIE_LABEL,
                "accounts": [tie.accounts_tied, tie.accounts_total],
                "difference": str(tie.difference),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    parameters: dict[str, object] = {
        "je_test_id": str(je_test_id),
        "run_id": str(run["id"]),
        "score_version": int(row["score_version"]),
        "score_min": body.score_min,
        "top_n": body.top_n,
        "unpredictable_n": body.unpredictable_n,
        "by_score": selection.by_score,
        "unpredictable": selection.unpredictable,
        "strata": [],
    }
    async with uow(ctx.tenant) as tx:
        locked = await repo.test(tx.session, je_test_id, lock=True)
        if locked is None or locked["status"] != "scored":
            raise JeTestNotScored
        if row["sample_set_id"] is None:
            await set_repo.insert_set(
                tx.session,
                {
                    "id": sample_set_id,
                    "tenant_id": ctx.tenant_id,
                    "engagement_id": found.engagement_id,
                    "work_item_id": row["work_item_id"],
                    "title": "Journal entry testing selection",
                    "purpose": "Journal entries selected by risk score and unpredictably",
                    "program_step_key": None,
                    "created_by": ctx.user_id,
                },
            )
            await repo.set_sample_set(tx.session, je_test_id, sample_set_id)
            tx.record(
                "sample_set.created",
                target=Target("sample_set", sample_set_id),
                after=Ref(
                    engagement=found.engagement_id, work_item=cast(UUID, row["work_item_id"])
                ),
            )
        await population_repo.insert_population(
            tx.session,
            {
                "id": population_id,
                "tenant_id": ctx.tenant_id,
                "engagement_id": found.engagement_id,
                "work_item_id": row["work_item_id"],
                "source_kind": "general_ledger",
                "evidence_version_id": None,
                "gl_snapshot_id": row["gl_snapshot_id"],
                "query": json.dumps(
                    {"je_test_id": str(je_test_id), "score_version": int(row["score_version"])}
                ),
                "column_map": "{}",
                "record_count": len(population.records),
                "record_unit": "entries",
                "amount_total": population.total,
                "sha256": population.population_hash,
                "sampling_unit": "Journal entries",
                "deviation_definition": None,
                "pulled_at": await now(),
                "created_by": ctx.user_id,
            },
        )
        await population_repo.insert_records(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "population_id": population_id,
                    "ordinal": n,
                    "record_key": r.key,
                    "amount": r.amount,
                    "display": json.dumps({"score": str(by_ref.get(r.key, 0))}),
                }
                for n, r in enumerate(population.records)
            ],
        )
        await population_repo.insert_tie(
            tx.session,
            {
                "id": uuid4(),
                "tenant_id": ctx.tenant_id,
                "population_id": population_id,
                "position": 1,
                "label": TIE_LABEL,
                "left_amount": None,
                "comparisons": json.dumps(
                    [
                        {
                            "label": f"{tie.accounts_tied} of {tie.accounts_total} accounts",
                            "amount": str(tie.difference),
                            "citation_id": None,
                            "ledger_ref": str(row["gl_snapshot_id"]),
                        }
                    ]
                ),
                "difference": Decimal(0),
                "result": "tie",
                "explanation": None,
                "engine_version": TIE_ENGINE,
                "inputs_hash": tie_inputs,
                "created_by": ctx.user_id,
            },
        )
        tx.record(
            "population.created",
            target=Target("population", population_id),
            after=Ref(
                engagement=found.engagement_id,
                records=len(population.records),
                sha256=population.population_hash,
            ),
        )
        await set_repo.lock_set(tx.session, sample_set_id)
        version_no = await set_repo.next_version_no(tx.session, sample_set_id)
        await set_repo.insert_version(
            tx.session,
            {
                "id": version_id,
                "tenant_id": ctx.tenant_id,
                "sample_set_id": sample_set_id,
                "version_no": version_no,
                "population_id": population_id,
                "method": je_selection.METHOD,
                "parameters": json.dumps(parameters),
                "size_policy_version_id": None,
                "computed_size": len(selection.picks),
                "statistical_crosscheck_size": None,
                "override_size": None,
                "override_rationale": None,
                "final_size": len(selection.picks),
                "seed": seed,
                "seed_source": "server",
                "sampler_version": je_selection.VERSION,
                "inputs_hash": selection.inputs_hash,
                "created_by": ctx.user_id,
            },
        )
        tx.record(
            "sample_set.drawn",
            target=Target("sample_set_version", version_id),
            after=Ref(
                version=version_no,
                seed=seed,
                size=len(selection.picks),
                inputs=selection.inputs_hash,
            ),
        )
        tx.record(
            "je_test.selection_requested",
            target=Target("je_test", je_test_id),
            after=Ref(sample_set=sample_set_id, version=version_no),
        )
    given = SampleDrawInput(str(ctx.tenant_id), str(version_id), str(ctx.user_id))
    try:
        await dispatch(
            _draw_workflow(),
            given,
            id=f"sample_draw:{ctx.tenant_id}:{sample_set_id}:{version_no}",
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    except Exception:
        from abacus.modules.sampling.draw import fail_draw

        await fail_draw(ctx.tenant_id, version_id, "dispatch_failed")
        raise
    return version_id


# --- the view ------------------------------------------------------------------------------------


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split() if part)[:3].upper()


async def _selection(tenant: TenantContext, sample_set_id: UUID | None) -> SelectionOut | None:
    if sample_set_id is None:
        return None
    async with tenant_session(tenant) as session:
        versions = [
            v for v in await set_repo.versions(session, [sample_set_id]) if v["status"] != "failed"
        ]
        if not versions:
            return None
        version = versions[-1]
        items = await set_repo.items(session, cast(UUID, version["id"]))
    p = (
        json.loads(version["parameters"])
        if isinstance(version["parameters"], str)
        else dict(version["parameters"])
    )
    by_score = sum(1 for i in items if i["selection_reason"] == "risk_score")
    unpredictable = sum(1 for i in items if i["selection_reason"] == "unpredictable")
    if not items:  # still drawing: the counts the version was requested with
        by_score, unpredictable = int(p.get("by_score") or 0), int(p.get("unpredictable") or 0)
    approver = cast(UUID | None, version.get("approved_by"))
    names = await names_of([approver]) if approver is not None else {}
    approved_at = version.get("approved_at")
    return SelectionOut(
        sample_set_id=sample_set_id,
        version_no=int(version["version_no"]),
        by_score=by_score,
        unpredictable=unpredictable,
        score_min=int(p.get("score_min") or 0),
        seed=f"0x{int(version['seed']):06X}",
        sampler_version=str(version["sampler_version"]),
        approved_by_initials=_initials(names[approver])
        if approver is not None and approver in names
        else None,
        approved_on=approved_at.date() if approved_at is not None else None,
    )


async def je_test_view(ctx: AuthContext, je_test_id: UUID) -> JeTestOut:
    found = await _find(ctx, je_test_id, "je_test.read")
    row = found.row
    snapshot = await gl_snapshot_view(ctx.tenant, cast(UUID, row["gl_snapshot_id"]))
    facts = await je_fields_available(ctx.tenant, cast(UUID, row["gl_snapshot_id"]))
    score_version = int(row["score_version"])
    async with tenant_session(ctx.tenant) as session:
        criteria_rows = await repo.criteria(session, je_test_id)
        run = await repo.run_of(session, je_test_id, score_version) if score_version else None
    hits = cast(dict[str, int], (run or {}).get("hits") or {})
    criteria: list[CriterionOut] = []
    for c in criteria_rows:
        key = cast(CriterionKey, c["key"])
        usable, missing = je_scoring.available(key, facts.available)
        criteria.append(
            CriterionOut(
                position=int(c["position"]),
                key=key,
                params={k: str(v) for k, v in dict(c["params"]).items()},
                availability=JeCriterionStatus.AVAILABLE
                if usable
                else JeCriterionStatus.NOT_AVAILABLE,
                missing_fields=list(missing),
                hit_count=int(hits.get(key, 0)) if usable else 0,
            )
        )
    allowed: list[AllowedAction] = [a for a in _ACTIONS if await _may(ctx, a, found.resource)]
    if row["status"] == "scoring":
        allowed = []
    if row["status"] != "scored":
        allowed = [a for a in allowed if a != "sample_set.create"]
    return JeTestOut(
        id=je_test_id,
        status=cast(Any, row["status"]),  # Any: a JeTestStatus word the CHECK holds
        entries_count=int(run["entries_count"]) if run else 0,
        lines_count=snapshot.line_count,
        tie=tie_of(snapshot),
        criteria=criteria,
        unique_flagged=int(run["unique_flagged"]) if run else 0,
        score_version=score_version,
        engine_version=str(run["engine_version"]) if run else None,
        selection=await _selection(ctx.tenant, cast(UUID | None, row["sample_set_id"])),
        allowed_actions=allowed,
    )
