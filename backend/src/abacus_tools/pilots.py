"""`make pilot-enrol` (Q-04-T007): enrol one work item of one firm in a pilot window, or move an
enrolment's mode. The operator's command: it writes through `platform.api` as the system, on
behalf of the named operator, and every change is audited.

    python -m abacus_tools.pilots enrol --firm F --work-item W --start 2027-06-01 \
        --end 2027-07-12 --baseline-days 14 --operator U
    python -m abacus_tools.pilots mode --firm F --enrolment E --mode live --operator U \
        [--confirmed-by U2]
    python -m abacus_tools.pilots metrics --firm F --week 2027-06-07   (Q-04-T008, a rerun)

`--confirmed-by` names the firm person (the champion) who confirms the system of record (Q-04
AC-8.4): an active member of that firm, checked here before the mode moves (Q-04-T012, DEC-834).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from typing import cast
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import member_context
from abacus.modules.platform.api import (
    PilotMode,
    compute_pilot_week,
    cross_firm,
    enrol_pilot,
    set_pilot_mode,
    wedge_read,
    wedge_report,
)


async def confirmer_is_member(firm: UUID, person: UUID) -> bool:
    """Whether the confirming person holds an active membership in the firm (Q-04 AC-8.4)."""
    return await member_context(firm, person) is not None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    enrol = sub.add_parser("enrol")
    enrol.add_argument("--firm", type=UUID, required=True)
    enrol.add_argument("--work-item", type=UUID, required=True)
    enrol.add_argument("--start", type=date.fromisoformat, required=True)
    enrol.add_argument("--end", type=date.fromisoformat, required=True)
    enrol.add_argument("--baseline-days", type=int, default=None)
    enrol.add_argument("--operator", type=UUID, required=True)
    mode = sub.add_parser("mode")
    mode.add_argument("--firm", type=UUID, required=True)
    mode.add_argument("--enrolment", type=UUID, required=True)
    mode.add_argument("--mode", choices=("live", "system_of_record", "exited"), required=True)
    mode.add_argument("--operator", type=UUID, required=True)
    mode.add_argument("--confirmed-by", type=UUID, default=None)
    metrics = sub.add_parser("metrics")
    metrics.add_argument("--firm", type=UUID, required=True)
    metrics.add_argument("--week", type=date.fromisoformat, required=True)
    # Q-04-T050: the W4/W5 read for the sprint review, one row per firm and signal (Markdown).
    read = sub.add_parser("read")
    read.add_argument("--firm", type=UUID, action="append", required=True)
    read.add_argument("--week", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    if args.command == "read":
        print(asyncio.run(_read(cast(list[UUID], args.firm), args.week)), end="")
        return 0
    if args.command == "metrics":
        print(asyncio.run(compute_pilot_week(args.firm, args.week)))
        return 0
    tenant = TenantContext(args.firm, "system", "operator:pilots", args.operator)
    if args.command == "enrol":
        found = asyncio.run(
            enrol_pilot(
                tenant, args.work_item, args.start, args.end, args.baseline_days, args.operator
            )
        )
        print(found)
        return 0
    mode_ = cast(PilotMode, args.mode)
    return asyncio.run(_mode(tenant, args.enrolment, mode_, args.confirmed_by))


async def _read(firms: list[UUID], week: date) -> str:
    reads = [await wedge_read(firm, week) for firm in firms]
    return wedge_report(cross_firm(reads))


async def _mode(
    tenant: TenantContext, enrolment: UUID, mode: PilotMode, confirmed_by: UUID | None
) -> int:
    """One event loop for the check and the change (the engine's connections belong to it)."""
    if confirmed_by is not None and not await confirmer_is_member(tenant.tenant_id, confirmed_by):
        print(f"{confirmed_by} is not an active member of the firm", file=sys.stderr)
        return 2
    await set_pilot_mode(tenant, enrolment, mode, confirmed_by)
    return 0


if __name__ == "__main__":
    sys.exit(main())
