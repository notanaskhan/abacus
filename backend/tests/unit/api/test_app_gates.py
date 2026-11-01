"""AC-20: route introspection of the TASK-008 routes, the production walls gate and the new
exports (TASK-008 contract and revision 1)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, cast

import pytest
from fastapi.routing import APIRoute

import abacus.modules.engagements.api as engagements_api
import abacus.modules.identity.api as identity_api
import abacus.modules.requests.api as requests_api
from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.modules.identity.api import declared_action

EXPECTED = {
    ("POST", "/v1/engagements"): "engagement.create",
    ("GET", "/v1/engagements"): "engagement.read_metadata",
    ("GET", "/v1/engagements/{engagement_id}"): "engagement.read_metadata",
    ("POST", "/v1/engagements/{engagement_id}/request-items"): "request_item.create",
    ("GET", "/v1/engagements/{engagement_id}/request-items"): "request_item.read",
    ("POST", "/v1/walls"): "wall.create",
    ("POST", "/v1/walls/{wall_id}/remove"): "wall.remove",
    ("GET", "/v1/walls"): "wall.list",
}


class _RouteContext(Protocol):
    @property
    def original_route(self) -> object: ...


class _Included(Protocol):
    def effective_route_contexts(self) -> Iterable[_RouteContext]: ...


RETRIEVALS = "/v1/engagements/{engagement_id}/retrievals"
# SPEC-024 (TASK-042): "Screen now" starts work and answers 202, as retrievals do.
SCREEN_REQUEST = "/v1/engagements/{engagement_id}/screening-results/request"
# SPEC-030 (TASK-059): "Review now" starts a run and answers 202, as screening does.
REVIEW_REQUEST = "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/review"
MATCH_REQUEST = "/v1/engagements/{engagement_id}/inbox/{file_id}/match"  # SPEC-033: 202
DRAFTS = "/v1/engagements/{engagement_id}/request-items/draft-guidance"  # SPEC-035: 202
TEMPLATE_DRAFTS = "/v1/methodology/versions/{version_id}/draft-guidance"  # TASK-074: 202
SELECT = "/v1/engagements/{engagement_id}/procedures/{procedure_id}/select"  # TASK-083: 202
ASSESS = "/v1/engagements/{engagement_id}/procedures/{procedure_id}/assess"  # TASK-085: 202
GL_IMPORT = (
    "/v1/engagements/{engagement_id}/connection/import/gl"  # SPEC-034: 202, processed later
)


def _routes() -> list[APIRoute]:
    found: list[APIRoute] = []
    for item in create_app().routes:
        if isinstance(item, APIRoute):
            found.append(item)
        elif hasattr(item, "effective_route_contexts"):
            for context in cast(_Included, item).effective_route_contexts():
                assert isinstance(context.original_route, APIRoute)
                found.append(context.original_route)
    return found


def _methods(route: APIRoute) -> set[str]:
    return set(route.methods or ())


def test_ac20_the_five_engagement_routes_exist_with_their_actions() -> None:
    actual = {
        (method, route.path): declared_action(route)
        for route in _routes()
        for method in _methods(route)
    }
    for key, action in EXPECTED.items():
        assert actual.get(key) == action, key


def test_ac20_each_new_route_declares_exactly_one_action_and_a_response_model() -> None:
    for route in _routes():
        if route.path.startswith("/v1/engagements"):
            assert declared_action(route) is not None
            assert route.response_model is not None


# TASK-019: taking, releasing and assigning a review return the assignment, so 200.
REVIEW_QUEUE = "/v1/engagements/{engagement_id}/review-queue/{version_id}"
NOT_CREATING = {
    # A-05-T04: a Form 5500 line's value and a related party's screen-out act on existing rows.
    "/v1/audits/{work_item_id}/ebp/form-5500/lines/{line_id}/value",
    "/v1/audits/{work_item_id}/related-parties/{party_id}/screen-out",
    # A-03 (T08, T10, T13): confirming a mapping set, approving a sample version and previewing
    # the item-request fan-out act on existing rows or write nothing, so 200.
    "/v1/mapping-sets/{mapping_set_id}/confirm",
    "/v1/sample-sets/{sample_set_id}/versions/{version_no}/approve",
    "/v1/sample-sets/{sample_set_id}/versions/{version_no}/item-requests/preview",
    # N-02: withdrawing a letter's envelope voids it, so 200.
    "/v1/engagements/{engagement_id}/letter/withdraw-envelope",
    # P-11-T03/T06 (C11 stub): an import answers its results, a preview renders and stores
    # nothing, a publish and a regenerate act on existing rows, so 200 (missing since #745).
    "/v1/report-templates/import",
    "/v1/report-templates/{template_id}/versions/{version_no}/preview",
    "/v1/report-templates/{template_id}/versions/{version_no}/publish",
    # T-01-T17 (C11 v1.1): deprecating a version creates nothing, so 200.
    "/v1/report-templates/{template_id}/versions/{version_no}/deprecate",
    "/v1/generated-documents/{document_id}/regenerate",
    "/v1/platform/email-templates/import",  # TASK-401: idempotent, may write nothing, so 200
    # I-01-T07: a snooze, an unsnooze and a reassign change who a gate waits on, so 200.
    "/v1/human-gates/{gate_id}/snooze",
    "/v1/human-gates/{gate_id}/unsnooze",
    "/v1/human-gates/{gate_id}/reassign",
    # K-01-T01 (C21 stub): moving a methodology version or a step's flag changes it, so 200.
    "/v1/methodology/versions/{version_id}/approve",
    "/v1/methodology/versions/{version_id}/discard",
    "/v1/methodology/versions/{version_id}/submit",
    "/v1/methodology/versions/{version_id}/steps/{step_id}/mandatory",
    # G-02-T11 (security-center stub): a decision, a sign-out, an unlock and a schedule approval
    # change what exists and return it, so 200.
    "/v1/firm/data-exports/schedule/approve",
    "/v1/firm/security/incidents/{incident_id}/decisions",
    "/v1/firm/security/sessions/{session_id}/sign-out",
    "/v1/firm/staff/{user_id}/unlock",
    # G-02-T15 (AI-policy stub): a partner's decision and the requester's withdrawal change a
    # version's state and return it, so 200.
    "/v1/firm/ai-policy/versions/{version_no}/approve",
    "/v1/firm/ai-policy/versions/{version_no}/decline",
    "/v1/firm/ai-policy/versions/{version_no}/withdraw",
    # G-01-T02: deactivating and approving change a person or a wall and return it, so 200.
    "/v1/firm/staff/{user_id}/deactivate",
    "/v1/walls/{wall_id}/approve",
    # Q-02-T23: publishing changes a draft set's status, so 200.
    "/v1/platform/retention/floors/{set_version}/publish",
    "/v1/platform/retention/defaults/{set_version}/publish",
    # G-02-T20: publishing a Pub 4557 control set changes a draft's status, so 200.
    "/v1/platform/safeguards-controls/{set_version}/publish",
    # T-02-T02 (K-1 and questionnaire stubs): sharing, undoing, resending, a details review,
    # publishing, sending and the portal's done, submit and consent change records, so 200.
    "/v1/tax-returns/{return_id}/k1-packages:share-internal",
    "/v1/k1-releases/{release_id}:undo",
    "/v1/k1-packages/{package_id}:resend",
    "/v1/recipient-details-changes/{change_id}:accept",
    "/v1/recipient-details-changes/{change_id}:reject",
    "/v1/questionnaire-templates/{template_id}/versions/{version}:publish",
    "/v1/questions/{question_id}:send",
    "/v1/portal/questionnaires/{questionnaire_id}:mark-done",
    "/v1/portal/questionnaires/{questionnaire_id}:submit",
    "/v1/portal/k1s/{package_id}/e-furnishing-consent",
    # T-02-T01 (tax-returns stub): a bulk assignment, an assignment and a transition change the
    # returns and return them, so 200.
    "/v1/tax-returns:bulk-assign",
    "/v1/tax-returns/{return_id}/assignments",
    "/v1/tax-returns/{return_id}/transitions",
    # T-01-T02 (engine-bridge stub): approvals, marks, rejections, letters, publishing and the
    # format check change or read a record, so 200.
    "/v1/tax-returns/{return_id}/final-approval",
    "/v1/engine-exports/{export_id}/mark-exported",
    "/v1/engine-imports/{import_id}/approve",
    "/v1/engine-imports/{import_id}/reject",
    "/v1/delivery-packets/{packet_id}/letter:regenerate",
    "/v1/delivery-packets/{packet_id}/approve",
    "/v1/tax-returns/{return_id}/deliverables:publish",
    "/v1/firm/integrations/{key}/test",
    # T-01-T01 (C19 stub): a decline, a revocation and a template publish change a record, so 200.
    "/v1/consents/{consent_id}/declines",
    "/v1/consents/{consent_id}/revocations",
    "/v1/consent-templates/{template_id}/publish",
    # K-02-T02 (C21 stub): publishing a firm standard's draft changes its status, so 200.
    "/v1/standards/{standard_id}/versions/{version_id}/publish",
    "/v1/walls/{wall_id}/remove",  # TASK-016: returns the removed wall, so 200
    REVIEW_QUEUE + "/take",
    REVIEW_QUEUE + "/release",
    REVIEW_QUEUE + "/assign",
    "/v1/knowledge/documents/{document_id}/withdraw",  # SPEC-009: returns the document, so 200
    "/v1/knowledge/search",  # SPEC-009: a query, nothing created
    "/v1/engagements/{engagement_id}/self-join",  # SPEC-013: returns the engagement, so 200
    "/v1/notifications/{notification_id}/read",  # SPEC-013: own read state
    "/v1/notifications/read-all",
    # SPEC-015: acceptance returns the engagement; revoke and resend return the invitation.
    "/v1/invitations/accept",
    "/v1/engagements/{engagement_id}/request-items/import/preview",  # SPEC-018: nothing stored
    "/v1/engagements/{engagement_id}/client-invitations/{invitation_id}/revoke",
    "/v1/engagements/{engagement_id}/client-invitations/{invitation_id}/resend",
    # SPEC-012: lifecycle changes return the session, so 200.
    "/v1/support/sessions/{session_id}/approve",
    "/v1/support/sessions/{session_id}/end",
    "/v1/support-sessions/{session_id}/approve",
    "/v1/support-sessions/{session_id}/revoke",
    "/v1/support-sessions/{session_id}/acknowledge",
    # SPEC-020 (TASK-036): starting returns the provider's URL; check and revoke return state.
    "/v1/engagements/{engagement_id}/connection/start",
    "/v1/engagements/{engagement_id}/connection/check",
    "/v1/engagements/{engagement_id}/connection/revoke",
    "/v1/engagements/{engagement_id}/inbox/{file_id}/discard",  # SPEC-023: returns the id
    # SPEC-024 (TASK-041): lifecycle changes return the id; acceptance returns the firm.
    "/v1/firm/staff/invitations/{invitation_id}/resend",
    "/v1/firm/staff/invitations/{invitation_id}/revoke",
    "/v1/firm/staff/{user_id}/revoke",
    "/v1/invitations/staff/accept",
    # SPEC-024 (TASK-042): the checklist's state comes back.
    "/v1/firm/onboarding/{step}/acknowledge",
    "/v1/firm/onboarding/dismiss",
    "/v1/engagements/proposal",  # SPEC-025 (TASK-048): a proposal, nothing stored
    # SPEC-312 (TASK-324): a statement review's decisions applied, nothing stored
    "/v1/engagements/{engagement_id}/request-items/{item_id}/uploads/{version_id}/statement/preview",
    # SPEC-027 (TASK-050): pausing and resuming return the agent's state.
    "/v1/engagements/{engagement_id}/agent/pause",
    "/v1/engagements/{engagement_id}/agent/resume",
    "/v1/firm/agents/pause",
    "/v1/firm/agents/resume",
    # SPEC-027 (TASK-051): sending or dismissing a draft returns its id.
    "/v1/engagements/{engagement_id}/follow-ups/{follow_up_id}/send",
    "/v1/engagements/{engagement_id}/follow-ups/{follow_up_id}/dismiss",
    "/v1/engagements/{engagement_id}/follow-ups/{follow_up_id}/preview",  # TASK-104: a read
    "/v1/engagements/{engagement_id}/request-items/{item_id}/comments/read",  # SPEC-032: a mark
    # P-04-T07 (C3 stub 1): bulk returns per-item results; note events return the note.
    "/v1/sign-offs:bulk",
    "/v1/review-notes/{note_id}/respond",
    "/v1/review-notes/{note_id}/clear",
    "/v1/review-notes/{note_id}/withdraw",
    # P-04-T08 (C3 stub 2): decisions, proposal and suggestion resolutions return the record.
    "/v1/decision-cards/{card_id}/decide",
    "/v1/decision-cards/{card_id}/notify",
    "/v1/decision-cards/{card_id}/reassess",
    "/v1/proposals/{proposal_id}/approve",
    "/v1/proposals/{proposal_id}/reject",
    "/v1/proposals/{proposal_id}/route",
    "/v1/proposals/{proposal_id}/follow-up",
    "/v1/proposals/{proposal_id}/undo",
    "/v1/suggestions/{suggestion_id}/adopt",
    "/v1/suggestions/{suggestion_id}/dismiss",
    # P-04-T11 (C3 stub 3): issue status changes and checkpoint decisions return the record.
    "/v1/issues/{issue_id}/resolve",
    "/v1/issues/{issue_id}/verify",
    "/v1/issues/{issue_id}/reopen",
    "/v1/issues/{issue_id}/mark-not-applicable",
    "/v1/issues/{issue_id}/send-to-client",
    "/v1/checkpoints/{checkpoint_id}/approve",
    "/v1/checkpoints/{checkpoint_id}/reject",
    # P-06-T01 (C5 stub): state changes on a binder or request item that return the record.
    "/v1/binders/{binder_id}/publish",
    "/v1/binders/{binder_id}/publish/undo",
    "/v1/binders/{binder_id}/unpublish",
    "/v1/engagements/{engagement_id}/request-items/{item_id}/send",
    "/v1/engagements/{engagement_id}/request-items/{item_id}/send/undo",
    "/v1/engagements/{engagement_id}/request-items/{item_id}/waive",
    "/v1/engagements/{engagement_id}/request-items/{item_id}/return-to-client",
    "/v1/engagements/{engagement_id}/request-items/{item_id}/incorporate",
    "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/withdraw",
    "/v1/engagements/{engagement_id}/request-items/{item_id}/evidence-versions/{version_id}"
    "/duplicate-resolution",
    "/v1/portal/binders/{binder_id}/mark-done",
    "/v1/portal/request-items/{item_id}/ignore",
    # P-06-T14 (follow-ups v2): sending, its Undo and dismissing return the follow-up.
    "/v1/follow-ups/{follow_up_id}/send",
    "/v1/follow-ups/send",
    "/v1/follow-ups/{follow_up_id}/undo",
    "/v1/follow-ups/{follow_up_id}/dismiss",
    # P-08-T01 (C5 v1.1 portal half): firm-side recovery returns the contact's portal access.
    "/v1/clients/{client_id}/contacts/{contact_id}/portal-unlock",
    "/v1/clients/{client_id}/contacts/{contact_id}/mfa-reset",
    "/v1/telemetry/errors",  # Q-01-T48: forwards a browser error, creates nothing
    "/v1/evidence-versions/{version_id}/unlock",  # P-03-T02: a derivation, answered 200
    # P-01-T09 (ADR-165): a refresh rotates the cookie; sign-out ends the session.
    "/v1/auth/refresh",
    "/v1/auth/sign-out",
    # P-08-T10 (ADR-168): verifying a code or refreshing returns a token; resend and start
    # answer 202; sign-out ends the session.
    "/v1/portal/auth/verify",
    "/v1/portal/auth/refresh",
    "/v1/portal/auth/sign-out",
    # P-08-T17: the second step and its setup return a session or a key; nothing is created
    # the caller can address.
    "/v1/portal/auth/mfa",
    "/v1/portal/auth/mfa/setup",
    "/v1/portal/auth/mfa/setup/verify",
    # P-07-T04 (clients stub): a reveal returns the value once and stores nothing but its audit.
    "/v1/client-entities/{entity_id}/tin/reveal",
    # P-07-T17 (contacts stub): a resend replaces the token and an unlock clears a lock, so 200.
    "/v1/invitations/{invitation_id}/resend",
    "/v1/invitations/{invitation_id}/revoke",
    "/v1/contacts/{contact_id}/unlock",
    # P-07-T05 (engagements v2 stub): per-step validation returns findings, nothing stored.
    "/v1/engagement-drafts/{draft_id}/validate",
    # R-01-T01 (C5 portal-pbc stub): undos are compensating events on an existing record, a void
    # stamps an existing fulfilment, and the room's suggest reads file names and stores nothing.
    "/v1/portal/request-items/{item_id}/ignore/undo",
    "/v1/portal/binders/{binder_id}/mark-done/undo",
    "/v1/engagements/{engagement_id}/fulfilments/{fulfilment_id}/void",
    "/v1/portal/room/suggest",
    # P-08-T18 (SPEC-320 AC-12): the invitation preview reads; nothing is created.
    "/v1/invitations/preview",
    # P-07-T29 (team, acceptance, independence and conflict stubs): these move a record or
    # answer an existing request (a completed check or condition, a send to the partner, a
    # confirmation or decline, a reminder, a replaced EQR, a cleared result), so 200.
    "/v1/engagements/{engagement_id}/acceptance/manual-checks/{section_code}/complete",
    "/v1/engagements/{engagement_id}/acceptance/send-to-partner",
    "/v1/engagements/{engagement_id}/acceptance/conditions/{condition_id}/complete",
    "/v1/engagements/{engagement_id}/independence/confirm",
    "/v1/engagements/{engagement_id}/independence/decline",
    "/v1/engagements/{engagement_id}/independence/reminders",
    "/v1/engagements/{engagement_id}/eqr",
    "/v1/conflict-checks/{check_id}/results/{result_id}/clear",
    # P-07-T35: completing the requested risk-partner review is an event on it, so 200.
    "/v1/engagements/{engagement_id}/acceptance/risk-partner-review/complete",
    # P-07-T37 (intake stub): a dedupe read and a step validation write nothing, so 200.
    "/v1/clients/dedupe",
    "/v1/client-intake-drafts/{draft_id}/validate",
    # TASK-1198 (ENG-02 status menu): holding and resuming move an engagement, so 200.
    "/v1/engagements/{engagement_id}/hold",
    "/v1/engagements/{engagement_id}/resume",
    # Q-02-T38 (compliance-kernel v1.1 stub): a decision on an existing export, and a link.
    "/v1/firm/data-exports/{export_id}/approve",
    "/v1/firm/data-exports/{export_id}/decline",
    "/v1/firm/data-exports/{export_id}/link",
    "/v1/audit-events/exports/{export_id}/link",  # G-02-T04: a download link, nothing created
    # A-01-T17 (engagement export v1 stub): Undo voids an existing export's grant.
    "/v1/exports/{export_id}/undo",
    # A-02-T06 (C20 v1 stub): a disconnect revokes an existing connection and returns its card.
    "/v1/portal/connections/{connection_id}/disconnect",
    # R-01-T16 (C16 v1.1 stub): an import answers its results (a dry run by default), a preview
    # renders and stores nothing, a check reads the SES identity, a logo replaces the draft's.
    "/v1/firm/email-templates/import",
    "/v1/firm/email-templates/{key}/preview",
    "/v1/firm/sending-domains/{domain_id}/check",
    "/v1/firm/portal-settings/logo",
    # N-01-T02, N-02-T03 (S13 stubs): state changes and sessions on existing records, so 200.
    "/v1/engagements/{engagement_id}/letter/approve",
    "/v1/engagements/{engagement_id}/letter/request-approval",
    "/v1/engagements/{engagement_id}/letter/send",
    "/v1/envelopes/remind/preview",
    "/v1/envelopes/remind/send",
    "/v1/envelopes/{envelope_id}/countersign/session",
    "/v1/envelopes/{envelope_id}/send",
    "/v1/envelopes/{envelope_id}/send/undo",
    "/v1/envelopes/{envelope_id}/signers/{signer_id}/reveal-ip",
    "/v1/envelopes/{envelope_id}/signers/{signer_id}/wet-signature",
    "/v1/envelopes/{envelope_id}/validate",
    "/v1/envelopes/{envelope_id}/void",
    "/v1/inbox/attachments/bulk-file",
    "/v1/inbox/messages/{message_id}/triage/apply",
    "/v1/inbox/threads/{thread_id}/ignore",
    "/v1/inbox/threads/{thread_id}/match-client",
    "/v1/portal/envelopes/{envelope_id}/decline",
    "/v1/portal/envelopes/{envelope_id}/decline/withdraw",
    "/v1/portal/envelopes/{envelope_id}/esign-consent",
    "/v1/portal/envelopes/{envelope_id}/progress",
    "/v1/portal/envelopes/{envelope_id}/signing-session",
    "/v1/portal/envelopes/{envelope_id}/viewed",
    "/v1/portal/intake-uploads/{upload_id}/withdraw",
    # K-01-T18 (DEC-1755): starting and cancelling an import, and resolving a parse flag, move an
    # existing record, so 200.
    "/v1/methodology/imports/{import_id}/start",
    "/v1/methodology/imports/{import_id}/cancel",
    "/v1/methodology/versions/{version_id}/steps/{step_id}/flag-resolution",
    # A-04-T01 (stubs, DEC-1757): a preview and a coverage check compute and store nothing; a
    # flag conversion, a reminder draft, the minutes approval and an exception's routing act on
    # existing records, so 200.
    "/v1/engagements/{engagement_id}/materiality/preview",
    "/v1/engagements/{engagement_id}/risks/coverage",
    "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/flags/{flag_id}/convert",
    "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/flags/{flag_id}/remind",
    "/v1/engagements/{engagement_id}/fraud-brainstorm/minutes/approve",
    "/v1/engagements/{engagement_id}/internal-control/exceptions/{sheet_row}/send-to-findings",
    "/v1/engagements/{engagement_id}/internal-control/exceptions/{sheet_row}/convert-to-misstatement",
}


def test_ac20_creating_routes_answer_201() -> None:
    posts = [r for r in _routes() if "POST" in _methods(r)]
    accepted = {
        RETRIEVALS,
        SCREEN_REQUEST,
        REVIEW_REQUEST,
        MATCH_REQUEST,
        GL_IMPORT,
        DRAFTS,
        TEMPLATE_DRAFTS,
        SELECT,
        ASSESS,
        # P-06-T15 (C5 v1.2 SHL-20 stub): a rerun starts screening, so 202.
        "/v1/engagements/{engagement_id}/request-items/{item_id}/screening/rerun",
        # P-04-T11 (C3 stub 3): fix instructions and Explain start an agent run, so 202.
        "/v1/issues/{issue_id}/fix-instructions",
        "/v1/issues/fix-instructions:bulk",
        "/v1/issues/{issue_id}/explanations",
        # A-05-T04: a plan review starts the agent's draft, so 202.
        "/v1/audits/{work_item_id}/ebp/plan-reviews",
        # Q-02-T29: placing and releasing a legal hold start their workflows, so 202.
        "/v1/legal-holds",
        "/v1/legal-holds/{hold_id}/release",
        # Q-02-T33: staff propagation of an Accrued incident starts IncidentPropagation, so 202.
        "/v1/platform/incidents/{accrued_ref}/propagate",
        # P-08-T10 (SPEC-320): a sign-in start and a resend answer 202 for any email.
        "/v1/portal/auth/start",
        # R-01-T01: a portal drop is stored and sorted later, so 202 (polled by its batch).
        "/v1/portal/binders/{binder_id}/drops",
        "/v1/portal/auth/resend",
        # P-08-T21: a link renewal answers 202 for any token (the email goes out later).
        "/v1/portal/links/renew",
        # Q-02-T38: a firm-export request waits for its approver, then builds, so 202.
        "/v1/firm/data-exports",
        # G-02-T04: an audit-log export is requested, then builds, so 202.
        "/v1/audit-events/exports",
        # A-01-T17: an engagement export waits out its Undo window, then builds, so 202.
        "/v1/work-items/{work_item_id}/exports",
        # A-02-T06 (C20 v1 stub): a retry and an on-demand pull start a sync run, so 202.
        "/v1/portal/connections/{connection_id}/retry",
        "/v1/engagements/{engagement_id}/connection/pulls",
        # R-01-T16: a test send queues one email to the acting admin, so 202.
        "/v1/firm/email-templates/{key}/test-send",
        # P-07-T37: an import run starts ClientImportWorkflow, so 202.
        "/v1/client-imports/{import_id}/run",
        # T-02-T02: a K-1 release waits out its Undo window, so 202.
        "/v1/tax-returns/{return_id}/k1-packages:release",
        # T-01-T01 (C19 stub): a consent export builds later, so 202.
        "/v1/consents/exports",
        # G-02-T11 (security-center stub): a WISP pack is built later, so 202.
        "/v1/firm/safeguards/wisp-pack",
        # DEC-1281: a DocuSeal delivery is a hint only, always an empty 202.
        "/v1/webhooks/docuseal/{tenant_id}/{install_id}",
        # A-03-T08 and T10: a mapping run and a sample draw start their workflows, so 202.
        "/v1/engagements/{engagement_id}/mapping-sets",
        "/v1/sample-sets/{sample_set_id}/versions",
        # A-04-T01: a draft starts a section-drafter run, so 202.
        "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/drafts",
        "/v1/engagements/{engagement_id}/risks/{risk_id}/drafts",
        "/v1/engagements/{engagement_id}/soc-reports/{soc_report_id}/drafts",
    }
    created = {r.path for r in posts if r.path not in accepted and r.path not in NOT_CREATING}
    assert all(r.status_code == 202 for r in posts if r.path == SCREEN_REQUEST)
    decisions = "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/"
    assert created == {
        "/v1/engagements",
        "/v1/engagements/{engagement_id}/request-items",
        # A-03 (T06, T07, T10, T13): a grouping import, a population and its ties, a sample set
        # and the item-request fan-out each create rows, so 201.
        "/v1/grouping-sets/imports/file",
        "/v1/work-items/{work_item_id}/populations",
        "/v1/populations/{population_id}/ties",
        "/v1/work-items/{work_item_id}/sample-sets",
        "/v1/sample-sets/{sample_set_id}/versions/{version_no}/item-requests",
        # T-01: issuing an acknowledgement records it, so 201.
        "/v1/tax-returns/{return_id}/acks/{ack_id}/issue",
        # K-01-T01 (C21 stub): a methodology draft and a program step.
        "/v1/methodology/versions/{version_id}/drafts",
        # K-01-T18: a methodology import.
        "/v1/methodology/imports",
        # A-04-T01 (stubs): a materiality proposal and reassessment, a risk approval request and
        # response, a fraud inquiry, an evidence request draft, a service organization, SOC
        # request drafts and a reliance card.
        "/v1/engagements/{engagement_id}/materiality/proposals",
        "/v1/engagements/{engagement_id}/materiality/reassessments",
        "/v1/engagements/{engagement_id}/risks/approval-requests",
        "/v1/engagements/{engagement_id}/risks/{risk_id}/responses",
        "/v1/engagements/{engagement_id}/fraud-inquiries",
        "/v1/engagements/{engagement_id}/internal-control/exceptions/{sheet_row}/request-evidence",
        "/v1/engagements/{engagement_id}/service-organizations",
        "/v1/engagements/{engagement_id}/soc-reports/{soc_report_id}/requests",
        "/v1/engagements/{engagement_id}/soc-reports/{soc_report_id}/reliance-requests",
        # A-05-T04 (ebp-workpapers stub): an import, a provider and its invite, a correction, a
        # logged census reveal, a trust TB adoption, a reconciliation note, an estimate's
        # conclusion request, related parties, parties in interest and a test each create a row.
        "/v1/audits/{work_item_id}/ebp/imports",
        "/v1/audits/{work_item_id}/ebp/providers",
        "/v1/audits/{work_item_id}/ebp/providers/{provider_id}/invite",
        "/v1/audits/{work_item_id}/ebp/late-remittances/{remittance_id}/corrections",
        "/v1/audits/{work_item_id}/ebp/participants/{participant_id}/reveals",
        "/v1/audits/{work_item_id}/ebp/trust-tb/adopt",
        "/v1/audits/{work_item_id}/ebp/form-5500/reconciliation-note",
        "/v1/audits/{work_item_id}/estimates/{estimate_id}/request-conclusion",
        "/v1/audits/{work_item_id}/related-parties",
        "/v1/audits/{work_item_id}/parties-in-interest",
        "/v1/audits/{work_item_id}/tests",
        # POR-13 (TASK-2537, TASK-2538): a recipient's W-9/W-8 upload and a furnishing consent.
        "/v1/portal/k1-recipients/{recipient_id}/details-changes:upload",
        "/v1/k1-furnishing-disclosures",
        # T-02-T02: a template import, an organizer, a questionnaire, a question, a portal
        # attachment and a recipient's details change.
        "/v1/questionnaire-templates:import",
        "/v1/request-lists/{request_list_id}/questionnaires",
        "/v1/questionnaires",
        "/v1/questionnaires/{questionnaire_id}/questions",
        "/v1/portal/questionnaires/{questionnaire_id}/questions/{question_id}/attachments",
        "/v1/portal/k1-recipients/{recipient_id}/details-changes",
        # T-01-T02 (engine-bridge stub): an export, an import, a packet, the 8879 envelope, an ERO
        # notice, a transmission record and an ack.
        "/v1/tax-returns/{return_id}/engine-exports",
        "/v1/tax-returns/{return_id}/engine-imports",
        "/v1/tax-returns/{return_id}/delivery-packet:assemble",
        "/v1/tax-returns/{return_id}/efile-envelope",
        "/v1/tax-returns/{return_id}/ero-notices",
        "/v1/tax-returns/{return_id}/transmissions",
        "/v1/tax-returns/{return_id}/acks",
        # T-01-T01 (C19 stub): consent drafts and records, templates, authorizations, transcripts.
        "/v1/consents/requests",
        "/v1/consents/renewals",
        "/v1/consents/records",
        "/v1/consent-templates/imports",
        "/v1/client-entities/{client_entity_id}/authorizations",
        "/v1/client-entities/{client_entity_id}/authorizations/requests",
        "/v1/client-entities/{client_entity_id}/transcripts",
        "/v1/transcripts/{transcript_id}/comparisons",
        # T-01-T43: a staged transcript or authorization file.
        "/v1/client-entities/{client_entity_id}/transcripts/files",
        "/v1/client-entities/{client_entity_id}/authorizations/files",
        # K-02-T02 (C21 stub): a firm standard, a draft version, and drafts from an import.
        "/v1/standards",
        "/v1/standards/{standard_id}/versions",
        "/v1/standards/{standard_id}/imports",
        "/v1/standards/imports",
        "/v1/methodology/versions/{version_id}/programs/{program_id}/steps",
        # G-02-T11 (security-center stub): an incident timeline entry.
        "/v1/firm/security/incidents/{incident_id}/timeline",
        # G-01-T02 (firm-settings stub): an office, a team, and one's annual confirmation.
        "/v1/firm/offices",
        "/v1/firm/teams",
        "/v1/me/independence/annual",
        # Q-02-T23: a draft retention floor set and a draft default-policy set.
        "/v1/platform/retention/floors",
        "/v1/platform/retention/defaults",
        # G-02-T20: a draft Pub 4557 control set.
        "/v1/platform/safeguards-controls",
        # P-03-T02 (C4 v1 stub): a citation, a re-linked citation and a logged reveal.
        "/v1/citations",
        "/v1/citations/{citation_id}/relink",
        "/v1/evidence-versions/{version_id}/pii-reveals",
        # P-06-T01 (C5 stub): a binder, its copy, a delegation and an upload intent.
        "/v1/binders",
        "/v1/binders/{binder_id}/duplicate",
        "/v1/follow-ups/drafts",  # P-06-T14: one draft per client contact
        # P-06-T15 (SHL-20 stub): a feedback row and a screening-return draft.
        "/v1/screenings/{screening_result_id}/feedback",
        "/v1/engagements/{engagement_id}/request-items/{item_id}/follow-ups",
        "/v1/engagements/{engagement_id}/request-items/{item_id}/delegate",
        "/v1/portal/request-items/{item_id}/upload-intents",
        # P-07-T05 (engagements v2 stub): a draft, a Prospect engagement, an engagement.
        # A-01-T02 (audits stub): a phase event, an external release and an external archive.
        "/v1/audits/{work_item_id}/phase",
        "/v1/audits/{work_item_id}/release-record",
        "/v1/audits/{work_item_id}/archive-record",
        "/v1/engagement-drafts",
        "/v1/engagement-drafts/{draft_id}/start-acceptance",
        "/v1/engagement-drafts/{draft_id}/create",
        # P-07-T17 (contacts stub): a contact, and an invitation with its pending grants.
        "/v1/clients/{client_id}/contacts",
        "/v1/contacts/{contact_id}/invitations",
        # P-07-T29: a flag, a manual check, a risk-partner review, the decision, a breach and
        # its events, a conclusion, a team approval, an EQR eligibility approval, a conflict
        # check and a screening record (each an insert-only row).
        "/v1/engagements/{engagement_id}/acceptance/flags",
        "/v1/engagements/{engagement_id}/acceptance/manual-checks/{section_code}/request",
        "/v1/engagements/{engagement_id}/acceptance/risk-partner-review",
        "/v1/engagements/{engagement_id}/acceptance/decision",
        "/v1/engagements/{engagement_id}/independence/breaches",
        "/v1/engagements/{engagement_id}/independence/breaches/{breach_id}/events",
        "/v1/engagements/{engagement_id}/independence/conclude",
        "/v1/engagements/{engagement_id}/team/approve",
        "/v1/engagements/{engagement_id}/eqr/eligibility/approve",
        "/v1/conflict-checks",
        "/v1/screening-records",
        # P-07-T37 (intake stub): an intake draft, the committed client, an uploaded import.
        "/v1/client-intake-drafts",
        "/v1/client-intake-drafts/{draft_id}/commit",
        "/v1/client-imports",
        # P-07-T55: a roll-forward draft, and the engagement Create makes from it.
        "/v1/engagements/{engagement_id}/roll-forward/drafts",
        "/v1/engagements/{engagement_id}/roll-forward/drafts/{draft_id}/create",
        "/v1/walls",
        "/v1/methodology/templates/{name}/versions",  # SPEC-008: a template version
        "/v1/engagements/{engagement_id}/methodology",  # SPEC-008: items seeded
        "/v1/knowledge/documents",  # SPEC-009: a knowledge document
        "/v1/support/sessions",  # SPEC-012: a support session is requested
        "/v1/engagements/{engagement_id}/client-invitations",  # SPEC-015: an invitation
        "/v1/engagements/{engagement_id}/team",  # SPEC-017: a team member
        "/v1/engagements/{engagement_id}/request-items/import",  # SPEC-018: items created
        "/v1/engagements/{engagement_id}/request-items/{item_id}/uploads",  # SPEC-020: evidence
        "/v1/connections/complete",  # SPEC-020: a connection
        "/v1/engagements/{engagement_id}/inbox",  # SPEC-023: an inbox file
        "/v1/signup",  # SPEC-024: a firm
        "/v1/firm/staff/invitations",  # SPEC-024: a staff invitation
        "/v1/engagements/{engagement_id}/letter/file",
        "/v1/engagements/{engagement_id}/inbox/{file_id}/assign",  # SPEC-023: evidence
        "/v1/engagements/{engagement_id}/connection/import",  # SPEC-028: a ledger import
        decisions + "accept",  # TASK-019: a review decision is created
        decisions + "reject",
        decisions + "send-back",
        # P-01-T13 (TASK-1001): Undo writes a compensating review decision.
        "/v1/engagements/{engagement_id}/review-decisions/{decision_id}/undo",
        # SPEC-032 (TASK-062): a comment, or a redaction, is created.
        "/v1/engagements/{engagement_id}/request-items/{item_id}/comments",
        "/v1/engagements/{engagement_id}/request-items/{item_id}/versions/{version_id}/comments",
        "/v1/engagements/{engagement_id}/request-items/{item_id}/comments/{comment_id}/redact",
        # SPEC-035 (TASK-073): a decision on each draft is created.
        "/v1/engagements/{engagement_id}/guidance-drafts/approve",
        "/v1/engagements/{engagement_id}/guidance-drafts/discard",
        # SPEC-035 Q3 (TASK-074): a decision on each template draft; a template version.
        "/v1/methodology/versions/{version_id}/guidance-drafts/approve",
        "/v1/methodology/versions/{version_id}/guidance-drafts/discard",
        "/v1/methodology/versions/{version_id}/publish-drafted",
        # SPEC-037 (TASK-083): a procedure, and people's picks, are created.
        "/v1/engagements/{engagement_id}/procedures",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/picks",
        # SPEC-037 (TASK-084): a support request, and each signature, are created.
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/items/{item_id}/request-support",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/approve",  # SPEC-040
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/request-support",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/items/sign-prepared",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/items/sign-reviewed",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/notes",  # SPEC-041
        "/v1/engagements/{engagement_id}/follow-ups/draft",  # TASK-104
        "/v1/engagements/{engagement_id}/request-items/{item_id}/client-response",  # SPEC-042
        "/v1/engagements/{engagement_id}/request-items/{item_id}/client-response/withdraw",
        "/v1/engagements/{engagement_id}/request-items/client-done",
        "/v1/engagements/{engagement_id}/findings",  # SPEC-043
        # SPEC-300 (TASK-301): the partner's materiality decision; risks and their approval
        "/v1/engagements/{engagement_id}/materiality/decide",
        "/v1/engagements/{engagement_id}/risks",
        "/v1/engagements/{engagement_id}/risks/{risk_id}/versions",
        "/v1/engagements/{engagement_id}/risks/{risk_id}/approve",
        # SPEC-301 (TASK-302): severity, communication, proposed entries, representations
        "/v1/engagements/{engagement_id}/findings/{finding_id}/severity/propose",
        "/v1/engagements/{engagement_id}/findings/{finding_id}/severity/conclude",
        "/v1/engagements/{engagement_id}/findings/{finding_id}/communicated",
        "/v1/engagements/{engagement_id}/adjustments",
        "/v1/engagements/{engagement_id}/adjustments/{adjustment_id}/approve",
        "/v1/engagements/{engagement_id}/adjustments/{adjustment_id}/client-answer",
        "/v1/engagements/{engagement_id}/representations",
        "/v1/engagements/{engagement_id}/representations/{representation_id}/remove",
        # SPEC-044 (TASK-109): the session's plan approval and adopting the agent's proposals
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/session/approve-plan",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/adopt",
        "/v1/engagements/{engagement_id}/findings/{finding_id}/misstatement",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/notes/{note_id}/respond",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/notes/{note_id}/clear",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/workpaper/sign-ready",
        "/v1/engagements/{engagement_id}/procedures/{procedure_id}/workpaper/sign-reviewed",
        # SPEC-308 (TASK-319): working papers, citations and sign-offs
        "/v1/engagements/{engagement_id}/workpapers",
        "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/cells/{cell_key}/citations",
        "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/sign-offs/prepare",
        "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/sign-offs/review",
        "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/sign-offs/manager",
        "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/sign-offs/partner",
        "/v1/engagements/{engagement_id}/workpapers/{workpaper_id}/sign-offs/eqr",
        # SPEC-309 (TASK-320): adopting a trial balance, its versions and annotations
        "/v1/engagements/{engagement_id}/trial-balances",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/versions",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/annotations",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/checks",  # SPEC-310
        # A-02-T03 (C9 v1 stub): an issue linked to a check that does not tie.
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/checks/{check_id}/issue-link",
        # TASK-323: a password-protected upload saved again without its password
        "/v1/engagements/{engagement_id}/request-items/{item_id}/uploads/{version_id}/unlock",
        "/v1/engagements/{engagement_id}/request-items/{item_id}/uploads/{version_id}/statement/approve",
        # SPEC-313 (TASK-331): review notes and their events; trial balance sign-offs
        "/v1/engagements/{engagement_id}/review-notes",
        "/v1/engagements/{engagement_id}/review-notes/{note_id}/respond",
        "/v1/engagements/{engagement_id}/review-notes/{note_id}/clear",
        "/v1/engagements/{engagement_id}/review-notes/{note_id}/reopen",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/sign-offs/prepare",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/sign-offs/review",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/sign-offs/manager",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/sign-offs/partner",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/sign-offs/eqr",
        # SPEC-314 (TASK-332): completion, release and archive records
        "/v1/engagements/{engagement_id}/completion/eqr/concur",
        "/v1/engagements/{engagement_id}/completion/going-concern",
        "/v1/engagements/{engagement_id}/completion/report",
        "/v1/engagements/{engagement_id}/completion/report/approve",
        "/v1/engagements/{engagement_id}/completion/rep-letter",
        "/v1/engagements/{engagement_id}/completion/release",
        "/v1/engagements/{engagement_id}/completion/archive/lock",
        # SPEC-316 (TASK-345): grouping sets, mapping and its sign-offs
        "/v1/grouping-sets/imports",
        "/v1/grouping-sets/versions/{version_id}/publish",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/mapping",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/mapping/sign-offs/prepare",
        "/v1/engagements/{engagement_id}/trial-balances/{tb_id}/mapping/sign-offs/review",
        # P-04-T07 (C3 stub 1): a sign-off row, a review note
        "/v1/sign-offs",
        "/v1/review-notes",
        # SPEC-318 (TASK-461): a run trace export
        "/v1/agent-runs/{run_id}/trace-exports",
        "/v1/decision-cards/{card_id}/analysis-requests",  # P-04-T08: a recorded request
        # P-04-T11 (C3 stub 3): an issue, a checkpoint (saved or restored as a copy), a field
        # reference and a field tick.
        "/v1/issues",
        "/v1/checkpoints",
        "/v1/checkpoints/{checkpoint_id}/restore",
        "/v1/fields/{target_type}/{target_id}/{field_key}/references",
        "/v1/fields/{target_type}/{target_id}/{field_key}/ticks",
        "/v1/firm/security/incidents",  # Q-02-T33: a register entry
        # A-02-T06 (C20 v1 stub): a consent record, and a reconnect request.
        "/v1/portal/entities/{entity_id}/connections/{catalog_key}/start",
        "/v1/connections/{connection_id}/reconnect-requests",
        # R-01-T16 (C16 v1.1 stub): a template version, a sending domain, a settings version.
        "/v1/firm/email-templates/{key}/publish",
        "/v1/firm/sending-domains",
        "/v1/firm/portal-settings/publish",
        "/v1/firm/ai-policy/versions",  # G-02-T15 (AI-policy stub): a version requested
        # N-01-T02, N-02-T03 (S13 stubs): an intake log and its files, a portal upload batch
        # and its files, an envelope (drafted, imported or resent) and a letter amendment or file.
        "/v1/inbox/intake",
        "/v1/inbox/intake/{message_id}/files",
        "/v1/portal/intake-uploads",
        "/v1/portal/intake-uploads/{upload_id}/files",
        "/v1/envelopes",
        "/v1/envelopes/import",
        "/v1/envelopes/import/files",  # N-02: one stored file a record-mode import names
        "/v1/envelopes/{envelope_id}/resend",
        "/v1/engagements/{engagement_id}/letter/amend",
    }
    assert all(r.status_code == 201 for r in posts if r.path in created)
    assert {r.path for r in posts if r.path in NOT_CREATING} == NOT_CREATING
    assert all(r.status_code in (None, 200) for r in posts if r.path in NOT_CREATING)


def test_ac20_the_retrieval_routes_exist_with_their_actions_and_the_post_answers_202() -> None:
    actual = {
        (method, route.path): declared_action(route)
        for route in _routes()
        for method in _methods(route)
    }
    assert actual[("POST", RETRIEVALS)] == "evidence.upload"
    assert actual[("GET", RETRIEVALS + "/{sync_run_id}")] == "request_item.read"
    [post] = [r for r in _routes() if r.path == RETRIEVALS and "POST" in _methods(r)]
    assert post.status_code == 202
    assert post.response_model is not None


def test_ac20_self_is_still_used_only_on_v1_me() -> None:
    assert [r.path for r in _routes() if declared_action(r) == identity_api.SELF] == ["/v1/me"]


def test_ac20_the_new_module_exports_exist() -> None:
    for name in ("EngagementCreated", "EngagementRef", "get_ref", "lock_ref", "router"):
        assert hasattr(engagements_api, name), name
        assert name in engagements_api.__all__
    for name in ("RequestItemCreated", "router"):
        assert hasattr(requests_api, name), name
        assert name in requests_api.__all__


def test_ac20_identity_exports_add_creator_as_partner_and_not_add_engagement_member() -> None:
    assert callable(identity_api.add_creator_as_partner)
    assert "add_creator_as_partner" in identity_api.__all__
    assert not hasattr(identity_api, "add_engagement_member")
    assert "add_engagement_member" not in identity_api.__all__
    assert "WALL_SAFE" in identity_api.__all__


PRODUCTION_SETTINGS = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "RELAY_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "IDENTITY_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "IDENTITY_ISSUER": "https://idp.example.test",
    "IDENTITY_AUDIENCE": "abacus-api",
    "IDENTITY_JWKS": '{"keys": []}',
    "S3_ENDPOINT_URL": "http://s3.example.test",
    "S3_ACCESS_KEY": "k",
    "S3_SECRET_KEY": "s",
    "TEMPORAL_TARGET": "t:7233",
    "TRUSTED_HOSTS": "api.example.test",
    "KMS_PLATFORM_KEY_ALIAS": "alias/abacus/platform",
    "TEMPORAL_PAYLOAD_KEYS": '{"platform-v1": "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs"}',
    "TEMPORAL_PAYLOAD_CURRENT": "platform-v1",
    "SCANNER_ENDPOINT": "scanner.abacus.internal:3310",
    "SES_CONFIGURATION_SET": "abacus-staging",
    "SES_FROM_ADDRESS": "notifications@mail.example.test",
    "TEMPORAL_PAYLOAD_KEY": "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs",
    "TEMPORAL_TLS": "true",
    "TEMPORAL_API_KEY": "test-temporal-api-key",
    "EVIDENCE_BUCKET": "test-evidence-bucket",
}


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "production")
    for name, value in PRODUCTION_SETTINGS.items():
        monkeypatch.setenv(f"ABACUS_{name}", value)
    settings.cache_clear()


def test_ac20_production_refuses_to_start_while_walls_are_not_implemented(
    production: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(identity_api, "WALL_SAFE", False)
    try:
        with pytest.raises(RuntimeError):
            create_app()
    finally:
        settings.cache_clear()


def test_ac11_production_starts_now_that_walls_are_enforced(production: None) -> None:
    # TASK-016: WALL_SAFE is True, so the gate lets `create_app` start in production.
    assert identity_api.WALL_SAFE is True
    try:
        assert create_app() is not None
    finally:
        settings.cache_clear()


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_non_production_environments_start_without_walls(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    settings.cache_clear()
    try:
        assert create_app() is not None
    finally:
        settings.cache_clear()
