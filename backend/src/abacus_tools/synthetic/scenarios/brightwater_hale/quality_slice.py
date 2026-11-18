"""The Brightwater Hale quality and records slice (Q-05-T04; TASK-8613; Q-05 §5.3; SPEC-711 AC-34):
the SQMS No. 1 dashboard at E0 (Mon Sep 14, 2026, 9:24 AM CT), the override projection by agent
and for Denver, draft-vs-final accuracy, PI-01 at Mon Jan 25, 2027, and destruction batch
2026-Q3 with its `fil02e` variant. Typed by the Q-05 contract models so a contract change fails
here. Every name and figure is the ADM-11, AUD-30 and FIL-02 handoffs'. Rates and differences
are computed here by code from the counts (ADR-050), never typed. No database code: the
service-API load (`make seed-demo`) follows each service task.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from abacus.modules.assurance.api import post_issuance_contract as _pi
from abacus.modules.evidence.api import records_governance_contract as _rg
from abacus.modules.practice.api import quality_contract as _qm

D = Decimal
E0: Final = date(2026, 9, 14)
EVALUATION_AS_OF: Final = date(2026, 12, 15)
TOLERANCE_PCT: Final = D("8.0")
_NS: Final = uuid.UUID("5f0c0500-0000-4000-8000-0000000e0500")

# ADM-11 a, c (handoff spec rows): agent, outputs, overrides; Denver's subset (ADM-11 b).
AGENTS: Final = (
    ("ebp_audit_workpapers", "EBP Audit Workpapers", 412, 37, 96, 8),
    ("k1_reconciliation_workpaper", "K-1 Reconciliation Workpaper", 318, 29, 74, 6),
    ("missing_document_chaser", "Missing Document Chaser", 880, 61, 290, 19),
    ("return_review_packet", "Return Review Packet", 1260, 63, 418, 21),
    ("bank_reconciliation", "Bank Reconciliation", 540, 16, 250, 7),
)
# ADM-12 a: the two agent-monitoring findings the nightly job raised (system actor).
AGENT_FINDINGS: Final = {
    "ebp_audit_workpapers": "QM-F-04",
    "k1_reconciliation_workpaper": "QM-F-05",
}
# ADM-11 c: EBP Audit Workpapers' 37 overrides by reason.
EBP_REASONS: Final = (("wrong_value", 21), ("missing_citation", 9), ("wrong_classification", 7))
FIELDS: Final = 41260
FIELDS_CHANGED: Final = 1320
RETURNS_FILED: Final = 145


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


def rate(part: int, whole: int) -> Decimal | None:
    """A percentage to one place, half up, from exact counts; None below one output."""
    if whole == 0:
        return None
    return (D(part) * 100 / D(whole)).quantize(D("0.1"), rounding=ROUND_HALF_UP)


def agent_rows(*, denver: bool = False) -> list[_qm.QualityAgentRowOut]:
    rows: list[_qm.QualityAgentRowOut] = []
    for key, label, outputs, overrides, den_out, den_over in AGENTS:
        n, k = (den_out, den_over) if denver else (outputs, overrides)
        r = rate(k, n)
        rows.append(
            _qm.QualityAgentRowOut(
                agent_key=key,
                label=label,
                outputs=n,
                overrides=k,
                rate=r,
                rated=n >= 25,
                above_tolerance=r is not None and r > TOLERANCE_PCT,
                finding_ref=None if denver else AGENT_FINDINGS.get(key),
            )
        )
    return rows


def overrides(*, denver: bool = False) -> _qm.QualityOverridesOut:
    rows = agent_rows(denver=denver)
    outputs = sum(r.outputs for r in rows)
    over = sum(r.overrides for r in rows)
    return _qm.QualityOverridesOut(
        window_days=30,
        tolerance_pct=TOLERANCE_PCT,
        sample_n=25,
        outputs=outputs,
        overrides=over,
        rate=rate(over, outputs),
        unrated=sum(1 for r in rows if not r.rated),
        rows=rows,
    )


def accuracy() -> _qm.QualityAccuracyOut:
    """ADM-11 f: 1 - 1,320 / 41,260 = 96.8% over 145 filed TY2025 returns."""
    return _qm.QualityAccuracyOut(
        returns_filed=RETURNS_FILED,
        fields=FIELDS,
        changed=FIELDS_CHANGED,
        accuracy=rate(FIELDS - FIELDS_CHANGED, FIELDS),
    )


def tiles() -> _qm.QualityTilesOut:
    """ADM-11 a: 2 of 24 · 5 · 6.0% (206 of 3,410) · 96.8% · 2 · 92 days."""
    o = overrides()
    return _qm.QualityTilesOut(
        objectives_at_risk=2,
        objectives=24,
        findings_open=3 + 2,  # inspection findings + agent-monitoring findings (QM-F-04, F-05)
        override_rate=o.rate,
        overrides=o.overrides,
        outputs=o.outputs,
        tolerance_pct=TOLERANCE_PCT,
        accuracy=accuracy().accuracy,
        consultations_open=2,
        days_to_evaluation=(EVALUATION_AS_OF - E0).days,
    )


def register() -> tuple[int, int, int]:
    """24 objectives, 38 risks, 58 responses (the imported register)."""
    return (24, 38, 58)


# AUD-30 a (handoff spec): PI-01, the Harborline corrected 2025 certification.
PI01_LINES: Final = (
    ("stable_value_fund", "Harborline Stable Value Fund", D("1163480"), D("1151230")),
    ("total_investments", "Total investments at fair value", D("16500000"), D("16487750")),
    ("net_assets", "Net assets available for benefits", D("16861000"), D("16848750")),
)
CLEARLY_TRIVIAL: Final = D("12610")
OVERALL_MATERIALITY: Final = D("252200")


def pi01() -> _pi.PostIssuanceCaseOut:
    lines = [
        _pi.PostIssuanceComparisonLineOut(
            line_key=key, label=label, as_certified=a, as_corrected=b, difference=b - a
        )
        for key, label, a, b in PI01_LINES
    ]
    diff = lines[0].difference
    return _pi.PostIssuanceCaseOut(
        case_id=_id("PI-01"),
        ref="PI-01",
        type="subsequently_discovered_facts",
        standard="au_c_560",
        source_kind="inbox_evidence",
        received_at=datetime(2027, 1, 19, 15, 24, tzinfo=UTC),
        description="Harborline issued a corrected 2025 certification for the Stable Value Fund",
        status="under_evaluation",
        comparison=lines,
        evaluation=_pi.PostIssuanceEvaluationOut(
            total_difference=diff,
            clearly_trivial=CLEARLY_TRIVIAL,
            overall_materiality=OVERALL_MATERIALITY,
            share_pct=(abs(diff) * 100 / OVERALL_MATERIALITY).quantize(
                D("0.1"), rounding=ROUND_HALF_UP
            ),
            materiality_version_id=_id("northwind-materiality-final"),
            below_clearly_trivial=abs(diff) < CLEARLY_TRIVIAL,
        ),
    )


# FIL-02 c, e, i (handoff spec): batch 2026-Q3; 3 documents held in the fil02e variant.
BATCH_DOCUMENTS: Final = 1204
BATCH_CLIENTS: Final = 31
FIL02E_HELD: Final = 3


def batch_2026_q3(*, fil02e: bool = False) -> _rg.RecordsBatchOut:
    held = FIL02E_HELD if fil02e else 0
    return _rg.RecordsBatchOut(
        batch_id=_id("batch-2026-Q3"),
        ref="2026-Q3",
        scope_description="TY2018 tax files of 31 former clients",
        status="awaiting_approval",
        assembled_at=datetime(2026, 9, 1, 13, 0, tzinfo=UTC),
        eligible_count=BATCH_DOCUMENTS,
        held_excluded_count=held,
        destroyed_count=0,
        client_count=BATCH_CLIENTS,
        approvals=[
            _rg.RecordsApprovalOut(
                approver=_rg.RecordsPersonOut(user_id=_id("grace"), name="Grace Holloway"),
                approver_role="firm_admin",
                approved_at=datetime(2026, 9, 8, 15, 0, tzinfo=UTC),
            )
        ],
        confirmation_phrase="DESTROY 2026-Q3",
    )


def to_destroy(batch: _rg.RecordsBatchOut) -> int:
    """1,204 - 3 = 1,201 in the fil02e variant (AC-24)."""
    return batch.eligible_count - batch.held_excluded_count
