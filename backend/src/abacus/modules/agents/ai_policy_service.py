"""The AI policy's services (G-02-T24; ADR-186, ADR-187; SPEC-349 AC-31..AC-44; DEC-712).

Reads: the policy (effective, pending, scheduled, draft summary, the gate catalogue with the
firm's overrides, locks, immediate controls, sub-processors and model family from the
provider-terms register), the version history and one version with its diff, and the effective
policy at a time for an engagement type (`effective_ai_policy`, also `agents.api`'s).

Writes, each in one unit of work with its audit event:

- **Draft** (`ai_policy.draft_saved`, `ai_policy.draft_discarded`): one per firm, saved against
  If-Match (409 `stale_version`), stricter-only (422 `policy_loosening_refused`). A security admin
  may change the `client_data` section only (AC-40).
- **Publish request** (`ai_policy.publish_requested`): the draft becomes the next version,
  `awaiting_approval`, effective from the chosen business date; the named approver must be another
  partner (409 `approver_must_differ`). The approver is notified (`ai_policy_approval_requested`).
- **Approve, decline** (`ai_policy.approved`, `ai_policy.declined`): only the named approver; the
  database trigger holds the same rules. **Withdraw** (`ai_policy.withdrawn`): only the requester.

Firm-level approvals are not C13 human gates (C13 is engagement-scoped, as G-01-T09's wall gate):
the approver's Approvals queue entry is the notification (DEC-712).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import RowMapping, text

from abacus.kernel import clock, provider_terms
from abacus.kernel._flags import AI_POLICY_V1
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.agents._ai_policy_defaults import GATES, LOCKS, SCHEMA_VERSION, SECTIONS
from abacus.modules.agents.ai_policy_errors import AiPolicyLoosened, ApproverMustDiffer
from abacus.modules.agents.ai_policy_validator import check_stricter_only
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    agents_pause,
    agents_paused,
    ai_client_data_opted_in,
    allowed_actions,
    authorise,
    firm_tenancy,
    member_facts,
    names_of,
)

MODEL_ROUTE: Final = "bedrock"
_DECLINE_REASONS: Final = frozenset({"needs_changes", "wrong_effective_date", "other"})
PLATFORM_FLOOR: Final = ("client_data.client_drafts_enabled", "governance.trace_retention_years")
# The viewer's ADM-04 actions, probed at the firm (AC-33, AC-40): read-only without the draft.
VIEWER_ACTIONS: Final = (
    "ai_policy.read",
    "ai_policy.draft",
    "ai_policy.publish",
    "ai_policy.approve",
    "firm_agents.pause",
)


class StaleDraft(DomainConflict):
    """The draft changed since it was read (If-Match)."""

    code = "stale_version"


class NoPendingVersion(DomainConflict):
    """There is no version awaiting approval with that number."""

    code = "no_pending_version"


class PendingVersionExists(DomainConflict):
    """A version is already awaiting approval: withdraw it first."""

    code = "pending_version_exists"


class ApprovalRequested(DomainEvent):
    """A version awaits a named partner's approval (identifiers only)."""

    event_type: ClassVar[str] = "ai_policy.publish_requested"

    version_no: Annotated[int, classified("internal")]
    assignee_user_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class Version:
    version_no: int
    state: str
    sections: dict[str, object]
    schema_version: int
    effective_from: datetime
    requested_by: UUID | None
    requested_at: datetime | None
    approver_user_id: UUID | None
    decided_by: UUID | None
    decided_at: datetime | None
    decline_reason: str | None
    carried_over: bool


@dataclass(frozen=True)
class Draft:
    base_version_no: int
    sections: dict[str, object]
    version: int
    updated_at: datetime | None
    updated_by: UUID | None


@dataclass(frozen=True)
class PolicyView:
    effective: Version
    pending: Version | None
    scheduled: Version | None
    draft: Draft | None
    gates: list[dict[str, object]]
    locks: list[tuple[str, str]]
    opted_in: bool
    paused_at: datetime | None
    paused_by: UUID | None
    sub_processors: list[dict[str, object]]
    model_family: str | None
    real_firm: bool
    actions: frozenset[str] = frozenset()


# --- reading -------------------------------------------------------------------------------------


def _json(value: object) -> dict[str, object]:
    if isinstance(value, str):
        value = json.loads(value)
    return cast(dict[str, object], value)


def _version(row: RowMapping) -> Version:
    return Version(
        int(row["version_no"]),
        str(row["state"]),
        _json(row["sections"]),
        int(row["schema_version"]),
        row["effective_from"],
        row["requested_by"],
        row["requested_at"],
        row["approver_user_id"],
        row["decided_by"],
        row["decided_at"],
        row["decline_reason"],
        bool(row["carried_over"]),
    )


async def _versions(tenant: TenantContext) -> list[Version]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text("SELECT * FROM autonomy_policy_versions ORDER BY version_no DESC")
            )
        ).mappings()
        found = [_version(r) for r in rows]
    if all(v.version_no != 1 for v in found):
        found.append(_IMPLICIT_V1)
    return found


# A firm created after migration 0272's carry-over has no stored version: it reads the compiled
# defaults as its v1, published and carried over (DEC-711), until it publishes v2.
_IMPLICIT_V1: Final = Version(
    1,
    "published",
    SECTIONS,
    SCHEMA_VERSION,
    datetime(2026, 1, 1, tzinfo=UTC),
    None,
    None,
    None,
    None,
    None,
    None,
    True,
)


async def _draft(tenant: TenantContext) -> Draft | None:
    async with tenant_session(tenant) as session:
        row = (
            (await session.execute(text("SELECT * FROM autonomy_policy_drafts")))
            .mappings()
            .first()
        )
    if row is None:
        return None
    return Draft(
        int(row["base_version_no"]),
        _json(row["sections"]),
        int(row["version"]),
        row["updated_at"],
        row["updated_by"],
    )


def effective_of(versions: list[Version], at: datetime) -> Version | None:
    """The newest published version whose effective time has passed at `at`."""
    published = [v for v in versions if v.state == "published" and v.effective_from <= at]
    return max(published, key=lambda v: (v.effective_from, v.version_no), default=None)


def superseded(versions: list[Version], version: Version, at: datetime) -> bool:
    effective = effective_of(versions, at)
    return (
        version.state == "published"
        and effective is not None
        and (version.effective_from, version.version_no)
        < (effective.effective_from, effective.version_no)
    )


def changed_cells(
    before: Mapping[str, object] | None, after: Mapping[str, object]
) -> list[tuple[str, str | None, str | None]]:
    """Changed cells as (path, before, after), each value its JSON text; code, never a model."""

    def flat(sections: Mapping[str, object] | None) -> dict[str, str]:
        out: dict[str, str] = {}
        for head, node in (sections or {}).items():
            if isinstance(node, dict):
                for key, value in cast(dict[str, object], node).items():
                    out[f"{head}.{key}"] = json.dumps(value)
            else:
                out[head] = json.dumps(node, sort_keys=True)
        return out

    a, b = flat(before), flat(after)
    return [(p, a.get(p), b.get(p)) for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p)]


def gate_rows(sections: Mapping[str, object]) -> list[dict[str, object]]:
    overrides = {
        str(g.get("action_key")): bool(g.get("policy_acceptance_on", False))
        for g in cast(list[dict[str, object]], sections.get("gates", []))
    }
    return [
        {**gate, "policy_acceptance_on": overrides.get(str(gate["gate_key"]), False)}
        for gate in GATES
    ]


def locks_for(
    real_firm: bool, security_admin_only: bool, read_only: bool = False
) -> list[tuple[str, str]]:
    found = [
        (path, "policy_principal_dormant" if "policy" in path else "platform_floor")
        for path in LOCKS
    ]
    # Display only: the floor the validator holds (no drafts for clients, seven-year traces).
    found += [(path, "platform_floor") for path in PLATFORM_FLOOR]
    if real_firm:
        found += [(f"auto_mode_defaults.{k}", "real_firm_season_1") for k in _auto_keys()]
    if security_admin_only:
        found += [(head, "client_data_only") for head in SECTIONS if head != "client_data"]
    if read_only:  # "Only partners can change the AI policy." (AC-33)
        found += [(head, "not_a_partner") for head in SECTIONS]
    return found


def _auto_keys() -> list[str]:
    return sorted(cast(dict[str, object], SECTIONS["auto_mode_defaults"]))


async def _real_firm(tenant: TenantContext) -> bool:
    tenancy = await firm_tenancy(tenant)
    return tenancy is None or not tenancy.synthetic


def _sub_processors(on: date) -> tuple[list[dict[str, object]], str | None]:
    """The model route's provider and its named sub-processors, from the register (DF-16); the
    register names no model family yet, so none is shown (DEC-87: a model, not a processor)."""
    entry = provider_terms.covering(MODEL_ROUTE, on)
    if entry is None:
        return [], None
    rows: list[dict[str, object]] = [
        {"name": name, "purpose": "model_inference", "region": entry.region}
        for name in (entry.provider, *entry.subprocessors)
    ]
    return rows, None


async def _open(ctx: AuthContext, action: str) -> None:
    """The stub's order, now open: a client 404; a principal that is not a person 403; the
    action; the flag off 404."""
    if ctx.client:
        raise NotFound("ai_policy")
    if ctx.tenant.actor_kind not in ("human", "support"):
        raise Forbidden(action, "role")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, AI_POLICY_V1):
        raise NotFound("ai_policy.v1")


async def read_policy(ctx: AuthContext) -> PolicyView:
    await _open(ctx, "ai_policy.read")
    now = await clock.now(ctx.tenant)
    versions = await _versions(ctx.tenant)
    effective = effective_of(versions, now)
    if effective is None:
        raise NotFound("ai_policy_version")
    pending = next((v for v in versions if v.state == "awaiting_approval"), None)
    scheduled = next(
        (v for v in versions if v.state == "published" and v.effective_from > now), None
    )
    real_firm = await _real_firm(ctx.tenant)
    processors, family = _sub_processors(now.date())
    actions = await allowed_actions(ctx, Resource.firm(ctx.tenant_id), VIEWER_ACTIONS)
    # A drafter who may not publish (the security admin) edits fieldset D only (AC-40).
    security_admin = "ai_policy.draft" in actions and "ai_policy.publish" not in actions
    return PolicyView(
        effective,
        pending,
        scheduled,
        await _draft(ctx.tenant) or Draft(effective.version_no, effective.sections, 0, None, None),
        gate_rows(effective.sections),
        locks_for(real_firm, security_admin, "ai_policy.draft" not in actions),
        await ai_client_data_opted_in(ctx.tenant),
        *(await agents_pause(ctx.tenant) or (None, None)),
        processors,
        family,
        real_firm,
        actions,
    )


async def list_versions(ctx: AuthContext) -> tuple[list[Version], datetime]:
    await _open(ctx, "ai_policy.read")
    return await _versions(ctx.tenant), await clock.now(ctx.tenant)


async def read_version(ctx: AuthContext, version_no: int) -> tuple[Version, Version | None]:
    await _open(ctx, "ai_policy.read")
    versions = await _versions(ctx.tenant)
    found = next((v for v in versions if v.version_no == version_no), None)
    if found is None:
        raise NotFound("ai_policy_version")
    before = next((v for v in versions if v.version_no == version_no - 1), None)
    return found, before


@dataclass(frozen=True)
class Effective:
    version: Version
    at: datetime
    auto_mode: bool
    auto_mode_effective: bool
    real_firm: bool
    paused: bool


async def effective_ai_policy(
    tenant: TenantContext, engagement_type: str, at: datetime | None = None
) -> Effective | None:
    """The version effective at `at` (now on the firm's clock), for other modules: Auto mode is
    stored per type and forced off for real firms until runtime v2 (AC-39)."""
    when = at or await clock.now(tenant)
    version = effective_of(await _versions(tenant), when)
    if version is None:
        return None
    auto = bool(
        cast(dict[str, object], version.sections.get("auto_mode_defaults", {})).get(
            engagement_type, False
        )
    )
    real_firm = await _real_firm(tenant)
    return Effective(
        version,
        when,
        auto,
        auto and not real_firm,
        real_firm,
        await agents_paused(tenant) is not None,
    )


async def read_effective(ctx: AuthContext, engagement_type: str, at: datetime | None) -> Effective:
    await _open(ctx, "ai_policy.read")
    found = await effective_ai_policy(ctx.tenant, engagement_type, at)
    if found is None:
        raise NotFound("ai_policy_version")
    return found


# --- the draft -----------------------------------------------------------------------------------


async def read_draft(ctx: AuthContext) -> tuple[Draft, Version]:
    await _open(ctx, "ai_policy.draft")
    now = await clock.now(ctx.tenant)
    effective = effective_of(await _versions(ctx.tenant), now)
    if effective is None:
        raise NotFound("ai_policy_version")
    draft = await _draft(ctx.tenant)
    if draft is None:
        draft = Draft(effective.version_no, effective.sections, 0, None, None)
    return draft, effective


async def _security_admin_scope(
    ctx: AuthContext, base: Mapping[str, object], new: Mapping[str, object]
) -> None:
    """AC-40: a security admin changes the client-data section only; a refusal names the first
    changed cell outside it."""
    allowed = await allowed_actions(ctx, Resource.firm(ctx.tenant_id), ("ai_policy.publish",))
    if "ai_policy.publish" in allowed:
        return
    for path, _, _ in changed_cells(base, new):
        if not path.startswith("client_data"):
            raise AiPolicyLoosened(path, facts={"field": path})


def _real_firm_auto_mode(current: Mapping[str, object], new: Mapping[str, object]) -> None:
    """AC-35, AC-38: on a real firm Auto mode may be turned off, never on (Season 1)."""
    was = cast(Mapping[str, object], current.get("auto_mode_defaults", {}))
    now = cast(Mapping[str, object], new.get("auto_mode_defaults", {}))
    for kind, on in now.items():
        if on is True and was.get(kind) is not True:
            field = f"auto_mode_defaults.{kind}"
            raise AiPolicyLoosened(field, facts={"field": field})


async def save_draft(ctx: AuthContext, sections: dict[str, object], if_match: int) -> Draft:
    await _open(ctx, "ai_policy.draft")
    check_stricter_only(sections)
    current, effective = await read_draft(ctx)
    await _security_admin_scope(ctx, current.sections, sections)
    if await _real_firm(ctx.tenant):
        _real_firm_auto_mode(current.sections, sections)
    if current.version != if_match:
        raise StaleDraft(facts={"version": current.version})
    async with uow(ctx.tenant) as tx:
        if current.updated_at is None:
            await tx.session.execute(
                text(
                    "INSERT INTO autonomy_policy_drafts (tenant_id, base_version_no, sections, "
                    "schema_version, updated_by) VALUES (:t, :b, CAST(:s AS jsonb), 1, :u)"
                ),
                {
                    "t": ctx.tenant_id,
                    "b": effective.version_no,
                    "s": json.dumps(sections),
                    "u": ctx.user_id,
                },
            )
        else:
            changed = await tx.session.execute(
                text(
                    "UPDATE autonomy_policy_drafts SET sections = CAST(:s AS jsonb), "
                    "version = version + 1, updated_at = clock_timestamp(), updated_by = :u "
                    "WHERE version = :v"
                ),
                {"s": json.dumps(sections), "u": ctx.user_id, "v": if_match},
            )
            if cast(int, getattr(changed, "rowcount", 0)) != 1:
                raise StaleDraft(facts={"version": if_match})
        tx.record(
            "ai_policy.draft_saved",
            target=Target("ai_policy", ctx.tenant_id),
            after=Ref(changed_cells=len(changed_cells(effective.sections, sections))),
        )
    saved = await _draft(ctx.tenant)
    if saved is None:
        raise StaleDraft(facts={"version": if_match})
    return saved


async def discard_draft(ctx: AuthContext, if_match: int) -> None:
    await _open(ctx, "ai_policy.draft")
    current, effective = await read_draft(ctx)
    if current.version != if_match:
        raise StaleDraft(facts={"version": current.version})
    if current.updated_at is None:
        return  # nothing saved: the draft already is the effective version
    async with uow(ctx.tenant) as tx:
        changed = await tx.session.execute(
            text(
                "UPDATE autonomy_policy_drafts SET sections = CAST(:s AS jsonb), "
                "base_version_no = :b, version = version + 1, updated_at = clock_timestamp(), "
                "updated_by = :u WHERE version = :v"
            ),
            {
                "s": json.dumps(effective.sections),
                "b": effective.version_no,
                "u": ctx.user_id,
                "v": if_match,
            },
        )
        if cast(int, getattr(changed, "rowcount", 0)) != 1:
            raise StaleDraft(facts={"version": if_match})
        tx.record("ai_policy.draft_discarded", target=Target("ai_policy", ctx.tenant_id))


# --- versions ------------------------------------------------------------------------------------


async def request_publish(ctx: AuthContext, effective_from: date, approver: UUID) -> Version:
    await _open(ctx, "ai_policy.publish")
    if approver == ctx.user_id:
        raise ApproverMustDiffer
    facts = await member_facts(ctx.tenant, approver)
    if facts is None or facts.client:
        raise NotFound("approver")  # another firm's person, or nobody: never named here
    if facts.level != "partner":
        raise ApproverMustDiffer(facts={"reason": "not_a_partner"})
    draft, effective = await read_draft(ctx)
    check_stricter_only(draft.sections)
    versions = await _versions(ctx.tenant)
    if any(v.state == "awaiting_approval" for v in versions):
        raise PendingVersionExists
    number = max(v.version_no for v in versions) + 1
    # "Effective Sep 15" is the firm's Sep 15: midnight in `kernel.clock`'s firm zone (AC-39).
    starts = datetime.combine(effective_from, time.min, clock.FIRM_ZONE)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO autonomy_policy_versions (tenant_id, version_no, sections, "
                "schema_version, effective_from, requested_by, requested_at, approver_user_id) "
                "VALUES (:t, :n, CAST(:s AS jsonb), 1, :e, :u, clock_timestamp(), :a)"
            ),
            {
                "t": ctx.tenant_id,
                "n": number,
                "s": json.dumps(draft.sections),
                "e": starts,
                "u": ctx.user_id,
                "a": approver,
            },
        )
        tx.record(
            "ai_policy.publish_requested",
            target=Target("ai_policy", ctx.tenant_id),
            after=Ref(version_no=number, approver_user_id=approver, base=effective.version_no),
        )
        tx.emit(ApprovalRequested(version_no=number, assignee_user_id=approver))
    return next(v for v in await _versions(ctx.tenant) if v.version_no == number)


async def _decide(
    ctx: AuthContext, action: str, version_no: int, state: str, reason: str | None = None
) -> Version:
    await _open(ctx, action)
    found = next((v for v in await _versions(ctx.tenant) if v.version_no == version_no), None)
    if found is None:
        raise NotFound("ai_policy_version")
    if found.state != "awaiting_approval":
        raise NoPendingVersion
    if state in ("published", "declined"):
        if found.requested_by == ctx.user_id:
            raise ApproverMustDiffer
        if found.approver_user_id != ctx.user_id:
            raise Forbidden(action, "role")
    elif found.requested_by != ctx.user_id:
        raise Forbidden(action, "role")
    verb = {"published": "approved", "declined": "declined", "withdrawn": "withdrawn"}[state]
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE autonomy_policy_versions SET state = :s, decided_by = :u, "
                "decided_at = clock_timestamp(), decline_reason = :r "
                "WHERE version_no = :n AND state = 'awaiting_approval'"
            ),
            {"s": state, "u": ctx.user_id, "r": reason, "n": version_no},
        )
        tx.record(
            f"ai_policy.{verb}",
            target=Target("ai_policy", ctx.tenant_id),
            after=Ref(version_no=version_no),
        )
    return next(v for v in await _versions(ctx.tenant) if v.version_no == version_no)


async def approve(ctx: AuthContext, version_no: int) -> Version:
    return await _decide(ctx, "ai_policy.approve", version_no, "published")


async def decline(ctx: AuthContext, version_no: int, reason_code: str) -> Version:
    if reason_code not in _DECLINE_REASONS:
        reason_code = "other"
    return await _decide(ctx, "ai_policy.approve", version_no, "declined", reason_code)


async def withdraw(ctx: AuthContext, version_no: int) -> Version:
    return await _decide(ctx, "ai_policy.publish", version_no, "withdrawn")


async def person_names(user_ids: list[UUID | None]) -> dict[UUID, str]:
    found = [u for u in user_ids if u is not None]
    return await names_of(found) if found else {}
