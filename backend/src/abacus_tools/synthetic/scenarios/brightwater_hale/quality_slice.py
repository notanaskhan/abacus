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


# AUD-30 a, d, e (Q-05-T24, DEC-5936): Northwind's two cases, PI-02's memo addition and PI-01's
# analysis, as the case, additions and analysis reads return them on Mon Jan 25, 2027.
NORTHWIND_AUDIT: Final = _id("northwind-audit")
RELEASED_AT: Final = datetime(2026, 10, 9, 21, 0, tzinfo=UTC)
ARCHIVE_LOCKED_AT: Final = datetime(2026, 12, 3, 22, 0, tzinfo=UTC)
PEOPLE: Final = {"HL": "Hannah Leclerc", "MO": "Margaret Okonkwo"}
PI01_SOURCE: Final = "Harborline Corrected Certification 2025.pdf"
PI01_ANALYSIS: Final = (
    "The corrected certification lowers the Stable Value Fund by $12,250. The amount is below "
    "clearly trivial ($12,610), and no note or supplemental-schedule total changes by more than "
    "that. The \u00a7103(a)(3)(C) opinion covers whether certified information agrees with the "
    "institution's certification; on the corrected figure the financial statements would differ "
    "by $12,250. I have not decided whether this needs action."
)
PI02_DESCRIPTION: Final = (
    "Report-date bring-down inquiry of the benefits committee was not documented\n"
    "The completion file has no documented inquiry of the benefits committee at the report date, "
    "Oct 9, 2026. The other report-date procedures are documented."
)
PI02_RATIONALE: Final = (
    "Alternative procedure: obtained benefits committee minutes of Oct 8, 2026; no events "
    "requiring adjustment or disclosure. The report remains supported."
)
PI02_MEMO: Final = "Memo \u2014 alternative procedure for the omitted bring-down inquiry"


def _sha(seed: str) -> str:
    """A fixture content hash with the handoff's visible ends (7c41\u2026e2a9)."""
    import hashlib

    return "7c41" + hashlib.sha256(seed.encode()).hexdigest()[4:60] + "e2a9"


def aud30_rows() -> dict[str, object]:
    """The case list (PI-01 under evaluation, PI-02 concluded), the additions and PI-01's
    analysis, JSON-ready (`scenario.aud30.json`)."""
    pi01_case = pi01().model_copy(
        update={
            "source_evidence_version_id": _id("pi01-source"),
            "source_name": PI01_SOURCE,
            "raised_by_name": PEOPLE["HL"],
            "opened_at": datetime(2027, 1, 20, 15, 10, tzinfo=UTC),
            "report_released_at": RELEASED_AT,
            "analysis_run_id": _id("run-4511"),
            "options": ["no_action", "revise_and_reissue", "notify_users"],
            "recommended_option": "no_action",
            "allowed_actions": [
                "post_issuance.analyse",
                "post_issuance.decide",
                "post_issuance.reissue",
            ],
        }
    )
    pi02_case = _pi.PostIssuanceCaseOut(
        case_id=_id("PI-02"),
        ref="PI-02",
        type="omitted_procedure",
        standard="au_c_585",
        source_kind="inspection_finding",
        received_at=datetime(2027, 1, 11, 15, 0, tzinfo=UTC),
        description=PI02_DESCRIPTION,
        status="concluded_no_action",
        options=["no_action", "revise_and_reissue"],
        decision="no_action",
        decided_by_user_id=_id("user:MO"),
        decided_at=datetime(2027, 1, 15, 16, 30, tzinfo=UTC),
        decided_by_name=PEOPLE["MO"],
        raised_by_name=PEOPLE["HL"],
        opened_at=datetime(2027, 1, 12, 15, 0, tzinfo=UTC),
        report_released_at=RELEASED_AT,
        rationale=PI02_RATIONALE,
        source_evidence_version_id=_id("pi02-memo"),
        allowed_actions=pi01_case.allowed_actions,
    )
    memo = {
        "id": str(_id("addition:PI-02")),
        "description": PI02_MEMO,
        "reason_code": "au_c_585_omitted_procedure",
        "evidence_version_id": str(_id("pi02-memo")),
        "content_sha256": _sha("addition:PI-02"),
        "added_by_name": PEOPLE["HL"],
        "added_at": "2027-01-15T16:00:00Z",
        "decision": "approved",
        "decided_by_name": PEOPLE["MO"],
        "decided_at": "2027-01-15T16:30:00Z",
        "post_issuance_case_id": str(_id("PI-02")),
    }
    return {
        "audit_id": str(NORTHWIND_AUDIT),
        "archive_locked_at": ARCHIVE_LOCKED_AT.isoformat().replace("+00:00", "Z"),
        "cases": [c.model_dump(mode="json") for c in (pi01_case, pi02_case)],
        "additions": [memo],
        "analysis": {
            "case_id": str(_id("PI-01")),
            "run_id": str(_id("run-4511")),
            "run_number": 4511,
            "blocks": {
                "version": 1,
                "parts": [{"kind": "p", "segments": [{"kind": "text", "text": PI01_ANALYSIS}]}],
            },
            "recommendation": "no_action",
            "citation_ids": [],
        },
        "next_addition_sha": _sha("addition:PI-01"),
    }


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
