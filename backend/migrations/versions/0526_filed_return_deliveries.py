"""Filed-return delivery (T-01-T41; T-01 §3.14; DEC-1571). Expand-only.

`filed_return_deliveries` (insert-only): client service released an accepted return's client
copy (the approved packet's `client_copy` engine PDF, an evidence version) to the household's
portal scope. A person's act only: `actor_kind = 'human'` is a CHECK, and `return.delivered`
joins `abacus_human_only_actions()` (the downgrade restores 0525's list). When R-02's C10
deliverables registry lands, each row is registered there by its id (the migration path: the
row keeps the engagement, client, return and version C10 needs). Tax's table, forced RLS.

Classification (ADR-031): ids Internal; `published_at` Confidential.

Revision ID: 0526
Revises: 0525
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0526"
down_revision = "0525"
branch_labels = None
depends_on = None

INSERT = (
    "id",
    "tenant_id",
    "return_id",
    "engagement_id",
    "client_id",
    "packet_id",
    "evidence_version_id",
    "published_by",
    "actor_kind",
)
# docs/architecture/human-only-actions.yaml as of this migration (a drift test holds them).
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
    "delivery_packet.approved",
    "efile_ack.recorded",
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
    "return.delivered",
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
    "transmission.recorded",
]
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
    "delivery_packet.approved",
    "efile_ack.recorded",
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
    "transmission.recorded",
]


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE filed_return_deliveries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            client_id uuid NOT NULL,
            packet_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            published_by uuid NOT NULL,
            published_at timestamptz NOT NULL DEFAULT abacus_now(),
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, return_id, evidence_version_id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id)
        )
        """
    )
    tenant_table(op, "filed_return_deliveries")
    op.execute("REVOKE TRUNCATE ON filed_return_deliveries FROM abacus_app")
    insert_only(op, "filed_return_deliveries")
    insert_columns(op, "filed_return_deliveries", INSERT)
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_BEFORE)
    op.execute("DROP TABLE filed_return_deliveries")
