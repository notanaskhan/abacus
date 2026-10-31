"""Letter approval, send and amend (N-02-T33; N-02 §3.11, §4.2; ENG-04; DEC-1468). Expand-only.

`engagement_letter_versions` gains the approval request (`approval_requested_at`,
`approval_requested_by`: who asked the engagement partner, and when; the C13 gate
`letter_partner_approval` waits while it stands on a draft) and `final_document_version_id` (the
C11 final the approval rendered, which Send names; set with the approval and never rewritten). The
guard trigger (0560) is replaced to add INV-1's database layer: a version moves to
`partner_approved` only in a transaction whose actor is a person (`app.actor_kind = 'human'`), and
the approver named is that person (`app.actor_id`). `letter.approved` joins
`abacus_human_only_actions()` (63 entries; the downgrade restores 0561's 62).

Revision ID: 0563
Revises: 0562
"""

from __future__ import annotations

from alembic import op

revision = "0563"
down_revision = "0562"
branch_labels = None
depends_on = None

_BEFORE = [
    "acceptance.decided",
    "acceptance.review_completed",
    "ai_policy.approved",
    "ai_policy.declined",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "client_import.row_decided",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "engine_export.generated",
    "engine_export.marked_exported",
    "eqr.eligibility_approved",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "firm_export.declined",
    "follow_up.sent",
    "fulfilment.voided",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.annual_confirmed",
    "independence.annual_declined",
    "independence.concluded",
    "independence.confirmed",
    "independence.declined",
    "independence.statement_published",
    "legal_hold.lifted",
    "legal_hold.placed",
    "materiality.decided",
    "methodology_version.approved",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "proposal.approved",
    "proposal.approved_with_edits",
    "proposal.rejected",
    "proposal.routed",
    "report.approved",
    "report.released",
    "retention_policy.updated",
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "service_line_policy.updated",
    "sign_off.recorded",
    "statement.approved",
    "suggestion.adopted",
    "suggestion.dismissed",
    "suggestion.edited",
    "team.approved",
]

_HUMAN_ONLY = [
    "acceptance.decided",
    "acceptance.review_completed",
    "ai_policy.approved",
    "ai_policy.declined",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "client_import.row_decided",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "engine_export.generated",
    "engine_export.marked_exported",
    "eqr.eligibility_approved",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "firm_export.declined",
    "follow_up.sent",
    "fulfilment.voided",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.annual_confirmed",
    "independence.annual_declined",
    "independence.concluded",
    "independence.confirmed",
    "independence.declined",
    "independence.statement_published",
    "legal_hold.lifted",
    "legal_hold.placed",
    "letter.approved",
    "materiality.decided",
    "methodology_version.approved",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "proposal.approved",
    "proposal.approved_with_edits",
    "proposal.rejected",
    "proposal.routed",
    "report.approved",
    "report.released",
    "retention_policy.updated",
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "service_line_policy.updated",
    "sign_off.recorded",
    "statement.approved",
    "suggestion.adopted",
    "suggestion.dismissed",
    "suggestion.edited",
    "team.approved",
]


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


_GUARD = """
CREATE OR REPLACE FUNCTION engagement_letter_versions_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF TG_OP <> 'UPDATE' THEN
        RAISE EXCEPTION 'engagement_letter_versions is insert-only'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.tenant_id, NEW.engagement_id, NEW.version_no, NEW.kind,
        NEW.amends_version_id, NEW.template_version_id, NEW.clause_states,
        NEW.variables, NEW.section_overrides, NEW.fee_terms,
        NEW.generated_document_id, NEW.content_hash, NEW.created_by,
        NEW.created_by_kind, NEW.created_at)
       IS DISTINCT FROM
       (OLD.tenant_id, OLD.engagement_id, OLD.version_no, OLD.kind,
        OLD.amends_version_id, OLD.template_version_id, OLD.clause_states,
        OLD.variables, OLD.section_overrides, OLD.fee_terms,
        OLD.generated_document_id, OLD.content_hash, OLD.created_by,
        OLD.created_by_kind, OLD.created_at) THEN
        RAISE EXCEPTION 'a letter version''s content never changes'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.approved_by IS NOT NULL AND (NEW.approved_by, NEW.approved_at,
        NEW.approval_content_hash) IS DISTINCT FROM (OLD.approved_by, OLD.approved_at,
        OLD.approval_content_hash) THEN
        RAISE EXCEPTION 'an approval is never rewritten'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.final_document_version_id IS NOT NULL
       AND NEW.final_document_version_id IS DISTINCT FROM OLD.final_document_version_id THEN
        RAISE EXCEPTION 'an approval is never rewritten'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.status = 'partner_approved' AND OLD.status IS DISTINCT FROM 'partner_approved' AND (
        current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
        OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.approved_by::text
    ) THEN
        RAISE EXCEPTION 'only the approving person approves a letter'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
        (OLD.status = 'draft' AND NEW.status IN ('partner_approved', 'superseded'))
        OR (OLD.status = 'partner_approved' AND NEW.status IN ('sent', 'superseded'))
        OR (OLD.status = 'sent' AND NEW.status IN ('signed', 'superseded'))
    ) THEN
        RAISE EXCEPTION 'letter version % cannot move from % to %',
            OLD.id, OLD.status, NEW.status USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$
"""


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE engagement_letter_versions
            ADD COLUMN approval_requested_at timestamptz NULL,
            ADD COLUMN approval_requested_by uuid NULL,
            ADD COLUMN final_document_version_id uuid NULL,
            ADD CONSTRAINT engagement_letter_versions_request
                CHECK ((approval_requested_at IS NULL) = (approval_requested_by IS NULL)),
            ADD CONSTRAINT engagement_letter_versions_final
                CHECK (final_document_version_id IS NULL OR approved_by IS NOT NULL)
        """
    )
    op.execute(
        "GRANT UPDATE (approval_requested_at, approval_requested_by, final_document_version_id) "
        "ON engagement_letter_versions TO abacus_app"
    )
    op.execute(_GUARD)
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_BEFORE)
    op.execute(
        """
        ALTER TABLE engagement_letter_versions
            DROP CONSTRAINT engagement_letter_versions_final,
            DROP CONSTRAINT engagement_letter_versions_request,
            DROP COLUMN final_document_version_id,
            DROP COLUMN approval_requested_by,
            DROP COLUMN approval_requested_at
        """
    )
