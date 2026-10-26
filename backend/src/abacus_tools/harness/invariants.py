"""The journey harness's data-layer invariants (F-04-T30; F-04.30, F-04.31). Read-only.

The UI half (`apps/web/e2e/harness/invariants.ts`) checks what a page shows after each step; this
half checks what the step wrote, from `audit_events`:

- **INV-1, the agent never decides:** no audit event of a human-only action has `actor_kind`
  `agent` or `policy`. Human-only is the register (`kernel._human_only_actions`, which the
  database trigger also enforces) plus every audit action the permission matrix's agent-denied
  cells name: matrix action `acceptance.decide` covers the audit action `acceptance.decided`,
  `report.release` covers `report.released` (same object, the matrix verb as the stem).
- **INV-5, attribution is correct:** every event resolves to a person (`human`: a known user),
  "<person> via Agent" (`agent`: `on_behalf_of_user_id` names a known user), a policy
  (`policy`: a `policy_ref`), the platform (`system`) or a support session (`support`).

INV-2, INV-3 and INV-4 are UI and API checks (citations shown, walls, portal scopes) and stay in
the Playwright half. The checks are pure functions over rows, so the self-tests inject violations
without a database; `load` reads a firm's events after a sequence number for a journey step.

CLI (loopback databases only):

    python -m abacus_tools.harness.invariants <tenant-id> [--since-seq N]   # 1 on a violation
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Literal, cast
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg

from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus_tools.db_connect import connect as connect_db
from abacus_tools.local.db_guard import violations as hosted_settings

Invariant = Literal["INV-1", "INV-5"]
DSN_ENV: Final = "ABACUS_LOCAL_SUPERUSER_DSN"
DEFAULT_DSN: Final = "postgresql://postgres:postgres@127.0.0.1:55432/abacus"
LOOPBACK: Final = frozenset({"127.0.0.1", "localhost", "::1"})
NOT_DECIDERS: Final = frozenset({"agent", "policy"})


@dataclass(frozen=True)
class AuditRow:
    seq: int
    actor_kind: str
    actor_id: str | None
    action: str
    on_behalf_of_user_id: UUID | None = None
    policy_ref: str | None = None


@dataclass(frozen=True)
class Violation:
    invariant: Invariant
    seq: int
    action: str
    detail: str  # codes and identifiers only

    def __str__(self) -> str:
        return f"{self.invariant} at seq {self.seq} ({self.action}): {self.detail}"


def agent_denied_actions(matrix: Mapping[str, Mapping[str, str]] = ACTIONS) -> frozenset[str]:
    """The matrix actions whose `agent` cell is `deny` (the generated `_matrix.py`)."""
    return frozenset(action for action, cells in matrix.items() if cells.get("agent") == "deny")


def _past(verb: str) -> frozenset[str]:
    """The audit verbs a matrix verb records: decided, accepted, sent."""
    found = {verb, verb + "d", verb + "ed"}
    if verb.endswith("d"):
        found.add(verb[:-1] + "t")
    return frozenset(found)


def _covers(matrix_action: str, audit_action: str) -> bool:
    """`report.release` covers `report.released`; `follow_up.send` covers `follow_up.sent`."""
    m_object, _, m_verb = matrix_action.rpartition(".")
    a_object, _, a_verb = audit_action.rpartition(".")
    return bool(m_object) and m_object == a_object and a_verb in _past(m_verb)


def human_only(
    action: str,
    denied: frozenset[str] | None = None,
    register: frozenset[str] = HUMAN_ONLY_ACTIONS,
) -> bool:
    """Whether an audit action is a decision only a person may record."""
    if action in register:
        return True
    return any(_covers(m, action) for m in (agent_denied_actions() if denied is None else denied))


def check_inv1(rows: Iterable[AuditRow], denied: frozenset[str] | None = None) -> list[Violation]:
    denied = agent_denied_actions() if denied is None else denied
    return [
        Violation("INV-1", r.seq, r.action, f"actor_kind={r.actor_kind}")
        for r in rows
        if r.actor_kind in NOT_DECIDERS and human_only(r.action, denied)
    ]


def _user(value: str | UUID | None, users: frozenset[UUID]) -> bool:
    if value is None:
        return False
    try:
        return UUID(str(value)) in users
    except ValueError:
        return False


def check_inv5(rows: Iterable[AuditRow], users: frozenset[UUID]) -> list[Violation]:
    out: list[Violation] = []
    for r in rows:
        problem: str | None = None
        if r.actor_kind == "human" and not _user(r.actor_id, users):
            problem = "human actor is not a known user"
        elif r.actor_kind == "agent" and not _user(r.on_behalf_of_user_id, users):
            problem = "agent row names no person it acted for"
        elif r.actor_kind == "policy" and not r.policy_ref:
            problem = "policy row has no policy_ref"
        elif r.actor_kind not in ("human", "agent", "policy", "system", "support"):
            problem = f"unknown actor_kind={r.actor_kind}"
        if problem is not None:
            out.append(Violation("INV-5", r.seq, r.action, problem))
    return out


def check(rows: Iterable[AuditRow], users: frozenset[UUID]) -> list[Violation]:
    """INV-1 then INV-5 over the same rows."""
    found = list(rows)
    return [*check_inv1(found), *check_inv5(found, users)]


async def load(
    conn: asyncpg.Connection, tenant_id: UUID, since_seq: int = 0
) -> tuple[list[AuditRow], frozenset[UUID]]:
    """A firm's events after `since_seq` (a journey step's window) and the known user ids."""
    records = await conn.fetch(
        "SELECT seq, actor_kind, actor_id, action, on_behalf_of_user_id, policy_ref "
        "FROM audit_events WHERE tenant_id = $1 AND seq > $2 ORDER BY seq",
        tenant_id,
        since_seq,
    )
    users = await conn.fetch("SELECT id FROM users")
    rows = [
        AuditRow(
            seq=int(r["seq"]),
            actor_kind=str(r["actor_kind"]),
            actor_id=cast(str | None, r["actor_id"]),
            action=str(r["action"]),
            on_behalf_of_user_id=cast(UUID | None, r["on_behalf_of_user_id"]),
            policy_ref=cast(str | None, r["policy_ref"]),
        )
        for r in records
    ]
    return rows, frozenset(cast(UUID, u["id"]) for u in users)


async def _run(tenant_id: UUID, since_seq: int) -> list[Violation]:
    dsn = os.environ.get(DSN_ENV, DEFAULT_DSN)
    if urlsplit(dsn).hostname not in LOOPBACK or hosted_settings():
        raise SystemExit("refused: the invariant checker reads a database on this machine only")
    conn = await connect_db(dsn)
    try:
        rows, users = await load(conn, tenant_id, since_seq)
    finally:
        await conn.close()
    return check(rows, users)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check INV-1 and INV-5 over a firm's events.")
    parser.add_argument("tenant", type=UUID)
    parser.add_argument("--since-seq", type=int, default=0)
    args = parser.parse_args(argv)
    found = asyncio.run(_run(args.tenant, args.since_seq))
    for violation in found:
        print(violation)
    print(f"{len(found)} violation(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
