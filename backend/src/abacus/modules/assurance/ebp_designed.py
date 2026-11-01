"""A-05-T09: the nine EBP designed workpapers (A-05 §2.1, §4.1; SPEC-641; DEC-1954).

EBP-01 to EBP-09 are workpapers of A-04's cell store (`workpapers`, kinds admitted by 0641), each
with its firm program-step references, its Open-in-Excel layout and its seeded cell-address
anchors (`EBP-04!C14`, the Dec 26 business-day cell `EBP-04!F31`, `'EBP-04 Participant
data'!F12:F15`). This module registers, at import:

- a cockpit rail row per paper (`register_audit_section`): the paper's state by code for an EBP
  audit, no row for any other audit (fail closed);
- each paper's designed layout (`workpapers.api.register_designed_layout`), whose anchors must
  resolve to exactly the cells the export writes;
- the `ebp_workpapers` export section (the engagement export's list of the papers and their
  versions).

The papers' own content (cells, sign-offs, citations) goes through A-04's workpaper routes, the
`workpaper` reviewable and the `workpaper_cell` citable that workpapers registers; nothing here
writes.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from abacus.kernel._statuses import AuditSectionStatus
from abacus.kernel.db import TenantContext
from abacus.modules.agents.api import register_mode_plan
from abacus.modules.assurance.sections import (
    Band,
    SectionState,
    SectionStateProvider,
    register_audit_section,
)
from abacus.modules.engagements.api import assurance_item
from abacus.modules.evidence.api import SectionFile, SectionRequest, register_export_section
from abacus.modules.workpapers.api import (
    DesignedLayout,
    SheetLayout,
    register_designed_layout,
    work_item_papers,
)

EXPORT_SECTION: Final = "ebp_workpapers"


@dataclass(frozen=True)
class DesignedPaper:
    code: str  # "EBP-04"
    kind: str
    title: str
    band: Band
    order: int
    program_refs: tuple[str, ...]  # BH-EBP program or step keys ("BH-EBP-410:6")
    sheets: tuple[tuple[str, str], ...] = (("main", ""),)  # (sheet key, title; "" is the code)
    anchors: Mapping[str, str] = field(default_factory=dict[str, str])

    @property
    def section_key(self) -> str:
        return self.code.lower().replace("-", "_")

    def layout(self) -> DesignedLayout:
        return DesignedLayout(
            self.kind,
            self.code,
            tuple(SheetLayout(key, title or self.code) for key, title in self.sheets),
            dict(self.anchors),
        )


# Titles are the manifest's (A-05 §2.1); program references are the firm program's as the
# AUD-08 linkage and the plan name them, at the program level where no step is named.
DESIGNED: Final[tuple[DesignedPaper, ...]] = (
    DesignedPaper("EBP-01", "ebp_plan", "Plan profile & service providers", "planning", 410,
                  ("BH-EBP-110",)),
    DesignedPaper("EBP-02", "ebp_provisions", "Plan provisions review", "planning", 420,
                  ("BH-EBP-110",)),
    DesignedPaper("EBP-03", "ebp_eligibility", "Eligibility testing", "fieldwork", 410,
                  ("BH-EBP-210",)),
    DesignedPaper(
        "EBP-04",
        "ebp_contributions",
        "Contributions & remittance timeliness",
        "fieldwork",
        420,
        ("BH-EBP-410:2", "BH-EBP-410:3", "BH-EBP-410:4", "BH-EBP-410:6"),
        sheets=(("main", ""), ("participant_data", "EBP-04 Participant data")),
        anchors={
            "contributions_total": "EBP-04!C14",
            "dec_26_business_days": "EBP-04!F31",
            "participant_deferrals": "'EBP-04 Participant data'!F12:F15",
        },
    ),
    DesignedPaper("EBP-05", "ebp_distributions_loans", "Distributions & participant loans",
                  "fieldwork", 430, ("BH-EBP-310:6", "BH-EBP-410:8")),
    DesignedPaper("EBP-06", "ebp_investments", "Investments, certification & trust tie-out",
                  "fieldwork", 440, ("BH-EBP-310:1", "BH-EBP-310:2", "BH-EBP-310:3",
                                     "BH-EBP-310:4")),
    DesignedPaper("EBP-07", "ebp_form5500", "Form 5500 tie-out & supplemental schedules",
                  "fieldwork", 450, ()),
    DesignedPaper("EBP-08", "ebp_participant_accounts", "Participant accounts summary",
                  "fieldwork", 460, ("BH-EBP-310",)),
    DesignedPaper("EBP-09", "ebp_admin_expenses",
                  "Administrative expenses & operational compliance", "fieldwork", 470,
                  ("BH-EBP-410:9",)),
)  # fmt: skip
BY_KIND: Final = {p.kind: p for p in DESIGNED}


async def _is_ebp(tenant: TenantContext, work_item_id: UUID) -> bool:
    item = await assurance_item(tenant, work_item_id)
    return item.ebp_plan_kind is not None or item.assurance_type.startswith("ebp")


def _state_provider(paper: DesignedPaper) -> SectionStateProvider:
    async def state(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
        """The paper's rail state by code: no row outside an EBP audit; Not started until its
        first version; In progress after it (sign-off states come with the screens' services)."""
        if not await _is_ebp(tenant, work_item_id):
            return None
        found = next(
            (p for p in await work_item_papers(tenant, work_item_id) if p.kind == paper.kind),
            None,
        )
        if found is None or found.version_no == 0:
            return SectionState(AuditSectionStatus.NOT_STARTED, "idle_pill")
        return SectionState(
            AuditSectionStatus.IN_PROGRESS, "idle_pill", sub_line=f"v{found.version_no}"
        )

    state.__qualname__ = f"ebp_section_state.{paper.section_key}"
    return state


async def export_section(tenant: TenantContext, request: SectionRequest) -> Sequence[SectionFile]:
    """The engagement export's EBP section: each designed paper on the work item and its
    version (the papers' cells travel in their own workpaper exports)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(("code", "kind", "title", "version_no"))
    for paper in await work_item_papers(tenant, request.work_item_id):
        if paper.kind in BY_KIND:
            writer.writerow((paper.code, paper.kind, paper.title, paper.version_no))
    return [SectionFile("ebp_workpapers.csv", out.getvalue().encode("utf-8"))]


_PROVIDERS: dict[str, SectionStateProvider] = {}


def register() -> None:
    for paper in DESIGNED:
        register_designed_layout(paper.layout())
        provider = _PROVIDERS.setdefault(paper.section_key, _state_provider(paper))
        register_audit_section(
            paper.section_key,
            paper.band,
            paper.order,
            paper.code,
            provider,
            title=paper.title,
            link="planned",  # each screen's row goes live with its screen (A-05-T11 for EBP-01)
            required_action="workpaper.read",
        )
    register_export_section(EXPORT_SECTION, export_section)


# A-05-T12 (DEC-1956): the paper kinds each EBP section-draft mode drafts (A-05 §6's table);
# `related_parties` drafts AUD-27's records, which are not designed papers, so nothing yet.
MODE_PLANS: Final[dict[str, frozenset[str]]] = {
    "ebp_provisions": frozenset({"ebp_provisions"}),
    "ebp_attribute": frozenset({"ebp_eligibility", "ebp_distributions_loans"}),
    "ebp_reconcile": frozenset(
        {"ebp_contributions", "ebp_distributions_loans", "ebp_participant_accounts"}
        | {"ebp_admin_expenses"}
    ),
    "ebp_trust": frozenset({"ebp_investments"}),
    "ebp_form5500": frozenset({"ebp_form5500"}),
    "related_parties": frozenset(),
}


def register_modes() -> None:
    for mode, kinds in MODE_PLANS.items():
        register_mode_plan(mode, kinds)
