"""The transmission record and e-file acknowledgements (T-01-T37; T-01 §3.13, §4.2; R-04;
DEC-1570). Expand-only.

- `transmissions` (insert-only): the designated ERO's record that they transmitted the return from
  the tax engine (federal and states, the date and method), against the 8879 amount binding they
  saw. A person's record only: `actor_kind = 'human'` is a CHECK. Accrued never transmits (R-04).
- `efile_acks` (insert-only): one acknowledgement per jurisdiction, taken up from the engine's
  e-file status report (`engine_acks`, idempotent on the ack's facts) or entered by hand with an
  evidence upload (a CHECK: a manual ack names its evidence version). Only the submission id's
  last four is kept.
- `memberships.ero_designated`: the firm admin's designation (fresh MFA); the app may update this
  column only.
- `abacus_human_only_actions()`: `transmission.recorded` and `efile_ack.recorded` join the list;
  the downgrade restores 0566's.

Classification (ADR-031): reject text TRI (client-system content, ADR-052); jurisdictions, dates
and last four Confidential; ids Internal. Tax's tables, forced RLS.

Revision ID: 0568
Revises: 0567
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0568"
down_revision = "0567"
branch_labels = None
depends_on = None

TRANSMISSION_INSERT = (
    "id",
    "tenant_id",
    "return_id",
    "binding_id",
    "envelope_id",
    "ero_user_id",
    "method",
    "jurisdictions",
    "transmitted_on",
    "recorded_by",
    "actor_kind",
)
ACK_INSERT = (
    "id",
    "tenant_id",
    "return_id",
    "transmission_id",
    "jurisdiction",
    "status",
    "submission_id_last4",
    "reject_code",
    "reject_text",
    "received_at",
    "source",
    "engine_ack_id",
    "evidence_version_id",
    "recorded_by",
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
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "schedule_k_release.requested",
    "schedule_k_release.undone",
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
    "schedule_k_release.requested",
    "schedule_k_release.undone",
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


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE transmissions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            binding_id uuid NOT NULL,
            envelope_id uuid NOT NULL,
            ero_user_id uuid NOT NULL,
            method text NOT NULL CHECK (method IN ('practitioner_pin', 'ero_signature')),
            jurisdictions text[] NOT NULL CHECK (
                cardinality(jurisdictions) BETWEEN 1 AND 60
                AND array_position(jurisdictions, NULL) IS NULL
            ),
            transmitted_on date NOT NULL,
            recorded_by uuid NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT abacus_now(),
            actor_kind text NOT NULL CHECK (actor_kind = 'human'),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id),
            FOREIGN KEY (tenant_id, binding_id) REFERENCES efile_amount_bindings (tenant_id, id),
            CHECK (recorded_by = ero_user_id)
        )
        """
    )
    op.execute("CREATE INDEX transmissions_return ON transmissions (tenant_id, return_id)")
    op.execute(
        """
        CREATE TABLE efile_acks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            return_id uuid NOT NULL,
            transmission_id uuid NULL,
            jurisdiction text NOT NULL CHECK (jurisdiction ~ '^(federal|[A-Z]{2})$'),
            status text NOT NULL CHECK (status IN ('accepted', 'rejected')),
            submission_id_last4 text NOT NULL CHECK (submission_id_last4 ~ '^[A-Za-z0-9]{4}$'),
            reject_code text NULL CHECK (char_length(reject_code) BETWEEN 1 AND 40),
            reject_text text NULL CHECK (char_length(reject_text) <= 2000),
            received_at timestamptz NOT NULL,
            source text NOT NULL CHECK (source IN ('engine_file', 'manual')),
            engine_ack_id uuid NULL,
            evidence_version_id uuid NULL,
            recorded_by uuid NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT abacus_now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (return_id) REFERENCES tax_returns (work_item_id),
            FOREIGN KEY (tenant_id, transmission_id) REFERENCES transmissions (tenant_id, id),
            FOREIGN KEY (tenant_id, engine_ack_id) REFERENCES engine_acks (tenant_id, id),
            CHECK (status <> 'rejected' OR reject_code IS NOT NULL),
            CHECK (source <> 'manual' OR evidence_version_id IS NOT NULL),
            CHECK (source <> 'engine_file' OR engine_ack_id IS NOT NULL)
        )
        """
    )
    # A status report uploaded again (or the same ack typed by hand) is the same ack.
    op.execute(
        "CREATE UNIQUE INDEX efile_acks_once ON efile_acks (tenant_id, return_id, jurisdiction, "
        "status, submission_id_last4, received_at)"
    )
    for table, columns in (("transmissions", TRANSMISSION_INSERT), ("efile_acks", ACK_INSERT)):
        tenant_table(op, table)
        op.execute(f"REVOKE TRUNCATE ON {table} FROM abacus_app")
        insert_only(op, table)
        insert_columns(op, table, columns)
    op.execute("ALTER TABLE memberships ADD COLUMN ero_designated boolean NOT NULL DEFAULT false")
    op.execute("GRANT UPDATE (ero_designated) ON memberships TO abacus_app")
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_BEFORE)
    op.execute("REVOKE UPDATE (ero_designated) ON memberships FROM abacus_app")
    op.execute("ALTER TABLE memberships DROP COLUMN ero_designated")
    op.execute("DROP TABLE efile_acks")
    op.execute("DROP TABLE transmissions")
