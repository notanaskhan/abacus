"""T-01-T18 (TASK-2314; SPEC-501 AC-45 to AC-50): final approval is the named signer's alone, on
the content they saw, with nothing blocking it; a blocker provider that cannot answer blocks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest

from abacus.kernel._statuses import ReturnStatus as S
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden, Resource
from abacus.modules.tax import approval

HASH = "sha256:" + "a" * 64


def _ctx(kind: str = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # each actor kind
        user,
        uuid.uuid4(),
        "practice_leader",
        datetime.now(UTC),
        client=client,
    )


def _found(
    ctx: AuthContext,
    *,
    signer: UUID | None = None,
    checkpoint: UUID | None = None,
    blockers: list[approval.Blocker] | None = None,
) -> approval.Eligibility:
    return approval.Eligibility(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        ctx.user_id if signer is None else signer,
        checkpoint or uuid.uuid4(),
        HASH,
        blockers or [],
    )


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, approval.Eligibility]:
    """`eligibility`, the resource and the matrix stand in; the test sets what they answer."""
    holder: dict[str, approval.Eligibility] = {}

    async def eligibility(ctx: AuthContext, return_id: UUID) -> approval.Eligibility:
        return holder["found"]

    async def resource(ctx: AuthContext, engagement_id: UUID, return_id: UUID) -> Resource:
        return Resource.firm(ctx.tenant_id)

    async def authorise(ctx: AuthContext, action: str, resource: Resource) -> None:
        return None

    monkeypatch.setattr(approval, "eligibility", eligibility)
    monkeypatch.setattr(approval, "_resource", resource)
    monkeypatch.setattr(approval, "authorise", authorise)
    return holder


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_ac45_only_a_person_approves(
    kind: str, wired: dict[str, approval.Eligibility]
) -> None:
    ctx = _ctx(kind)
    wired["found"] = _found(ctx)
    with pytest.raises(Forbidden):
        await approval.approve(ctx, uuid.uuid4(), uuid.uuid4(), HASH)


async def test_ac45_a_client_principal_sees_no_return(
    wired: dict[str, approval.Eligibility],
) -> None:
    ctx = _ctx(client=True)
    wired["found"] = _found(ctx)
    with pytest.raises(NotFound):
        await approval.approve(ctx, uuid.uuid4(), uuid.uuid4(), HASH)


async def test_ac46_only_the_named_signer_approves(wired: dict[str, approval.Eligibility]) -> None:
    ctx = _ctx()
    found = _found(ctx, signer=uuid.uuid4())
    wired["found"] = found
    with pytest.raises(approval.NotSigner):
        await approval.approve(ctx, found.return_id, found.checkpoint_id or uuid.uuid4(), HASH)


async def test_ac46_no_policy_means_nobody_approves(
    wired: dict[str, approval.Eligibility],
) -> None:
    ctx = _ctx()
    found = approval.Eligibility(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        None,
        uuid.uuid4(),
        HASH,
        [approval.Blocker("policy_unassigned")],
    )
    wired["found"] = found
    with pytest.raises(approval.NotSigner):
        await approval.approve(ctx, found.return_id, found.checkpoint_id or uuid.uuid4(), HASH)


@pytest.mark.parametrize("what", ["checkpoint", "hash"])
async def test_ac47_approval_is_on_the_content_seen(
    what: str, wired: dict[str, approval.Eligibility]
) -> None:
    ctx = _ctx()
    found = _found(ctx)
    wired["found"] = found
    seen = uuid.uuid4() if what == "checkpoint" else found.checkpoint_id
    content = HASH if what == "checkpoint" else "sha256:" + "b" * 64
    assert seen is not None
    with pytest.raises(approval.ContentChanged):
        await approval.approve(ctx, found.return_id, seen, content)


async def test_ac48_any_blocker_refuses(wired: dict[str, approval.Eligibility]) -> None:
    ctx = _ctx()
    found = _found(ctx, blockers=[approval.Blocker("issue_blocks_final_approval", uuid.uuid4())])
    wired["found"] = found
    assert found.checkpoint_id is not None
    with pytest.raises(approval.FinalApprovalBlocked) as raised:
        await approval.approve(ctx, found.return_id, found.checkpoint_id, HASH)
    assert raised.value.code == "final_approval_blocked"


def test_ac49_a_blocker_kind_registers_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(approval, "_PROVIDERS", {})

    async def one(tenant: TenantContext, return_id: UUID) -> list[approval.Blocker]:
        return []

    async def other(tenant: TenantContext, return_id: UUID) -> list[approval.Blocker]:
        return []

    approval.register_final_approval_blocker("draft_k1", one)
    approval.register_final_approval_blocker("draft_k1", one)  # idempotent at re-import
    with pytest.raises(RuntimeError):
        approval.register_final_approval_blocker("draft_k1", other)


async def test_ac49_a_provider_that_cannot_answer_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx()
    return_id, engagement_id, client_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def facts(ctx: AuthContext, rid: UUID) -> tuple[UUID, UUID]:
        return engagement_id, client_id

    async def signer(tenant_id: UUID, cid: UUID) -> UUID:
        return ctx.user_id

    async def checkpoint(tenant: TenantContext, t: str, rid: UUID) -> tuple[UUID, str]:
        return uuid.uuid4(), HASH

    async def states(*args: object) -> dict[UUID, list[object]]:
        return {return_id: []}

    async def none(*args: object) -> list[UUID]:
        return []

    async def broken(tenant: TenantContext, rid: UUID) -> list[approval.Blocker]:
        raise RuntimeError("engine diagnostics unreachable")

    monkeypatch.setattr(approval, "_facts", facts)
    monkeypatch.setattr(approval, "signer_for", signer)
    monkeypatch.setattr(approval, "current_checkpoint", checkpoint)
    monkeypatch.setattr(approval, "sign_off_states", states)
    monkeypatch.setattr(approval, "blocking_issues", none)
    monkeypatch.setattr(approval, "pending_imports", none)
    monkeypatch.setattr(approval, "_PROVIDERS", {"engine_diagnostics": broken})
    found = await approval.eligibility(ctx, return_id)
    assert [b.kind for b in found.blockers] == ["engine_diagnostics"]
    assert not found.eligible


async def test_ac50_the_gate_needs_every_return_approved_or_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers: list[list[str]] = []

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    async def statuses(session: object, values: object) -> list[str]:
        return answers[-1]

    def session(tenant: TenantContext) -> _Session:
        return _Session()

    monkeypatch.setattr(approval, "tenant_session", session)
    monkeypatch.setattr(approval.repository, "statuses_on", statuses)
    tenant = TenantContext(uuid.uuid4(), "system", "test")
    for given, met in [
        ([], False),
        ([S.APPROVED.value, S.FILED.value], True),
        ([S.APPROVED.value, S.IN_REVIEW.value], False),
        ([S.REJECTED.value], False),
    ]:
        answers.append(given)
        assert await approval.final_approval_gate(tenant, uuid.uuid4()) is met, given
