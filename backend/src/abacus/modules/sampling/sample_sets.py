"""Sample sets, versions, override and approval (A-03-T10; A-03 §3 F3 US-3.1 to US-3.4; SPEC-580;
ADR-340, ADR-160, ADR-042; DEC-1662).

A sample set belongs to a work item; it holds numbered versions, each drawn once and then frozen
(0520's trigger). A version is drawn in three steps:

- **Start** (`start_version`, a person): the population must be the work item's and carry at least
  one completeness tie (409 `completeness_tie_required`). The size is computed by code: the firm's
  published size table (`methodology.api.attribute_sample_size`, K-02's `attribute_sample_sizes`)
  for a non-statistical attribute draw, the exact binomial size for a statistical one (also shown
  beside the table as the cross-check), the strata's counts for a stratified draw. A smaller size
  is an override with a rationale; a size at or above the computed one is not (422
  `override_not_below`). The seed is 24 bits from `secrets`; no request carries one. Only the
  scenario loader on a synthetic firm passes a seed (`draw(..., scenario_seed=)`, 403
  `seed_not_allowed` otherwise). The version is inserted as `drawing`, audited
  `sample_set.drawn` (and `sample_set.override_requested`), and `SampleDrawWorkflow` starts.
- **Draw** (`draw.run_draw`, the workflow's activity): the selection by the frozen sampler, its
  strata and items in one transaction, then `draft` with its items and content hashes.
- **Approve** (`approve`, an engagement partner or manager who did not prepare it): the person saw
  the current content (409 `content_changed`), every tie of its population ties (409
  `population_not_tied`), an override is acknowledged (409 `override_not_acknowledged`), and the
  version is a draft (409 `version_not_draft`). One unit of work then supersedes the set's earlier
  approved version, approves this one, writes one level-2 sign-off through
  `review.api.record_sign_off`, audits and emits `sample_set.approved`.

Reads (`sample_sets_of`, `sample_set_view`, `draw_progress`, `items`, `export_xlsx`) authorise on
the set's own engagement: a walled person gets 404 and no count (INV-3).
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Final, cast
from uuid import UUID, uuid4

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from abacus.kernel.classification import classified
from abacus.kernel.clock import now, today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    TargetFacts,
    authorise,
    is_synthetic_firm,
    names_of,
)
from abacus.modules.methodology.api import attribute_sample_size
from abacus.modules.review.api import (
    Reviewable,
    ReviewableFacts,
    content_hash,
    record_sign_off,
    sign_off_states,
)
from abacus.modules.sampling import sample_set_repository as repo
from abacus.modules.sampling.compute import CURRENT, attribute_size
from abacus.modules.sampling.contract import (
    ApproveIn,
    CitationOut,
    DrawProgressOut,
    ParametersOut,
    PersonStampOut,
    SampleItemOut,
    SampleSetAction,
    SampleSetIn,
    SampleSetOut,
    SampleSetSummaryOut,
    SampleSetVersionOut,
    StratumIn,
    StratumOut,
    VersionIn,
    VersionStartedOut,
)
from abacus.modules.sampling.draw_types import SampleDrawInput

TARGET: Final = "sample_set_version"
GATE_KIND: Final = "sample_set_approval"
APPROVAL_LEVEL: Final = 2
SEED_BITS: Final = 24
ITEMS_PAGE: Final = 100
_HUNDRED: Final = Decimal(100)
_ACTIONS: Final[tuple[SampleSetAction, ...]] = (
    "sample_set.create",
    "sample_set.approve",
    "sample_set.export",
    "sample_set.generate_requests",
    "population.create",
    "sign_off.prepare",
)
_FORMULA_LEAD: Final = ("=", "+", "-", "@", "\t", "\r")
_ZIP_TIME: Final = (1980, 1, 1, 0, 0, 0)
_EPOCH: Final = datetime(2026, 1, 1)
Row = Mapping[str, Any]  # Any: database rows and stored JSON of mixed column types


class CompletenessTieRequired(DomainConflict):
    """A draw needs at least one completeness tie on its population (ADR-340 §7)."""

    code = "completeness_tie_required"


class PopulationNotTied(DomainConflict):
    """A tie of the version's population is off or unchecked: nobody may approve it."""

    code = "population_not_tied"


class OverrideNotAcknowledged(DomainConflict):
    """An override below the computed size must be acknowledged by the approver."""

    code = "override_not_acknowledged"


class ContentChanged(DomainConflict):
    """The version is not what the approver saw (`seen_hash`)."""

    code = "content_changed"


class VersionNotDraft(DomainConflict):
    """Only a drawn draft can be approved (drawing, approved, superseded and failed cannot)."""

    code = "version_not_draft"


class OverrideNotBelow(DomainInvalid):
    """An override is a size below the computed one; a larger size is not an override."""

    code = "override_not_below"


class ParametersInvalid(DomainInvalid):
    """The method's parameters are missing or inconsistent (`facts.field`)."""

    code = "parameters_invalid"


class SizeTableMissing(DomainInvalid):
    """No attribute sample size table is in effect for the firm (K-02's import loads it)."""

    code = "size_table_missing"


class SizeExceedsPopulation(DomainInvalid):
    """A size larger than the population cannot be drawn without replacement."""

    code = "size_exceeds_population"


class SeedNotAllowed(DomainForbidden):
    """Only the scenario loader on a synthetic firm may choose a seed (ADR-340 §5)."""

    code = "seed_not_allowed"


class SampleSetApproved(DomainEvent):
    """A version was approved (identifiers only): the addendum trigger "Sample approved"."""

    event_type: ClassVar[str] = "sample_set.approved"

    sample_set_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    approved_by: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class _Size:
    computed: int
    crosscheck: int | None
    policy: Mapping[str, object] | None


@dataclass(frozen=True)
class _Set:
    row: Row
    engagement_id: UUID
    resource: Resource


# --- pure helpers -----------------------------------------------------------------------------


def seed_hex(seed: int) -> str:
    return f"0x{seed:06X}"


def inputs_hash(
    method: str,
    seed: int,
    population_hash: str,
    size: int | None,
    strata: Sequence[StratumIn],
) -> str:
    """The draw's inputs as the sampler records them (`compute.v2_3`): the run re-checks it."""
    document = {
        "engine_version": CURRENT,
        "method": method,
        "seed": seed,
        "population_hash": population_hash,
        "size": size,
        "strata": [
            [
                None if s.min_amount is None else str(s.min_amount),
                None if s.max_amount is None else str(s.max_amount),
                s.test_rule,
                s.random_count,
            ]
            for s in strata
        ],
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()


def version_content_hash(version: Row, population_hash: str, items_hash: str) -> str:
    """What an approver sees and an approval records: the version's inputs, size and items."""
    return content_hash(
        {
            "sample_set_version_id": str(version["id"]),
            "version_no": int(version["version_no"]),
            "population_hash": population_hash,
            "inputs_hash": str(version["inputs_hash"]),
            "final_size": int(version["final_size"]),
            "override_size": version["override_size"],
            "items_hash": items_hash,
        }
    )


def stratified_size(amounts: Sequence[Decimal | None], strata: Sequence[StratumIn]) -> int:
    """How many items a stratified draw selects: every member of an `all` stratum and each
    `random` stratum's count (capped by its members), by code."""
    members = [0] * len(strata)
    for amount in amounts:
        if amount is None:
            raise ParametersInvalid(facts={"field": "strata"})
        homes = [
            i
            for i, s in enumerate(strata)
            if (s.min_amount is None or amount >= s.min_amount)
            and (s.max_amount is None or amount < s.max_amount)
        ]
        if len(homes) != 1:
            raise ParametersInvalid(facts={"field": "strata"})
        members[homes[0]] += 1
    total = 0
    for i, s in enumerate(strata):
        if (s.test_rule == "random") != (s.random_count is not None):
            raise ParametersInvalid(facts={"field": "strata"})
        if s.test_rule == "all":
            total += members[i]
        elif s.test_rule == "random":
            total += min(s.random_count or 0, members[i])
    return total


def tie_summary(rows: Sequence[Row]) -> tuple[str, Decimal | None]:
    """A population's ties in one word: `off` (with the first off difference), else `check`,
    else `tie`; no tie at all is `check`."""
    if not rows:
        return "check", None
    off = next((r for r in rows if r["result"] == "off"), None)
    if off is not None:
        difference = off["difference"]
        return "off", difference if isinstance(difference, Decimal) else None
    if any(r["result"] != "tie" for r in rows):
        return "check", None
    return "tie", None


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split() if part)[:3].upper()


# --- access -------------------------------------------------------------------------------------


async def _set(ctx: AuthContext, sample_set_id: UUID, action: str) -> _Set:
    async with tenant_session(ctx.tenant) as session:
        found = await repo.sample_set(session, sample_set_id)
    if found is None:
        raise NotFound("sample_set")
    engagement_id = cast(UUID, found["engagement_id"])
    ref = await get_ref(ctx, engagement_id)
    resource = ref.resource()
    await authorise(ctx, action, resource)
    return _Set(found, engagement_id, resource)


async def _version(ctx: AuthContext, sample_set_id: UUID, version_no: int) -> Row:
    async with tenant_session(ctx.tenant) as session:
        found = await repo.version(session, sample_set_id, version_no)
    if found is None:
        raise NotFound("sample_set_version")
    return found


async def _may(ctx: AuthContext, action: str, resource: Resource) -> bool:
    try:
        await authorise(ctx, action, resource)
    except Forbidden:
        return False
    return True


# --- sample sets --------------------------------------------------------------------------------


def _current(versions: Sequence[Row]) -> Row | None:
    """The version a set shows by default: its newest that did not fail."""
    usable = [v for v in versions if v["status"] != "failed"]
    return usable[-1] if usable else None


async def sample_sets_of(ctx: AuthContext, work_item_id: UUID) -> list[SampleSetSummaryOut]:
    """The header picker (DF-05): every sample set on the work item that has a drawn version.
    The caller authorised `sample_set.read` on the work item's engagement."""
    async with tenant_session(ctx.tenant) as session:
        sets = await repo.sets_of_work_item(session, work_item_id)
        versions = await repo.versions(session, [cast(UUID, s["id"]) for s in sets])
        populations = {
            cast(UUID, p["id"]): p
            for p in await repo.populations(
                session, sorted({cast(UUID, v["population_id"]) for v in versions})
            )
        }
    out: list[SampleSetSummaryOut] = []
    for s in sets:
        current = _current([v for v in versions if v["sample_set_id"] == s["id"]])
        if current is None:
            continue
        population = populations[cast(UUID, current["population_id"])]
        out.append(
            SampleSetSummaryOut(
                id=cast(UUID, s["id"]),
                title=str(s["title"]),
                current_version_no=int(current["version_no"]),
                status=current["status"],
                final_size=int(current["final_size"]),
                population_count=int(population["record_count"]),
            )
        )
    return out


async def create_sample_set(ctx: AuthContext, work_item_id: UUID, body: SampleSetIn) -> UUID:
    """US-3.1's first step: a named sample set on the work item, audited `sample_set.created`.
    The caller authorised `sample_set.create` on the work item's engagement."""
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work item")
    sample_set_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await repo.insert_set(
            tx.session,
            {
                "id": sample_set_id,
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "work_item_id": work_item_id,
                "title": body.title.strip(),
                "purpose": body.purpose,
                "program_step_key": body.program_step_key,
                "created_by": ctx.user_id,
            },
        )
        tx.record(
            "sample_set.created",
            target=Target("sample_set", sample_set_id),
            after=Ref(engagement=engagement_id, work_item=work_item_id),
        )
    return sample_set_id


# --- starting a draw ----------------------------------------------------------------------------


async def _size(
    tenant: TenantContext, body: VersionIn, amounts: Sequence[Decimal | None]
) -> _Size:
    p = body.parameters
    if body.method == "threshold_random_stratified":
        if not body.strata or body.override is not None:
            raise ParametersInvalid(facts={"field": "strata"})
        size = stratified_size(amounts, body.strata)
        if size < 1:
            raise ParametersInvalid(facts={"field": "strata"})
        return _Size(size, None, None)
    if body.strata:
        raise ParametersInvalid(facts={"field": "strata"})
    if p.tolerable_rate is None or p.confidence is None:
        raise ParametersInvalid(facts={"field": "parameters"})
    expected = p.expected_rate if p.expected_rate is not None else Decimal(0)
    if expected >= p.tolerable_rate:
        raise ParametersInvalid(facts={"field": "expected_rate"})
    crosscheck = attribute_size(p.confidence, p.tolerable_rate, expected)
    if body.method == "attribute_statistical":
        return _Size(crosscheck, None, None)
    if p.rmm is None:
        raise ParametersInvalid(facts={"field": "rmm"})
    try:
        found = await attribute_sample_size(
            tenant.tenant_id,
            rmm=p.rmm,
            tolerable_rate=p.tolerable_rate,
            expected_rate=expected,
            confidence=p.confidence,
            as_of=today(),
        )
    except LookupError:
        raise SizeTableMissing from None
    policy = {
        "standard_key": found.policy.standard_key,
        "name": found.policy.name,
        "version": found.policy.version,
        "version_id": str(found.policy.version_id),
    }
    return _Size(found.size, crosscheck, policy)


async def _seed(tenant: TenantContext, scenario_seed: int | None) -> tuple[int, str]:
    if scenario_seed is None:
        return secrets.randbits(SEED_BITS), "server"
    if not 0 <= scenario_seed < 2**SEED_BITS or not await is_synthetic_firm(tenant):
        raise SeedNotAllowed
    return scenario_seed, "scenario"


async def draw(
    ctx: AuthContext,
    sample_set_id: UUID,
    body: VersionIn,
    *,
    scenario_seed: int | None = None,
) -> tuple[int, UUID]:
    """Insert a `drawing` version and start its workflow; (version number, version id).

    `scenario_seed` is the scenario loader's (A-03-T16) on a synthetic firm only."""
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("sample_set.create", "role")
    found = await _set(ctx, sample_set_id, "sample_set.create")
    async with tenant_session(ctx.tenant) as session:
        population = next(iter(await repo.populations(session, [body.population_id])), None)
        if population is None or population["work_item_id"] != found.row["work_item_id"]:
            raise NotFound("population")
        ties = await repo.tie_results(session, [body.population_id])
        records = await repo.records(session, body.population_id)
    if not ties:
        raise CompletenessTieRequired
    amounts = [r["amount"] if isinstance(r["amount"], Decimal) else None for r in records]
    size = await _size(ctx.tenant, body, amounts)
    override = body.override
    if override is not None and override.size >= size.computed:
        raise OverrideNotBelow(facts={"computed_size": size.computed})
    final = size.computed if override is None else override.size
    if body.method != "threshold_random_stratified" and final > len(records):
        raise SizeExceedsPopulation(facts={"records": len(records)})
    seed, seed_source = await _seed(ctx.tenant, scenario_seed)
    stratified = body.method == "threshold_random_stratified"
    hashed = inputs_hash(
        body.method, seed, str(population["sha256"]), None if stratified else final, body.strata
    )
    parameters: dict[str, object] = {
        **body.parameters.model_dump(mode="json"),
        "strata": [s.model_dump(mode="json") for s in body.strata],
        "size_policy": size.policy,
    }
    version_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await repo.lock_set(tx.session, sample_set_id)
        version_no = await repo.next_version_no(tx.session, sample_set_id)
        await repo.insert_version(
            tx.session,
            {
                "id": version_id,
                "tenant_id": ctx.tenant_id,
                "sample_set_id": sample_set_id,
                "version_no": version_no,
                "population_id": body.population_id,
                "method": body.method,
                "parameters": json.dumps(parameters),
                "size_policy_version_id": None
                if size.policy is None
                else UUID(str(size.policy["version_id"])),
                "computed_size": size.computed,
                "statistical_crosscheck_size": size.crosscheck,
                "override_size": None if override is None else override.size,
                "override_rationale": None if override is None else override.rationale,
                "final_size": final,
                "seed": seed,
                "seed_source": seed_source,
                "sampler_version": CURRENT,
                "inputs_hash": hashed,
                "created_by": ctx.user_id,
            },
        )
        tx.record(
            "sample_set.drawn",
            target=Target(TARGET, version_id),
            after=Ref(version=version_no, seed=seed, size=final, inputs=hashed),
        )
        if override is not None:
            tx.record(
                "sample_set.override_requested",
                target=Target(TARGET, version_id),
                after=Ref(version=version_no, size=override.size, computed=size.computed),
            )
    given = SampleDrawInput(str(ctx.tenant_id), str(version_id), str(ctx.user_id))
    try:
        await dispatch(
            _workflow(),
            given,
            id=f"sample_draw:{ctx.tenant_id}:{sample_set_id}:{version_no}",
        )
    except Exception:
        await _fail(ctx.tenant, version_id, "dispatch_failed")
        raise
    return version_no, version_id


def _workflow() -> type:
    from abacus.modules.sampling.draw_workflow import SampleDrawWorkflow  # imports temporalio

    return SampleDrawWorkflow


async def _fail(tenant: TenantContext, version_id: UUID, code: str) -> None:
    async with uow(tenant) as tx:
        if await repo.mark_failed(tx.session, version_id, code):
            tx.record("sample_set.draw_failed", target=Target(TARGET, version_id))


async def start_version(
    ctx: AuthContext, sample_set_id: UUID, body: VersionIn, idempotency_key: str
) -> VersionStartedOut:
    """`POST /v1/sample-sets/{sid}/versions`: 202 with the status URL; a replay of the same key
    and body answers the first version and draws nothing."""

    async def run() -> tuple[int, dict[str, object]]:
        version_no, _ = await draw(ctx, sample_set_id, body)
        return 202, {"version_no": version_no}

    stored = await idempotent(
        ctx.tenant,
        route="sample_set.draw",
        key=idempotency_key,
        body={"sample_set_id": str(sample_set_id), **body.model_dump(mode="json")},
        run=run,
    )
    version_no = int(cast(int, stored.body["version_no"]))
    return VersionStartedOut(
        version_no=version_no,
        status_url=f"/v1/sample-sets/{sample_set_id}/versions/{version_no}/draw",
    )


# --- reads --------------------------------------------------------------------------------------


def _item_out(row: Row) -> SampleItemOut:
    raw = row["display"]
    display = cast(dict[str, str], json.loads(raw) if isinstance(raw, str) else raw or {})
    on: date | None = None
    try:
        on = date.fromisoformat(display.get("date", ""))
    except ValueError:
        on = None
    amount = row["amount"]
    return SampleItemOut(
        position=int(row["position"]),
        record_key=str(row["record_key"]),
        name=display.get("name") or display.get("counterparty") or None,
        hire_date=on,
        amount=amount if isinstance(amount, Decimal) else None,
        selection_reason=row["selection_reason"],
        stratum_position=row["stratum_position"],
    )


async def _stamps(
    ctx: AuthContext, versions: Sequence[Row]
) -> dict[UUID, tuple[PersonStampOut | None, PersonStampOut | None]]:
    """Per version: its L1 "Prepared · MD" (current content) and its approval "✓ HL"."""
    hashes = {cast(UUID, v["id"]): str(v["content_hash"]) for v in versions if v["content_hash"]}
    states = await sign_off_states(ctx.tenant, TARGET, list(hashes), hashes) if hashes else {}
    people: set[UUID] = {cast(UUID, v["approved_by"]) for v in versions if v["approved_by"]}
    for levels in states.values():
        people |= {s.signed_by for s in levels if s.signed_by is not None}
    names = await names_of(sorted(people))

    def stamp(user_id: UUID | None, at: datetime | None) -> PersonStampOut | None:
        if user_id is None or at is None:
            return None
        name = names.get(user_id, "")
        return PersonStampOut(user_id=user_id, name=name, initials=_initials(name), at=at)

    out: dict[UUID, tuple[PersonStampOut | None, PersonStampOut | None]] = {}
    for v in versions:
        vid = cast(UUID, v["id"])
        l1 = next((s for s in states.get(vid, []) if s.level == 1 and not s.stale), None)
        prepared = None if l1 is None else stamp(l1.signed_by, l1.signed_at)
        approved = stamp(
            cast(UUID | None, v["approved_by"]), cast(datetime | None, v["approved_at"])
        )
        out[vid] = (prepared, approved)
    return out


async def _allowed(
    ctx: AuthContext, found: _Set, version: Row, preparers: frozenset[UUID]
) -> list[SampleSetAction]:
    out: list[SampleSetAction] = []
    if ctx.tenant.actor_kind != "human":
        return out
    for action in _ACTIONS:
        resource = found.resource
        if action == "sample_set.approve":
            if version["status"] != "draft":
                continue
            resource = replace(resource, target=TargetFacts(preparer_user_ids=preparers))
        if action == "sample_set.generate_requests" and version["status"] != "approved":
            continue
        if await _may(ctx, action, resource):
            out.append(action)
    return out


async def _preparers(tenant: TenantContext, version: Row) -> frozenset[UUID]:
    """Who prepared a version: whoever drew it and everyone who signed L1 on it."""
    people = {cast(UUID, version["created_by"])}
    if version["content_hash"]:
        vid = cast(UUID, version["id"])
        states = await sign_off_states(tenant, TARGET, [vid], {vid: str(version["content_hash"])})
        people |= {s.signed_by for s in states.get(vid, []) if s.level == 1 and s.signed_by}
    return frozenset(people)


async def sample_set_view(
    ctx: AuthContext, sample_set_id: UUID, version_no: int | None
) -> SampleSetOut:
    """`GET /v1/sample-sets/{sid}?version=n`: AUD-11's projection of one version (by default
    the newest that did not fail)."""
    from abacus.modules.sampling.populations import population_view

    found = await _set(ctx, sample_set_id, "sample_set.read")
    async with tenant_session(ctx.tenant) as session:
        versions = await repo.versions(session, [sample_set_id])
        chosen = (
            _current(versions)
            if version_no is None
            else next((v for v in versions if v["version_no"] == version_no), None)
        )
        if chosen is None:
            raise NotFound("sample_set_version")
        vid = cast(UUID, chosen["id"])
        strata = await repo.strata(session, vid)
        items = await repo.items(session, vid)
        ties = await repo.tie_results(
            session, sorted({cast(UUID, v["population_id"]) for v in versions})
        )
        populations = {
            cast(UUID, p["id"]): p
            for p in await repo.populations(
                session, sorted({cast(UUID, v["population_id"]) for v in versions})
            )
        }
    population = await population_view(ctx, cast(UUID, chosen["population_id"]))
    stamps = await _stamps(ctx, versions)
    creators = await names_of(sorted({cast(UUID, v["created_by"]) for v in versions}))
    parameters = cast(
        dict[str, Any],  # Any: the stored parameters' JSON
        chosen["parameters"]
        if isinstance(chosen["parameters"], dict)
        else json.loads(str(chosen["parameters"])),
    )
    policy = cast(Mapping[str, object] | None, parameters.get("size_policy"))
    citations = (
        []
        if policy is None
        else [
            CitationOut(
                label=f"{policy['name']} v{policy['version']}", citation_id=None, verified=True
            )
        ]
    )

    def rate(key: str) -> Decimal | None:
        value = parameters.get(key)
        return None if value is None else Decimal(str(value))

    version_rows: list[SampleSetVersionOut] = []
    for v in versions:
        if v["status"] == "drawing" and v["id"] != chosen["id"]:
            continue
        pid = cast(UUID, v["population_id"])
        result, difference = tie_summary([t for t in ties if t["population_id"] == pid])
        prepared, approved = stamps[cast(UUID, v["id"])]
        version_rows.append(
            SampleSetVersionOut(
                version_no=int(v["version_no"]),
                status=v["status"],
                population_id=pid,
                population_label=str(population.record_unit),
                record_count=int(populations[pid]["record_count"]),
                tie_result=result,  # pyright: ignore[reportArgumentType] -- the table's CHECK
                tie_difference=difference,
                seed_hex=seed_hex(int(v["seed"])),
                final_size=int(v["final_size"]),
                override_pending=v["override_size"] is not None and v["status"] == "draft",
                created_by_name=creators.get(cast(UUID, v["created_by"]), ""),
                created_at=cast(datetime, v["created_at"]),
                prepared=prepared,
                approved=approved,
            )
        )
    amounts = [i["amount"] for i in items if isinstance(i["amount"], Decimal)]
    preparers = await _preparers(ctx.tenant, chosen)
    return SampleSetOut(
        id=sample_set_id,
        engagement_id=found.engagement_id,
        work_item_id=cast(UUID, found.row["work_item_id"]),
        title=str(found.row["title"]),
        purpose=cast(str | None, found.row["purpose"]),
        program_step_key=cast(str | None, found.row["program_step_key"]),
        version_no=int(chosen["version_no"]),
        status=chosen["status"],
        population=population,
        parameters=ParametersOut(
            method=chosen["method"],
            rmm=parameters.get("rmm"),
            tolerable_rate=rate("tolerable_rate"),
            expected_rate=rate("expected_rate"),
            confidence=rate("confidence"),
            computed_size=int(chosen["computed_size"]),
            statistical_crosscheck_size=chosen["statistical_crosscheck_size"],
            override_size=chosen["override_size"],
            override_rationale=chosen["override_rationale"],
            final_size=int(chosen["final_size"]),
            seed=int(chosen["seed"]),
            seed_hex=seed_hex(int(chosen["seed"])),
            seed_source=chosen["seed_source"],
            sampler_version=str(chosen["sampler_version"]),
            citations=citations,
        ),
        strata=[StratumOut.model_validate(s) for s in strata],
        items_total=len(items),
        items_amount=sum(amounts, Decimal(0)) if amounts else None,
        versions=version_rows,
        inputs_hash=str(chosen["inputs_hash"]),
        items_hash=cast(str | None, chosen["items_hash"]),
        content_hash=cast(str | None, chosen["content_hash"]),
        allowed_actions=await _allowed(ctx, found, chosen, preparers),
    )


async def draw_progress(ctx: AuthContext, sample_set_id: UUID, version_no: int) -> DrawProgressOut:
    """`…/draw`: what AUD-11e polls until the version is a draft or failed."""
    await _set(ctx, sample_set_id, "sample_set.read")
    version = await _version(ctx, sample_set_id, version_no)
    async with tenant_session(ctx.tenant) as session:
        items = await repo.items(session, cast(UUID, version["id"]))
    return DrawProgressOut(
        version_no=version_no,
        status=version["status"],
        items_done=len(items),
        items_total=int(version["final_size"]) if version["status"] == "drawing" else len(items),
        failure_code=cast(str | None, version["failure_code"]),
        items=[_item_out(i) for i in items],
    )


async def items_page(
    ctx: AuthContext, sample_set_id: UUID, version_no: int, q: str | None, cursor: str | None
) -> tuple[list[SampleItemOut], int, str | None]:
    """The selected items, filtered by name or record key ("Okoro" leaves Benjamin Okoro),
    100 to a page."""
    await _set(ctx, sample_set_id, "sample_set.read")
    version = await _version(ctx, sample_set_id, version_no)
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.items(session, cast(UUID, version["id"]))
    shown = [_item_out(r) for r in rows]
    if q:
        needle = q.strip().casefold()
        shown = [
            i
            for i in shown
            if needle in i.record_key.casefold() or needle in (i.name or "").casefold()
        ]
    start = int(cursor) if cursor is not None and cursor.isdigit() else 0
    page = shown[start : start + ITEMS_PAGE]
    following = start + ITEMS_PAGE
    return page, len(shown), str(following) if following < len(shown) else None


# --- approval -----------------------------------------------------------------------------------


async def approve(
    ctx: AuthContext, sample_set_id: UUID, version_no: int, body: ApproveIn
) -> SampleSetOut:
    """US-3.3: the level-2 approval (see the module note)."""
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("sample_set.approve", "role")
    found = await _set(ctx, sample_set_id, "sample_set.read")
    version = await _version(ctx, sample_set_id, version_no)
    preparers = await _preparers(ctx.tenant, version)
    target = replace(found.resource, target=TargetFacts(preparer_user_ids=preparers))
    await authorise(ctx, "sample_set.approve", target)
    if version["status"] != "draft":
        raise VersionNotDraft(facts={"status": str(version["status"])})
    hashed = str(version["content_hash"])
    if body.seen_hash.removeprefix("sha256:") != hashed:
        raise ContentChanged
    async with tenant_session(ctx.tenant) as session:
        ties = await repo.tie_results(session, [cast(UUID, version["population_id"])])
    if tie_summary(ties)[0] != "tie":
        raise PopulationNotTied
    if version["override_size"] is not None and not body.acknowledge_override:
        raise OverrideNotAcknowledged
    vid = cast(UUID, version["id"])
    async with uow(ctx.tenant) as tx:
        await repo.lock_set(tx.session, sample_set_id)
        await record_sign_off(
            tx, ctx, found.resource, found.engagement_id, TARGET, vid, APPROVAL_LEVEL, hashed
        )
        for old_id, old_no in await repo.supersede_approved(tx.session, sample_set_id, vid):
            tx.record(
                "sample_set.superseded",
                target=Target(TARGET, old_id),
                after=Ref(version=old_no, superseded_by=vid),
            )
        if not await repo.approve(
            tx.session,
            {
                "id": vid,
                "approved_by": ctx.user_id,
                "approved_at": now(),
                "row_version": int(version["row_version"]),
            },
        ):
            raise ContentChanged
        if version["override_size"] is not None:
            tx.record(
                "sample_set.override_approved",
                target=Target(TARGET, vid),
                after=Ref(version=version_no, size=int(version["override_size"])),
            )
        tx.record(
            "sample_set.approved",
            target=Target(TARGET, vid),
            after=Ref(version=version_no, content_hash=hashed),
        )
        tx.emit(
            SampleSetApproved(
                sample_set_id=sample_set_id,
                version_id=vid,
                engagement_id=found.engagement_id,
                work_item_id=cast(UUID, found.row["work_item_id"]),
                approved_by=ctx.user_id,
            )
        )
    return await sample_set_view(ctx, sample_set_id, version_no)


# --- export -------------------------------------------------------------------------------------


def _write(ws: Worksheet, row: Sequence[object]) -> None:
    ws.append(list(row))
    for cell in ws[ws.max_row]:
        if isinstance(cell.value, str) and cell.value.startswith(_FORMULA_LEAD):
            cell.data_type = "s"  # kept as text: never evaluated as a formula


def _rebuild(raw: bytes) -> bytes:
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for name in sorted(source.namelist()):
            entry = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            entry.create_system = 3
            target.writestr(entry, source.read(name))
    return out.getvalue()


def workbook(view: SampleSetOut, items: Sequence[SampleItemOut]) -> bytes:
    """The sample as a workbook, byte-identical for the same version (ADR-042): a cover sheet
    with the seed, algorithm, parameters and population hash, then the items."""
    p = view.parameters
    book = Workbook()
    cover = book.active
    if cover is None:  # a new Workbook always has its first sheet
        cover = book.create_sheet()
    cover.title = "Sample"
    for label, value in (
        ("Sample set", view.title),
        ("Version", str(view.version_no)),
        ("Status", view.status),
        ("Method", p.method),
        ("Sampler version", p.sampler_version),
        ("Seed", p.seed_hex),
        ("RMM", p.rmm or ""),
        ("Tolerable deviation rate", "" if p.tolerable_rate is None else str(p.tolerable_rate)),
        ("Expected deviation rate", "" if p.expected_rate is None else str(p.expected_rate)),
        ("Confidence", "" if p.confidence is None else str(p.confidence)),
        ("Computed size", str(p.computed_size)),
        ("Override size", "" if p.override_size is None else str(p.override_size)),
        ("Final size", str(p.final_size)),
        ("Population records", str(view.population.record_count)),
        ("Population SHA-256", view.population.sha256),
        ("Inputs hash", view.inputs_hash),
        ("Items hash", view.items_hash or ""),
    ):
        _write(cover, (label, value))
    sheet = book.create_sheet("Items")
    _write(sheet, ("Position", "Record", "Name", "Date", "Amount", "Reason", "Stratum"))
    for i in items:
        _write(
            sheet,
            (
                i.position,
                i.record_key,
                i.name or "",
                "" if i.hire_date is None else i.hire_date.isoformat(),
                "" if i.amount is None else str(i.amount),
                i.selection_reason,
                "" if i.stratum_position is None else i.stratum_position,
            ),
        )
    props = book.properties
    props.creator = "abacus"
    props.lastModifiedBy = "abacus"
    props.title = view.title
    props.created = _EPOCH
    props.modified = _EPOCH
    raw = io.BytesIO()
    book.save(raw)
    return _rebuild(raw.getvalue())


async def export_xlsx(ctx: AuthContext, sample_set_id: UUID, version_no: int) -> bytes:
    """US-3.4: "Open in Excel", audited `sample_set.exported`."""
    found = await _set(ctx, sample_set_id, "sample_set.export")
    view = await sample_set_view(ctx, sample_set_id, version_no)
    if view.items_hash is None:
        raise VersionNotDraft(facts={"status": view.status})
    version = await _version(ctx, sample_set_id, version_no)
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.items(session, cast(UUID, version["id"]))
    data = workbook(view, [_item_out(r) for r in rows])
    async with uow(ctx.tenant) as tx:
        tx.record(
            "sample_set.exported",
            target=Target(TARGET, cast(UUID, version["id"])),
            after=Ref(version=version_no, engagement=found.engagement_id),
        )
    return data


# --- the review grammar's view, the gate and the audit owners -----------------------------------


async def reviewable_facts(tenant: TenantContext, version_id: UUID) -> ReviewableFacts | None:
    """A drawn version's facts for the sign-off rules: L1 the preparer, L2 the approval."""
    async with tenant_session(tenant) as session:
        version = await repo.version_by_id(session, version_id)
        if version is None or not version["content_hash"]:
            return None
        found = await repo.sample_set(session, cast(UUID, version["sample_set_id"]))
    if found is None:
        return None
    return ReviewableFacts(
        target_type=TARGET,
        target_id=version_id,
        engagement_id=cast(UUID, found["engagement_id"]),
        content_hash=str(version["content_hash"]),
        version_no=int(version["version_no"]),
        preparer_user_ids=frozenset({cast(UUID, version["created_by"])}),
        required_levels=(1, 2),
        label=f"{found['title']} · Version {version['version_no']}",
        work_item_id=cast(UUID, found["work_item_id"]),
    )


async def reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    """Each sample set's current drawn version, for the sign-off matrix (P-04)."""
    async with tenant_session(tenant) as session:
        ids = await repo.sets_of_engagement(session, engagement_id)
        sets = {i: await repo.sample_set(session, i) for i in ids}
        versions = await repo.versions(session, ids)
    out: list[Reviewable] = []
    for sid in ids:
        current = _current([v for v in versions if v["sample_set_id"] == sid])
        row = sets.get(sid)
        if current is None or row is None or not current["content_hash"]:
            continue
        out.append(
            Reviewable(
                TARGET,
                cast(UUID, current["id"]),
                f"SMP {current['version_no']}",
                f"{row['title']} · Version {current['version_no']}",
                str(current["content_hash"]),
                True,
            )
        )
    return out


_SECTION_STATE: Final = {
    "drawing": "running",
    "draft": "draft_ready",
    "approved": "signed_off",
    "failed": "failed",
}


async def section_state(tenant: TenantContext, work_item_id: UUID) -> tuple[str, str | None]:
    """The Sample Selection rail row: its state word and sub-line ("2 sample sets"), by code.
    With several sets the least advanced one's state shows (a draft waits on someone)."""
    async with tenant_session(tenant) as session:
        sets = await repo.sets_of_work_item(session, work_item_id)
        versions = await repo.versions(session, [cast(UUID, s["id"]) for s in sets])
    states = [
        _SECTION_STATE.get(str(current["status"]), "not_started")
        for current in (
            _current([v for v in versions if v["sample_set_id"] == s["id"]]) for s in sets
        )
        if current is not None
    ]
    if not states:
        return "not_started", None
    order = ("failed", "running", "draft_ready", "signed_off")
    shown = min(states, key=order.index)
    count = len(sets)
    return shown, f"{count} sample set{'s' if count != 1 else ''}"


async def approval_gate(tenant: TenantContext, engagement_id: UUID) -> bool:
    """`sample_set_approval` (C13, HOME-02): met when no sample set on the engagement shows a
    draft or a draw in progress as its current version."""
    async with tenant_session(tenant) as session:
        ids = await repo.sets_of_engagement(session, engagement_id)
        versions = await repo.versions(session, ids)
    for sid in ids:
        current = _current([v for v in versions if v["sample_set_id"] == sid])
        if current is not None and current["status"] in ("draft", "drawing"):
            return False
    return True


__all__ = (
    "GATE_KIND",
    "TARGET",
    "approval_gate",
    "approve",
    "create_sample_set",
    "draw",
    "draw_progress",
    "export_xlsx",
    "items_page",
    "reviewable_facts",
    "reviewables",
    "sample_set_view",
    "sample_sets_of",
    "section_state",
    "start_version",
)
