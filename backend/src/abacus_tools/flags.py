"""`make flag FIRM=<tenant_id> FLAG=<name> VALUE=<value> OPERATOR=<name> REASON=<text>`
(SPEC-011 AC-3; Q2): set a firm's value for a registered flag, audited.

Runs with the application database credentials in the firm's tenant context, as the platform
(`system`, actor `operator:<name>`). The audit event carries fingerprints of the old and new
values (audit references never hold text, TASK-026 D2); the reason is kept on the row.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import FLAGS
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Ref, Target, uow

_OPERATOR = re.compile(r"^[a-z][a-z0-9._-]{0,60}$")


def _fingerprint(value: str | None) -> str:
    return hashlib.sha256((value or "").encode()).hexdigest()


async def set_flag(firm: UUID, name: str, value: str, operator: str, reason: str) -> str | None:
    """Set the firm's value; returns the previous one (None when it had none)."""
    found = FLAGS.get(name)
    if found is None:
        raise ValueError(f"{name} is not a registered flag")
    if found.kind == "boolean":
        value = value.lower()
    if not found.valid(value):
        raise ValueError(f"{value!r} is not a value of {name}")
    if not _OPERATOR.fullmatch(operator):
        raise ValueError("operator is a lower-case name")
    if not 1 <= len(reason.strip()) <= 500:
        raise ValueError("a reason (1 to 500 characters) is required")
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
            after=Ref(value=_fingerprint(value)),
        )
    forget_flags()
    return str(before) if before is not None else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flag")
    parser.add_argument("--firm", type=UUID, required=True)
    parser.add_argument("--flag", required=True)
    parser.add_argument("--value", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    url = settings().database_url
    if url is None:
        print("database_url is not set", file=sys.stderr)
        return 2

    async def run() -> str | None:
        configure_engine(url.get_secret_value())
        try:
            return await set_flag(args.firm, args.flag, args.value, args.operator, args.reason)
        finally:
            await dispose_engine()

    try:
        before = asyncio.run(run())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"{args.flag} for {args.firm}: {before or '(default)'} -> {args.value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
