"""The letter envelope's withdrawal (N-02-T35; N-02 §3.11; ENG-04; DEC-1480). Expand-only.

A letter whose envelope was declined, expired or voided goes back to its partner approval with the
envelope cleared, so a fresh Send drafts a new one (DEC-1468's "Not here"). `engagement_letter_
versions_guard` (0563's) is replaced so that:
- `sent` may move back to `partner_approved` only while the envelope is cleared in the same
  update; the approval, its hash and the final document never change;
- an envelope is cleared only to `partner_approved`, by a person (`app.actor_kind` human).
Nothing else changes; the downgrade restores 0563's guard.

Revision ID: 0567
Revises: 0566
"""

from __future__ import annotations

from alembic import op

revision = "0567"
down_revision = "0566"
branch_labels = None
depends_on = None

_BEFORE = """
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
    IF OLD.envelope_id IS NOT NULL AND NEW.envelope_id IS DISTINCT FROM OLD.envelope_id
       AND NOT (NEW.envelope_id IS NULL AND NEW.status = 'partner_approved'
                AND current_setting('app.actor_kind', true) = 'human') THEN
        RAISE EXCEPTION 'a letter''s envelope is cleared only by a person''s withdrawal'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.status = 'partner_approved' AND OLD.status = 'sent'
       AND OLD.envelope_id IS NOT NULL AND NEW.envelope_id IS NULL THEN
        RETURN NEW;  -- the withdrawal above: no new approval is being recorded
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
        -- N-02-T35: a withdrawn envelope (declined, expired or voided) takes the letter back to
        -- its approval, the envelope cleared; the approval and content stay as they were.
        OR (OLD.status = 'sent' AND NEW.status = 'partner_approved'
            AND OLD.envelope_id IS NOT NULL AND NEW.envelope_id IS NULL)
    ) THEN
        RAISE EXCEPTION 'letter version % cannot move from % to %',
            OLD.id, OLD.status, NEW.status USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$
"""


def upgrade() -> None:
    op.execute(_GUARD)


def downgrade() -> None:
    op.execute(_BEFORE)
