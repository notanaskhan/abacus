"""`make pilot-enrol` (Q-04-T007): enrol one work item of one firm in a pilot window, or move an
enrolment's mode. The operator's command: it writes through `platform.api` as the system, on
behalf of the named operator, and every change is audited.

    python -m abacus_tools.pilots enrol --firm F --work-item W --start 2027-06-01 \
        --end 2027-07-12 --baseline-days 14 --operator U
    python -m abacus_tools.pilots mode --firm F --enrolment E --mode live --operator U \
        [--confirmed-by U2]
    python -m abacus_tools.pilots metrics --firm F --week 2027-06-07   (Q-04-T008, a rerun)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from typing import cast
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.platform.api import (
    PilotMode,
    compute_pilot_week,
    enrol_pilot,
    set_pilot_mode,
)


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
    args = parser.parse_args(argv)
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
    asyncio.run(
        set_pilot_mode(tenant, args.enrolment, cast(PilotMode, args.mode), args.confirmed_by)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
