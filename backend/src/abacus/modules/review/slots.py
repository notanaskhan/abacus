"""What can be reviewed (P-04; SPEC-313). Each owner registers a provider that lists its
reviewables on an engagement with their current content hash; the matrix and the G5 gate read
every registered provider. Fail closed: an unregistered type has nothing to review, and a
provider that raises makes the gate unmet."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid, NotFound, ServiceUnavailable

if TYPE_CHECKING:
    from abacus.kernel.uow import UnitOfWork
    from abacus.modules.identity.api import AuthContext

# The levels every reviewable needs before completion (L1 preparer, L2 reviewer). K-02's
# methodology policies will set more per area and risk.
REQUIRED_LEVELS: Final = (1, 2)


@dataclass(frozen=True)
class Reviewable:
    target_type: str
    target_id: UUID
    code: str
    title: str
    content_hash: str
    has_content: bool


ReviewableProvider = Callable[[TenantContext, UUID], Awaitable[list[Reviewable]]]
_PROVIDERS: dict[str, ReviewableProvider] = {}


def register_reviewable(target_type: str, provider: ReviewableProvider) -> None:
    known = _PROVIDERS.get(target_type)
    if known is not None and (known.__module__, known.__qualname__) != (
        provider.__module__,
        provider.__qualname__,
    ):
        raise ValueError(f"reviewable {target_type!r} is already registered")
    _PROVIDERS[target_type] = provider


def reviewable_types() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDERS))


async def reviewables_of(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    """Every registered type's reviewables, by type then code (callers authorised first)."""
    out: list[Reviewable] = []
    for target_type in reviewable_types():
        found = await _PROVIDERS[target_type](tenant, engagement_id)
        out.extend(sorted(found, key=lambda r: r.code))
    return out


# --- P-04-T14 (ADR-160; DEC-215): one target's facts, for the sign-off rules and conditions.


@dataclass(frozen=True)
class ReviewableFacts:
    """What the owner knows about one reviewable now: its content hash (`review.hashing`), its
    version number, who prepared it (the matrix condition `not_preparer_of_target` reads these,
    with the target's current L1 signers), the levels it needs, and whether it is locked (an
    archive lock: no sign-off then)."""

    target_type: str
    target_id: UUID
    engagement_id: UUID
    content_hash: str
    version_no: int
    preparer_user_ids: frozenset[UUID]
    required_levels: tuple[int, ...] = REQUIRED_LEVELS
    locked: bool = False
    # P-04-T18 (SHL-12): what the sheet shows and the R-SO-6 and R-SO-8 facts, from the owner's
    # records. Defaults keep an owner that states none working: nothing incomplete or uncited.
    label: str = ""
    context_label: str = ""
    work_item_id: UUID | None = None
    cell_count: int = 0
    citation_count: int = 0
    cited_count: int = 0
    incomplete_count: int = 0  # required fields still empty (R-SO-6, 409 `incomplete`)
    uncited_count: int = 0  # agent values with no citation (R-SO-6, 422 `uncited_change`)
    adopted_run_id: UUID | None = None  # the agent run whose work an L1 adopts (R-SO-8)
    adopted_run_number: int | None = None


ReviewableFactsProvider = Callable[[TenantContext, UUID], Awaitable[ReviewableFacts | None]]
_FACTS: dict[str, ReviewableFactsProvider] = {}


def register_reviewable_facts(target_type: str, provider: ReviewableFactsProvider) -> None:
    known = _FACTS.get(target_type)
    if known is not None and _name(known) != _name(provider):
        raise ValueError(f"reviewable facts for {target_type!r} are already registered")
    _FACTS[target_type] = provider


def reviewable_fact_types() -> tuple[str, ...]:
    return tuple(sorted(_FACTS))


async def reviewable_facts(
    tenant: TenantContext, target_type: str, target_id: UUID
) -> ReviewableFacts:
    """Fail closed: an unregistered type is refused (422 `unregistered_kind`), an unknown
    target is `NotFound`. For callers authorised on the target's engagement."""
    provider = _FACTS.get(target_type)
    if provider is None:
        raise UnregisteredKind
    found = await provider(tenant, target_id)
    if found is None or (found.target_type, found.target_id) != (target_type, target_id):
        raise NotFound(target_type)
    return found


# --- P-04-T06 (ADR-160): the other review slots. Each fails closed: an unregistered kind is
# refused (422 `unregistered_kind`), and an owner that isn't there answers 503.


class UnregisteredKind(DomainInvalid):
    """A decision kind, gate kind, field owner or fix runner nobody registered."""

    code = "unregistered_kind"


GateCheck = Callable[[TenantContext, UUID], Awaitable[bool]]
FieldValue = Callable[[TenantContext, UUID, str], Awaitable[dict[str, object] | None]]
# P-04-T35: a person's edit lands in the owner's own record, in the editing unit of work, as the
# person (the owner authorises its own write). Returns the target's content hash after the edit,
# for the human checkpoint where the owner checkpoints (SHL-16), or None.
FieldEdit = Callable[
    ["UnitOfWork", "AuthContext", UUID, str, dict[str, object]], Awaitable[str | None]
]
FixRunner = Callable[[TenantContext, UUID], Awaitable[UUID]]  # the agent run it started


# --- P-04-T23 (ADR-160 clause 8): what a decision kind's provider computes, in code.


@dataclass(frozen=True)
class CardOption:
    """One option, computed by the kind's provider (never a model, ADR-050). Money is a decimal
    string in `figures`; `label` and `detail` are the provider's fixed copy over those figures."""

    key: str
    label: str
    figures: Mapping[str, str] = field(default_factory=dict[str, str])
    detail: str | None = None


@dataclass(frozen=True)
class CardContext:
    """A context row ("Benchmark", "Amount", "Firm range", "Prior year")."""

    key: str
    label: str
    value: str
    citation_id: UUID | None = None


@dataclass(frozen=True)
class CardFactor:
    key: str
    label: str
    applicable: bool = True


@dataclass(frozen=True)
class ComputedCard:
    options: tuple[CardOption, ...]
    context: tuple[CardContext, ...] = ()
    factors: tuple[CardFactor, ...] = ()
    blocking_refs: tuple[tuple[str, UUID], ...] = ()


@dataclass(frozen=True)
class CardSubject:
    """What a card is about: the provider reads its own records for it."""

    engagement_id: UUID
    work_item_id: UUID | None
    question_key: str


@dataclass(frozen=True)
class Reassessment:
    """The provider's recompute: `changed` False is "No change" (a new version of the same card);
    True raises a superseding card from `card`. `figures` are what the history row shows (the
    new amount, the difference)."""

    changed: bool
    figures: Mapping[str, str] = field(default_factory=dict[str, str])
    card: ComputedCard | None = None


CardCompute = Callable[[TenantContext, CardSubject], Awaitable[ComputedCard]]
# (tenant, subject, the decided option or None, the card as computed when raised)
CardReassess = Callable[
    [TenantContext, CardSubject, str | None, ComputedCard], Awaitable[Reassessment]
]


@dataclass(frozen=True)
class AppliedDecision:
    """A-04-T12 (DEC-1950): what the kind's owner applies, inside the decider's unit of work."""

    card_id: UUID
    decision_id: UUID
    engagement_id: UUID
    work_item_id: UUID | None
    question_key: str
    option_key: str
    figures: Mapping[str, str]


# (the decider's unit of work, the decider, the decision): the owner writes its own record with
# the decision in one unit of work (A-04 AC3.4); raising refuses the whole decision.
CardApply = Callable[["UnitOfWork", "AuthContext", AppliedDecision], Awaitable[None]]
# The fresh-MFA window for deciding: the matrix's `mfa_recent` (15 minutes) is the floor every
# kind gets; a kind may only tighten it (DEC-505; no kind opts out).
DECIDE_MFA_MAX_AGE_S: Final = 900


@dataclass(frozen=True)
class DecisionKind:
    """A decision card's kind (A-04 materiality, T-04 treatment, ...): who it is reserved to,
    how its options are computed (by code, never a model: ADR-050), its questions' copy, how it
    is reassessed, and how recent the decider's second factor must be (ADR-160 clause 8: the
    kind declares it, within the matrix's 15 minutes; DEC-505 removed the opt-out)."""

    code: str
    reserved_role: str
    options: CardCompute
    questions: Mapping[str, str] = field(default_factory=dict[str, str])
    reassess: CardReassess | None = None
    mfa_max_age_s: int = DECIDE_MFA_MAX_AGE_S
    # A-04-T12 (DEC-1950): the owner's applier, run inside the decision's unit of work.
    apply: CardApply | None = None


@dataclass(frozen=True)
class FieldOwner:
    """The module that owns a target type's fields: their current value, and whether a field
    holds tax-return information (TRI facts resolve behind C19's consent gate)."""

    target_type: str
    value_of: FieldValue
    tri_fields: frozenset[str] = frozenset()
    # P-04-T35 (SHL-09): the tray's label for a field key ("Taxable interest — Halvard
    # Securities"); without one the key itself. `apply_edit`: with none, a person's edit is
    # refused (503: nobody writes it). `checkpoints`: a person's edit is also a checkpoint.
    label_of: Callable[[str], str] | None = None
    apply_edit: FieldEdit | None = None
    checkpoints: bool = False


_DECISION_KINDS: dict[str, DecisionKind] = {}
_GATE_KINDS: dict[str, GateCheck] = {}
_FIELD_OWNERS: dict[str, FieldOwner] = {}
_FIX_RUNNERS: dict[str, FixRunner] = {}
_RESERVED_ROLES: Final = frozenset({"engagement_partner", "manager", "eqr_reviewer", "signer"})
_CODE: Final = re.compile(r"[a-z][a-z_]{0,39}")


def _name(f: object) -> tuple[object, object]:
    return (getattr(f, "__module__", None), getattr(f, "__qualname__", None))


def _register[T](registry: dict[str, T], what: str, code: str, value: T, same: bool) -> None:
    if not _CODE.fullmatch(code):
        raise ValueError(f"{what} {code!r} must be snake_case")
    if code in registry and not same:
        raise ValueError(f"{what} {code!r} is already registered")
    registry[code] = value


def register_decision_kind(kind: DecisionKind) -> None:
    if kind.reserved_role not in _RESERVED_ROLES:
        raise ValueError(f"decision kind {kind.code!r}: unknown reserved role")
    if not 0 < kind.mfa_max_age_s <= DECIDE_MFA_MAX_AGE_S:
        raise ValueError(f"decision kind {kind.code!r}: MFA window must be 1 to 900 seconds")
    known = _DECISION_KINDS.get(kind.code)
    same = known is not None and (known.reserved_role, _name(known.options)) == (
        kind.reserved_role,
        _name(kind.options),
    )
    _register(_DECISION_KINDS, "decision kind", kind.code, kind, same)


def decision_kind(code: str) -> DecisionKind:
    found = _DECISION_KINDS.get(code)
    if found is None:
        raise UnregisteredKind
    return found


# P-04-T23 (security review L8): who owns an agent suggestion, so a card's recommendation can be
# checked against the card's engagement. The agents module registers it (review never imports
# agents); unregistered, every suggestion is unknown (fail closed).
SuggestionOwner = Callable[[TenantContext, UUID], Awaitable[UUID | None]]
_SUGGESTION_OWNER: list[SuggestionOwner] = []


def register_suggestion_owner(owner: SuggestionOwner) -> None:
    if _SUGGESTION_OWNER and _name(_SUGGESTION_OWNER[0]) != _name(owner):
        raise ValueError("the suggestion owner is already registered")
    _SUGGESTION_OWNER[:] = [owner]


async def suggestion_engagement(tenant: TenantContext, suggestion_id: UUID) -> UUID | None:
    """The suggestion's engagement, or None (unknown, another firm's, or no owner registered)."""
    if not _SUGGESTION_OWNER:
        return None
    return await _SUGGESTION_OWNER[0](tenant, suggestion_id)


def register_gate_kind(code: str, check: GateCheck) -> None:
    known = _GATE_KINDS.get(code)
    _register(
        _GATE_KINDS, "gate kind", code, check, known is not None and _name(known) == _name(check)
    )


async def gate_met(tenant: TenantContext, code: str, engagement_id: UUID) -> bool:
    """Fail closed: an unregistered gate kind is refused; an owner that raises is unmet."""
    check = _GATE_KINDS.get(code)
    if check is None:
        raise UnregisteredKind
    try:
        return await check(tenant, engagement_id)
    except Exception:
        return False


def register_field_owner(owner: FieldOwner) -> None:
    known = _FIELD_OWNERS.get(owner.target_type)
    same = known is not None and (_name(known.value_of), known.tri_fields) == (
        _name(owner.value_of),
        owner.tri_fields,
    )
    _register(_FIELD_OWNERS, "field owner", owner.target_type, owner, same)


def field_owner(target_type: str) -> FieldOwner:
    found = _FIELD_OWNERS.get(target_type)
    if found is None:
        raise UnregisteredKind
    return found


# --- P-04-T35 (DEC-1050): a field's citations, through C4 ----------------------------------------
# `review` never imports `evidence`; the module that composes both (agents) registers how a
# field's citations are checked, described and written.


@dataclass(frozen=True)
class FieldCitation:
    """One citation as SHL-09's reference row shows it."""

    id: UUID
    kind: str  # `document`, `engine_import`, `workpaper` or `prior_return`
    label: str
    detail: str | None
    document_id: UUID | None
    page: int | None


@dataclass(frozen=True)
class DocumentCitation:
    """ "Add reference": a document page claimed to show the field's value."""

    engagement_id: UUID
    work_item_id: UUID | None
    client_id: UUID | None
    field_id: UUID
    field_key: str
    document_id: UUID
    page: int | None
    value: str


@dataclass(frozen=True)
class FieldCitations:
    # (tenant, engagement, ids) -> the ids that support a value now (verified, shown, valid)
    supported: Callable[[TenantContext, UUID, list[UUID]], Awaitable[frozenset[UUID]]]
    # (reader, ids) -> the rows the reader may see
    describe: Callable[[AuthContext, list[UUID]], Awaitable[dict[UUID, FieldCitation]]]
    # (the writer's unit of work, the person, the claim) -> (citation id, verified)
    cite_document: Callable[
        [UnitOfWork, AuthContext, DocumentCitation], Awaitable[tuple[UUID, bool]]
    ]


_FIELD_CITATIONS: list[FieldCitations] = []


def register_field_citations(citations: FieldCitations) -> None:
    _FIELD_CITATIONS[:] = [citations]


def field_citations() -> FieldCitations:
    """Fail closed: with no reader registered, nothing can say a value is supported (503)."""
    if not _FIELD_CITATIONS:
        raise ServiceUnavailable
    return _FIELD_CITATIONS[0]


def register_fix_runner(issue_kind: str, runner: FixRunner) -> None:
    known = _FIX_RUNNERS.get(issue_kind)
    _register(
        _FIX_RUNNERS,
        "fix runner",
        issue_kind,
        runner,
        known is not None and _name(known) == _name(runner),
    )


def fix_runner_registered(issue_kind: str) -> bool:
    """P-04-T31: whether a runner fixes this kind (no runner: 409 `fix_runner_unavailable`)."""
    return issue_kind in _FIX_RUNNERS


async def run_fix(tenant: TenantContext, issue_kind: str, issue_id: UUID) -> UUID:
    """A registered runner applies the fix and answers its agent run; with none, the fix is
    unavailable (503)."""
    runner = _FIX_RUNNERS.get(issue_kind)
    if runner is None:
        raise ServiceUnavailable
    return await runner(tenant, issue_id)


# --- P-04-T32 (SHL-16, DEC-804): a checkpoint that came from an SHL-10 proposal is decided
# through that proposal, so SHL-16 and SHL-10 show one decision. The proposal's owner (agents)
# registers how; with none, the decision is unavailable (503) and nothing is written.

CheckpointProposalApprove = Callable[[object, UUID], Awaitable[None]]
CheckpointProposalReject = Callable[[object, UUID, str], Awaitable[None]]


@dataclass(frozen=True)
class CheckpointProposalHooks:
    """`approve(person, proposal_id)` and `reject(person, proposal_id, reason)`: the owner decides
    the proposal at its current version and, in the same unit of work, the checkpoint follows
    (`review.api.follow_proposal_decision`)."""

    approve: CheckpointProposalApprove
    reject: CheckpointProposalReject


_CHECKPOINT_PROPOSALS: list[CheckpointProposalHooks] = []


def register_checkpoint_proposal_hooks(hooks: CheckpointProposalHooks) -> None:
    if _CHECKPOINT_PROPOSALS:
        known = _CHECKPOINT_PROPOSALS[0]
        if _name(known.approve) != _name(hooks.approve) or _name(known.reject) != _name(
            hooks.reject
        ):
            raise ValueError("checkpoint proposal hooks are already registered")
        return
    _CHECKPOINT_PROPOSALS.append(hooks)


def checkpoint_proposal_hooks() -> CheckpointProposalHooks:
    if not _CHECKPOINT_PROPOSALS:
        raise ServiceUnavailable
    return _CHECKPOINT_PROPOSALS[0]
