"""The section drafter's three fieldwork modes (A-08-T23; A-08 §6; DEC-5310; red): their inputs,
built by code, behind `audits.fieldwork_agents`.

- `fieldwork_attribute`: an AUD-12 test's deviation log as facts (items tested, deviations, UDL).
- `flux_explain`: the paper's flux lines come as cells; drivers are read through
  `ledger.counterparty_activity` and proposed through `assurance.propose_explanation`.
- `confirmation_reconcile`: the work item's confirmations as facts (by status, books, responses);
  reconciling items are proposed through `assurance.propose_reconciliation`. Respondent text is
  untrusted (`respondent_text`).

Each mode writes suggestions only (the two propose tools); no tool reaches a reserved action.
With the flag off a mode's mapping answers 404 `feature_disabled` before any input is read.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import AUDITS_FIELDWORK_AGENTS
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.agents.api import (
    ModeInputs,
    register_mode_mapping,
    register_suggestion_target,
)
from abacus.modules.engagements.api import work_item_engagement
from abacus.modules.identity.api import AgentContext

MODES: Final = ("fieldwork_attribute", "flux_explain", "confirmation_reconcile")
_CONFIRMATIONS: Final = text(
    "SELECT status, count(*) FROM confirmations WHERE work_item_id = :w GROUP BY status"
)
_BOOKS: Final = text(
    "SELECT coalesce(sum(l.book_amount), 0) FROM confirmation_lines l JOIN confirmations c "
    "ON c.id = l.confirmation_id WHERE c.work_item_id = :w"
)


async def _on(agent: AgentContext) -> None:
    if not await flag_enabled(agent.tenant, AUDITS_FIELDWORK_AGENTS):
        raise NotFound(AUDITS_FIELDWORK_AGENTS.name)


def _fact(kind: str, value: object, basis: str) -> dict[str, object]:
    return {"kind": kind, "value": str(value), "basis": basis}


async def fieldwork_attribute_inputs(agent: AgentContext, paper: object) -> ModeInputs:
    await _on(agent)
    from abacus.modules.workpapers.api import deviation_counts

    deviations, logged = await deviation_counts(agent.tenant, paper.work_item_id)  # type: ignore[attr-defined] -- a SourcePaper
    return ModeInputs(
        facts=(
            ("deviations", _fact("count", deviations, "control_deviations, one per item")),
            ("logged", _fact("count", logged, "control_deviations rows")),
        )
    )


async def flux_explain_inputs(agent: AgentContext, paper: object) -> ModeInputs:
    await _on(agent)
    return ModeInputs()


async def confirmation_reconcile_inputs(agent: AgentContext, paper: object) -> ModeInputs:
    await _on(agent)
    work_item = paper.work_item_id  # type: ignore[attr-defined] -- a SourcePaper
    async with tenant_session(agent.tenant) as session:
        by_status = {
            str(s): int(n)
            for s, n in (await session.execute(_CONFIRMATIONS, {"w": work_item})).all()
        }
        books = Decimal(await session.scalar(_BOOKS, {"w": work_item}) or 0)
    facts = [("books_total", _fact("money", books, "confirmation_lines"))]
    facts += [
        (f"confirmations_{s}", _fact("count", n, "confirmations by status"))
        for s, n in sorted(by_status.items())
    ]
    return ModeInputs(facts=tuple(facts))


async def confirmation_engagement(tenant: TenantContext, confirmation_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT engagement_id FROM confirmations WHERE id = :c"), {"c": confirmation_id}
        )
    return found if isinstance(found, UUID) else None


async def mapping_set_engagement(tenant: TenantContext, mapping_set_id: UUID) -> UUID | None:
    from abacus.modules.ledger import api as ledger

    found = await ledger.mapping_set_by_id(tenant, mapping_set_id)
    return None if found is None else found.engagement_id


def register() -> None:
    register_suggestion_target("analytics_line", engagement_of=work_item_engagement)
    register_suggestion_target("confirmation", engagement_of=confirmation_engagement)
    # A-09-T29 (DEC-5409): ledger.tb_mapper's suggestions on a mapping set (AUD-31).
    register_suggestion_target("account_mapping", engagement_of=mapping_set_engagement)
    register_mode_mapping("fieldwork_attribute", fieldwork_attribute_inputs)
    register_mode_mapping("flux_explain", flux_explain_inputs)
    register_mode_mapping("confirmation_reconcile", confirmation_reconcile_inputs)
