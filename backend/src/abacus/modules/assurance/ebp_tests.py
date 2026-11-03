"""EBP tests on the shared attribute grid (A-05-T22; A-05 §3 F4; EBP-03, EBP-04 c, EBP-05;
DEC-2212). The grid itself is `workpapers`' (A-08 reuses it); this maps EBP's variants and
attribute sets onto it. Attribute sets are the test design (code), not firm content.
"""

from __future__ import annotations

from typing import Final, Literal, cast
from uuid import UUID

from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.modules.assurance.ebp_contract import (
    TestGridCellOut,
    TestGridRowOut,
    ResultIn,
    TestGridOut,
    TestIn,
)
from abacus.modules.engagements.api import assurance_item
from abacus.modules.identity.api import AuthContext
from abacus.modules.workpapers.api import Attribute, create_test, grid, work_item_papers
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
