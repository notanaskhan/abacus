"""The M17 runtime v2 flip plan (P-10-T54; TASK-7424; DEC-4413; runbook
`docs/runbooks/runtime-v2-flip.md`).

M17 turns runtime v2 on for a pilot firm on **Tue May 2, 2028** in the 19:00 CT slot, after the
2028 window, with both founders' approvals. It is three ordinary flip requests (one flag each,
DEC-809; `abacus_tools.flip_request`), in this order, and rolled back in the reverse order:

1. `agent_runtime.v2`: the run commands, plan approval, questions and the loop harness;
2. `realtime.sse`: `GET /v1/events` and the run streams (off is the kill switch: clients poll);
3. `engagement_run.enabled`: Run on an engagement.

Rollback is flags off; nothing is deleted: runs, plans, proposals and records persist, and a run in
flight keeps its workflow (a person can still stop it).

This module checks the plan, beyond what `flip_request.precheck` checks per file:
- three requests, one per flag above, numbered in that order (`-1` to `-3`), all for the same
  pilot firm, all in the M17 slot;
- each names the J11 and J23 journeys, the same shadow evidence, and the runbook's rollback;
- the operator and the approver are the two founders, each once (both approvals);
- each flag's registry entry expires after the slot (P-10-T56 renews them on the Apr 25 train);
- the shadow evidence: engagement runs shadowed on staging for at least 14 days with at least 50
  runs and no invariant failure, and the canary running since Mon Mar 20, 2028.

    python -m abacus_tools.runtime_v2_flip render --firm <tenant> --code PF-A1 --shadow-run <link>
    python -m abacus_tools.runtime_v2_flip check <flip files>... --shadow shadow.json
    python -m abacus_tools.runtime_v2_flip shadow --firm <PF-X1 tenant> --from <date> --to <date> \
        [--canary-from <date>] [--staging] > shadow.json

`shadow` (TASK-7429) builds the evidence from the database instead of by hand: the firm's
engagement runs (`engagements.run`) started in the window, and INV-1 and INV-5
(`abacus_tools.harness.invariants`) over the firm's audit events in it. The synthetic firm only;
the same guards as the load profiles. `canary_from` is the canary job's first green (SLO-10).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final, cast
from uuid import UUID

import asyncpg
import yaml

from abacus_tools import flip_request
from abacus_tools.flip_request import FlipRequest

REPO: Final = Path(__file__).resolve().parents[3]
FLAGS_ON: Final[tuple[str, ...]] = ("agent_runtime.v2", "realtime.sse", "engagement_run.enabled")
FLAGS_OFF: Final = tuple(reversed(FLAGS_ON))
M17_SLOT: Final = datetime.fromisoformat("2028-05-02T19:00:00-05:00")
CANARY_FROM: Final = date(2028, 3, 20)
JOURNEYS: Final[tuple[str, ...]] = ("j11-workbench", "j23-audit-partner-morning")
FOUNDERS: Final = frozenset({"ayushkbhatia", "notanaskhan"})
OWNER: Final = "ayushkbhatia"  # the three flags' registry owner, so the operator
ROLLBACK: Final = "docs/runbooks/runtime-v2-flip.md#rollback"
SHADOW_DAYS: Final = 14
SHADOW_RUNS: Final = 50
REGISTRY: Final = REPO / "docs" / "architecture" / "feature-flags" / "agents.yaml"


@dataclass(frozen=True)
class ShadowEvidence:
    """The staging shadow of engagement runs and the canary, as the operator recorded them."""

    shadow_from: date
    shadow_to: date
    runs: int
    invariant_failures: int
    canary_from: date | None

    @classmethod
    def from_json(cls, raw: Mapping[str, object]) -> ShadowEvidence:
        canary = raw.get("canary_from")
        return cls(
            date.fromisoformat(str(raw["shadow_from"])),
            date.fromisoformat(str(raw["shadow_to"])),
            int(cast(int, raw["runs"])),
            int(cast(int, raw["invariant_failures"])),
            None if canary is None else date.fromisoformat(str(canary)),
        )


ENGAGEMENT_RUN: Final = "engagements.run"


async def shadow_evidence(
    conn: asyncpg.Connection,
    tenant: UUID,
    start: date,
    end: date,
    canary_from: date | None,
) -> ShadowEvidence:
    """The window's engagement runs and invariant failures for one synthetic firm."""
    from abacus_tools.harness.invariants import AuditRow, check

    synthetic = await conn.fetchval("SELECT synthetic FROM firms WHERE tenant_id = $1", tenant)
    if synthetic is not True:
        raise ValueError("the shadow is read for the synthetic firm (PF-X1) only")
    upper = end + timedelta(days=1)
    runs = await conn.fetchval(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = $1 AND agent_id = $2 "
        "AND started_at >= $3 AND started_at < $4",
        tenant,
        ENGAGEMENT_RUN,
        start,
        upper,
    )
    records = await conn.fetch(
        "SELECT seq, actor_kind, actor_id, action, on_behalf_of_user_id, policy_ref "
        "FROM audit_events WHERE tenant_id = $1 AND occurred_at >= $2 AND occurred_at < $3 "
        "ORDER BY seq",
        tenant,
        start,
        upper,
    )
    users = frozenset(cast(UUID, u["id"]) for u in await conn.fetch("SELECT id FROM users"))
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
    return ShadowEvidence(start, end, int(runs or 0), len(check(rows, users)), canary_from)


def evidence_json(shadow: ShadowEvidence) -> str:
    return json.dumps(
        {
            "shadow_from": shadow.shadow_from.isoformat(),
            "shadow_to": shadow.shadow_to.isoformat(),
            "runs": shadow.runs,
            "invariant_failures": shadow.invariant_failures,
            "canary_from": None if shadow.canary_from is None else shadow.canary_from.isoformat(),
        },
        sort_keys=True,
    )


def shadow_findings(shadow: ShadowEvidence) -> list[str]:
    why: list[str] = []
    if (shadow.shadow_to - shadow.shadow_from) < timedelta(days=SHADOW_DAYS):
        why.append("shadow_under_14_days")
    if shadow.runs < SHADOW_RUNS:
        why.append("shadow_under_50_runs")
    if shadow.invariant_failures:
        why.append("shadow_invariant_failures")
    if shadow.canary_from is None or shadow.canary_from > CANARY_FROM:
        why.append("canary_not_running_since_mar_20")
    return why


def registry_expiry(path: Path = REGISTRY) -> dict[str, date]:
    """Each flag's `expires` from the agents registry file."""
    raw = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    flags = cast(list[dict[str, object]], raw.get("flags", []))
    out: dict[str, date] = {}
    for entry in flags:
        when = entry.get("expires")
        if isinstance(when, date):
            out[str(entry["name"])] = when
        elif isinstance(when, str):
            out[str(entry["name"])] = date.fromisoformat(when)
    return out


def plan_findings(
    requests: Sequence[FlipRequest], shadow: ShadowEvidence, expiry: Mapping[str, date]
) -> list[str]:
    """Why the M17 plan may not go ahead; empty when it may (per-file prechecks still run)."""
    why: list[str] = []
    by_flag = {r.flag: r for r in requests}
    if sorted(by_flag) != sorted(FLAGS_ON) or len(requests) != len(FLAGS_ON):
        why.append("needs_one_request_per_flag:" + ",".join(FLAGS_ON))
    if len({r.tenant for r in requests}) > 1:
        why.append("requests_for_more_than_one_firm")
    for r in requests:
        if r.slot != M17_SLOT:
            why.append(f"not_the_m17_slot:{r.flag}")
        if r.flag in FLAGS_ON and not r.file.endswith(f"-{FLAGS_ON.index(r.flag) + 1}.yaml"):
            why.append(f"out_of_order:{r.flag}")
        if r.value != "true":
            why.append(f"not_on:{r.flag}")
        missing = [j for j in JOURNEYS if j not in r.journeys]
        if missing:
            why.append(f"journeys_missing:{r.flag}:" + ",".join(missing))
        if frozenset({r.operator, r.approved_by}) != FOUNDERS:
            why.append(f"needs_both_founders:{r.flag}")
        if r.operator != OWNER:
            why.append(f"operator_is_not_the_flag_owner:{r.flag}")
        if r.rollback != ROLLBACK:
            why.append(f"rollback_is_not_the_runbook:{r.flag}")
        expires = expiry.get(r.flag)
        if expires is None or expires <= M17_SLOT.date():
            why.append(f"flag_expires_before_slot:{r.flag}")
    if len({r.shadow_run for r in requests}) > 1:
        why.append("shadow_evidence_differs")
    return why + shadow_findings(shadow)


def render(tenant: UUID, code: str, shadow_run: str) -> dict[str, str]:
    """The three requests, in flip order: `{file name: yaml}`, one file per flag
    (`flip-2028-05-02-<code>-<n>.yaml`), reviewed together in one PR."""
    out: dict[str, str] = {}
    for n, flag in enumerate(FLAGS_ON, start=1):
        body = {
            "kind": "flag_flip",
            "tenant": str(tenant),
            "slot": M17_SLOT.isoformat(),
            "flags": [{"name": flag, "value": "true"}],
            "journeys": list(JOURNEYS),
            "shadow_run": shadow_run,
            "rollback": ROLLBACK,
            "operator": OWNER,
            "approved_by": next(iter(FOUNDERS - {OWNER})),
        }
        out[f"flip-{M17_SLOT.date().isoformat()}-{code}-{n}.yaml"] = yaml.safe_dump(
            body, sort_keys=False
        )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.runtime_v2_flip")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("render")
    make.add_argument("--firm", required=True, type=UUID)
    make.add_argument("--code", required=True)
    make.add_argument("--shadow-run", required=True)
    make.add_argument("--out", type=Path, help="write the files here instead of stdout")
    shadow = sub.add_parser("shadow")
    shadow.add_argument("--firm", required=True, type=UUID)
    shadow.add_argument("--from", dest="start", required=True, type=date.fromisoformat)
    shadow.add_argument("--to", dest="end", required=True, type=date.fromisoformat)
    shadow.add_argument("--canary-from", type=date.fromisoformat, default=None)
    shadow.add_argument("--staging", action="store_true")
    check = sub.add_parser("check")
    check.add_argument("files", nargs="+", type=Path)
    check.add_argument("--shadow", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "render":
        for name, body in render(args.firm, args.code, args.shadow_run).items():
            if args.out is None:
                sys.stdout.write(f"# {name}\n{body}---\n")
            else:
                (args.out / name).write_text(body, encoding="utf-8")
        return 0
    if args.command == "shadow":
        return _shadow_main(args)
    order = sorted(cast(list[Path], args.files), key=lambda p: p.name)
    requests: list[FlipRequest] = []
    for path in order:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            requests.append(flip_request.parse(raw, path.name))
        except flip_request.RequestError as exc:
            sys.stderr.write(f"{path.name}: {exc}\n")
            return 2
    shadow = ShadowEvidence.from_json(json.loads(Path(args.shadow).read_text(encoding="utf-8")))
    found = plan_findings(requests, shadow, registry_expiry())
    for reason in found:
        sys.stdout.write(f"{reason}\n")
    return 1 if found else 0


def _shadow_main(args: argparse.Namespace) -> int:
    import asyncio
    import os

    from abacus.kernel.config import settings
    from abacus_tools.db_connect import connect as connect_db
    from abacus_tools.synthetic.scenarios.brightwater_hale.loader import (
        DEFAULT_SUPERUSER,
        SUPERUSER_ENV,
        LoadRefused,
        guard,
    )

    owner = settings().migrations_database_url
    dsn = (
        owner.get_secret_value()
        if args.staging and owner is not None
        else os.environ.get(SUPERUSER_ENV, DEFAULT_SUPERUSER)
    )

    async def read() -> ShadowEvidence:
        guard(dsn, staging=bool(args.staging))
        conn = await connect_db(dsn)
        try:
            return await shadow_evidence(conn, args.firm, args.start, args.end, args.canary_from)
        finally:
            await conn.close()

    try:
        found = asyncio.run(read())
    except (LoadRefused, ValueError) as refused:
        sys.stderr.write(f"refused: {refused}\n")
        return 2
    sys.stdout.write(evidence_json(found) + "\n")
    return 1 if shadow_findings(found) else 0


if __name__ == "__main__":
    raise SystemExit(main())
