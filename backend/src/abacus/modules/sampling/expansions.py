"""Sample expansions (A-08-T17; A-08 §3 F3; SPEC-657 AC-3.1 to AC-3.4; AUD-12 f to h; DEC-5307;
amber).

- **Request** (a person with `sample_expansion.request`): how many to add by score and
  unpredictably, or by key, a required rationale (422 `expansion_rationale_required`) and a named
  approver who is not the requester (422 `approver_required`). Nothing in the sample changes; one
  HOME-02 gate `sample_expansion_approval` waits on the approver (`assigned_only`).
- Named keys (Northwind's "Add participants", AC-3.4; DEC-5327) append last with reason `named`,
  each in the population and not yet selected (422 `expansion_key_invalid`).
- **Decide** (the named approver only, never the requester or an agent; `seen_hash` must be the
  request's content hash, else 409 `content_changed`). Approval appends a new sample-set version:
  the base version's items keep their positions (1 to n) and the additions follow: the next
  highest scores not yet selected, then seeded unpredictable picks from the rest, then named keys
  (`expand`, code; the draw workflow honours the prefix through the version's parameters).
- **Withdraw** (the requester, while pending).

"Selected becomes 50" is code (`resulting_count`).
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, names_of
from abacus.modules.sampling import sample_set_repository as set_repo
from abacus.modules.sampling.compute import je_selection
from abacus.modules.sampling.compute.draw import Stream, partial_fisher_yates

TARGET: Final = "sample_expansion"
REQUEST: Final = "sample_expansion.request"
DECIDE: Final = "sample_expansion.decide"
GATE: Final = "sample_expansion_approval"
_I = classified("internal")


class SampleExpansionRequested(DomainEvent):
    """A-08-T17: C13 raises the approver's `sample_expansion_approval` gate."""

    event_type: ClassVar[str] = "sample_expansion.requested"

    expansion_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    # A-08 §4.7 (DEC-5327): the named approver, told by `sample_expansion_approval_requested`.
    approver_user_id: Annotated[UUID | None, _I] = None
    requested_by: Annotated[UUID | None, _I] = None


class SampleExpansionDecided(DomainEvent):
    """Approved, rejected or withdrawn: the gate closes."""

    event_type: ClassVar[str] = "sample_expansion.decided"

    expansion_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    status: Annotated[str, _I]


class RationaleRequired(DomainInvalid):
    code = "expansion_rationale_required"


class ApproverRequired(DomainInvalid):
    code = "approver_required"


class ContentChanged(DomainConflict):
    code = "content_changed"


class ExpansionClosed(DomainConflict):
    code = "expansion_not_pending"


class ExpansionKeyInvalid(DomainInvalid):
    code = "expansion_key_invalid"


class ExpansionTooLarge(DomainInvalid):
    code = "expansion_exceeds_population"


@dataclass(frozen=True)
class Expanded:
    picks: tuple[je_selection.Pick, ...]
    items_hash: str
    prefix_hash: str


def expand(
    base: Sequence[je_selection.Pick],
    scores: Sequence[je_selection.Scored],
    *,
    add_by_score: int,
    add_unpredictable: int,
    add_keys: Sequence[str] = (),
    seed: int,
) -> Expanded:
    """The base picks unchanged, then the next by score, the seeded unpredictable, the named."""
    taken = {p.entry_ref for p in base}
    ranked = sorted(
        (s for s in scores if s.entry_ref not in taken and s.score >= 1),
        key=lambda s: (-s.score, s.entry_ref),
    )
    by_score = ranked[:add_by_score]
    taken |= {s.entry_ref for s in by_score}
    rest = sorted((s for s in scores if s.entry_ref not in taken), key=lambda s: s.entry_ref)
    if add_unpredictable > len(rest):
        raise ExpansionTooLarge(facts={"field": "add_unpredictable"})
    drawn = [rest[j] for j in partial_fisher_yates(Stream(seed), len(rest), add_unpredictable)]
    taken |= {s.entry_ref for s in drawn}
    # AC-3.4 (DEC-5327): named keys last, each one in the population and not yet selected.
    known = {s.entry_ref: s for s in scores}
    named: list[je_selection.Scored] = []
    for key in dict.fromkeys(add_keys):
        found = known.get(key)
        if found is None or key in taken:
            raise ExpansionKeyInvalid(facts={"field": "add_item_keys"})
        named.append(found)
        taken.add(key)
    picks = list(base)
    n = len(picks)
    for reason, group in (("risk_score", by_score), ("unpredictable", drawn), ("named", named)):
        for s in group:
            n += 1
            picks.append(
                je_selection.Pick(n, s.entry_ref, cast(je_selection.Reason, reason), s.score)
            )
    return Expanded(
        tuple(picks), je_selection.items_hash(picks), je_selection.items_hash(list(base))
    )


# --- the service ---------------------------------------------------------------------------------

_BASE: Final = text(
    "SELECT v.id, v.sample_set_id, v.version_no, v.status, v.population_id, v.parameters, "
    "s.engagement_id, s.work_item_id FROM sample_set_versions v JOIN sample_sets s "
    "ON s.id = v.sample_set_id WHERE v.sample_set_id = :s AND v.status = 'approved' "
    "ORDER BY v.version_no DESC LIMIT 1"
)
_INSERT: Final = text(
    "INSERT INTO sample_expansions (tenant_id, engagement_id, work_item_id, sample_set_id, "
    "base_version_id, base_count, add_by_score, add_unpredictable, add_item_keys, rationale, "
    "rationale_suggestion_id, requested_by, approver_user_id, content_hash) VALUES (:t, :e, :w, "
    ":s, :b, :n, :score, :unp, :keys, :r, :sug, :u, :a, :h) RETURNING id"
)
_ONE: Final = text(
    "SELECT id, engagement_id, work_item_id, sample_set_id, base_version_id, base_count, "
    "add_by_score, add_unpredictable, add_item_keys, requested_by, requested_at, "
    "approver_user_id, status, content_hash, resulting_version_id FROM sample_expansions "
    "WHERE id = :id"
)
_DECIDE: Final = text(
    "UPDATE sample_expansions SET status = :status, decided_by = :u, decided_actor_kind = "
    "'human', decided_at = clock_timestamp(), resulting_version_id = :v WHERE id = :id "
    "AND status = 'pending_approval' RETURNING id"
)
_WITHDRAW: Final = text(
    "UPDATE sample_expansions SET status = 'withdrawn' WHERE id = :id "
    "AND status = 'pending_approval' AND requested_by = :u RETURNING id"
)
_PENDING: Final = text(
    "SELECT id, engagement_id, work_item_id, approver_user_id FROM sample_expansions "
    "WHERE status = 'pending_approval'"
)


@dataclass(frozen=True)
class ExpansionView:
    id: UUID
    status: str
    base_count: int
    add_count: int
    resulting_count: int
    approver_user_id: UUID
    approver_name: str
    requested_at: object
    content_hash: str
    resulting_version_id: UUID | None


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


def _hash(
    base: UUID, by_score: int, unpredictable: int, keys: Sequence[str], rationale: str
) -> str:
    body = json.dumps(
        {"base": str(base), "s": by_score, "u": unpredictable, "k": list(keys), "r": rationale},
        sort_keys=True,
    )
    return hashlib.sha256(body.encode()).hexdigest()


async def _resource(ctx: AuthContext, engagement_id: UUID) -> object:
    from abacus.modules.engagements.api import engagement_resource_of

    return await engagement_resource_of(ctx.tenant, engagement_id)


async def _view(tenant: TenantContext, expansion_id: UUID) -> ExpansionView:
    async with tenant_session(tenant) as session:
        r = (await session.execute(_ONE, {"id": expansion_id})).mappings().first()
    if r is None:
        raise NotFound(TARGET)
    add = int(r["add_by_score"]) + int(r["add_unpredictable"]) + len(r["add_item_keys"] or [])
    names = await names_of([r["approver_user_id"]])
    return ExpansionView(
        id=r["id"],
        status=str(r["status"]),
        base_count=int(r["base_count"]),
        add_count=add,
        resulting_count=int(r["base_count"]) + add,
        approver_user_id=r["approver_user_id"],
        approver_name=names.get(r["approver_user_id"], ""),
        requested_at=r["requested_at"],
        content_hash=str(r["content_hash"]),
        resulting_version_id=r["resulting_version_id"],
    )


async def request_expansion(
    ctx: AuthContext,
    sample_set_id: UUID,
    *,
    add_by_score: int,
    add_unpredictable: int,
    add_item_keys: Sequence[str],
    rationale: str,
    approver_user_id: UUID | None,
    rationale_suggestion_id: UUID | None = None,
) -> ExpansionView:
    _human(ctx, REQUEST)
    if not rationale.strip():
        raise RationaleRequired(facts={"field": "rationale"})
    if approver_user_id is None or approver_user_id == ctx.user_id:
        raise ApproverRequired(facts={"field": "approver_user_id"})
    if add_by_score + add_unpredictable + len(add_item_keys) == 0:
        raise DomainInvalid(facts={"field": "add_by_score"})
    async with tenant_session(ctx.tenant) as session:
        base = (await session.execute(_BASE, {"s": sample_set_id})).mappings().first()
        if base is None:
            raise NotFound("sample_set")
        count = len(await set_repo.items(session, base["id"]))
    await authorise(ctx, REQUEST, await _resource(ctx, base["engagement_id"]))  # type: ignore[arg-type] -- a Resource
    digest = _hash(base["id"], add_by_score, add_unpredictable, add_item_keys, rationale.strip())
    async with uow(ctx.tenant) as tx:
        made = cast(
            UUID,
            await tx.session.scalar(
                _INSERT,
                {
                    "t": ctx.tenant_id,
                    "e": base["engagement_id"],
                    "w": base["work_item_id"],
                    "s": sample_set_id,
                    "b": base["id"],
                    "n": count,
                    "score": add_by_score,
                    "unp": add_unpredictable,
                    "keys": list(add_item_keys),
                    "r": rationale.strip(),
                    "sug": rationale_suggestion_id,
                    "u": ctx.user_id,
                    "a": approver_user_id,
                    "h": digest,
                },
            ),
        )
        tx.record("sample_expansion.requested", target=Target(TARGET, made))
        tx.emit(
            SampleExpansionRequested(
                expansion_id=made,
                engagement_id=base["engagement_id"],
                approver_user_id=approver_user_id,
                requested_by=ctx.user_id,
            )
        )
    return await _view(ctx.tenant, made)


async def record_decision(
    ctx: AuthContext, expansion_id: UUID, decision: str, seen_hash: str
) -> ExpansionView:
    """The named approver approves (a new version appended) or rejects."""
    _human(ctx, DECIDE)
    current = await _view(ctx.tenant, expansion_id)
    if current.approver_user_id != ctx.user_id:
        raise Forbidden(DECIDE, "role")  # only the named approver decides (AC-3.3)
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_ONE, {"id": expansion_id})).mappings().one()
    await authorise(ctx, DECIDE, await _resource(ctx, row["engagement_id"]))  # type: ignore[arg-type] -- a Resource
    if current.status != "pending_approval":
        raise ExpansionClosed(facts={"status": current.status})
    if seen_hash != current.content_hash:
        raise ContentChanged(facts={"expansion": str(expansion_id)})
    version_id: UUID | None = None
    if decision == "approved":
        version_id = await _append_version(ctx, row)
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(
            _DECIDE, {"status": decision, "u": ctx.user_id, "v": version_id, "id": expansion_id}
        )
        if done is None:
            raise ExpansionClosed(facts={"status": "decided"})
        tx.record(
            f"sample_expansion.{decision}",
            target=Target(TARGET, expansion_id),
            after=Ref(version=version_id) if version_id else None,
        )
        tx.emit(
            SampleExpansionDecided(
                expansion_id=expansion_id,
                engagement_id=cast(UUID, row["engagement_id"]),
                status=decision,
            )
        )
    return await _view(ctx.tenant, expansion_id)


async def withdraw(ctx: AuthContext, expansion_id: UUID) -> ExpansionView:
    _human(ctx, REQUEST)
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_ONE, {"id": expansion_id})).mappings().first()
    if row is None:
        raise NotFound(TARGET)
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(_WITHDRAW, {"id": expansion_id, "u": ctx.user_id})
        if done is None:
            raise ExpansionClosed(facts={"expansion": str(expansion_id)})
        tx.record("sample_expansion.withdrawn", target=Target(TARGET, expansion_id))
        tx.emit(
            SampleExpansionDecided(
                expansion_id=expansion_id, engagement_id=row["engagement_id"], status="withdrawn"
            )
        )
    return await _view(ctx.tenant, expansion_id)


async def _append_version(ctx: AuthContext, row: dict[str, object] | object) -> UUID:
    """A new sample-set version: the base's items first, in place, then the additions; drawn by
    the same workflow (its parameters name the expansion, so the draw honours the prefix)."""
    from abacus.modules.sampling import je_repository as repo

    r = cast("dict[str, object]", dict(row))  # type: ignore[call-overload] -- a mapping row
    async with tenant_session(ctx.tenant) as session:
        base = (await session.execute(_BASE, {"s": r["sample_set_id"]})).mappings().one()
        items = await set_repo.items(session, cast(UUID, base["id"]))
        params = base["parameters"]
        params = json.loads(params) if isinstance(params, str) else dict(params)
        run_id = UUID(str(params["run_id"]))
        scores = [
            je_selection.Scored(ref, s) for ref, s, _ in await repo.all_scores(session, run_id)
        ]
    by_ref = {s.entry_ref: s.score for s in scores}
    prefix = [
        je_selection.Pick(
            int(i["position"]),
            str(i["record_key"]),
            i["selection_reason"],
            by_ref.get(str(i["record_key"]), 0),
        )
        for i in sorted(items, key=lambda i: int(i["position"]))
    ]
    seed = secrets.randbits(24)
    expanded = expand(
        prefix,
        scores,
        add_by_score=int(cast(int, r["add_by_score"])),
        add_unpredictable=int(cast(int, r["add_unpredictable"])),
        add_keys=[str(k) for k in cast("list[str]", r["add_item_keys"] or [])],
        seed=seed,
    )
    version_id = uuid4()
    params["expansion"] = {
        "expansion_id": str(r["id"]),
        "base_version_id": str(base["id"]),
        "prefix_hash": expanded.prefix_hash,
        "add_by_score": int(cast(int, r["add_by_score"])),
        "add_unpredictable": int(cast(int, r["add_unpredictable"])),
        "add_item_keys": [str(k) for k in cast("list[str]", r["add_item_keys"] or [])],
    }
    async with uow(ctx.tenant) as tx:
        await set_repo.lock_set(tx.session, cast(UUID, r["sample_set_id"]))
        version_no = await set_repo.next_version_no(tx.session, cast(UUID, r["sample_set_id"]))
        await set_repo.insert_version(
            tx.session,
            {
                "id": version_id,
                "tenant_id": ctx.tenant_id,
                "sample_set_id": r["sample_set_id"],
                "version_no": version_no,
                "population_id": base["population_id"],
                "method": je_selection.METHOD,
                "parameters": json.dumps(params),
                "size_policy_version_id": None,
                "computed_size": len(expanded.picks),
                "statistical_crosscheck_size": None,
                "override_size": None,
                "override_rationale": None,
                "final_size": len(expanded.picks),
                "seed": seed,
                "seed_source": "server",
                "sampler_version": je_selection.VERSION,
                "inputs_hash": expanded.items_hash,
                "created_by": ctx.user_id,
            },
        )
        tx.record(
            "sample_set.drawn",
            target=Target("sample_set_version", version_id),
            after=Ref(version=version_no, seed=seed, size=len(expanded.picks)),
        )
    from abacus.modules.sampling.je_tests import dispatch_draw

    await dispatch_draw(ctx, cast(UUID, r["sample_set_id"]), version_id, version_no)
    return version_id


# --- HOME-02: the approver's gate ----------------------------------------------------------------


async def expansions_due(tenant: TenantContext, engagement_id: UUID | None) -> list[object]:
    from abacus.modules.review.api import OpenGate

    async with tenant_session(tenant) as session:
        rows = (await session.execute(_PENDING)).mappings().all()
    return [
        OpenGate(
            r["id"],
            r["engagement_id"],
            assignee_user_id=r["approver_user_id"],
            work_item_id=r["work_item_id"],
        )
        for r in rows
        if engagement_id is None or r["engagement_id"] == engagement_id
    ]


def register_expansion_gate() -> None:
    from abacus.modules.review.api import GateSource, register_gate_source

    register_gate_source(
        GateSource(
            GATE,
            "decision",
            "je_test.read",
            frozenset({"sample_expansion.requested", "sample_expansion.decided"}),
            expansions_due,  # type: ignore[arg-type] -- returns OpenGate rows
            assigned_only=True,
        )
    )
