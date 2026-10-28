"""The client-mail gate, the operator's command (R-01-T27; R-01 story 9.2; chapter 01 §1.2.4
rule 3; DEC-953). Run as an ECS one-off `abacus-ops` task in the Tuesday window, never from a
laptop against a hosted database.

    python -m abacus_tools.client_mail open --tenant <tenant_id> --operator <handle> \
        --second <handle> --request-ref <change record>
    python -m abacus_tools.client_mail close --tenant <tenant_id> --operator <handle> \
        --request-ref <change record>

`open` names both founders (two different handles) and calls `set_client_mail(...)` as
`abacus_ops` (`ops_database_url`; EXECUTE only), which upserts the firm's `firm_mail_policies` row
and writes `firm_mail_policy.client_mail_enabled` into that firm's audit trail as
`operator:<handle>`. `close` (a rollback) needs one. Until a firm is opened, `send_templated`
records its client, third-party and respondent mail `blocked` with `firm_not_client_facing`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.config import settings
from abacus.modules.platform.api import OPERATOR_HANDLE
from abacus_tools.db_connect import connect as connect_db


class Refused(Exception):
    """The command was refused before or by the database; nothing was written."""


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@dataclass(frozen=True)
class MailChange:
    tenant: UUID
    open: bool
    operator: str
    second: str | None
    request_ref: str

    def checked(self) -> MailChange:
        if not OPERATOR_HANDLE.fullmatch(self.operator):
            raise Refused("--operator is a lower-case handle, never an email address")
        if self.open:
            if self.second is None or not OPERATOR_HANDLE.fullmatch(self.second):
                raise Refused("open names a second operator (--second, a lower-case handle)")
            if self.second == self.operator:
                raise Refused("--second is a different person from --operator")
        if not 1 <= len(self.request_ref.strip()) <= 200:
            raise Refused("--request-ref is 1 to 200 characters")
        return self


async def set_client_mail(ops_dsn: str, change: MailChange) -> bool:
    """Whether the firm's client mail is open after the change, as `abacus_ops`."""
    change = change.checked()
    connection = await connect_db(_dsn(ops_dsn))
    try:
        result = await connection.fetchval(
            "SELECT set_client_mail($1, $2, $3, $4, $5)",
            change.tenant,
            change.open,
            change.operator,
            change.second,
            change.request_ref.strip(),
        )
    finally:
        await connection.close()
    return bool(result)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.client_mail")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("open", "close"):
        command = sub.add_parser(name)
        command.add_argument("--tenant", type=UUID, required=True)
        command.add_argument("--operator", required=True)
        if name == "open":
            command.add_argument("--second", required=True)
        command.add_argument("--request-ref", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    s = settings()
    try:
        if s.ops_database_url is None:
            raise Refused("ops_database_url (the abacus_ops role) is not set")
        change = MailChange(
            tenant=args.tenant,
            open=args.command == "open",
            operator=args.operator,
            second=getattr(args, "second", None),
            request_ref=args.request_ref,
        )
        state = asyncio.run(set_client_mail(s.ops_database_url.get_secret_value(), change))
        print(f"client mail for {change.tenant}: {'open' if state else 'closed'}")
        return 0
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
