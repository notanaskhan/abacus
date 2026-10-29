"""`make go-live-check FIRM=<tenant_id> LEVEL=shadow|client_facing|tax|season` (Q-04-T009;
SPEC-403 AC-11; Q-04 AC-6.1 to AC-6.4, AC-5.6, AC-5.7).

The dossier's evidence, read rather than remembered: for each chapter 06 §8.3 item at the level,
`pass` or `fail` with the value it read, or `manual` with the dossier section that owns it. The
result is JSON for `docs/ops/go-live/<pilot-code>.md`; the exit code is 1 when any item fails.

Reads only public interfaces, as the platform in the firm's tenant context (an ops task, actor
`operator:go-live-check`): identity's operator posture (SSO, MFA, admins, support switch), the
platform's provisioning status and entitlements, the flag registry and the firm's flag values, the
AI opt-in and the agents' stages, the provider terms register, the write-capability registry,
`deploy/windows.yaml`, the flag calendar, the runbooks' rehearsal dates and the on-call file.

    python -m abacus_tools.go_live --firm <tenant_id> --level shadow [--at <ISO instant>]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final, Literal, cast
from uuid import UUID

import yaml

from abacus.kernel.clock import system_now
from abacus_tools import release_windows

Level = Literal["shadow", "client_facing", "tax", "season"]
Status = Literal["pass", "fail", "manual"]
LEVELS: Final[tuple[Level, ...]] = ("shadow", "client_facing", "tax", "season")
REPO: Final = Path(__file__).resolve().parents[3]
ON_CALL: Final = REPO / "docs" / "ops" / "on-call.md"
RUNBOOKS: Final = REPO / "docs" / "runbooks"
SEASON_RUNBOOKS: Final = ("RB-16",)  # busy-season readiness; RB-18/19 join when written
TERMS_MARGIN: Final = timedelta(days=90)
ON_CALL_MAX_AGE: Final = timedelta(days=31)
# Flags whose being on reaches a client: the portal, client email and signatures (AC-5.7).
CLIENT_FACING: Final = re.compile(r"^(portal|signatures|communications|notifications)\.")


@dataclass(frozen=True)
class Item:
    id: str
    section: str  # chapter 06 §8.3 category
    status: Status
    value: str
    dossier: str = ""  # where a manual item's evidence lives


@dataclass(frozen=True)
class Facts:
    """What the collector read for one firm (nothing a person typed; no names)."""

    tenant_id: UUID
    synthetic: bool
    provisioned: bool
    pilot_code: str | None
    sso_enforced: bool
    sso_exempt_designated: bool
    mfa_enrolled: int
    mfa_seats: int
    firm_admins: int
    security_admins: int
    support_requests_allowed: bool
    ai_opted_in: bool
    agent_stages: Mapping[str, str | None] = field(default_factory=dict[str, str | None])
    flags_on: frozenset[str] = frozenset()
    terms_review_by: tuple[date, ...] = ()
    writes_enabled: int = 0
    flag_expiries: Mapping[str, date] = field(default_factory=dict[str, date])
    runbooks_rehearsed: Mapping[str, date | None] = field(default_factory=dict[str, date | None])
    on_call_updated: date | None = None
    # G-01-T19 (DEC-903): the M9 checklist rows.
    members_without_level: int = 0
    walls_active: int = 0
    offshore_members: int = 0
    offshore_consented_clients: int = 0


def _item(ok: bool, id: str, section: str, value: str) -> Item:
    return Item(id, section, "pass" if ok else "fail", value)


def _manual(id: str, section: str, dossier: str) -> Item:
    return Item(id, section, "manual", "evidence in the dossier", dossier)


def walls_item(f: Facts) -> Item:
    """M9 "walls configured" (G-01-T19): any active wall passes; none is manual, because only
    the dossier can say the firm declared no conflict that needs one (ADM-03 b)."""
    if f.walls_active > 0:
        return Item("identity.walls", "Identity", "pass", f"{f.walls_active} active walls")
    return _manual(
        "identity.walls", "Identity", "§Identity: no active wall; confirm no declared conflict"
    )


def shadow_items(f: Facts, at: datetime, cal: release_windows.Calendar) -> list[Item]:
    """Q-04 AC-6.1: the items every level carries."""
    today = release_windows.local_day(at)
    stages = dict(f.agent_stages)
    off_stage = sorted(a for a, s in stages.items() if s != "shadow" and s != "live")
    lapsed = [d for d in f.terms_review_by if d < today + TERMS_MARGIN]
    client_flags = sorted(n for n in f.flags_on if CLIENT_FACING.match(n))
    return [
        _item(
            f.provisioned,
            "tenant.provisioned",
            "Tenant",
            "provisioned" if f.provisioned else "not provisioned",
        ),
        _item(not f.synthetic, "tenant.real", "Tenant", "synthetic" if f.synthetic else "real"),
        _item(
            f.pilot_code is not None,
            "windows.entry",
            "Operations",
            f.pilot_code or "not in deploy/windows.yaml (P-29 entry missing)",
        ),
        _item(
            f.sso_enforced,
            "identity.sso_enforced",
            "Identity",
            "required" if f.sso_enforced else "not required",
        ),
        _item(
            f.mfa_seats > 0 and f.mfa_enrolled == f.mfa_seats,
            "identity.mfa_all_staff",
            "Identity",
            f"{f.mfa_enrolled} of {f.mfa_seats} staff",
        ),
        _item(
            f.sso_exempt_designated,
            "identity.break_glass",
            "Identity",
            "SSO-exempt account designated" if f.sso_exempt_designated else "none designated",
        ),
        _item(
            f.firm_admins >= 1 and f.security_admins >= 1 and f.members_without_level == 0,
            "identity.roles_mapped",
            "Identity",
            f"{f.firm_admins} firm admins, {f.security_admins} security admins, "
            f"{f.members_without_level} staff without a role template (P-10)",
        ),
        walls_item(f),
        _item(
            True,  # the gate is code: assignment refuses an offshore member without a consent
            "identity.offshore_consent_gated",
            "Identity",
            f"{f.offshore_members} offshore members; assignment needs an offshore-disclosure "
            f"consent ({f.offshore_consented_clients} clients consented)",
        ),
        Item(
            "operations.support_switch",
            "Operations",
            "pass",
            "support requests allowed" if f.support_requests_allowed else "support requests off",
        ),
        _manual("data.retention", "Data protection", "§Data protection: ADM-06 h policies"),
        _manual(
            "data.audit_chain",
            "Data protection",
            "§Data protection: make audit-chain-verify, 7 days",
        ),
        _manual("data.tin_sealing", "Data protection", "§Data protection: tax or EBP only"),
        _item(
            bool(f.terms_review_by) and not lapsed,
            "ai.provider_terms",
            "AI",
            "no provider terms registered"
            if not f.terms_review_by
            else f"review_by {min(f.terms_review_by)} (needs {today + TERMS_MARGIN} or later)",
        ),
        _item(
            f.ai_opted_in,
            "ai.client_data_opt_in",
            "AI",
            "opted in against the current terms" if f.ai_opted_in else "not opted in (AC-5.6)",
        ),
        _item(
            not off_stage,
            "ai.agents_at_shadow",
            "AI",
            "every cleared agent at shadow or live"
            if not off_stage
            else "no stage: " + ", ".join(off_stage),
        ),
        _manual("ai.platform_pause_tested", "AI", "§AI: platform AI pause tested this quarter"),
        _item(
            f.writes_enabled == 0,
            "integrations.no_writes",
            "Integrations",
            f"{f.writes_enabled} write capabilities enabled",
        ),
        _item(
            not client_flags,
            "communications.no_client_facing",
            "Operations",
            "none on" if not client_flags else "on: " + ", ".join(client_flags),
        ),
        _item(
            f.on_call_updated is not None and today - f.on_call_updated <= ON_CALL_MAX_AGE,
            "operations.on_call_current",
            "Operations",
            "docs/ops/on-call.md missing"
            if f.on_call_updated is None
            else f"updated {f.on_call_updated}",
        ),
        _manual(
            "operations.restore_drill",
            "Operations",
            "§Operations: restore drill and game day this quarter",
        ),
    ]


def _blackout(at: datetime) -> bool:
    """Jan 15 to Apr 15 inclusive, Central time: nothing client-facing goes live (AC-5.7)."""
    day = release_windows.local_day(at)
    return date(day.year, 1, 15) <= day <= date(day.year, 4, 15)


def client_facing_items(f: Facts, at: datetime) -> list[Item]:
    """Q-04 AC-6.2 and AC-5.7: what turning on a client-facing surface adds."""
    blackout = _blackout(at)
    return [
        _item(
            not blackout,
            "season.no_client_facing_go_live",
            "Operations",
            "inside Jan 15 to Apr 15: no client-facing go-live, no override"
            if blackout
            else "outside Jan 15 to Apr 15",
        ),
        _manual("ai.live_stage_criteria", "AI", "§AI: live-stage criteria per agent (QD-10)"),
        _manual("contract.delta_1", "Contract and legal", "§Contract: delta #1 closed (F-09)"),
        _manual("identity.portal_mfa", "Identity", "§Identity: portal MFA for owners and signers"),
        _manual(
            "communications.sender_domain",
            "Operations",
            "§Operations: ADM-10 f, sending domain verified",
        ),
        _manual(
            "communications.templates_published",
            "Operations",
            "§Operations: POR-20 l for every key",
        ),
        _manual("ai.autonomy_level_1", "AI", "§AI: ADM-04 autonomy level 1"),
        _manual("ai.w1_attest_refused", "AI", "§AI: W1 refused for attest-flagged clients"),
    ]


def tax_items() -> list[Item]:
    """Q-04 AC-6.3."""
    return [
        _manual(
            "tax.consent_7216",
            "Data protection",
            "§Data protection: condition 6 consent_7216 live",
        ),
        _manual("tax.tri_mfa", "Identity", "§Identity: TRI MFA"),
        _manual(
            "tax.tin_reveal_logged",
            "Data protection",
            "§Data protection: sealed TIN, logged reveal",
        ),
        _manual(
            "tax.cch_format_signoff",
            "Contract and legal",
            "§Contract: CCH format sign-off (F-09-T120)",
        ),
        _manual(
            "tax.never_ero", "Operations", "§Operations: never-ERO tests green on the release"
        ),
        _manual(
            "tax.support_us_only", "Operations", "§Operations: support US-located only (DEC-72)"
        ),
    ]


def season_items(f: Facts, at: datetime, cal: release_windows.Calendar) -> list[Item]:
    """Q-04 AC-6.4: no flag expiring inside the coming window; season runbooks rehearsed."""
    today = release_windows.local_day(at)
    coming = next((w for w in cal.windows if w.span.end >= today), None)
    inside = (
        sorted(n for n, d in f.flag_expiries.items() if d in coming.span)
        if coming is not None
        else []
    )
    unrehearsed = sorted(rb for rb, d in f.runbooks_rehearsed.items() if d is None)
    return [
        _item(
            coming is not None,
            "season.windows_entries",
            "Operations",
            coming.id if coming is not None else "no coming window in deploy/windows.yaml",
        ),
        _item(
            not inside,
            "season.flags_outside_window",
            "Operations",
            "none expire inside " + coming.id
            if coming is not None and not inside
            else "expire inside: " + ", ".join(inside),
        ),
        _item(
            not unrehearsed,
            "season.runbooks_rehearsed",
            "Operations",
            "rehearsed" if not unrehearsed else "never rehearsed: " + ", ".join(unrehearsed),
        ),
        _manual("season.reference_sets", "Operations", "§Operations: C21 reference sets current"),
        _manual(
            "season.extended_on_call", "Operations", "§Operations: extended on-call published"
        ),
        _manual(
            "season.load_test",
            "Operations",
            "§Operations: load-test result where the gate needs one",
        ),
    ]


def evaluate(
    level: Level, facts: Facts, at: datetime, cal: release_windows.Calendar
) -> list[Item]:
    """Every item for `level`: shadow's, plus the level's own (Q-04 AC-6.1 to AC-6.4)."""
    items = shadow_items(facts, at, cal)
    if level == "client_facing":
        items += client_facing_items(facts, at)
    elif level == "tax":
        items += client_facing_items(facts, at) + tax_items()
    elif level == "season":
        items += season_items(facts, at, cal)
    return items


def report(level: Level, facts: Facts, at: datetime, items: Sequence[Item]) -> dict[str, object]:
    failed = [i.id for i in items if i.status == "fail"]
    return {
        "tenant_id": str(facts.tenant_id),
        "pilot_code": facts.pilot_code,
        "level": level,
        "at": at.isoformat(),
        "passed": not failed,
        "failed": failed,
        "items": [asdict(i) for i in items],
    }


# --- reading the facts ---------------------------------------------------------------------------


def _frontmatter_date(path: Path, key: str) -> date | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    head = cast(dict[str, object], yaml.safe_load(text.split("---\n", 2)[1]) or {})
    value = head.get(key)
    return value if isinstance(value, date) else None


def runbooks_rehearsed(ids: Iterable[str] = SEASON_RUNBOOKS) -> dict[str, date | None]:
    out: dict[str, date | None] = {}
    for rb in ids:
        found = sorted(RUNBOOKS.glob(f"{rb}-*.md"))
        out[rb] = _frontmatter_date(found[0], "last_rehearsed") if found else None
    return out


def on_call_updated(path: Path = ON_CALL) -> date | None:
    """`updated:` in the on-call file's frontmatter, or None when the file is missing."""
    return _frontmatter_date(path, "updated") if path.is_file() else None


async def collect(tenant_id: UUID, cal: release_windows.Calendar) -> Facts:
    """The firm's facts through public interfaces, as the platform (read-only)."""
    from abacus.kernel._flags import FLAGS
    from abacus.kernel._provider_terms import ENTRIES
    from abacus.kernel.flags import flag
    from abacus.modules.agents.api import AGENTS, stage_for
    from abacus.modules.identity.api import ai_client_data_opted_in, operator_posture
    from abacus.modules.integrations.api import registry
    from abacus.modules.platform.api import operator_context
    from abacus_tools.codegen import feature_flags
    from abacus_tools.tenants import status

    tenant = operator_context(tenant_id, "go-live-check")
    try:
        facts = await status(tenant_id, with_workflow=True)
    except Exception:  # Temporal unreachable: the key state still answers
        facts = await status(tenant_id, with_workflow=False)
    posture = await operator_posture(tenant)
    on = frozenset(
        [
            name
            for name, f in FLAGS.items()
            if f.kind == "boolean" and await flag(tenant, f) is True
        ]
    )
    stages = {
        agent: await stage_for(tenant, agent)
        for agent, spec in AGENTS.items()
        if spec.client_data == "cleared"
    }
    firm = cal.firm(tenant_id)
    return Facts(
        tenant_id=tenant_id,
        synthetic=bool(facts["synthetic"]),
        provisioned=bool(facts["key_ready"]) and facts.get("workflow") in (None, "COMPLETED"),
        pilot_code=firm.code if firm is not None else None,
        sso_enforced=posture.sso_enforced,
        sso_exempt_designated=posture.sso_exempt_designated,
        mfa_enrolled=posture.mfa_enrolled,
        mfa_seats=posture.mfa_seats,
        firm_admins=posture.firm_admins,
        security_admins=posture.security_admins,
        support_requests_allowed=posture.support_requests_allowed,
        ai_opted_in=await ai_client_data_opted_in(tenant),
        agent_stages=stages,
        flags_on=on,
        terms_review_by=tuple(e.review_by for e in ENTRIES),
        writes_enabled=sum(1 for w in registry().writes if w.enabled),
        flag_expiries={e.name: e.expires for e in feature_flags.parse(feature_flags.source())},
        runbooks_rehearsed=runbooks_rehearsed(),
        on_call_updated=on_call_updated(),
        members_without_level=posture.members_without_level,
        walls_active=posture.walls_active,
        offshore_members=posture.offshore_members,
        offshore_consented_clients=posture.offshore_consented_clients,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.go_live")
    parser.add_argument("--firm", type=UUID, required=True)
    parser.add_argument("--level", choices=LEVELS, required=True)
    parser.add_argument("--at", default=None, help="ISO 8601 with an offset; now by default")
    args = parser.parse_args(list(argv) if argv is not None else None)
    at = system_now() if args.at is None else datetime.fromisoformat(cast(str, args.at))
    if at.tzinfo is None:
        print("--at needs an offset", file=sys.stderr)
        return 2
    try:
        cal = release_windows.load()
    except release_windows.WindowsError as broken:
        print(f"deploy/windows.yaml: {broken}", file=sys.stderr)
        return 2
    from abacus.kernel.config import settings
    from abacus.kernel.db.session import configure_engine, dispose_engine

    url = settings().database_url
    if url is None:
        print("database_url is not set", file=sys.stderr)
        return 2

    async def run() -> Facts:
        configure_engine(url.get_secret_value())
        try:
            return await collect(cast(UUID, args.firm), cal)
        finally:
            await dispose_engine()

    facts = asyncio.run(run())
    level = cast(Level, args.level)
    items = evaluate(level, facts, at, cal)
    out = report(level, facts, at, items)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
