"""Q-05-T12 (S51 partials, TASK-8730; DEC-5724; SPEC-711 AC-15 to AC-18): a post-issuance case
carries its source evidence version and the engagement partner's decision.

- `type` gains `reissuance_request` (AUD-30 f lists three types; 0984 had two).
- `source_evidence_version_id` (the filed certification, when the source is the inbox).
- `decision` (no_action, revise_and_reissue, notify_users), `decided_by`, `decided_at` and a
  sealed rationale: the EP decides on the case row itself. The audit is locked and its decision
  cards are behind `archived_guard()`; the case row is the one table the `post_issuance` kind
  reaches (ADR P-43), so the decision lives there. Human-only (a CHECK on `app.actor_kind`).

Revision ID: 0986
Revises: 0985
"""

from __future__ import annotations

from alembic import op

revision = "0986"
down_revision = "0985"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE post_issuance_events DROP CONSTRAINT post_issuance_events_type_check")
    op.execute(
        "ALTER TABLE post_issuance_events ADD CONSTRAINT post_issuance_events_type_check "
        "CHECK (type IN ('subsequent_fact', 'omitted_procedure', 'reissuance_request'))"
    )
    op.execute(
        "ALTER TABLE post_issuance_events "
        "ADD COLUMN source_evidence_version_id uuid NULL, "
        "ADD COLUMN decision text NULL "
        "CHECK (decision IN ('no_action', 'revise_and_reissue', 'notify_users')), "
        "ADD COLUMN decided_by uuid NULL, "
        "ADD COLUMN decided_at timestamptz NULL, "
        "ADD COLUMN rationale_sealed bytea NULL CHECK (octet_length(rationale_sealed) <= 65536), "
        "ADD COLUMN decided_actor_kind text NULL "
        "CHECK (decided_actor_kind IS NULL OR (decided_actor_kind = 'human' "
        "AND decided_actor_kind = current_setting('app.actor_kind', true))), "
        "ADD CONSTRAINT post_issuance_events_decided_whole CHECK ("
        "(decision IS NULL) = (decided_by IS NULL) AND (decision IS NULL) = (decided_at IS NULL) "
        "AND (decision IS NULL) = (decided_actor_kind IS NULL) "
        "AND (decision IS NULL OR status = 'decided'))"
    )
    op.execute("GRANT INSERT (source_evidence_version_id) ON post_issuance_events TO abacus_app")
    op.execute(
        "GRANT UPDATE (decision, decided_by, decided_at, rationale_sealed, decided_actor_kind) "
        "ON post_issuance_events TO abacus_app"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE UPDATE (decision, decided_by, decided_at, rationale_sealed, decided_actor_kind) "
        "ON post_issuance_events FROM abacus_app"
    )
    op.execute(
        "REVOKE INSERT (source_evidence_version_id) ON post_issuance_events FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE post_issuance_events DROP CONSTRAINT post_issuance_events_decided_whole, "
        "DROP COLUMN decided_actor_kind, DROP COLUMN rationale_sealed, DROP COLUMN decided_at, "
        "DROP COLUMN decided_by, DROP COLUMN decision, DROP COLUMN source_evidence_version_id"
    )
    op.execute("ALTER TABLE post_issuance_events DROP CONSTRAINT post_issuance_events_type_check")
    op.execute(
        "ALTER TABLE post_issuance_events ADD CONSTRAINT post_issuance_events_type_check "
        "CHECK (type IN ('subsequent_fact', 'omitted_procedure'))"
    )
