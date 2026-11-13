"""EBP tests on the shared attribute grid (A-05-T22; A-05 §3 F4; EBP-03, EBP-04 c, EBP-05;
DEC-2212). The grid itself is `workpapers`' (A-08 reuses it); this maps EBP's variants and
attribute sets onto it. Attribute sets are the test design (code), not firm content.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import RowMapping, text

from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.numeric import quantize_half_up
from abacus.modules.assurance.compute.ebp.eligibility import (
    EntryRule,
    Escalation,
    Rates,
    entry,
    escalation_rate,
    missed,
)
from abacus.modules.assurance.ebp_contract import (
    ResultIn,
    TestGridCellOut,
    TestGridOut,
    TestGridRowOut,
    TestIn,
)
from abacus.modules.assurance.ebp_participants import binding
from abacus.modules.assurance.ebp_provisions import plan_reads
from abacus.modules.engagements.api import assurance_item, engagement_metadata
from abacus.modules.identity.api import AuthContext
from abacus.modules.workpapers.api import (
    Attribute,
    create_test,
    grid,
    latest_test_of_variant,
    work_item_papers,
)
from abacus.modules.workpapers.api import mark as mark_cell

_VARIANT: Final[dict[str, str]] = {
    "eligibility": "ebp_eligibility",
    "deferral": "ebp_contribution_recalc",
    "match": "ebp_contribution_recalc",
    "distribution": "ebp_distribution",
}
_PAPER: Final[dict[str, str]] = {
    "ebp_eligibility": "EBP-03",
    "ebp_contribution_recalc": "EBP-04",
    "ebp_distribution": "EBP-05",
}
ATTRIBUTES: Final[dict[str, tuple[Attribute, ...]]] = {
    "eligibility": (
        Attribute("hire_date", "Hire date agrees (census = HR)"),
        Attribute("entry_date", "Entry date per the plan's terms"),
        Attribute("deferral_rate", "Deferral rate per auto-enrollment and escalation"),
        Attribute("enrollment", "Enrolled or opted out (form on file)"),
    ),
    "deferral": (
        Attribute("compensation", "Plan compensation per the definition"),
        Attribute("deferral_amount", "Deferrals recalculated"),
    ),
    "match": (
        Attribute("compensation", "Plan compensation per the definition"),
        Attribute("match_amount", "Match recalculated (safe harbor formula)"),
    ),
    "distribution": (
        Attribute("eligibility", "Distribution event permitted"),
        Attribute("amount", "Amount agrees to the request and the trust"),
        Attribute("withholding", "Withholding and 1099-R"),
    ),
}


class NoWorkpaper(DomainConflict):
    """The work item has no paper for this test's variant yet."""

    code = "no_workpaper"


async def create(ctx: AuthContext, work_item_id: UUID, body: TestIn) -> UUID:
    variant = _VARIANT.get(body.variant)
    if variant is None:
        raise DomainInvalid(facts={"field": "variant"})
    item = await assurance_item(ctx.tenant, work_item_id)
    paper = body.workpaper_id
    if paper is None:
        code = _PAPER[variant]
        found = [p for p in await work_item_papers(ctx.tenant, work_item_id) if p.code == code]
        if not found:
            raise NoWorkpaper(facts={"code": code})
        paper = found[0].id
    return await create_test(
        ctx,
        engagement_id=item.engagement_id,
        work_item_id=work_item_id,
        workpaper_id=paper,
        variant=cast(
            Literal[
                "ebp_eligibility",
                "ebp_contribution_recalc",
                "ebp_distribution",
                "aud12_tod",
                "aud12_toc",
            ],
            variant,
        ),
        sample_set_id=body.sample_set_id,
        sample_version=body.sample_version,
        attributes=ATTRIBUTES[body.variant],
    )


async def grid_out(ctx: AuthContext, work_item_id: UUID, test_id: UUID) -> TestGridOut:
    item = await assurance_item(ctx.tenant, work_item_id)
    found = await grid(ctx, item.engagement_id, test_id)
    return TestGridOut(
        test_id=found.test_id,
        variant=found.variant,
        attributes=[a.key for a in found.attributes],
        rows=[
            TestGridRowOut(
                position=r.position,
                item_id=r.item_id,
                record_key=r.record_key,
                state=r.state,
                cells=[
                    TestGridCellOut(
                        attribute_key=c.attribute_key,
                        result=cast(
                            Literal[
                                "not_started",
                                "agent_tested",
                                "needs_human",
                                "pass",
                                "exception",
                                "no_effect",
                            ],
                            c.result,
                        ),
                        by=cast(Literal["human", "agent", "system", "policy"], c.actor_kind),
                        citation_ids=list(c.citation_ids),
                    )
                    for c in r.cells
                ],
            )
            for r in found.rows
        ],
        counts=dict(found.counts),
        version_no=found.version_no,
    )


async def mark(
    ctx: AuthContext,
    work_item_id: UUID,
    test_id: UUID,
    item_id: UUID,
    attribute: str,
    body: ResultIn,
) -> None:
    item = await assurance_item(ctx.tenant, work_item_id)
    await mark_cell(ctx, item.engagement_id, test_id, item_id, attribute, body.result, body.note)


async def _rule_of(
    ctx: AuthContext,
    person: RowMapping,
    plan_year: int,
    entry_rule: EntryRule,
    rates: Rates,
) -> Escalation:
    """The participant's rate this plan year under the verified rates, from their entry date under
    the verified entry rule (DEC-2361, DEC-2488). The date of birth opens here to place the entry
    and goes no further. Unknown either date: the verified default rate."""
    if person["dob_sealed"] is None or person["hire_on"] is None:
        return rates.escalation
    opened = await open_sealed(
        ctx.tenant_id,
        bytes(person["dob_sealed"]),
        binding(person["import_id"], person["participant_key"], "dob"),
    )
    entered = entry(date.fromisoformat(opened.decode()), person["hire_on"], entry_rule).entry_on
    return replace(
        rates.escalation, default_pct=escalation_rate(entered, plan_year, rates.escalation)
    )


async def contribution_recalc(ctx: AuthContext, work_item_id: UUID) -> TestGridOut:
    """EBP-04 c (A-05-T32; DEC-2356, DEC-2361): the shared grid with code's figures on each cell.
    `value` is what the participant's election gives on their compensation, and for the match what
    the census says was matched; `expected` is the plan's rule: the verified rates and entry rule
    from EBP-02 (`ebp_provisions.plan_reads`; DEC-2488), so with any of them unverified or unread
    no cell has an `expected`. Same record key in the newest EBP-03 grid links the row. The browser
    computes nothing."""
    latest = await latest_test_of_variant(ctx.tenant, work_item_id, "ebp_contribution_recalc")
    if latest is None:
        raise NotFound("attribute_test")
    out = await grid_out(ctx, work_item_id, latest[0])
    keys = [r.record_key for r in out.rows]
    item = await assurance_item(ctx.tenant, work_item_id)
    metadata = await engagement_metadata(ctx, item.engagement_id)
    plan_year = metadata.engagement.fiscal_period_end.year
    reads = await plan_reads(ctx.tenant, item.engagement_id, work_item_id)
    entry_rule, rates = reads.entry.rule, reads.rates.rates
    async with tenant_session(ctx.tenant) as session:
        people = {
            row["participant_key"]: row
            for row in (
                await session.execute(
                    text(
                        "SELECT p.participant_key, p.compensation, p.deferral_election_pct, "
                        "p.match_ytd, p.hire_on, p.dob_sealed, p.import_id "
                        "FROM ebp_participants p JOIN ebp_source_imports i ON i.id = p.import_id "
                        "WHERE i.work_item_id = :w AND p.participant_key = ANY(:k) "
                        "ORDER BY p.created_at"
                    ),
                    {"w": work_item_id, "k": keys},
                )
            ).mappings()
        }
    linked: dict[str, UUID] = {}
    eligibility = await latest_test_of_variant(ctx.tenant, work_item_id, "ebp_eligibility")
    if eligibility is not None:
        grid_rows = (await grid_out(ctx, work_item_id, eligibility[0])).rows
        linked = {r.record_key: r.item_id for r in grid_rows}
    rows: list[TestGridRowOut] = []
    for row in out.rows:
        person = people.get(row.record_key)
        comp = None if person is None else person["compensation"]
        if person is None or comp is None or entry_rule is None or rates is None:
            rows.append(row.model_copy(update={"linked_item_id": linked.get(row.record_key)}))
            continue
        compensation = Decimal(str(comp))
        rule = missed(
            compensation,
            await _rule_of(ctx, person, plan_year, entry_rule, rates),
            rates.match_pct,
        )
        elected = quantize_half_up(
            compensation * Decimal(str(person["deferral_election_pct"] or 0)) / Decimal(100), 2
        )
        cells = [
            c.model_copy(update={"value": elected, "expected": rule.deferral})
            if c.attribute_key == "deferral"
            else c.model_copy(update={"value": person["match_ytd"], "expected": rule.match})
            if c.attribute_key == "match"
            else c
            for c in row.cells
        ]
        rows.append(
            row.model_copy(update={"cells": cells, "linked_item_id": linked.get(row.record_key)})
        )
    return out.model_copy(update={"rows": rows})
