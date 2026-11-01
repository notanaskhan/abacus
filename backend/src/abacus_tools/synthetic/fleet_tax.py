"""Tax-surge content for the load profiles (Q-03-T132; chapter 10 section 10.11.3, the S21 row;
DEC-1675). `make seed-staging PROFILE=x25` loads it after each firm's audits.

Each firm gets 5 to 15 TY2025 returns (`5 + 7n mod 11` for firm n, so x25 spans the range), on
clients after its audit clients: four in five are Feld-shaped joint 1040s, one in five a
Ridgeline-shaped 1065 with four K-1 recipients. Per return, the steps the tax surge exercises:

- **Return**: a `tax_compliance` engagement, its `tax_return` work item and subtype row, a team
  (partner, manager, senior, staff) and an organizer binder. Engagement creation has no owning
  service (a draft-and-accept flow), so these are bootstrapped as the fleet's audits are (DEC-144).
- **Organizer** (1040s): the firm's organizer template, imported by its firm admin and published
  by its tax partner once per firm (`requests.api`), then attached to each binder by the return's
  manager, as a person attaches it on TAX-03.
- **Signing** (1040s): the engine's Form 8879 and NY TR-579-IT PDFs through the bridge
  (`tax.api.import_engine_file`, `pdfs`), the documents C7's 8879 draft reads; the draft and the
  send are the people's acts the load run times (`signing_surge`).
- **K-1** (1065s): each recipient's engine K-1 PDF, then the K-1 set (`k1_set`), which applies the
  draft packages TXP-12 releases.

Firm-level template rights come from a membership level (`firm_partner`), which the fleet's seats
lack: the slice gives each return team's partner and manager seats their level once. Every step is
skipped when its result already exists, so a second run writes nothing. Synthetic only: numbered
names, `.test` addresses, no real taxpayer data; amounts are made up and never footed by a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal
from uuid import UUID

import asyncpg

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.api import (
    attach_organizer,
    import_questionnaire_template,
    publish_questionnaire_template,
    questionnaire_templates,
)
from abacus.modules.tax.api import import_engine_file
from abacus_tools.flags import set_flag
from abacus_tools.synthetic.documents import positioned_pdf
from abacus_tools.synthetic.fleet import (
    HQ,
    LOADER,
    Counts,
    Firm,
    _step,  # pyright: ignore[reportPrivateUsage] -- the fleet's own write-once step
    client_ids,
    seat_user,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import tenant_rows, tenant_value
from abacus_tools.synthetic.scenarios.brightwater_hale.tax_content import (
    Box,
    K1Set,
    Recipient,
    organizer_csv,
)

TAX_YEAR: Final = 2025
PERIOD: Final = (date(2025, 1, 1), date(2025, 12, 31))
ORGANIZER: Final = "Load Tax Organizer"
RECIPIENTS: Final = 4
AUTHORIZATIONS: Final = ("form_8879", "tr_579_it")
# The tax rollout flags (T-01, T-02) on for every synthetic firm with tax content.
TAX_FLAGS: Final = ("tax.returns_v1", "tax.engine_bridge", "questionnaires.v1", "tax.k1_release")


def returns_per_firm(firm: Firm) -> int:
    """5 to 15 returns: firm 1 has 12, firm 2 has 8, ... (fixed per firm, nested by profile)."""
    return 5 + (firm.n * 7) % 11


@dataclass(frozen=True)
class TaxReturn:
    firm: Firm
    r: int

    @property
    def partnership(self) -> bool:
        return self.r % 5 == 4

    @property
    def form(self) -> str:
        return "1065" if self.partnership else "1040"

    @property
    def client(self) -> int:
        """Clients after the firm's audit clients, so a return never shares an audit's client."""
        return self.firm.shape.audits + self.r

    @property
    def engagement(self) -> UUID:
        return self.firm.id("tax-engagement", self.r)

    @property
    def work_item(self) -> UUID:
        return self.firm.id("tax-return", self.r)

    @property
    def binder(self) -> UUID:
        return self.firm.id("tax-binder", self.r)

    @property
    def team(self) -> tuple[tuple[int, str], ...]:
        return self.firm.team(self.firm.shape.audits + self.r)

    @property
    def engine_id(self) -> str:
        """The engine's return id part (`[A-Za-z0-9]{1,20}`): `LoadF001R03`."""
        return f"LoadF{self.firm.n:03d}R{self.r:02d}"

    @property
    def code(self) -> str:
        return "2025P" if self.partnership else "2025I"

    @property
    def name(self) -> str:
        return f"{TAX_YEAR} Form {self.form} (Load {self.r + 1:02d})"


def returns_of(firm: Firm) -> tuple[TaxReturn, ...]:
    return tuple(TaxReturn(firm, r) for r in range(returns_per_firm(firm)))


def staff_context(
    firm: Firm, seat: int, firm_role: Literal["firm_admin"] | None = None
) -> AuthContext:
    """A seat signed in with a second factor just verified (`authorise` reads it on the system
    clock), as the scenario loader's `_staff_context` does."""
    user = seat_user(firm, seat)
    return AuthContext(
        TenantContext(firm.tenant, "human", str(user)), user, UUID(int=0), firm_role, system_now()
    )


def engine_pdf(ret: TaxReturn, title: str) -> bytes:
    lines = [title, f"Tax year {TAX_YEAR}", ret.name, f"Load Client {ret.client + 1:03d}"]
    return positioned_pdf([[(50.0, 740.0 - 14 * i, line) for i, line in enumerate(lines)]])


def k1_set(ret: TaxReturn) -> K1Set:
    """A Ridgeline-shaped draft set: four recipients, made-up amounts the engine would carry."""
    recipients = tuple(
        Recipient(
            ref=f"P{p + 1:02d}",
            name=f"Load Partner {p + 1} ({ret.engine_id})",
            kind="gp" if p == 0 else "lp",
            is_entity=p % 2 == 1,
            contact=f"Load Partner {p + 1}",
            tin_last4=f"{(ret.firm.n * 31 + ret.r * 7 + p) % 10000:04d}",
            tin_kind="ein" if p % 2 == 1 else "ssn",
            states=("IL",),
            boxes=(
                Box("1", "Ordinary business income (loss)", f"{12000 + 1000 * p}.00"),
                Box("19A", "Distributions", f"{4000 + 500 * p}.00"),
            ),
        )
        for p in range(RECIPIENTS)
    )
    return K1Set(
        client=f"Load Client {ret.client + 1:03d}",
        form="1065",
        engine_return_id=f"{ret.code}:{ret.engine_id}",
        version=1,
        is_final=False,
        imported_at=system_now(),
        recipients=recipients,
    )


async def _levels(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> None:
    """Each team's partner seat `partner` and manager seat `manager`, where no level is set."""
    for ret in returns_of(firm):
        for seat, role in ret.team[:2]:
            level = "partner" if role == "engagement_partner" else "manager"

            async def level_row(seat: int = seat, level: str = level) -> tuple[str, str, str]:
                await conn.execute(
                    "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2 "
                    "AND level IS NULL",
                    firm.tenant,
                    seat_user(firm, seat),
                    level,
                )
                return "membership.updated", "user", str(seat_user(firm, seat))

            await _step(conn, firm, f"tax-level:{seat}", LOADER, level_row, counts)


async def _return(conn: asyncpg.Connection, ret: TaxReturn, counts: Counts) -> None:
    firm = ret.firm
    client = client_ids(firm, ret.client)
    partner = seat_user(firm, ret.team[0][0])

    async def return_rows() -> tuple[str, str, str]:
        await conn.execute(
            "INSERT INTO engagements (id, tenant_id, client_id, client_entity_id, name, type, "
            "fiscal_period_start, fiscal_period_end, status, created_by, created_at, office_id) "
            "VALUES ($1, $2, $3, $4, $5, 'tax_compliance', $6, $7, 'active', $8, now(), $9) "
            "ON CONFLICT DO NOTHING",
            ret.engagement,
            firm.tenant,
            client.client_id,
            client.client_entity_id,
            f"TY{TAX_YEAR} Form {ret.form} (Load {ret.r + 1:02d})",
            PERIOD[0],
            PERIOD[1],
            partner,
            firm.id("office", HQ),
        )
        await conn.execute(
            "INSERT INTO work_items (id, tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, period_start, period_end, office_id, created_by) VALUES ($1, $2, $3, "
            "$4, $5, 'tax_return', $6, $7, $8, $9, $10) ON CONFLICT DO NOTHING",
            ret.work_item,
            firm.tenant,
            ret.engagement,
            client.client_id,
            client.client_entity_id,
            ret.name,
            PERIOD[0],
            PERIOD[1],
            firm.id("office", HQ),
            partner,
        )
        await conn.execute(
            "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
            "form, tax_year) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
            firm.tenant,
            ret.work_item,
            ret.engagement,
            client.client_entity_id,
            ret.form,
            TAX_YEAR,
        )
        for seat, role in ret.team:
            await conn.execute(
                "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                firm.tenant,
                ret.engagement,
                seat_user(firm, seat),
                role,
            )
        await conn.execute(
            "INSERT INTO request_lists (id, tenant_id, engagement_id, work_item_id, name, kind, "
            "status, created_at) VALUES ($1, $2, $3, $4, $5, 'organizer', 'draft', now()) "
            "ON CONFLICT DO NOTHING",
            ret.binder,
            firm.tenant,
            ret.engagement,
            ret.work_item,
            f"{TAX_YEAR} Binder (Load {ret.r + 1:02d})",
        )
        return "engagement.created", "engagement", str(ret.engagement)

    await _step(conn, firm, f"tax-return:{ret.r}", str(partner), return_rows, counts)


async def _organizer_version(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> UUID:
    """The firm's published organizer: imported by the firm admin, published by a tax partner."""
    partner_seat = returns_of(firm)[0].team[0][0]
    publisher = staff_context(firm, partner_seat)
    found = [t for t in await questionnaire_templates(publisher) if t.name == ORGANIZER]
    if not found:
        admin = staff_context(firm, 0, "firm_admin")
        await import_questionnaire_template(
            admin, ORGANIZER, organizer_csv(), "csv", dry_run=False
        )
        counts.written += 1
        found = [t for t in await questionnaire_templates(publisher) if t.name == ORGANIZER]
    template = found[0]
    if template.current_version_id is None:
        version = int(template.draft_version or 1)
        await publish_questionnaire_template(publisher, template.id, version)
        counts.written += 1
        template = next(t for t in await questionnaire_templates(publisher) if t.name == ORGANIZER)
    else:
        counts.skipped += 1
    if template.current_version_id is None:
        raise LookupError(f"{firm.name}: the organizer did not publish")
    return template.current_version_id


async def _organizer(
    conn: asyncpg.Connection, ret: TaxReturn, version: UUID, counts: Counts
) -> None:
    attached = await tenant_value(
        conn,
        ret.firm.tenant,
        "SELECT EXISTS (SELECT 1 FROM questionnaires WHERE tenant_id = $1 "
        "AND request_list_id = $2 AND kind = 'organizer')",
        ret.firm.tenant,
        ret.binder,
    )
    if attached:
        counts.skipped += 1
        return
    manager = staff_context(ret.firm, ret.team[1][0])
    await attach_organizer(manager, ret.binder, version, None)
    counts.written += 1


async def _imported_pdfs(conn: asyncpg.Connection, ret: TaxReturn) -> set[str]:
    rows = await tenant_rows(
        conn,
        ret.firm.tenant,
        "SELECT summary ->> 'pdf_kind' AS kind FROM engine_sync_events "
        "WHERE tenant_id = $1 AND return_id = $2 AND kind = 'pdfs'",
        ret.firm.tenant,
        ret.work_item,
    )
    return {str(r["kind"]) for r in rows}


async def _authorizations(conn: asyncpg.Connection, ret: TaxReturn, counts: Counts) -> None:
    """The 8879 family's PDFs through the bridge, a preparer's upload (the senior's)."""
    have = await _imported_pdfs(conn, ret)
    senior = staff_context(ret.firm, ret.team[2][0])
    for kind in AUTHORIZATIONS:
        if kind in have:
            counts.skipped += 1
            continue
        name = f"{ret.code}_{ret.engine_id}_V1_{kind}.pdf"
        title = "Form 8879" if kind == "form_8879" else "NY TR-579-IT"
        await import_engine_file(senior, ret.work_item, "pdfs", name, engine_pdf(ret, title))
        counts.written += 1


async def _k1s(conn: asyncpg.Connection, ret: TaxReturn, counts: Counts) -> None:
    """Each recipient's engine K-1 PDF, then the set (draft packages), by the return's manager."""
    packages = await tenant_value(
        conn,
        ret.firm.tenant,
        "SELECT count(*) FROM k1_packages WHERE tenant_id = $1 AND work_item_id = $2",
        ret.firm.tenant,
        ret.work_item,
    )
    if packages:
        counts.skipped += 1
        return
    manager = staff_context(ret.firm, ret.team[1][0])
    found = k1_set(ret)
    for recipient in found.recipients:
        await import_engine_file(
            manager,
            ret.work_item,
            "pdfs",
            found.pdf_name(recipient),
            engine_pdf(ret, f"Schedule K-1 (Form 1065) {TAX_YEAR} · {recipient.name}"),
        )
    name = f"{found.engine_return_id.replace(':', '_')}_k1_set.json"
    await import_engine_file(manager, ret.work_item, "k1_set", name, found.manifest())
    counts.written += 1


async def _flags(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> None:
    on = {
        str(r["flag"])
        for r in await tenant_rows(
            conn,
            firm.tenant,
            "SELECT flag FROM feature_flag_states WHERE tenant_id = $1 AND value = 'true'",
            firm.tenant,
        )
    }
    for name in TAX_FLAGS:
        if name in on:
            counts.skipped += 1
            continue
        await set_flag(firm.tenant, name, "true", LOADER, "tax-surge profile (Q-03-T132)")
        counts.written += 1


async def load_tax(conn: asyncpg.Connection, firm: Firm, counts: Counts) -> None:
    """One firm's tax-surge content, after its seats, clients and audits."""
    await _levels(conn, firm, counts)
    for ret in returns_of(firm):
        await _return(conn, ret, counts)
    version = await _organizer_version(conn, firm, counts)
    for ret in returns_of(firm):
        if ret.partnership:
            await _k1s(conn, ret, counts)
        else:
            await _organizer(conn, ret, version, counts)
            await _authorizations(conn, ret, counts)
    await _flags(conn, firm, counts)
