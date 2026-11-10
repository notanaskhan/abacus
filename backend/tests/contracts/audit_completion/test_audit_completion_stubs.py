# ac-test-author: ayushkbhatia
"""A-07-T06 (TASK-3253; SPEC-644 AC-6; DEC-2233): the consumer suite for A-07's two contract
stubs. Every AUD-18, AUD-19 and AUD-21 to AUD-25 operation exists with its one action and 404 and
501; every field is classified; clients hold nothing; the agent holds only reads and code runs;
every artboard field has a server source; and the refusal codes the screens word are catalogued.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel.classification import unclassified_fields
from abacus.modules.assurance import completion_contract as cc
from abacus.modules.assurance import completion_errors as ce
from abacus.modules.assurance import release_contract as rc
from abacus.modules.identity.authz import _matrix

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
CATALOGUE = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "error-codes.yaml"
A = "/v1/audits/{work_item_id}"
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party", "client_service")
AGENT_MAY = {
    "eqr.read", "eqr.build_digest", "completion.read", "rep_letter.read", "rep_letter.draft",
    "governance_comm.read", "governance_comm.draft", "report.read", "archive.read",
    "archive.build_index",
}  # fmt: skip

# Every artboard's numbers, words and clocks map to fields the server sends (A-07 §2.1).
SOURCES: dict[str, tuple[type[BaseModel], tuple[str, ...]]] = {
    "AUD-18 a 6 of 10 and the blocker sentence": (
        cc.EqrReviewOut,
        ("checklist_done", "checklist_total", "blockers", "notes", "allowed_actions"),
    ),
    "AUD-18 c Concurred · date · time · person": (
        cc.EqrConcurrenceOut,
        ("concurrence_date", "concurred_at", "concurred_by_name"),
    ),
    "AUD-18 digest card rows and citations": (
        cc.EqrDigestCardOut,
        ("rows", "citation_ids", "snapshot_sha256", "reviewed_at"),
    ),
    "AUD-18 e Not the EQR": (cc.EqrReviewOut, ("viewer_is_eqr", "eqr_name")),
    "AUD-19 a 12 of 17, N/A excluded": (
        cc.AuditCompletionOut,
        ("complete", "not_applicable", "open", "total", "blockers"),
    ),
    "AUD-19 gate tags and client dependence": (
        cc.AuditCompletionItemOut,
        ("gate_tag", "depends_on_client", "due_on", "link_target"),
    ),
    "AUD-19 b bring-down queued Oct 9": (cc.BringDownOut, ("scheduled_for", "status", "run_id")),
    "AUD-19 e DSCR 1.32x vs 1.25x": (cc.GoingConcernOut, ("inputs", "reserved_to", "conclusion")),
    "AUD-21 d G7 dated as of the report date": (
        rc.RepresentationLetterOut,
        ("dated_as_of", "report_date", "signed_on", "g7_met", "status"),
    ),
    "AUD-21 c viewed": (rc.RepLetterSignerOut, ("viewed_at", "signed_at", "identity")),
    "AUD-21 structure toggles": (
        rc.LetterRepresentationOut,
        ("locked", "included", "paragraph_no", "trigger_ref"),
    ),
    "AUD-22 due Dec 8 and Overdue": (
        rc.GovernanceRowOut,
        ("due_on", "overdue", "acknowledged_at"),
    ),
    "AUD-22 2 of 3 required sent": (rc.GovernanceListOut, ("required_sent", "required_total")),
    "AUD-23 approved by · time": (rc.ReportVersionOut, ("approved_by_name", "approved_at")),
    "AUD-23 j Out of date": (rc.GeneratedReportDocumentOut, ("out_of_date", "watermark")),
    "AUD-23 Request EQR": (rc.AuditReportOut, ("eqr_required_not_concurred",)),
    "AUD-24 gate cards with live values": (rc.GateCardOut, ("gate", "met", "value", "blockers")),
    "AUD-24 a, d and e": (
        rc.AuditReleaseOut,
        (
            "can_release",
            "viewer_can_release",
            "engagement_partner_name",
            "released_at",
            "documentation_completion_date",
            "gate_hash",
        ),
    ),
    "AUD-24 f Filed Oct 14": (rc.FilingOut, ("status", "filed_on", "ack_evidence_version_id")),
    "AUD-25 a Archive in 47 days, 8 of 9": (
        rc.AuditArchiveStateOut,
        ("days_left", "checklist_done", "checklist_total", "documentation_completion_date"),
    ),
    "AUD-25 c seal 7c41…a9e2 and G9": (
        rc.AuditArchiveStateOut,
        ("seal_sha256", "locked_at", "locked_by_name", "status"),
    ),
    "AUD-25 binder 26 workpapers, 24 source documents": (
        rc.BinderSectionOut,
        ("workpapers", "source_documents", "run_logs"),
    ),
    "AUD-25 d addition approved by MO": (
        rc.ArchiveAdditionOut,
        ("reason_code", "decision", "decided_by_name", "added_by_name"),
    ),
    "AUD-25 retention to Oct 9, 2033 and COMPLIANCE to Oct 9, 2031": (
        rc.ArchiveManifestOut,
        ("compliance_retain_until", "governance_retain_until", "manifest_sha256"),
    ),
}
REFUSALS = (
    "gates_not_met", "archived", "content_changed", "decision_required", "mfa_required",
    "checklist_incomplete", "approval_required", "date_mismatch", "seal_mismatch",
)  # fmt: skip


def _routes() -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for module in (cc, rc):
        for route in module.router.routes:
            for method in route.methods:
                out[(method.lower(), route.path)] = route.openapi_extra["x-abacus-action"]
    return out


ROUTES = _routes()


def test_both_stubs_carry_60_operations_under_the_audit_work_item() -> None:
    # 18 completion (A-07-T04) + 1 readiness check (A-07-T32, DEC-3109) + 41 release (A-07-T05)
    assert len(ROUTES) == 60
    assert all(path.startswith(A) for _, path in ROUTES)


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_each_route_declares_its_action_and_documents_404_and_501(method: str, path: str) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    assert {"404", "501"} <= set(cast(Json, operation["responses"]))


@pytest.mark.parametrize("module", [cc, rc], ids=["completion", "release"])
def test_every_field_is_classified(module: object) -> None:
    models = [
        v
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == module.__name__  # type: ignore[attr-defined] -- APIRoute carries methods and openapi_extra
    ]
    assert len(models) > 20
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


@pytest.mark.parametrize("action", sorted(set(ROUTES.values()) - {"envelope.remind"}))
def test_no_client_principal_holds_an_a07_action(action: str) -> None:
    decisions = _matrix.ACTIONS[action]
    for role in CLIENT_ROLES:
        assert decisions.get(role, "deny") == "deny", (action, role)


@pytest.mark.parametrize("action", sorted(set(ROUTES.values()) - {"envelope.remind"}))
def test_the_agent_holds_only_reads_and_code_runs(action: str) -> None:
    agent = _matrix.ACTIONS[action].get("agent", "deny")
    if action in AGENT_MAY:
        assert agent == "task_scope", action
    else:
        assert agent == "deny", action


@pytest.mark.parametrize("artboard", sorted(SOURCES))
def test_every_artboard_field_has_a_server_source(artboard: str) -> None:
    model, fields = SOURCES[artboard]
    missing = [f for f in fields if f not in model.model_fields]
    assert missing == [], (artboard, missing)


def test_the_refusal_codes_the_screens_word_are_catalogued() -> None:
    codes = set(yaml.safe_load(CATALOGUE.read_text())["codes"])
    assert set(REFUSALS) <= codes
    assert ce.EqrOnly.code == "eqr_only"
    assert ce.EpOnly.code == "ep_only"
