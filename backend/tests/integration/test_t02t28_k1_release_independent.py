# ac-test-author: ayushkbhatia
"""T-02-T28 (ADR-078; TASK-2532; SPEC-502 AC-1, AC-2; T-02 §3.6; DEC-24, DEC-53): the independent
suite for notanaskhan's red rows T-02-T17 and T-02-T21 and for T-02's use of T-01-T18's
final-approval guard, written from the SPEC, `docs/contracts/k1-packages.md` and the human-only
register rather than the code.

The row's acceptance: "Tests written in ayushkbhatia's session from the SPEC and contracts pass on
main and fail on a planted agent approval." Here:

- Five layers keep `k1_package.release` a person's: the matrix, the route, the service, the
  human-only register and the database (a planted agent or system release row is refused).
- The release waits on BH-TAX-02: no signer named, no release (`no_release_policy`); not final
  approved, no release.
- The draft K-1 blocker T-02 registers on the receiving return clears when the release replaces
  the draft.
- The Undo window: the requester, inside ten seconds; after it, or anyone else, refused.
- The grant is single use; a release with one Idempotency-Key is one release.
- A duplicate upload's resolution never voids or supersedes accepted evidence (T-02-T17).

The harness is T-02-T21's (Ridgeline's drafts shared to Feld, then the final set) and T-02-T19's
duplicate upload on the Feld binder.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from typing import cast

import asyncpg
import pytest
import yaml

from abacus.kernel.clock import frozen
from abacus.kernel.db import TenantContext
from abacus.modules.evidence import duplicates
from abacus.modules.identity.api import Forbidden, consume_grant
from abacus.modules.tax import approval, k1_release

from . import test_t02t09_practice_board as t02t09
from . import test_t02t18_intake as t02t18
from . import test_t02t19_intake_actions as t02t19
from . import test_t02t21_k1_release as t02t21
from .test_t02t09_practice_board import DEMO, Board
from .test_t02t13_return_overview import manager_on

engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board
sent = t02t21.sent
signer = t02t21.signer
_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
_ready = t02t21._ready  # pyright: ignore[reportPrivateUsage] -- T-02-T21's harness
_binder = t02t18._binder  # pyright: ignore[reportPrivateUsage] -- T-02-T18's Feld binder
_duplicate = t02t19._duplicate  # pyright: ignore[reportPrivateUsage] -- T-02-T19's duplicate

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = t02t21.TEMPLATE
LATER = t02t21.LATER


def _matrix(action: str) -> dict[str, object]:
    matrix = cast(
        dict[str, dict[str, dict[str, object]]],
        yaml.safe_load((ROOT / "docs/architecture/permission-matrix/tax.yaml").read_text()),
    )
    return matrix["actions"][action]


def _human_only() -> set[str]:
    found = cast(
        dict[str, list[dict[str, str]]],
        yaml.safe_load((ROOT / "docs/architecture/human-only-actions.yaml").read_text()),
    )
    return {row["action"] for row in found["actions"]}


# --- five layers ---------------------------------------------------------------------------------


async def test_release_is_a_persons_at_every_layer_and_a_planted_agent_release_fails(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    ridgeline, _feld, samuel, finals = await _ready(board)
    # 1 the matrix: agent, system and client principals deny; a recent second factor is required.
    row = _matrix("k1_package.release")
    assert {row.get(k) for k in ("agent", "system", "client_admin", "client_contributor")} == {
        "deny"
    }
    assert row.get("mfa_recent") == "required"
    # 2 the route: an agent principal is refused before anything is written.
    agent = replace(samuel, tenant=TenantContext(board.tenant, "agent", f"agent:x:{uuid.uuid4()}"))
    with frozen(DEMO):
        refused = await _as(agent)(
            "POST",
            f"/v1/tax-returns/{ridgeline}/k1-packages:release",
            json={
                "package_ids": [str(p) for p in finals],
                "channel": "portal",
                "email_template_version_id": str(TEMPLATE),
                "seen_version": 2,
            },
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    assert refused.status_code in (403, 404), refused.text
    # 3 the service: the agent, the system, a support session and a stale factor are refused.
    for ctx in (
        agent,
        replace(samuel, tenant=TenantContext(board.tenant, "system", "tax:planted")),
        replace(samuel, tenant=TenantContext(board.tenant, "support", "support:x")),
        replace(samuel, mfa_at=None),
    ):
        with frozen(DEMO), pytest.raises(Forbidden):
            await k1_release.request_release(ctx, ridgeline, finals, TEMPLATE, 2, None)
    # 4 the register: the release request is a human-only action.
    assert "schedule_k_release.requested" in _human_only()
    # 5 the database: a planted agent release row and a planted release of a package fail.
    engagement = await board.seed.value(
        "SELECT engagement_id FROM tax_returns WHERE work_item_id = $1", ridgeline
    )
    for actor in (("agent", f"agent:x:{uuid.uuid4()}"), ("system", "system")):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await board.seed.as_actor(
                board.tenant,
                actor,
                "INSERT INTO k1_releases (tenant_id, engagement_id, work_item_id, package_ids, "
                "grant_id, not_before, requested_by, mfa_at, email_template_version_id) VALUES "
                "($1, $2, $3, $4, gen_random_uuid(), now(), $5, now(), $6)",
                board.tenant,
                engagement,
                ridgeline,
                finals,
                samuel.user_id,
                TEMPLATE,
            )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await board.seed.as_actor(
            board.tenant,
            ("agent", f"agent:x:{uuid.uuid4()}"),
            "UPDATE k1_packages SET status = 'released', released_at = now() WHERE id = $1",
            finals[0],
        )
    assert (
        await board.seed.value(
            "SELECT count(*) FROM k1_releases WHERE work_item_id = $1", ridgeline
        )
        == 0
    )


# --- BH-TAX-02 and final approval ----------------------------------------------------------------


async def test_no_signer_or_no_final_approval_means_no_release(
    board: Board, sent: t02t21.Sent
) -> None:
    ridgeline, _feld, samuel, finals = await _ready(board)
    check = await k1_release.eligibility(samuel, ridgeline)
    assert "no_release_policy" in check.failing and not check.eligible
    with frozen(DEMO), pytest.raises(k1_release.K1ReleaseIneligible):
        await k1_release.request_release(samuel, ridgeline, finals, TEMPLATE, 2, None)
    await board.seed.run(
        "UPDATE tax_returns SET status = 'in_review' WHERE work_item_id = $1", ridgeline
    )
    again = await k1_release.eligibility(samuel, ridgeline)
    assert "not_final_approved" in again.failing


# --- the draft K-1 blocker -----------------------------------------------------------------------


async def test_the_draft_k1_blocker_holds_until_the_release_replaces_the_draft(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    ridgeline, feld, samuel, finals = await _ready(board)
    before = [b.kind for b in (await approval.eligibility(samuel, feld)).blockers]
    assert before.count("draft_k1") == 2
    with frozen(DEMO):
        made = await k1_release.request_release(samuel, ridgeline, finals, TEMPLATE, 2, None)
    with frozen(LATER):
        assert await k1_release.start(board.tenant, made.id) == "running"
        for package in finals:
            await k1_release.deliver(board.tenant, made.id, package)
        await k1_release.complete(board.tenant, made.id)
    after = [b.kind for b in (await approval.eligibility(samuel, feld)).blockers]
    assert "draft_k1" not in after


# --- Undo, single use and idempotency ------------------------------------------------------------


async def test_undo_is_the_requesters_inside_the_window_only(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    ridgeline, _feld, samuel, finals = await _ready(board)
    with frozen(DEMO):
        made = await k1_release.request_release(samuel, ridgeline, finals, TEMPLATE, 2, None)
    olivia = await board.person("Olivia Brandt", None)
    with frozen(DEMO), pytest.raises((k1_release.K1UndoClosed, Forbidden)):
        await k1_release.undo(olivia, made.id)
    with frozen(LATER), pytest.raises(k1_release.K1UndoClosed):
        await k1_release.undo(samuel, made.id)
    assert (
        await board.seed.value("SELECT status FROM k1_releases WHERE id = $1", made.id)
        == "pending"
    )


async def test_the_grant_is_spent_once_and_one_key_is_one_release(
    board: Board, sent: t02t21.Sent, signer: None
) -> None:
    ridgeline, _feld, samuel, finals = await _ready(board)
    with frozen(DEMO):
        first = await k1_release.request_release(
            samuel, ridgeline, finals, TEMPLATE, 2, "t02t28-release-key"
        )
        second = await k1_release.request_release(
            samuel, ridgeline, finals, TEMPLATE, 2, "t02t28-release-key"
        )
    assert first.id == second.id
    assert (
        await board.seed.value(
            "SELECT count(*) FROM k1_releases WHERE work_item_id = $1", ridgeline
        )
        == 1
    )
    grant = cast(
        uuid.UUID,
        await board.seed.value("SELECT grant_id FROM k1_releases WHERE id = $1", first.id),
    )
    with frozen(LATER):
        assert await k1_release.start(board.tenant, first.id) == "running"
        assert await k1_release.start(board.tenant, first.id) == "running"
        digest = k1_release.grant_digest(first.id, ridgeline, finals, TEMPLATE)
        # Single use: the release that spent it may replay; no other effect can spend it again.
        assert not await consume_grant(board.tenant, grant, uuid.uuid4(), digest)
    used = await board.seed.rows("SELECT used_at FROM approval_grants WHERE id = $1", grant)
    assert used[0]["used_at"] is not None


# --- duplicates never touch accepted evidence ----------------------------------------------------


async def test_a_duplicate_resolution_never_supersedes_accepted_evidence(board: Board) -> None:
    feld = board.returns["Feld Household 1040"]
    made = await _binder(board, feld)
    kevin = await manager_on(board, feld)
    w2 = made[t02t19.W2]
    original = cast(
        uuid.UUID,
        await board.seed.value(
            "SELECT evidence_version_id FROM fulfilments WHERE request_item_id = $1 "
            "ORDER BY created_at LIMIT 1",
            w2,
        ),
    )
    duplicate = await _duplicate(board, made["engagement"], w2)
    await board.seed.as_actor(
        board.tenant,
        ("human", str(kevin.user_id)),
        "INSERT INTO review_decisions (tenant_id, engagement_id, evidence_version_id, "
        "request_item_id, decision, corrects_proposal, actor_kind, actor_id, decision_seq) "
        "VALUES ($1, $2, $3, $4, 'accept', false, 'human', $5, 1)",
        board.tenant,
        made["engagement"],
        original,
        w2,
        str(kevin.user_id),
    )
    with pytest.raises(duplicates.DuplicateAccepted):
        await duplicates.resolve(kevin, made["engagement"], w2, duplicate, "keep_newer")
    assert (
        await board.seed.value(
            "SELECT count(*) FROM duplicate_resolutions WHERE version_id = $1", duplicate
        )
        == 0
    )
    withdrawn = await board.seed.value(
        "SELECT count(*) FROM evidence_withdrawals WHERE evidence_version_id = $1", original
    )
    assert withdrawn == 0  # the accepted original is neither voided nor superseded
