"""Frozen contract snapshots (F-03-T18; docs/contracts/README.md, "The frozen-contract rule").

Run: python -m abacus_tools.contracts [--check | --freeze <contract> <version>]

Each frozen contract keeps `backend/tests/contracts/<contract>/<version>.json`: the OpenAPI
schemas of its models at the freeze. `--check` (in the contract tests) compares them with today's
schemas. Additions pass; a removed or retyped field, a field made required, or a removed enum
member fails, unless the same change ships the next version (a new snapshot) with overlap.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from abacus.api.export_openapi import document

BACKEND = Path(__file__).resolve().parents[2]
CONTRACTS = BACKEND / "tests" / "contracts"
# The models each contract freezes (its OpenAPI component schema names).
MODELS: dict[str, tuple[str, ...]] = {
    "c1_work_items": ("EngagementSummaryOut", "EngagementOut", "GateOut", "WorkItemOut"),
    "c2_status_registry": ("EngagementStatus", "RequestStatus"),
    # C16 v1 (P-01-T12): the notifications half's v2 feed and preferences, and the email half's
    # template import. The v1 list (`NotificationPageOut`) is SPEC-013's and not part of C16.
    "c16_notifications": (
        "NotificationFeedOut",
        "NotificationItemOut",
        "NotificationCountsOut",
        "NotificationActorOut",
        "ObjectRefOut",
        "NotificationPreferenceOut",
        "NotificationPreferencesOut",
        "NotificationPreferencesIn",
        "EmailTemplateImportIn",
        "EmailTemplateImportOut",
    ),
    # C5 v1 with v1.1 and v1.2, the binders and requests half (P-06-T27, DEC-409; frozen
    # 2026-10-27): c5-requests-binders.md §3 and the SHL-20 family's follow-ups and card (§12).
    # The portal half (portal-identity.md, portal-pbc.md) is P-08's and R-01's and not listed.
    "c5_requests_binders": (
        "BinderRowOut",
        "ListPage_BinderRowOut_",
        "BinderOut",
        "BinderIn",
        "UnpublishIn",
        "RecipientsIn",
        "FollowUpOverrideIn",
        "BinderRequestRowOut",
        "ListPage_BinderRequestRowOut_",
        "BinderLiveOut",
        "BinderClientPreviewOut",
        "ActivityEventOut",
        "ListPage_ActivityEventOut_",
        "RequestItemV2Out",
        "RequestItemPatchIn",
        "WaiveIn",
        "ReturnToClientIn",
        "DelegateIn",
        "DelegationOut",
        "RequestItemDeletedOut",
        "IgnoreIn",
        "IgnoredOut",
        "UploadIntentIn",
        "UploadIntentOut",
        "BinderMarkedDoneOut",
        "WithdrawalOut",
        "FollowUpOut",
        "FollowUpDraftsIn",
        "FollowUpDraftsOut",
        "FollowUpEditIn",
        "FollowUpSendManyIn",
        "ScreeningCardOut",
    ),
    # C5 v1.1, the portal half (`docs/contracts/portal-identity.md`; P-08-T28, DEC-456): `/v1/me`
    # portal and MFA fields, the sign-in, second-step and link-renewal family, the invitation
    # preview, the firm-side unlock and MFA reset, home, preferences and branding.
    "c5_portal": (
        "MePortalScopeOut",
        "MePortalOut",
        "MeMfaOut",
        "ContactPortalStatusOut",
        "ContactMfaResetOut",
        "PortalSignInStartIn",
        "PortalSignInStartOut",
        "PortalSignInVerifyIn",
        "PortalSignInVerifyOut",
        "PortalSignInResendIn",
        "PortalMfaIn",
        "PortalMfaSetupIn",
        "PortalMfaSetupOut",
        "PortalMfaSetupVerifyIn",
        "PortalMfaSetupVerifyOut",
        "PortalLinkRenewIn",
        "PortalLinkRenewOut",
        "InvitationPreviewIn",
        "InvitationAccessOut",
        "InvitationPreviewOut",
        "PortalHomeScopeOut",
        "PortalHomeTargetOut",
        "PortalHomeTodoOut",
        "PortalHomePillOut",
        "PortalHomeStageOut",
        "PortalHomeWorkCardOut",
        "PortalHomeBinderOut",
        "PortalHomeTeamMemberOut",
        "PortalHomeEarlierOut",
        "PortalHomeK1Out",
        "PortalHomeThreadOut",
        "PortalHomeNoticeOut",
        "PortalHomeOut",
        "PortalPreferencesIn",
        "PortalPreferencesOut",
        "PortalSignInPolicyOut",
        "PortalBrandingOut",
    ),
    # C6 v1, agent runs (Q-02-T45; ADR-169 §4; DEC-595, the owner change; frozen 2026-10-27):
    # the run list and view, trace, items, writes, records read, export and the run record.
    "c06_agent_runs": (
        "AgentRunOut",
        "TraceRowOut",
        "RecordsReadOut",
        "OutputCountOut",
        "RunTraceOut",
        "RunViewOut",
        "RunWriteOut",
        "RunItemOut",
        "RunItemsOut",
        "TraceExportIn",
        "TraceExportOut",
        "RecordRefOut",
        "CitationLocatorOut",
        "RecordCitationOut",
        "RecordInputHashesOut",
        "RecordOutcomeOut",
        "RunRecordOut",
    ),
    # C3 v1, the review grammar's services (P-04-T27, DEC-606; frozen 2026-10-27): every request
    # and response model of `review/contract.py` (parts 1 and 3, decision cards) and
    # `agents/contract.py` (proposals and suggestions), and the status enums they carry.
    # `ObjectRefOut` is C16's (`c16_notifications`), which C3 shares.
    "review_grammar": (
        "SignOffTargetOut",
        "SignOffOut",
        "LadderLevelOut",
        "SignOffLadderOut",
        "EligibilityCheckOut",
        "SignOffStatementOut",
        "SignOffEligibilityOut",
        "SignOffIn",
        "BulkSignOffTargetIn",
        "BulkSignOffIn",
        "BulkSignOffItemOut",
        "BulkSignOffOut",
        "NoteAnchorIn",
        "NoteAnchorOut",
        "ReviewNoteItemOut",
        "ReviewNoteEventOut",
        "ReviewNoteDetailOut",
        "RaiseReviewNoteIn",
        "ReviewNoteEventIn",
        "HumanGateOut",
        "DecisionContextOut",
        "DecisionOptionOut",
        "DecisionFactorOut",
        "DecisionRecommendationOut",
        "CardDecisionOut",
        "DecisionCardVersionOut",
        "DecisionCardItemOut",
        "DecisionCardOut",
        "CardDecideIn",
        "AnalysisRequestIn",
        "AnalysisRequestOut",
        "DecisionNotifyOut",
        "CitedSourceOut",
        "IssueLinkOut",
        "IssueLinkIn",
        "IssueItemOut",
        "IssueClientContactOut",
        "IssueFixSuggestionOut",
        "IssueFixInstructionsOut",
        "IssueFixRunOut",
        "IssueExplanationOut",
        "IssueEventOut",
        "IssueDetailOut",
        "IssueCreateIn",
        "IssueUpdateIn",
        "IssueResolutionIn",
        "IssueSendToClientIn",
        "FixInstructionsIn",
        "FixInstructionsAcceptedOut",
        "BulkFixIssueIn",
        "BulkFixInstructionsIn",
        "BulkFixItemOut",
        "BulkFixInstructionsOut",
        "ExplainAcceptedOut",
        "CheckpointDecisionOut",
        "CheckpointItemOut",
        "CheckpointHistoryOut",
        "CheckpointStepOut",
        "CheckpointDiffRowOut",
        "CheckpointTotalOut",
        "CheckpointDetailOut",
        "CheckpointCreateIn",
        "CheckpointApproveIn",
        "CheckpointRejectIn",
        "CheckpointRestoreIn",
        "CheckpointRenameIn",
        "FieldValueOut",
        "FieldValueIn",
        "FieldReferenceOut",
        "FieldVersionOut",
        "FieldTickOut",
        "FieldFlagOut",
        "FieldProvenanceOut",
        "FieldEditIn",
        "FieldReferenceIn",
        "FieldTickIn",
        "ProposalRowOut",
        "ProposalTotalOut",
        "ProposalEvidenceOut",
        "ProposalPolicyOut",
        "ProposalSetOut",
        "ProposalDecisionOut",
        "AgentProposalOut",
        "ProposalEditIn",
        "ApproveProposalIn",
        "RejectProposalIn",
        "RouteProposalIn",
        "FollowUpIn",
        "UndoProposalIn",
        "AgentSuggestionOut",
        "AdoptSuggestionIn",
        "DismissSuggestionIn",
        "ReviewNoteStatus",
        "DecisionCardStatus",
        "ProposalStatus",
        "SuggestionStatus",
        "IssueStatus",
        "IssueSeverityStatus",
        "CheckpointStatus",
    ),
}
Schema = dict[str, object]


def current(contract: str) -> dict[str, Schema]:
    schemas = cast(dict[str, Schema], json.loads(document())["components"]["schemas"])
    return {name: schemas[name] for name in MODELS[contract]}


def _shape(schema: Schema) -> str:
    """A field's type, ignoring titles and descriptions."""
    keep = {k: v for k, v in schema.items() if k not in ("title", "description", "default")}
    return json.dumps(keep, sort_keys=True)


def _field_breaks(where: str, before: Schema, after: Schema) -> list[str]:
    """A field's breaks. An inline enum follows the same rule as a named one (README, "The
    frozen-contract rule"; DEC-597): a member added is additive, a member removed breaks."""
    old_enum = cast(list[object] | None, before.get("enum"))
    new_enum = cast(list[object] | None, after.get("enum"))
    if old_enum is not None and new_enum is not None:
        rest_before = {k: v for k, v in before.items() if k != "enum"}
        rest_after = {k: v for k, v in after.items() if k != "enum"}
        if _shape(rest_before) == _shape(rest_after):
            return [f"{where}: enum member {m!r} removed" for m in old_enum if m not in new_enum]
    return [f"{where}: type changed"] if _shape(before) != _shape(after) else []


def breaking(frozen: dict[str, Schema], now: dict[str, Schema]) -> list[str]:
    """What today's schemas break of a frozen snapshot."""
    problems: list[str] = []
    for name, before in frozen.items():
        after = now.get(name)
        if after is None:
            problems.append(f"{name}: removed")
            continue
        old_enum = cast(list[object] | None, before.get("enum"))
        if old_enum is not None:
            new_enum = cast(list[object], after.get("enum") or [])
            problems += [
                f"{name}: enum member {m!r} removed" for m in old_enum if m not in new_enum
            ]
        old_props = cast(dict[str, Schema], before.get("properties") or {})
        new_props = cast(dict[str, Schema], after.get("properties") or {})
        for field, spec in old_props.items():
            if field not in new_props:
                problems.append(f"{name}.{field}: removed or renamed")
                continue
            problems += _field_breaks(f"{name}.{field}", spec, new_props[field])
        newly_required = set(cast(list[str], after.get("required") or [])) - set(
            cast(list[str], before.get("required") or [])
        )
        problems += [f"{name}.{f}: now required" for f in sorted(newly_required) if f in old_props]
    return problems


def snapshots() -> dict[str, list[Path]]:
    return {c: sorted((CONTRACTS / c).glob("v*.json")) for c in MODELS}


def check() -> list[str]:
    problems: list[str] = []
    for contract, paths in snapshots().items():
        now = current(contract)
        for path in paths:
            frozen = cast(dict[str, Schema], json.loads(path.read_text()))
            problems += [f"{contract} {path.stem}: {p}" for p in breaking(frozen, now)]
    return problems


def freeze(contract: str, version: str) -> Path:
    path = CONTRACTS / contract / f"{version}.json"
    if path.exists():
        raise SystemExit(
            f"{path} exists: a frozen version is never rewritten; freeze v{version}+1"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current(contract), indent=2, sort_keys=True) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contracts")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--freeze", nargs=2, metavar=("CONTRACT", "VERSION"))
    args = parser.parse_args(argv)
    if args.freeze:
        print(freeze(args.freeze[0], args.freeze[1]))
        return 0
    problems = check()
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
