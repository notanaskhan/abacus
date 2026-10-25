"""R-01-T09 remainder (TASK-1248; R-01 Story 2.2; portal-pbc contract): a person voids a wrong
rule link.

- `fulfilments` gains `voided_at`, `voided_by` and `void_reason` (`wrong_request`), all three set
  together. The app may update those three columns only.
- `fulfilments_void_only` (BEFORE UPDATE): the one change a fulfilment ever takes is its void,
  once, of a `rule` link whose version no one has accepted (an `accept` decision, undone or
  not), by the person acting (`app.actor_kind` human, `voided_by` = `app.actor_id`). Anything
  else is refused.
- `abacus_human_only_actions()`: 0156's 32 entries plus `fulfilment.voided` (a decision, ADR-005);
  the downgrade restores 0156's list.
- `evidence_version_voids` (insert-only, tenant-scoped): the version a voided rule link made is
  retired with it, so every evidence read leaves it out as it does a withdrawn one (security
  review): the dropped file is assigned afresh from the inbox. The void is the acting person's.
- The database stamps `voided_at` itself (the app's value is never trusted).

Revision ID: 0159
Revises: 0158
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0159"
down_revision = "0158"
branch_labels = None
depends_on = None

# The register as 0156 left it (32 entries).
_HUMAN_ONLY_0156 = sorted(
    [
        "assurance.phase_recorded",
        "contact.unlocked",
        "engagement.acceptance_recorded",
        "engagement.accepted",
        "engagement.letter_recorded",
        "eqr.eligibility_approved",
        "evidence.accepted",
        "firm.ai_client_data_opted_in",
        "firm_export.approved",
        "firm_export.declined",
        "follow_up.sent",
        "going_concern.decided",
        "guidance_draft.approved",
        "independence.confirmed",
        "independence.declined",
        "legal_hold.lifted",
        "legal_hold.placed",
        "materiality.decided",
        "portal_mfa.reset",
        "procedure.concluded",
        "report.approved",
        "report.released",
        "retention_policy.updated",
        "review.decided",
        "review.released",
        "review_decision.created",
        "review_decision.undone",
        "risk.approved",
        "sample.approved",
        "sign_off.recorded",
        "statement.approved",
        "team.approved",
    ]
)
_HUMAN_ONLY = sorted([*_HUMAN_ONLY_0156, "fulfilment.voided"])


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
        ALTER TABLE fulfilments
            ADD COLUMN voided_at timestamptz NULL,
            ADD COLUMN voided_by uuid NULL,
            ADD COLUMN void_reason text NULL CHECK (void_reason IN ('wrong_request')),
            ADD CONSTRAINT fulfilments_void_whole CHECK (
                (voided_at IS NULL) = (voided_by IS NULL)
                AND (voided_at IS NULL) = (void_reason IS NULL)
            )
        """
    )
    op.execute(
        """
        CREATE FUNCTION fulfilments_void_only() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF (NEW.id, NEW.tenant_id, NEW.engagement_id, NEW.request_item_id,
                NEW.evidence_version_id, NEW.created_by_kind, NEW.created_by_id, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.tenant_id, OLD.engagement_id, OLD.request_item_id,
                OLD.evidence_version_id, OLD.created_by_kind, OLD.created_by_id, OLD.created_at)
            THEN
                RAISE EXCEPTION 'a fulfilment only takes its void'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.voided_at IS NOT NULL OR NEW.voided_at IS NULL THEN
                RAISE EXCEPTION 'a fulfilment is voided once, never restored'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.created_by_kind <> 'rule' THEN
                RAISE EXCEPTION 'only a rule fulfilment is voided'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.voided_by::text THEN
                RAISE EXCEPTION 'a fulfilment void is a person''s own act'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            NEW.voided_at := clock_timestamp();
            IF EXISTS (
                SELECT 1 FROM public.review_decisions d
                 WHERE d.tenant_id = OLD.tenant_id
                   AND d.evidence_version_id = OLD.evidence_version_id
                   AND d.decision = 'accept'
            ) THEN
                RAISE EXCEPTION 'an accepted fulfilment is not voided'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER fulfilments_void_only BEFORE UPDATE ON fulfilments "
        "FOR EACH ROW EXECUTE FUNCTION fulfilments_void_only()"
    )
    op.execute("GRANT UPDATE (voided_at, voided_by, void_reason) ON fulfilments TO abacus_app")
    op.execute(
        """
        CREATE TABLE evidence_version_voids (
            tenant_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            fulfilment_id uuid NOT NULL,
            voided_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, evidence_version_id),
            FOREIGN KEY (tenant_id, engagement_id, evidence_version_id)
                REFERENCES evidence_versions (tenant_id, engagement_id, id),
            FOREIGN KEY (tenant_id, fulfilment_id) REFERENCES fulfilments (tenant_id, id)
        )
        """
    )
    tenant_table(op, "evidence_version_voids")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON evidence_version_voids FROM abacus_app")
    insert_columns(
        op,
        "evidence_version_voids",
        ("tenant_id", "evidence_version_id", "engagement_id", "fulfilment_id", "voided_by"),
    )
    # Only the person voiding, for a fulfilment they voided, of that version.
    op.execute(
        """
        CREATE FUNCTION evidence_version_voids_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.voided_by::text
               OR NOT EXISTS (
                   SELECT 1 FROM public.fulfilments f
                    WHERE f.tenant_id = NEW.tenant_id AND f.id = NEW.fulfilment_id
                      AND f.evidence_version_id = NEW.evidence_version_id
                      AND f.voided_by = NEW.voided_by
               ) THEN
                RAISE EXCEPTION 'a version is retired only with its voided rule link'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER evidence_version_voids_guard BEFORE INSERT ON evidence_version_voids "
        "FOR EACH ROW EXECUTE FUNCTION evidence_version_voids_guard()"
    )
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    # Voided links come back to life with the columns: run this downgrade only before any void.
    op.execute("DROP TABLE evidence_version_voids")
    op.execute("DROP FUNCTION evidence_version_voids_guard()")
    _human_only(_HUMAN_ONLY_0156)
    op.execute("REVOKE UPDATE (voided_at, voided_by, void_reason) ON fulfilments FROM abacus_app")
    op.execute("DROP TRIGGER fulfilments_void_only ON fulfilments")
    op.execute("DROP FUNCTION fulfilments_void_only()")
    op.execute(
        "ALTER TABLE fulfilments DROP CONSTRAINT fulfilments_void_whole, "
        "DROP COLUMN void_reason, DROP COLUMN voided_by, DROP COLUMN voided_at"
    )
