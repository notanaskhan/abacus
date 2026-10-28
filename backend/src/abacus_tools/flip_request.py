"""Flip ops requests (Q-04-T010; SPEC-403 AC-12; Q-04 AC-4.1; P-29 rule 3; DEC-809).

A per-firm flip in production is a reviewed PR that adds one file,
`deploy/production/ops-requests/flip-<yyyy-mm-dd>-<pilot code>.yaml`:

    kind: flag_flip
    tenant: 00000000-0000-4000-8000-0000000000a1     # PF-A1
    slot: 2027-09-21T19:00:00-05:00
    flags: [{name: sampling.sample_sets, value: "true"}]
    journeys: [j04-fs-audit]
    shadow_run: https://...                           # the shadow comparison
    rollback: docs/ops/flips/2027-09-21-PF-A1.md#rollback
    operator: ayushkbhatia                            # owner of the flag
    approved_by: notanaskhan                          # never the operator
    # optional: eval_report (a prompt.* variant), cpa_memo, hotfix: <reason>

`flip-precheck` (`.github/workflows/ops-request.yml`, on the PR) refuses it unless each journey it
names, and each journey the flag registry lists for its flag, passed on staging within 24 hours,
it names a shadow run, the approver is not the operator, the firm is a pilot firm whose code is
the file's, and the slot is one the firm may flip in. Merged, `ops-task.yml` turns it into the
flag CLI's command, which runs the flip guard again at the moment it executes.

    python -m abacus_tools.flip_request precheck <file>... --journeys journeys.json [--now <ISO>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, cast
from uuid import UUID

import yaml

from abacus.kernel.clock import system_now
from abacus_tools import release_windows

_FILE: Final = re.compile(
    r"flip-(\d{4}-\d{2}-\d{2})-(PF-[A-Z][0-9]{1,3}|PC[0-9]{2}-[0-9]{2,3})\.yaml"
)
_HANDLE: Final = re.compile(r"[a-z][a-z0-9._-]{0,60}")
_JOURNEY: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,60}")
_LINK: Final = re.compile(
    r"(https://[^\s]{1,280}|docs/[A-Za-z0-9_./@-]{1,200}(#[a-z0-9-]{1,80})?)"
)
FRESH: Final = timedelta(hours=24)
KEYS: Final = frozenset(
    {"kind", "tenant", "slot", "flags", "journeys", "shadow_run", "rollback", "operator"}
    | {"approved_by"}
)
OPTIONAL: Final = frozenset({"eval_report", "cpa_memo", "hotfix"})
ANY_JOURNEY: Final = "*"  # the staging job ran every journey: one time for all


class RequestError(ValueError):
    pass


@dataclass(frozen=True)
class FlipRequest:
    file: str
    tenant: UUID
    code: str
    slot: datetime
    flag: str
    value: str
    journeys: tuple[str, ...]
    shadow_run: str
    rollback: str
    operator: str
    approved_by: str
    eval_report: str | None
    hotfix: str | None
    sha256: str  # the request as committed, canonical JSON (the audit's `request` reference)


def _link(value: object, field: str) -> str:
    if not isinstance(value, str) or not _LINK.fullmatch(value):
        raise RequestError(f"{field} is an https link or a docs/ path")
    return value


def parse(raw: object, file: str) -> FlipRequest:
    """The request, or `RequestError` naming the first field that is wrong."""
    match = _FILE.fullmatch(Path(file).name)
    if match is None:
        raise RequestError("the file is flip-<yyyy-mm-dd>-<pilot code>.yaml")
    if not isinstance(raw, dict):
        raise RequestError("a flip request is a mapping")
    data = cast(dict[str, object], raw)
    if data.get("kind") != "flag_flip":
        raise RequestError("kind is flag_flip")
    missing = sorted(KEYS - set(data))
    unknown = sorted(set(data) - KEYS - OPTIONAL)
    if missing or unknown:
        raise RequestError(f"missing {missing}, unknown {unknown}")
    try:
        tenant = UUID(str(data["tenant"]))
    except ValueError:
        raise RequestError("tenant is the firm's tenant id") from None
    slot_raw = data["slot"]
    slot = slot_raw if isinstance(slot_raw, datetime) else None
    if isinstance(slot_raw, str):
        try:
            slot = datetime.fromisoformat(slot_raw)
        except ValueError:
            slot = None
    if slot is None or slot.tzinfo is None:
        raise RequestError("slot is an ISO 8601 instant with an offset")
    if slot.astimezone(release_windows.CT).date().isoformat() != match.group(1):
        raise RequestError("the file's date is the slot's date (Central time)")
    flags = data["flags"]
    if not isinstance(flags, list) or len(cast(list[object], flags)) != 1:
        raise RequestError("one flag per request (DEC-809): flags is a list of one")
    entry = cast(list[object], flags)[0]
    if not isinstance(entry, dict) or set(cast(dict[str, object], entry)) != {"name", "value"}:
        raise RequestError("each flag is {name, value}")
    flag = cast(dict[str, object], entry)
    journeys = data["journeys"]
    if (
        not isinstance(journeys, list)
        or not journeys
        or not all(
            isinstance(j, str) and _JOURNEY.fullmatch(j) for j in cast(list[object], journeys)
        )
    ):
        raise RequestError("journeys is a list of journey spec slugs")
    for field in ("operator", "approved_by"):
        if not isinstance(data[field], str) or not _HANDLE.fullmatch(str(data[field])):
            raise RequestError(f"{field} is a handle")
    hotfix = data.get("hotfix")
    if hotfix is not None and (
        not isinstance(hotfix, str) or not 10 <= len(hotfix.strip()) <= 300
    ):
        raise RequestError("hotfix is a reason of 10-300 characters")
    canonical = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
    return FlipRequest(
        file=Path(file).name,
        tenant=tenant,
        code=match.group(2),
        slot=slot,
        flag=str(flag["name"]),
        value=str(flag["value"]).lower()
        if isinstance(flag["value"], bool)
        else str(flag["value"]),
        journeys=tuple(cast(list[str], journeys)),
        shadow_run=_link(data["shadow_run"], "shadow_run"),
        rollback=_link(data["rollback"], "rollback"),
        operator=str(data["operator"]),
        approved_by=str(data["approved_by"]),
        eval_report=None
        if data.get("eval_report") is None
        else _link(data["eval_report"], "eval_report"),
        hotfix=None if hotfix is None else str(hotfix),
        sha256=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def precheck(
    req: FlipRequest,
    cal: release_windows.Calendar,
    greens: Mapping[str, datetime],
    now: datetime,
    registry_journeys: Mapping[str, tuple[str, ...]],
    flag_values: Mapping[str, tuple[str, ...]],
) -> list[str]:
    """Why the request may not be approved (SPEC-403 AC-12); empty when it may."""
    why: list[str] = []
    firm = cal.firm(req.tenant)
    if firm is None:
        why.append("not_a_pilot_firm")
    elif firm.code != req.code:
        why.append("file_code_is_not_the_firms")
    if req.approved_by == req.operator:
        why.append("approver_is_operator")
    if req.flag not in flag_values:
        why.append("unknown_flag")
    elif req.value not in flag_values[req.flag]:
        why.append("unknown_value")
    needed = set(req.journeys) | set(registry_journeys.get(req.flag, ()))
    missing = sorted(set(registry_journeys.get(req.flag, ())) - set(req.journeys))
    if missing:
        why.append("journeys_missing:" + ",".join(missing))
    for journey in sorted(needed):
        passed = greens.get(journey, greens.get(ANY_JOURNEY))
        if passed is None:
            why.append(f"journey_never_green:{journey}")
        elif now - passed > FRESH:
            why.append(f"journey_stale:{journey}")
    if req.slot < now - timedelta(hours=2):
        why.append("slot_in_the_past")
    if firm is not None and req.hotfix is None:
        window = release_windows.in_window(cal, req.tenant, req.slot)
        if window is not None and not release_windows.flip_slot(cal, req.slot, req.tenant):
            why.append("no_slot")
        if window is None and req.slot.astimezone(release_windows.CT).weekday() not in (1, 3):
            why.append("not_a_release_day")
    if req.flag.startswith("prompt.") and req.eval_report is None:
        why.append("eval_report_missing")
    return why


def argv(req: FlipRequest) -> list[str]:
    """The flag CLI's command for the ops task: the flip guard runs again when it executes."""
    args = [
        "python", "-m", "abacus_tools.flags",
        "--firm", str(req.tenant), "--flag", req.flag, "--value", req.value,
        "--operator", req.operator, "--reason", f"ops request {req.file}",
        "--approved-by", req.approved_by, "--rollback", req.rollback,
        "--request-sha256", req.sha256, "--shadow-run", req.shadow_run,
    ]  # fmt: skip
    if req.eval_report is not None:
        args += ["--eval-report", req.eval_report]
    if req.hotfix is not None:
        args += ["--hotfix", req.hotfix]
    return args


def greens_from(path: Path) -> dict[str, datetime]:
    """`{journey: last green ISO instant}` as the CI step wrote it (`*` for the whole job)."""
    raw = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    out: dict[str, datetime] = {}
    for journey, when in raw.items():
        if isinstance(when, str):
            out[journey] = datetime.fromisoformat(when.replace("Z", "+00:00"))
    return out


def main(argv_: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.flip_request")
    sub = parser.add_subparsers(dest="command", required=True)
    checking = sub.add_parser("precheck")
    checking.add_argument("files", nargs="+", type=Path)
    checking.add_argument("--journeys", type=Path, required=True)
    checking.add_argument("--now", default=None)
    args = parser.parse_args(list(argv_) if argv_ is not None else None)
    from abacus.kernel._flags import FLAGS
    from abacus_tools.codegen import feature_flags

    cal = release_windows.load()
    now = system_now() if args.now is None else datetime.fromisoformat(cast(str, args.now))
    greens = greens_from(cast(Path, args.journeys))
    entries = feature_flags.parse(feature_flags.source())
    registry = {e.name: e.journeys for e in entries}
    values = {
        name: (("true", "false") if f.kind == "boolean" else tuple(f.values))
        for name, f in FLAGS.items()
    }
    status = 0
    for file in cast(list[Path], args.files):
        try:
            req = parse(yaml.safe_load(file.read_text(encoding="utf-8")), str(file))
        except RequestError as error:
            print(f"{file.name}: refused: {error}", file=sys.stderr)
            status = 1
            continue
        why = precheck(req, cal, greens, now, registry, values)
        if why:
            print(f"{file.name}: refused: {', '.join(why)}", file=sys.stderr)
            status = 1
        else:
            print(f"{file.name}: ready for approval by {req.approved_by}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
