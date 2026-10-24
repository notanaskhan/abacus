"""Propagate an Accrued-side security incident into the firms it touched (Q-02-T33; RB-27).

    python -m abacus_tools.incidents propagate --ref ACC-2026-001 --firms <id>,<id> \\
        --facts facts.json --staff <staff-user-id> --reason "Accrued SEV1 confirmed" [--dry-run]

`make incident-propagate` runs it. It does what the staff route does (`POST /v1/platform/
incidents/{accrued_ref}/propagate`): every firm must exist and have `compliance.incidents` on,
then `IncidentPropagation` writes each firm's entry as the system with Accrued's facts, and the
firm's QI and admins are told (`incident_from_accrued`). The DPA's notice clock is 72 hours from
`confirmed_at`. `facts.json` holds `title`, `event_kind`, `discovered_at`, `confirmed_at` (ISO
8601 with an offset), `consumers_affected` and `unencrypted`; the title is Confidential and is
never printed. `--dry-run` checks everything and starts nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Final, cast
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.db.session import configure_engine, dispose_engine
from abacus.modules.platform.api import IncidentFactsInput, start_propagation

_REF: Final = re.compile(r"[A-Z0-9][A-Z0-9-]{2,39}")
_KINDS: Final = frozenset(
    {
        "unauthorized_access",
        "credential_attack",
        "data_exposure",
        "lost_device",
        "vendor_incident",
        "other",
    }
)


class Refused(Exception):
    """The command was refused before anything started."""


def _aware(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise Refused(f"{name} is an ISO 8601 time with an offset")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise Refused(f"{name} is an ISO 8601 time with an offset") from None
    if parsed.tzinfo is None:
        raise Refused(f"{name} needs an offset")
    return parsed.isoformat()


def load_facts(path: Path) -> IncidentFactsInput:
    """Accrued's facts from a JSON file, checked as the staff route checks them."""
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise Refused("the facts file is a JSON object")
    raw = cast(dict[str, object], loaded)
    title = raw.get("title")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200 or "\n" in title:
        raise Refused("title is one line of 1 to 200 characters")
    kind = raw.get("event_kind")
    if kind not in _KINDS:
        raise Refused(f"event_kind is one of {', '.join(sorted(_KINDS))}")
    consumers = raw.get("consumers_affected")
    if consumers is not None and (
        not isinstance(consumers, int) or isinstance(consumers, bool) or consumers < 0
    ):
        raise Refused("consumers_affected is a whole number of at least 0, or null")
    unencrypted = raw.get("unencrypted")
    if unencrypted is not None and not isinstance(unencrypted, bool):
        raise Refused("unencrypted is true, false or null")
    return IncidentFactsInput(
        title=title.strip(),
        event_kind=str(kind),
        discovered_at=_aware(raw.get("discovered_at"), "discovered_at"),
        consumers_affected=consumers,
        unencrypted=unencrypted,
        confirmed_at=_aware(raw.get("confirmed_at"), "confirmed_at"),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.incidents")
    commands = parser.add_subparsers(dest="command", required=True)
    propagating = commands.add_parser("propagate", help="RB-27: Accrued's facts to each firm")
    propagating.add_argument("--ref", required=True, help="Accrued's incident reference")
    propagating.add_argument("--firms", required=True, help="comma-separated tenant ids")
    propagating.add_argument("--facts", required=True, type=Path)
    propagating.add_argument("--staff", required=True, type=UUID, help="the staff member's id")
    propagating.add_argument("--reason", required=True)
    propagating.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not _REF.fullmatch(args.ref):
            raise Refused("--ref is upper-case letters, digits and dashes (3 to 40)")
        reason = str(args.reason).strip()
        if not 1 <= len(reason) <= 500 or "\n" in reason:
            raise Refused("--reason is one line of 1 to 500 characters")
        try:
            firms = [UUID(f.strip()) for f in str(args.firms).split(",") if f.strip()]
        except ValueError:
            raise Refused("--firms are tenant ids") from None
        facts = load_facts(args.facts)
        if args.dry_run:
            print(json.dumps({"accrued_ref": args.ref, "firms": [str(f) for f in firms]}))
            return 0
        s = settings()
        if s.database_url is None:
            raise Refused("database_url is not set")
        app = s.database_url.get_secret_value()

        async def run() -> list[UUID]:
            configure_engine(app)
            try:
                return await start_propagation(args.staff, args.ref, firms, facts, reason)
            finally:
                await dispose_engine()

        started = asyncio.run(run())
        print(json.dumps({"accrued_ref": args.ref, "started_for": [str(f) for f in started]}))
        return 0
    except Refused as refused:
        print(str(refused), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
