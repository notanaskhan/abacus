"""`make flag FIRM=<tenant_id> FLAG=<name> VALUE=<value> OPERATOR=<name> REASON=<text>`
(SPEC-011 AC-3; Q2): set a firm's value for a registered flag, audited.

Runs with the application database credentials in the firm's tenant context, as the platform
(`system`, actor `operator:<name>`). The audit event carries fingerprints of the old and new
values (audit references never hold text, TASK-026 D2); the reason is kept on the row.

Q-04-T004 (SPEC-403 AC-8, AC-9; P-29): before anything is written, `abacus_tools.flip_guard` checks
the flip against `deploy/windows.yaml`. A pilot firm's flip names `--approved-by` (the other
founder) and `--rollback`; inside its window it also needs the Tuesday slot unless `--hotfix`
gives a reason, the `--request` file it runs from, and for a `prompt.*` variant `--eval-report`
and `--shadow-run`. `feature_flag.set` then carries those references. `--all-off` sets every
flag the firm has a value for back to its default in one unit of work, with one
`feature_flag.bulk_off` event.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import FLAGS
from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Ref, Target, uow
from abacus_tools import flip_guard, release_windows

_OPERATOR = re.compile(r"^[a-z][a-z0-9._-]{0,60}$")
Refs = Mapping[str, str | int]


def _fingerprint(value: str | None) -> str:
    return hashlib.sha256((value or "").encode()).hexdigest()


def _checked(operator: str, reason: str) -> None:
    if not _OPERATOR.fullmatch(operator):
        raise ValueError("operator is a lower-case name")
    if not 1 <= len(reason.strip()) <= 500:
        raise ValueError("a reason (1 to 500 characters) is required")


async def set_flag(
    firm: UUID, name: str, value: str, operator: str, reason: str, refs: Refs | None = None
) -> str | None:
    """Set the firm's value; returns the previous one (None when it had none). `refs` are the
    flip guard's references, recorded on `feature_flag.set` (Q-04 AC-4.1)."""
    found = FLAGS.get(name)
    if found is None:
        raise ValueError(f"{name} is not a registered flag")
    if found.kind == "boolean":
        value = value.lower()
    if not found.valid(value):
        raise ValueError(f"{value!r} is not a value of {name}")
    _checked(operator, reason)
    tenant = TenantContext(firm, "system", f"operator:{operator}")
    async with uow(tenant) as tx:
        before = await tx.session.scalar(
            text("SELECT value FROM feature_flag_states WHERE flag = :flag FOR UPDATE"),
            {"flag": name},
        )
        await tx.session.execute(
            text(
                "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
                "VALUES (:tenant, :flag, :value, :by, :reason) "
                "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = EXCLUDED.value, "
                "set_by = EXCLUDED.set_by, reason = EXCLUDED.reason, set_at = clock_timestamp()"
            ),
            {"tenant": firm, "flag": name, "value": value, "by": operator, "reason": reason},
        )
        tx.record(
            "feature_flag.set",
            target=Target("feature_flag", list(FLAGS).index(name)),
            before=Ref(value=_fingerprint(before)),
            after=Ref(value=_fingerprint(value), **dict(refs or {})),
        )
    forget_flags()
    return str(before) if before is not None else None


async def all_off(firm: UUID, operator: str, reason: str, refs: Refs | None = None) -> int:
    """Every flag the firm holds a value for, back to its registry default, in one unit of work
    with one `feature_flag.bulk_off` event (Q-04 AC-4.7). Returns how many changed; no other firm
    is touched (the tenant context scopes every statement)."""
    _checked(operator, reason)
    tenant = TenantContext(firm, "system", f"operator:{operator}")
    changed = 0
    async with uow(tenant) as tx:
        rows = (
            await tx.session.execute(
                text("SELECT flag, value FROM feature_flag_states ORDER BY flag FOR UPDATE")
            )
        ).all()
        for name, value in rows:
            found = FLAGS.get(str(name))
            if found is None:
                continue
            default = str(found.default).lower() if found.kind == "boolean" else str(found.default)
            if str(value) == default:
                continue
            await tx.session.execute(
                text(
                    "UPDATE feature_flag_states SET value = :value, set_by = :by, "
                    "reason = :reason, set_at = clock_timestamp() WHERE flag = :flag"
                ),
                {"flag": name, "value": default, "by": operator, "reason": reason},
            )
            changed += 1
        tx.record(
            "feature_flag.bulk_off",
            target=Target("firm", firm),
            after=Ref(flags=changed, **dict(refs or {})),
        )
    forget_flags()
    return changed


def guard(
    flip: flip_guard.Flip, windows: Path = release_windows.WINDOWS_FILE
) -> flip_guard.Verdict:
    """The flip guard over the committed calendar; a broken calendar refuses (fail closed)."""
    try:
        cal = release_windows.load(windows)
    except release_windows.WindowsError:
        return flip_guard.Verdict(("windows_unreadable",), None, True)
    return flip_guard.check(cal, flip)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flag")
    parser.add_argument("--firm", type=UUID, required=True)
    parser.add_argument("--flag")
    parser.add_argument("--value")
    parser.add_argument("--all-off", action="store_true")
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--approved-by")
    parser.add_argument("--rollback")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--request-sha256", help="the ops request's fingerprint (ops-task.yml)")
    parser.add_argument("--hotfix", help="a reason: a hotfix may flip outside the slot")
    parser.add_argument("--eval-report")
    parser.add_argument("--shadow-run")
    args = parser.parse_args(argv)
    if args.all_off == (args.flag is not None or args.value is not None):
        print("give --flag and --value, or --all-off", file=sys.stderr)
        return 2
    verdict = guard(
        flip_guard.Flip(
            firm=args.firm,
            operator=args.operator,
            at=system_now(),
            flags=(args.flag,) if args.flag else (),
            approved_by=args.approved_by,
            rollback=args.rollback,
            request=args.request,
            request_sha256=args.request_sha256,
            hotfix=args.hotfix,
            eval_report=args.eval_report,
            shadow_run=args.shadow_run,
        )
    )
    if not verdict.allowed:
        print("refused: " + ", ".join(verdict.why), file=sys.stderr)
        return 2
    url = settings().database_url
    if url is None:
        print("database_url is not set", file=sys.stderr)
        return 2

    async def run() -> str:
        configure_engine(url.get_secret_value())
        try:
            if args.all_off:
                n = await all_off(args.firm, args.operator, args.reason, verdict.refs)
                return f"{args.firm}: {n} flags back to their defaults"
            before = await set_flag(
                args.firm, args.flag, args.value, args.operator, args.reason, verdict.refs
            )
            return f"{args.flag} for {args.firm}: {before or '(default)'} -> {args.value}"
        finally:
            await dispose_engine()

    try:
        print(asyncio.run(run()))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
