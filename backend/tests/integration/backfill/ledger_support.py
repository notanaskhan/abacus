# ac-test-author: ayushkbhatia
"""Shared seeding for the Q-03-T023 and Q-03-T024 ledger back-fills (SPEC-028, SPEC-034): a firm
with the import flags on, an open engagement for FY2025 with a partner on its team, a small trial
balance typed here as literals, the evidence store on the compose S3 image, and the HTTP calls of
the "Export instead" path. The export files are written by the synthetic writers (the fixtures of
ADR-085), from the literal trial balance; every expected figure is typed from that literal.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast

import httpx
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus_tools.synthetic.model import TrialBalance, TrialBalanceLine

from .support import Net, Person, Seeder, Site

Json = dict[str, object]
YEAR_END: Final = date(2025, 12, 31)
YEAR_START: Final = date(2025, 1, 1)


def _line(code: str, name: str, debit: str = "0", credit: str = "0") -> TrialBalanceLine:
    return TrialBalanceLine(code, name, Decimal(debit), Decimal(credit))


# The trial balance every test imports: debits 170,840.00 = credits 170,840.00.
LINES: Final = (
    _line("1000", "Checking", debit="52340.00"),
    _line("1200", "Accounts Receivable", debit="18500.00"),
    _line("2000", "Accounts Payable", credit="9750.00"),
    _line("3000", "Retained Earnings", credit="41090.00"),
    _line("4000", "Revenue", credit="120000.00"),
    _line("5000", "Rent", debit="24000.00"),
    _line("6000", "Wages", debit="76000.00"),
)
TB: Final = TrialBalance(YEAR_END, LINES, "Seeded entity")
TOTAL: Final = Decimal("170840.00")
# Per account, (debit, credit) as the trial balance states them.
EXPECTED: Final = {
    "1000": (Decimal("52340.00"), Decimal(0)),
    "1200": (Decimal("18500.00"), Decimal(0)),
    "2000": (Decimal(0), Decimal("9750.00")),
    "3000": (Decimal(0), Decimal("41090.00")),
    "4000": (Decimal(0), Decimal("120000.00")),
    "5000": (Decimal("24000.00"), Decimal(0)),
    "6000": (Decimal("76000.00"), Decimal(0)),
}
# Row counts per table, as literal queries.
COUNTS: Final = {
    "gl_snapshots": "SELECT count(*) FROM gl_snapshots WHERE tenant_id = $1",
    "gl_account_balances": "SELECT count(*) FROM gl_account_balances WHERE tenant_id = $1",
    "gl_entries": "SELECT count(*) FROM gl_entries WHERE tenant_id = $1",
    "gl_imports": "SELECT count(*) FROM gl_imports WHERE tenant_id = $1",
    "ledger_snapshots": "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1",
    "trial_balance_lines": "SELECT count(*) FROM trial_balance_lines WHERE tenant_id = $1",
    "evidence_versions": "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1",
    "fulfilments": "SELECT count(*) FROM fulfilments WHERE tenant_id = $1",
}
# SPEC-028 Q1 and TASK-068: the five systems, by the name the formats route gives them.
SYSTEMS: Final = ("QuickBooks Online", "Xero", "QuickBooks Desktop", "NetSuite", "Sage Intacct")


def bucket(s3_settings: dict[str, str], name: str) -> S3Client:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=name, ObjectLockEnabledForBucket=True)
    return client


def wire_storage(client: S3Client, name: str, master: bytes) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(master))
    storage.configure_storage(client, name)
    yield
    storage.reset_storage()
    reset_key_service()


@dataclass(frozen=True)
class Ledger:
    """One firm, one open FY2025 engagement on the "Seeded entity", its partner, a manager and a
    staff member (staff hold neither `ledger_import.upload` nor `connection.read_log`)."""

    net: Net
    tenant_id: uuid.UUID
    admin: Person
    partner: Person
    manager: Person
    staff: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}/connection/import"

    async def format_id(self, system: str, *, gl: bool = False) -> str:
        path = f"{self.base}/gl/formats" if gl else f"{self.base}/formats"
        response = await self.net.call("GET", path, self.partner)
        assert response.status_code == 200, response.text
        found = [
            cast(str, f["id"])
            for f in cast(list[Json], response.json())
            if cast(str, f["system"]).lower() == system.lower()
        ]
        assert len(found) == 1, (system, response.json())
        return found[0]

    async def upload_tb(
        self, content: bytes, system: str, who: Person | None = None
    ) -> httpx.Response:
        return await self.net.http.post(
            self.base,
            params={"format": await self.format_id(system)},
            content=content,
            headers={
                **self.net.headers(who or self.partner),
                "Content-Type": "application/octet-stream",
            },
        )

    async def upload_gl(
        self, content: bytes, system: str, who: Person | None = None
    ) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/gl",
            params={"format": await self.format_id(system, gl=True)},
            content=content,
            headers={
                **self.net.headers(who or self.partner),
                "Content-Type": "application/octet-stream",
            },
        )

    async def latest_gl(self, who: Person | None = None) -> httpx.Response:
        return await self.net.call("GET", f"{self.base}/gl", who or self.partner)

    async def settled_gl(self, seconds: float = 60.0) -> Json:
        """The latest GL import once it has left `processing` (the background workflow)."""
        deadline = asyncio.get_running_loop().time() + seconds
        while True:
            response = await self.latest_gl()
            assert response.status_code == 200, response.text
            body = cast(Json | None, response.json())
            if body is not None and body["status"] != "processing":
                return body
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError(f"the GL import never settled: {body}")
            await asyncio.sleep(0.25)

    async def settled_gl_until(self, status: str, seconds: float = 60.0) -> Json:
        """The latest GL import once it reaches `status` (a waiting import is restarted)."""
        deadline = asyncio.get_running_loop().time() + seconds
        while True:
            body = await self.settled_gl(seconds)
            if body["status"] == status:
                return body
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError(f"the GL import never became {status}: {body}")
            await asyncio.sleep(0.25)

    async def snapshotted(self, seconds: float = 60.0) -> None:
        """Wait for the trial balance snapshot the import's retrieval records."""
        deadline = asyncio.get_running_loop().time() + seconds
        while await self.count("ledger_snapshots") == 0:
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError("no trial balance snapshot was recorded")
            await asyncio.sleep(0.25)

    async def fulfilled(self, *items: uuid.UUID, seconds: float = 60.0) -> None:
        """Rendering and fulfilment follow the snapshot: wait for every item's evidence link."""
        deadline = asyncio.get_running_loop().time() + seconds
        for item in items:
            while not await self.seed.value(
                "SELECT count(*) FROM fulfilments WHERE request_item_id = $1", item
            ):
                if asyncio.get_running_loop().time() > deadline:
                    raise AssertionError(f"item {item} was never fulfilled")
                await asyncio.sleep(0.25)

    async def count(self, table: str) -> int:
        return int(
            cast(
                int,
                await self.seed.value(COUNTS[table], self.tenant_id),
            )
        )

    async def requested(self, description: str) -> uuid.UUID:
        """A request item made through the firm's route, so classification runs (SPEC-022)."""
        response = await self.net.call(
            "POST",
            f"/v1/engagements/{self.site.engagement_id}/request-items",
            self.partner,
            body={"description": description, "audit_area": "Ledger"},
        )
        assert response.status_code == 201, response.text
        item = uuid.UUID(cast(str, response.json()["id"]))
        # Asked of the client (DEC-09 `requested`): fulfilment is for open items.
        await self.seed.run("UPDATE request_items SET status = 'requested' WHERE id = $1", item)
        return item

    async def item_status(self, item: uuid.UUID) -> str:
        return str(await self.seed.value("SELECT status FROM request_items WHERE id = $1", item))


async def ledger(
    net: Net, *, flags: tuple[str, ...] = ("ledger.import", "ledger.gl_import", "retrieval.auto")
) -> Ledger:
    seed = net.seed
    tenant_id = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant_id)
    for flag in flags:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'Q-03-T023')",
            tenant_id,
            flag,
        )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Ledger")
    await seed.run(
        "UPDATE client_entities SET name = 'Seeded entity' WHERE id = $1", site.entity_id
    )
    partner = await seed.person(tenant_id)
    manager = await seed.person(tenant_id)
    staff = await seed.person(tenant_id)
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, manager, "manager")
    await seed.member(site, staff, "staff")
    return Ledger(net, tenant_id, admin, partner, manager, staff, site)
