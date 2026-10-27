# ac-test-author: ayushkbhatia
"""Shared seeding for the A-02-T20 and A-02-T21 independent suites (ADR-078; TASK-1473,
TASK-1474): one firm with `ledger.tb_workpaper` and `evidence.citations_v2` on, an open audit
engagement with an assurance work item, a team (partner, manager, senior, staff, reviewer), and
ledger snapshots recorded through `ledger.api.record_snapshot` (the public writer the import and
the connectors use). Every figure is a literal typed here from SPEC-333 and the A-02 epic, never
imported from a scenario or a module constant.

The trial balance (period 2025-01-01 to 2025-12-31, prior 2024-12-31):

| Account | Name | EOY | BOY | Area |
|---|---|---|---|---|
| 1210 | KRS 500 Index | 6,120,450.00 Dr | 5,102,300.00 Dr | Investments |
| 1220 | Other funds | 8,772,990.00 Dr | 7,537,700.00 Dr | Investments |
| 1230 | BrokerWindow | 1,606,560.00 Dr | 1,300,000.00 Dr | Investments |
| 1900 | Suspense | 20,010.00 Dr | 20,000.00 Dr | (none: Unassigned) |
| 2500 | Loan payable | 312,400.00 Cr | 288,500.00 Cr | Debt |
| 3000 | Net assets | 16,207,610.00 Cr | 13,671,500.00 Cr | Net assets |

EOY debits = credits = 16,520,010.00; BOY 13,960,000.00. Investments foot to 16,500,000.00 EOY
and 13,940,000.00 BOY (SPEC-333 AC-18: Δ 2,560,000, Δ% 18.4; KRS 500 Index Δ 1,018,150, Δ%
20.0). Suspense moves 0.05 %: half-even to 0.1 % gives 0.0 (half-up would give 0.1). The newer
snapshot ("v2") agrees BrokerWindow at 1,608,120.00 and net assets at 16,209,170.00.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final, cast

import httpx

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow
from abacus.modules.evidence.api import CitationAnchor, CitationClaim, record_citations
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger.api import LedgerLine, NormalisedTrialBalance, record_snapshot

from .support import Net, Person, Role, Seeder, Site

Json = dict[str, object]
Line = tuple[str, str, str, str]  # code, name, debit, credit
START: Final = date(2025, 1, 1)
END: Final = date(2025, 12, 31)
PRIOR_START: Final = date(2024, 1, 1)
PRIOR_END: Final = date(2024, 12, 31)
SOURCE: Final = "import_netsuite_tb_csv"  # SPEC-028: a NetSuite export (source kind `import`)

EOY: Final[tuple[Line, ...]] = (
    ("1210", "KRS 500 Index", "6120450.00", "0"),
    ("1220", "Other funds", "8772990.00", "0"),
    ("1230", "BrokerWindow", "1606560.00", "0"),
    ("1900", "Suspense", "20010.00", "0"),
    ("2500", "Loan payable", "0", "312400.00"),
    ("3000", "Net assets", "0", "16207610.00"),
)
BOY: Final[tuple[Line, ...]] = (
    ("1210", "KRS 500 Index", "5102300.00", "0"),
    ("1220", "Other funds", "7537700.00", "0"),
    ("1230", "BrokerWindow", "1300000.00", "0"),
    ("1900", "Suspense", "20000.00", "0"),
    ("2500", "Loan payable", "0", "288500.00"),
    ("3000", "Net assets", "0", "13671500.00"),
)
NEWER: Final[tuple[Line, ...]] = (
    ("1210", "KRS 500 Index", "6120450.00", "0"),
    ("1220", "Other funds", "8772990.00", "0"),
    ("1230", "BrokerWindow", "1608120.00", "0"),
    ("1900", "Suspense", "20010.00", "0"),
    ("2500", "Loan payable", "0", "312400.00"),
    ("3000", "Net assets", "0", "16209170.00"),
)
EOY_TOTAL: Final = Decimal("16520010.00")
NEWER_TOTAL: Final = Decimal("16521570.00")
AREAS: Final = {
    "1210": "Investments",
    "1220": "Investments",
    "1230": "Investments",
    "2500": "Debt",
    "3000": "Net assets",
}
FLAGS: Final = ("ledger.tb_workpaper", "evidence.citations_v2")
# Row counts per table, as literal queries.
COUNTS: Final = {
    "trial_balances": "SELECT count(*) FROM trial_balances WHERE tenant_id = $1",
    "trial_balance_versions": "SELECT count(*) FROM trial_balance_versions WHERE tenant_id = $1",
    "trial_balance_lines": "SELECT count(*) FROM trial_balance_lines WHERE tenant_id = $1",
    "ledger_snapshots": "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1",
    "tie_out_checks": "SELECT count(*) FROM tie_out_checks WHERE tenant_id = $1",
}


def tb_path(engagement_id: uuid.UUID, tb_id: uuid.UUID | None = None) -> str:
    base = f"/v1/engagements/{engagement_id}/trial-balances"
    return base if tb_id is None else f"{base}/{tb_id}"


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def detail(response: httpx.Response) -> str:
    return str(cast(Json, response.json()).get("detail"))


def facts(response: httpx.Response) -> Mapping[str, object]:
    return cast(Mapping[str, object], cast(Json, response.json()).get("facts") or {})


async def snapshot(
    tenant_id: uuid.UUID,
    by: uuid.UUID,
    entity_id: uuid.UUID,
    lines: Sequence[Line],
    *,
    start: date = START,
    end: date = END,
    source: str = SOURCE,
) -> uuid.UUID:
    """A validated snapshot through the ledger's public writer, as a person, in one unit."""
    tb = NormalisedTrialBalance(
        period_start=start,
        period_end=end,
        currency="USD",
        lines=tuple(
            LedgerLine(code, name, Decimal(dr), Decimal(cr), f"row:{n}")
            for n, (code, name, dr, cr) in enumerate(lines, start=1)
        ),
        declared_debit=sum((Decimal(x[2]) for x in lines), Decimal(0)),
        declared_credit=sum((Decimal(x[3]) for x in lines), Decimal(0)),
    )
    async with uow(TenantContext(tenant_id, "human", str(by))) as tx:
        ref = await record_snapshot(
            tx,
            client_entity_id=entity_id,
            period_start=start,
            period_end=end,
            tb=tb,
            raw_fingerprint=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            pulled_at=datetime.now(UTC),
            source=source,
        )
        tx.record("ledger_snapshot.created", target=Target("ledger_snapshot", ref.id))
    return ref.id


@dataclass
class Books:
    """One firm's audit engagement, its team and three snapshots of its entity."""

    net: Net
    tenant_id: uuid.UUID
    admin: Person
    partner: Person
    manager: Person
    senior: Person
    staff: Person
    reviewer: Person
    site: Site
    work_item_id: uuid.UUID
    current: uuid.UUID
    prior: uuid.UUID
    newer: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return tb_path(self.site.engagement_id)

    def path(self, tb_id: uuid.UUID, rest: str = "") -> str:
        return f"{tb_path(self.site.engagement_id, tb_id)}{rest}"

    async def call(
        self,
        method: str,
        path: str,
        who: Person | None = None,
        body: Mapping[str, object] | None = None,
        *,
        mfa: bool = True,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        who = who or self.partner
        return await self.net.http.request(
            method,
            path,
            json=body,
            headers={**self.net.headers(who, mfa=mfa), **(headers or {})},
        )

    async def adopt(
        self,
        who: Person | None = None,
        *,
        snapshot_id: uuid.UUID | None = None,
        prior: uuid.UUID | bool | None = True,
        label: str = "standard",
        display_unit: str = "cents",
    ) -> httpx.Response:
        body: Json = {
            "snapshot_id": str(snapshot_id or self.current),
            "label": label,
            "display_unit": display_unit,
        }
        if prior is True:
            body["prior_snapshot_id"] = str(self.prior)
        elif isinstance(prior, uuid.UUID):
            body["prior_snapshot_id"] = str(prior)
        return await self.call("POST", self.base, who, body)

    async def adopted(
        self,
        *,
        snapshot_id: uuid.UUID | None = None,
        prior: uuid.UUID | bool | None = True,
        label: str = "standard",
    ) -> uuid.UUID:
        response = await self.adopt(snapshot_id=snapshot_id, prior=prior, label=label)
        assert response.status_code == 201, response.text
        return uuid.UUID(cast(str, cast(Json, response.json()["trial_balance"])["id"]))

    async def reversion(
        self,
        tb_id: uuid.UUID,
        *,
        snapshot_id: uuid.UUID | None = None,
        seen_version: int = 1,
        reason: str = "Client sent a corrected export",
        who: Person | None = None,
    ) -> httpx.Response:
        return await self.call(
            "POST",
            self.path(tb_id, "/versions"),
            who,
            {
                "snapshot_id": str(snapshot_id or self.newer),
                "prior_snapshot_id": str(self.prior),
                "reason": reason,
                "seen_version": seen_version,
            },
        )

    async def annotate(self, tb_id: uuid.UUID, areas: Mapping[str, str] = AREAS) -> None:
        response = await self.call(
            "POST",
            self.path(tb_id, "/annotations"),
            body={
                "accounts": [{"account_code": c, "area": a} for c, a in areas.items()],
                "reason": "Areas per the audit plan",
            },
        )
        assert response.status_code == 201, response.text

    async def layer(
        self, tb_id: uuid.UUID, layer: str = "unadjusted", who: Person | None = None
    ) -> httpx.Response:
        return await self.call("GET", self.path(tb_id, f"/layers/{layer}"), who)

    async def view(self, tb_id: uuid.UUID, layer: str = "unadjusted") -> Json:
        response = await self.layer(tb_id, layer)
        assert response.status_code == 200, response.text
        return cast(Json, response.json())

    async def actions(self) -> list[tuple[str, str]]:
        rows = await self.seed.rows(
            "SELECT action, actor_kind FROM audit_events WHERE tenant_id = $1 ORDER BY seq",
            self.tenant_id,
        )
        return [(str(r["action"]), str(r["actor_kind"])) for r in rows]

    async def count(self, table: str) -> int:
        return int(cast(int, await self.seed.value(COUNTS[table], self.tenant_id)))

    async def human(self, who: Person) -> AuthContext:
        """`who` as the request would build them, for the public service calls (citations)."""
        membership = cast(
            uuid.UUID,
            await self.seed.value(
                "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                who.tenant_id,
                who.user_id,
            ),
        )
        return AuthContext(
            TenantContext(who.tenant_id, "human", str(who.user_id)),
            who.user_id,
            membership,
            None,
            datetime.now(UTC),
        )

    async def cite_line(
        self,
        tb_id: uuid.UUID,
        snapshot_id: uuid.UUID,
        account: str,
        *,
        value: str | None = None,
        quote: str | None = None,
        who: Person | None = None,
        engagement_id: uuid.UUID | None = None,
        extra: Mapping[str, object] | None = None,
    ) -> tuple[uuid.UUID, bool, str | None, str | None]:
        """One `ledger_line` citation anchored on the trial balance: (id, verified, reason,
        match id)."""
        actor = await self.human(who or self.partner)
        locator: dict[str, object] = {
            "ledger_snapshot_id": str(snapshot_id),
            "account_code": account,
            **(extra or {}),
        }
        async with uow(actor.tenant) as tx:
            [row] = await record_citations(
                tx,
                actor=actor,
                anchor=CitationAnchor(
                    type="trial_balance",
                    id=tb_id,
                    ref=f"line:{account}",
                    engagement_id=engagement_id or self.site.engagement_id,
                ),
                claims=[CitationClaim("ledger_line", locator, quote=quote, value=value)],
            )
        return row.id, row.verified, row.verification_reason, row.match_id

    async def citations(
        self, tb_id: uuid.UUID, who: Person | None = None, engagement: uuid.UUID | None = None
    ) -> list[Json]:
        del engagement
        response = await self.call(
            "GET",
            f"/v1/citations?anchor_type=trial_balance&anchor_id={tb_id}",
            who,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        items = cast(Json, body)["items"] if isinstance(body, dict) else body
        return cast(list[Json], items)


async def work_item(seed: Seeder, site: Site, by: uuid.UUID) -> uuid.UUID:
    """The engagement's assurance work item (an audit holds working papers)."""
    found = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
        site.engagement_id,
    )
    if found is not None:
        return cast(uuid.UUID, found)
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'assurance', 'Audit', $5) "
            "RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            by,
        ),
    )


async def name(seed: Seeder, who: Person, display: str) -> None:
    await seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, display)


async def books(net: Net) -> Books:
    seed = net.seed
    tenant_id = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant_id)
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-02-T20') ON CONFLICT DO NOTHING",
            tenant_id,
            flag,
        )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Northwind")
    people: dict[str, Person] = {}
    roles: tuple[tuple[Role, str], ...] = (
        ("engagement_partner", "Hannah Leclerc"),
        ("manager", "Paul Okafor"),
        ("senior", "Marcus Delaney"),
        ("staff", "Ivy Chen"),
        ("reviewer", "Rhea Patel"),
    )
    for role, display in roles:
        who = await seed.person(tenant_id)
        await name(seed, who, display)
        await seed.member(site, who, role)
        people[role] = who
    item = await work_item(seed, site, admin.user_id)
    by = people["senior"].user_id
    current = await snapshot(tenant_id, by, site.entity_id, EOY)
    prior = await snapshot(tenant_id, by, site.entity_id, BOY, start=PRIOR_START, end=PRIOR_END)
    await asyncio.sleep(0.01)  # the newer pull is later than the first
    newer = await snapshot(tenant_id, by, site.entity_id, NEWER)
    return Books(
        net,
        tenant_id,
        admin,
        people["engagement_partner"],
        people["manager"],
        people["senior"],
        people["staff"],
        people["reviewer"],
        site,
        item,
        current,
        prior,
        newer,
    )


async def stranger_firm(net: Net) -> Person:
    """A partner of another firm with its own open engagement and a team role on it."""
    tenant_id = await net.seed.firm()
    admin = await net.seed.person(tenant_id, "firm_admin")
    site = await net.seed.site(tenant_id, admin.user_id, "Elsewhere")
    who = await net.seed.person(tenant_id)
    await net.seed.member(site, who, "engagement_partner")
    return who


async def without_independence(seed: Seeder, site: Site, role: str = "senior") -> Person:
    """A team member whose independence confirmation is not on file."""
    who = await seed.person(site.tenant_id)
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        site.tenant_id,
        site.engagement_id,
        who.user_id,
        role,
    )
    return who
