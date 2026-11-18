"""Season setup (T-08-T05; SPEC-710 AC-1 to AC-8, AC-35; T-08 §4.2; DEC-5604). Expand-only; the
pipeline runs it after 8 pm CT inside the window (P-29).

Eight engagements tables with forced RLS: `seasons`, `season_manifests` (one `ready` per season),
`season_cohorts`, `season_manifest_rows`, `season_asks`, and three insert-only tables:
`season_cohort_approvals` and `season_cohort_withdrawals` (human-only, bound to the session's
actor GUCs) and `season_row_steps` (the execution log; "31 of 42" is computed from it).

`season_rows_frozen` refuses an update of a row whose cohort holds an approval that was not
withdrawn (AC-3: 409 `cohort_approved` in the service, the trigger behind it), and
`season_withdrawal_before_start` refuses a withdrawal once a step of that cohort ran (AC-5).
Tallies, derived statuses and counts are never stored. Rows carry contacts, so they are
`confidential`; nothing here is TRI.

Revision ID: 0960
Revises: 0954
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0960"
down_revision = "0954"
branch_labels = None
depends_on = None

_ID = """
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,"""
_KEYS = """
            UNIQUE (tenant_id, id)"""
_HUMAN = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)),"
)

# (table, body, insert columns, update columns, insert-only)
TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    ("seasons", """
            tax_year integer NOT NULL CHECK (tax_year BETWEEN 2020 AND 2100),
            opened_by uuid NOT NULL,
            opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, tax_year),""",
     ("tenant_id", "tax_year", "opened_by"), (), False),
    ("season_manifests", """
            season_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            status text NOT NULL DEFAULT 'building'
                CHECK (status IN ('building', 'ready', 'superseded')),
            inputs_hash text NOT NULL CHECK (inputs_hash ~ '^[0-9a-f]{64}$'),
            planner_run_id uuid NULL,
            built_by uuid NOT NULL,
            built_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (season_id, version),
            FOREIGN KEY (tenant_id, season_id) REFERENCES seasons (tenant_id, id),""",
     ("tenant_id", "season_id", "version", "status", "inputs_hash", "planner_run_id", "built_by"),
     ("status", "planner_run_id"), False),
    ("season_cohorts", """
            manifest_id uuid NOT NULL,
            position smallint NOT NULL CHECK (position BETWEEN 1 AND 99),
            office_id uuid NOT NULL,
            segment text NOT NULL CHECK (segment IN ('individuals_trusts', 'entities_exempt')),
            approver_user_id uuid NULL,
            status text NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'approved', 'executing', 'executed', 'failed')),
            UNIQUE (manifest_id, position),
            UNIQUE (manifest_id, office_id, segment),
            FOREIGN KEY (tenant_id, manifest_id) REFERENCES season_manifests (tenant_id, id),""",
     ("tenant_id", "manifest_id", "position", "office_id", "segment", "approver_user_id"),
     ("status", "approver_user_id"), False),
    ("season_manifest_rows", """
            cohort_id uuid NOT NULL,
            client_id uuid NOT NULL,
            client_entity_ids uuid[] NOT NULL DEFAULT '{}',
            forms text[] NOT NULL CHECK (cardinality(forms) BETWEEN 1 AND 20),
            preparer_user_id uuid NULL,
            reviewer_user_id uuid NULL,
            signer_user_id uuid NULL,
            prior_engagement_id uuid NULL,
            binder_source jsonb NOT NULL CHECK (jsonb_typeof(binder_source) = 'object'),
            letter_plan jsonb NOT NULL CHECK (jsonb_typeof(letter_plan) = 'object'),
            consent_purposes text[] NOT NULL DEFAULT '{}',
            invitee_contact_ids uuid[] NOT NULL DEFAULT '{}',
            exception_codes text[] NOT NULL DEFAULT '{}',
            excluded_at timestamptz NULL,
            excluded_by uuid NULL,
            exclusion_reason text NULL CHECK (exclusion_reason IN
                ('client_departed', 'not_continuing', 'duplicate', 'other')),
            row_version integer NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            CONSTRAINT season_manifest_rows_exclusion CHECK (
                (excluded_at IS NULL) = (excluded_by IS NULL)
                AND (excluded_at IS NULL) = (exclusion_reason IS NULL)
            ),
            UNIQUE (cohort_id, client_id),
            FOREIGN KEY (tenant_id, cohort_id) REFERENCES season_cohorts (tenant_id, id),""",
     ("tenant_id", "cohort_id", "client_id", "client_entity_ids", "forms", "preparer_user_id",
      "reviewer_user_id", "signer_user_id", "prior_engagement_id", "binder_source", "letter_plan",
      "consent_purposes", "invitee_contact_ids", "exception_codes"),
     ("preparer_user_id", "reviewer_user_id", "signer_user_id", "exception_codes", "excluded_at",
      "excluded_by", "exclusion_reason", "row_version"), False),
    ("season_asks", """
            manifest_id uuid NOT NULL,
            row_ids uuid[] NOT NULL CHECK (cardinality(row_ids) >= 1),
            question_code text NOT NULL CHECK (question_code ~ '^[a-z][a-z0-9_]{0,59}$'),
            options jsonb NOT NULL CHECK (jsonb_typeof(options) = 'array'),
            recommended_option text NULL CHECK (char_length(recommended_option) <= 40),
            source text NOT NULL CHECK (source IN ('code', 'agent')),
            suggestion_id uuid NULL,
            answered_option text NULL CHECK (char_length(answered_option) <= 40),
            answered_by uuid NULL,
            answered_at timestamptz NULL,
            CONSTRAINT season_asks_answer CHECK (
                (answered_option IS NULL) = (answered_by IS NULL)
                AND (answered_by IS NULL) = (answered_at IS NULL)
            ),
            CONSTRAINT season_asks_agent_suggestion CHECK (
                source = 'code' OR suggestion_id IS NOT NULL
            ),
            FOREIGN KEY (tenant_id, manifest_id) REFERENCES season_manifests (tenant_id, id),""",
     ("tenant_id", "manifest_id", "row_ids", "question_code", "options", "recommended_option",
      "source", "suggestion_id"),
     ("answered_option", "answered_by", "answered_at"), False),
    ("season_cohort_approvals", f"""
            cohort_id uuid NOT NULL,
            manifest_version integer NOT NULL CHECK (manifest_version >= 1),
            rows_hash text NOT NULL CHECK (rows_hash ~ '^[0-9a-f]{{64}}$'),
            approval_grant_id uuid NOT NULL,
            approved_by uuid NOT NULL,
            approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN}
            UNIQUE (approval_grant_id),
            FOREIGN KEY (tenant_id, cohort_id) REFERENCES season_cohorts (tenant_id, id),""",
     ("tenant_id", "cohort_id", "manifest_version", "rows_hash", "approval_grant_id",
      "approved_by"), (), True),
    ("season_cohort_withdrawals", f"""
            approval_id uuid NOT NULL UNIQUE,
            reason text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 500),
            withdrawn_by uuid NOT NULL,
            withdrawn_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {_HUMAN}
            FOREIGN KEY (tenant_id, approval_id)
                REFERENCES season_cohort_approvals (tenant_id, id),""",
     ("tenant_id", "approval_id", "reason", "withdrawn_by"), (), True),
    ("season_row_steps", """
            row_id uuid NOT NULL,
            step text NOT NULL CHECK (step IN ('engagement', 'returns', 'assignments', 'binder',
                'letter', 'consents', 'invitations')),
            attempt smallint NOT NULL CHECK (attempt BETWEEN 1 AND 20),
            status text NOT NULL CHECK (status IN ('ok', 'failed')),
            ref_ids uuid[] NOT NULL DEFAULT '{}',
            error_code text NULL CHECK (error_code ~ '^[a-z][a-z0-9_]{0,59}$'),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT season_row_steps_error
                CHECK ((status = 'failed') = (error_code IS NOT NULL)),
            UNIQUE (row_id, step, attempt),
            FOREIGN KEY (tenant_id, row_id) REFERENCES season_manifest_rows (tenant_id, id),""",
     ("tenant_id", "row_id", "step", "attempt", "status", "ref_ids", "error_code"), (), True),
)  # fmt: skip


def _immutable(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_immutable()"
    )


def upgrade() -> None:
    for table, body, _ins, _upd, _io in TABLES:
        op.execute(f"CREATE TABLE {table} ({_ID}{body}{_KEYS}\n        )")
    op.execute(
        "CREATE UNIQUE INDEX season_manifests_one_ready ON season_manifests (season_id) "
        "WHERE status = 'ready'"
    )
    for table, _body, ins, upd, io in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, list(ins))
        if io:
            insert_only(op, table)
            _immutable(table)
        else:
            op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
            if upd:
                op.execute(f"GRANT UPDATE ({', '.join(upd)}) ON {table} TO abacus_app")
    # AC-3: an approved cohort's rows are frozen until its approval is withdrawn.
    op.execute(
        """
        CREATE FUNCTION season_rows_frozen() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM season_cohort_approvals a
                WHERE a.tenant_id = OLD.tenant_id AND a.cohort_id = OLD.cohort_id
                  AND NOT EXISTS (
                      SELECT 1 FROM season_cohort_withdrawals w
                      WHERE w.tenant_id = a.tenant_id AND w.approval_id = a.id
                  )
            ) THEN
                RAISE EXCEPTION 'cohort_approved' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER season_rows_frozen BEFORE UPDATE ON season_manifest_rows "
        "FOR EACH ROW EXECUTE FUNCTION season_rows_frozen()"
    )
    # AC-5: a withdrawal after the cohort's first step is refused.
    op.execute(
        """
        CREATE FUNCTION season_withdrawal_before_start() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM season_cohort_approvals a
                JOIN season_manifest_rows r
                  ON r.tenant_id = a.tenant_id AND r.cohort_id = a.cohort_id
                JOIN season_row_steps s ON s.tenant_id = r.tenant_id AND s.row_id = r.id
                WHERE a.tenant_id = NEW.tenant_id AND a.id = NEW.approval_id
            ) THEN
                RAISE EXCEPTION 'execution_started' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER season_withdrawal_before_start BEFORE INSERT ON season_cohort_withdrawals "
        "FOR EACH ROW EXECUTE FUNCTION season_withdrawal_before_start()"
    )


def downgrade() -> None:
    for table, _body, _ins, _upd, _io in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION season_withdrawal_before_start()")
    op.execute("DROP FUNCTION season_rows_frozen()")
    for table, _body, _ins, _upd, io in TABLES:
        if io:
            op.execute(f"DROP FUNCTION {table}_immutable()")
