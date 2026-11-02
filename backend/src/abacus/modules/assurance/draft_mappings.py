"""The planning modes' mappings for the section drafter (A-04-T22-T24; A-04 §6; DEC-2058).

A mapping adds to the context code builds for one mode: the documents the section is drafted from
(as the masked page text agents read, P-03-T15) and what it still waits for from the client.
Each is registered with `agents.api.register_mode_mapping` and reads as the run's agent, through
its task scope.

- **gap** (General Audit Planning, Service Organizations; AUD-04): the request items in the
  `service_organizations` area. An item with evidence is a document (a SOC 1 report, a bridge
  letter); an item still requested is a waiting input ("2 waiting inputs"), never guessed at.
- **risk_narrative** (Risk Assessment, AUD-05): every fulfilled request on the engagement (the
  plan document, the SPD, the trust report, the SOC 1, ...), so Menu 1 and Menu 2 cite across them;
  the presumed fraud risks are code's (`risks.prepopulate_presumed`, the mode's preparer).
- **risk** (the register, AUD-08): the register as its own grid on the `risk` sheet, one row per
  risk (row n + 1 for Rn): B rationale, C assertions, D inherent risk, E control risk, each landing
  on that risk's field through the `risk` applier; and code's coverage facts (risks, significant,
  unaddressed codes), so "Identify risks" cites numbers by reference only.
"""

from __future__ import annotations

from typing import Final

from abacus.modules.agents.api import (
    ModeDocument,
    ModeInputs,
    ModePage,
    ModeTarget,
    SourceCell,
    SourcePaper,
)
from abacus.modules.assurance import risks
from abacus.modules.evidence.api import review_material
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.api import request_items_for

SERVICE_ORG_AREA: Final = "service_organizations"
# A request with evidence is a document; one in these statuses is still waited for.
_WAITING: Final = frozenset({"draft", "requested", "returned"})


async def _documents_and_waits(
    actor: AuthContext, paper: SourcePaper, areas: frozenset[str]
) -> ModeInputs:
    items = [
        i for i in await request_items_for(actor, paper.engagement_id) if i.audit_area in areas
    ]
    documents: list[ModeDocument] = []
    waiting: list[str] = []
    for item in sorted(items, key=lambda i: i.created_at):
        if item.evidence_version_id is None:
            if item.status in _WAITING:
                waiting.append(item.description)
            continue
        material = await review_material(actor.tenant, item.evidence_version_id, sheets=False)
        if material is None or not material.pages:
            continue  # not scanned yet: nothing for an agent (fail closed)
        documents.append(
            ModeDocument(
                item.evidence_version_id,
                item.description,
                tuple(ModePage(n, text) for n, text in sorted(material.pages.items())),
            )
        )
    return ModeInputs(tuple(documents), tuple(waiting))


async def gap_inputs(actor: AuthContext, paper: SourcePaper) -> ModeInputs:
    """AUD-04's Service Organizations section: SOC reports and bridge letters, and the requests
    still open for them."""
    return await _documents_and_waits(actor, paper, frozenset({SERVICE_ORG_AREA}))


async def risk_narrative_inputs(actor: AuthContext, paper: SourcePaper) -> ModeInputs:
    """AUD-05's narrative: the documents the client provided, in the order requested."""
    items = [
        i for i in await request_items_for(actor, paper.engagement_id) if i.evidence_version_id
    ]
    areas = frozenset(i.audit_area for i in items)
    found = await _documents_and_waits(actor, paper, areas)
    return ModeInputs(found.documents, ())


# The register's grid on the `risk` sheet: column -> the risk's field.
RISK_SHEET: Final = "risk"
RISK_COLUMNS: Final = (
    ("B", "rationale"),
    ("C", "assertions"),
    ("D", "inherent_risk"),
    ("E", "control_risk"),
)


def _text(value: object) -> dict[str, object] | None:
    if value is None or value == "" or value == []:
        return None
    shown = ",".join(str(v) for v in value) if isinstance(value, list) else str(value)
    return {"t": "text", "v": shown}


async def risk_inputs(actor: AuthContext, paper: SourcePaper) -> ModeInputs:
    """AUD-08's register: each risk's fields as cells that land on the risk, and the coverage
    facts by code (AC4.6, AC4.7)."""
    rows = sorted(await risks.rows_of(actor.tenant, paper.work_item_id), key=lambda r: r.code)
    cells: list[SourceCell] = []
    targets: dict[str, ModeTarget] = {}
    for row in rows:
        line = int(row.code[1:]) + 1
        for column, field_key in RISK_COLUMNS:
            key = f"{column}{line}"
            cells.append(
                SourceCell(
                    RISK_SHEET, key, f"{row.code} {row.area_label}", field_key,
                    _text(getattr(row, field_key)),
                )
            )  # fmt: skip
            targets[f"{RISK_SHEET}!{key}"] = ModeTarget(risks.TARGET, row.id, field_key)
    linked = frozenset(await risks.linked_ids(actor.tenant, paper.work_item_id))
    tally = risks.tally(rows, linked)
    unaddressed = [r.code for r in rows if r.id not in linked]
    facts: list[tuple[str, dict[str, object]]] = [
        ("risks_total", {"t": "decimal", "v": str(tally.risks)}),
        ("risks_significant", {"t": "decimal", "v": str(tally.significant)}),
        ("risks_high_rmm", {"t": "decimal", "v": str(tally.high_rmm)}),
        ("risks_unaddressed", {"t": "text", "v": ", ".join(unaddressed)}),
    ]
    return ModeInputs(cells=tuple(cells), targets=targets, facts=tuple(facts))
