"""The AI policy's drafts and insert-only versions (G-02-T23; ADR-186, ADR-187; SPEC-349 AC-31..38;
G-02 §4.2; DEC-711).

- `autonomy_policy_drafts`: one per firm (`tenant_id` the key), the editable sections over a base
  version, with an optimistic `version` (If-Match).
- `autonomy_policy_versions`: insert-only content. State moves forward only, through one trigger:
  `awaiting_approval` -> `published` | `declined` | `withdrawn`; nothing leaves `published`, and
  "Superseded" is derived, never stored. Content columns never change after insert. A person
  requests and a *different* partner approves: `CHECK (carried_over OR (requested_by IS NOT NULL
  AND approver_user_id IS NOT NULL AND approver_user_id <> requested_by))`. A decision is the
  session's own human actor (`decided_by` must equal `app.actor_id` with `app.actor_kind` human,
  the 0015 pattern), so no agent or system may publish, decline or withdraw.
- **Carry-over back-fill:** every firm gets v1 `published`, `carried_over = true`, its sections the
  compiled defaults (`docs/architecture/ai-policy-defaults.yaml`, frozen here as they stand) with
  `autonomy.level` = its `firms.autonomy_level`, effective now. Written before row-level security
  is turned on, so the owner sees every firm (FORCE is lifted on `firms` for the read). No person
  is named (INV-5); the `carried_over` column is the record (DEC-711).

Revision ID: 0272
Revises: 0271 (renumbered on rebase at the S13 batch merge)
"""

from __future__ import annotations

import json

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0272"
down_revision = "0271"
branch_labels = None
depends_on = None

# The compiled defaults as they stand at this revision (a later change to the YAML does not
# rewrite history).
_DEFAULTS = {
    "auto_mode_defaults": {
        "advisory": False,
        "ebp_audit": False,
        "fs_audit": False,
        "monthly_close": True,
        "notice": False,
        "preparation": False,
        "review_compilation": False,
        "tax_return": True,
    },
    "autonomy": {"level": 1},
    "client_data": {
        "client_drafts_enabled": False,
        "consent_template_ref": None,
        "disclosure_in_letters": True,
        "require_7216_consent": True,
    },
    "gates": [],
    "governance": {
        "accuracy_sample_n": 25,
        "install_role": "manager_plus",
        "override_tolerance_pct": 8,
        "publish_approver": "methodology_owner",
        "trace_retention_years": 7,
    },
    "policy_principal": {"on": False},
}


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE autonomy_policy_drafts (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            base_version_no integer NOT NULL CHECK (base_version_no >= 1),
            sections jsonb NOT NULL CHECK (jsonb_typeof(sections) = 'object'),
            schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version >= 1),
            version integer NOT NULL DEFAULT 0 CHECK (version >= 0),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_by uuid NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE autonomy_policy_versions (
            tenant_id uuid NOT NULL REFERENCES firms (tenant_id),
            version_no integer NOT NULL CHECK (version_no >= 1),
            sections jsonb NOT NULL CHECK (jsonb_typeof(sections) = 'object'),
            schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version >= 1),
            effective_from timestamptz NOT NULL,
            requested_by uuid NULL,
            requested_at timestamptz NULL,
            approver_user_id uuid NULL,
            state text NOT NULL DEFAULT 'awaiting_approval'
                CHECK (state IN ('awaiting_approval', 'published', 'declined', 'withdrawn')),
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            decline_reason text NULL CHECK (length(decline_reason) BETWEEN 1 AND 500),
            carried_over boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, version_no),
            CONSTRAINT autonomy_policy_versions_two_people CHECK (
                carried_over OR (requested_by IS NOT NULL AND approver_user_id IS NOT NULL
                                 AND approver_user_id <> requested_by)
            ),
            CONSTRAINT autonomy_policy_versions_decided CHECK (
                (state = 'awaiting_approval') = (decided_at IS NULL)
                AND (carried_over OR state = 'awaiting_approval' OR decided_by IS NOT NULL)
                AND (state <> 'declined' OR decline_reason IS NOT NULL)
            )
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX autonomy_policy_versions_one_pending ON autonomy_policy_versions "
        "(tenant_id) WHERE state = 'awaiting_approval'"
    )
    # Forward-only state, immutable content, decisions by the session's own human actor.
    op.execute(
        """
        CREATE FUNCTION autonomy_policy_version_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'AI policy versions are never deleted (ADR-186)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NOT NEW.carried_over AND NEW.state <> 'awaiting_approval' THEN
                    RAISE EXCEPTION 'a version starts awaiting approval'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF NOT NEW.carried_over
                   AND (current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                        OR NEW.requested_by::text
                           IS DISTINCT FROM current_setting('app.actor_id', true)) THEN
                    RAISE EXCEPTION 'a version is requested by the session''s own person'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN NEW;
            END IF;
            IF (NEW.tenant_id, NEW.version_no, NEW.sections, NEW.schema_version,
                NEW.effective_from, NEW.requested_by, NEW.requested_at, NEW.approver_user_id,
                NEW.carried_over, NEW.created_at)
               IS DISTINCT FROM
               (OLD.tenant_id, OLD.version_no, OLD.sections, OLD.schema_version,
                OLD.effective_from, OLD.requested_by, OLD.requested_at, OLD.approver_user_id,
                OLD.carried_over, OLD.created_at) THEN
                RAISE EXCEPTION 'an AI policy version''s content is immutable (ADR-186)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF OLD.state <> 'awaiting_approval' OR NEW.state = 'awaiting_approval' THEN
                RAISE EXCEPTION 'an AI policy version''s state moves forward once'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
               OR NEW.decided_by::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
                RAISE EXCEPTION 'an AI policy decision is the session''s own person''s (ADR-005)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.state = 'published'
               AND NEW.decided_by IS DISTINCT FROM OLD.approver_user_id THEN
                RAISE EXCEPTION 'only the named approver publishes (AC-37)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.state = 'withdrawn' AND NEW.decided_by IS DISTINCT FROM OLD.requested_by THEN
                RAISE EXCEPTION 'only the requester withdraws'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER autonomy_policy_versions_guard BEFORE INSERT OR UPDATE OR DELETE "
        "ON autonomy_policy_versions FOR EACH ROW EXECUTE FUNCTION autonomy_policy_version_guard()"
    )

    # Carry-over: every firm's v1, before row-level security on the new table.
    defaults = json.dumps(_DEFAULTS).replace("'", "''")
    op.execute("ALTER TABLE firms NO FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        INSERT INTO autonomy_policy_versions (tenant_id, version_no, sections, effective_from,
            state, decided_at, carried_over)
        SELECT f.tenant_id, 1,
               jsonb_set('{defaults}'::jsonb, '{{autonomy,level}}', to_jsonb(f.autonomy_level)),
               clock_timestamp(), 'published', clock_timestamp(), true
          FROM firms f
        """  # noqa: S608 -- fixed SQL, no input
    )
    op.execute("ALTER TABLE firms FORCE ROW LEVEL SECURITY")

    for table in ("autonomy_policy_drafts", "autonomy_policy_versions"):
        tenant_table(op, table)
    op.execute("REVOKE UPDATE, DELETE ON autonomy_policy_drafts FROM abacus_app")
    op.execute(
        "GRANT UPDATE (base_version_no, sections, schema_version, version, updated_at, "
        "updated_by) ON autonomy_policy_drafts TO abacus_app"
    )
    insert_columns(
        op,
        "autonomy_policy_drafts",
        ("tenant_id", "base_version_no", "sections", "schema_version", "updated_by"),
    )
    op.execute("REVOKE UPDATE, DELETE ON autonomy_policy_versions FROM abacus_app")
    op.execute(
        "GRANT UPDATE (state, decided_by, decided_at, decline_reason) "
        "ON autonomy_policy_versions TO abacus_app"
    )
    insert_columns(
        op,
        "autonomy_policy_versions",
        (
            "tenant_id",
            "version_no",
            "sections",
            "schema_version",
            "effective_from",
            "requested_by",
            "requested_at",
            "approver_user_id",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE autonomy_policy_versions")
    op.execute("DROP FUNCTION autonomy_policy_version_guard()")
    op.execute("DROP TABLE autonomy_policy_drafts")
