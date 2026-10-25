"""Operator commands for platform-job Schedules (Q-01-T26; Q-01 §4.5; DISPATCH-001).
Run as an ECS one-off `abacus-ops` task (the staging deploy runs `ensure` after migrate), or
locally with `make schedules`.

    python -m abacus_tools.schedules ensure
    python -m abacus_tools.schedules show
    python -m abacus_tools.schedules pause --id spend_anomaly:platform --operator <handle> \
        --reason "RB-07 investigation"
    python -m abacus_tools.schedules unpause --id spend_anomaly:platform --operator <handle> \
        --reason "resolved"
    python -m abacus_tools.schedules delete --id spend_anomaly:platform --operator <handle> \
        --reason "job retired"

`ensure` creates each module's declared Schedule (`SCHEDULES` in its `api.py`) or converges it on
the declaration, keeping an operator's pause; running it twice changes nothing. Every Schedule
skips a run while the last is open and catches up at most an hour (`kernel.dispatch`). The other
commands act on one declared Schedule id; an unknown id is refused. Notes carry the operator's
handle and reason (at most 200 characters, no client data); nothing here touches a database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from importlib import import_module
from typing import Final, cast

from abacus.kernel import dispatch
from abacus.kernel.dispatch import PlatformSchedule
from abacus.modules import MODULES
from abacus.modules.platform.api import OPERATOR_HANDLE

REASON_LIMIT: Final = 200


class Refused(Exception):
    """The command was refused before it touched Temporal."""


def declared() -> tuple[PlatformSchedule, ...]:
    """Every module's Schedules, in MODULES order (P-39): its `schedules()` when it has one
    (they depend on settings, as the canary's does), else its `SCHEDULES`. Ids are unique."""
    found: list[PlatformSchedule] = []
    for name in MODULES:
        api = import_module(f"abacus.modules.{name}.api")
        current = getattr(api, "schedules", None)
        declared_here = current() if callable(current) else getattr(api, "SCHEDULES", ())
        found.extend(cast("tuple[PlatformSchedule, ...]", declared_here))
    ids = [job.id for job in found]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"a Schedule id is declared twice: {sorted(ids)}")
    return tuple(found)


def _note(operator: str, reason: str) -> str:
    if not OPERATOR_HANDLE.fullmatch(operator):
        raise Refused("--operator is a lower-case handle, never an email address")
    reason = reason.strip()
    if not reason or len(reason) > REASON_LIMIT:
        raise Refused(f"--reason is required and at most {REASON_LIMIT} characters")
    return f"operator:{operator}: {reason}"


def _known(schedule_id: str) -> str:
    if schedule_id not in {job.id for job in declared()}:
        raise Refused(f"{schedule_id!r} is not a declared Schedule")
    return schedule_id


async def ensure() -> dict[str, str]:
    """Create or converge every declared Schedule; returns `{id: created | updated}`."""
    return {job.id: await dispatch.schedule(job) for job in declared()}


async def show() -> list[dict[str, object]]:
    return [asdict(await dispatch.describe_schedule(job.id)) for job in declared()]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.schedules")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ensure")
    sub.add_parser("show")
    for name in ("pause", "unpause", "delete"):
        acting = sub.add_parser(name)
        acting.add_argument("--id", required=True)
        acting.add_argument("--operator", required=True)
        acting.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "ensure":
            print(json.dumps(asyncio.run(ensure()), sort_keys=True))
            return 0
        if args.command == "show":
            print(json.dumps(asyncio.run(show())))
            return 0
        schedule_id = _known(args.id)
        note = _note(args.operator, args.reason)
        if args.command == "pause":
            asyncio.run(dispatch.pause(schedule_id, note=note))
        elif args.command == "unpause":
            asyncio.run(dispatch.unpause(schedule_id, note=note))
        else:
            asyncio.run(dispatch.delete(schedule_id))
        print(f"{args.command}d {schedule_id} ({note})")
        return 0
    except Refused as refused:
        print(str(refused), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
