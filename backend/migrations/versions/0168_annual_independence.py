"""G-01-T13: seasonal access end and annual independence (G-01 §3.4 AC4.5, §3.6; DEC-91, DEC-381).

- `independence_statements` (new, identity, insert-only): the firm's annual independence
  statement text, one row per version (firm content, set by a firm admin; never seeded). The
  newest version is the one a person confirms.
- `independence_annual_confirmations` (new, identity, insert-only): a person's own confirmation
  or decline for a year, with the statement version they read. A decline carries a note. The
  newest row (`seq`) per person and year wins. `actor_kind` must be `human` (agents and the
  platform never confirm, INV-1); `decided_at` is business time.
- `access_end_notices` (new, identity, insert-only): one row per firm and access-end date once
  firm admins were told, seven days ahead, that seasonal access ends (the job's idempotence).

- Actors (DEC-383): the trigger `independence_own_row` refuses a confirmation whose `user_id`, or
  a statement whose `created_by`, isn't the transaction's `app.actor_id` (one answers only for
  oneself, publishes only as oneself).
- `abacus_human_only_actions()`: 0164's 36 entries (0159's 33 plus 0163's
  `acceptance.decided`, `acceptance.review_completed` and 0164's `conflict.cleared`) plus
  `independence.annual_confirmed`, `independence.annual_declined`,
  `independence.statement_published` and `service_line_policy.updated` (40; ED-011 precedent).
  The downgrade restores 0164's list.

The hourly access-end job lists firm ids through the identity role (which already reads
`firms.tenant_id`) and works inside each firm's own session, so no cross-firm function is added.

Revision ID: 0168
Revises: 0167
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0168"
down_revision = "0167"
branch_labels = None
depends_on = None

_TABLES = ("independence_statements", "independence_annual_confirmations", "access_end_notices")

# The register as 0164 left it (36 entries).
_HUMAN_ONLY_0164 = sorted(
    [
        "acceptance.decided",
        "acceptance.review_completed",
        "conflict.cleared",
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
        "fulfilment.voided",
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
_HUMAN_ONLY = sorted(
    [
        *_HUMAN_ONLY_0164,
        "independence.annual_confirmed",
        "independence.annual_declined",
        "independence.statement_published",
        "service_line_policy.updated",
    ]
)
_OWN_ROW = """
    CREATE FUNCTION independence_own_row() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp
    AS $$
    DECLARE v_person uuid;
    BEGIN
        IF TG_TABLE_NAME = 'independence_annual_confirmations' THEN
            v_person := NEW.user_id;
        ELSE
            v_person := NEW.created_by;
        END IF;
        IF v_person::text IS DISTINCT FROM current_setting('app.actor_id', true) THEN
            RAISE EXCEPTION 'one answers and publishes only as oneself'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END $$
"""


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


def _insert_only(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '{table} is insert-only' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_immutable()"
    )
    tenant_table(op, table)
    op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE independence_statements (
            tenant_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 4000),
            created_by uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT abacus_now(),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'),
            PRIMARY KEY (tenant_id, version),
            FOREIGN KEY (tenant_id, created_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    _insert_only("independence_statements")
    insert_columns(op, "independence_statements", ("tenant_id", "version", "body", "created_by"))

    op.execute(
        """
        CREATE TABLE independence_annual_confirmations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            seq bigint GENERATED ALWAYS AS IDENTITY,
            tenant_id uuid NOT NULL,
            user_id uuid NOT NULL,
            year smallint NOT NULL CHECK (year BETWEEN 2025 AND 2100),
            decision text NOT NULL CHECK (decision IN ('confirmed', 'declined')),
            note text NULL CHECK (note IS NULL OR length(note) BETWEEN 1 AND 1000),
            statement_version integer NOT NULL,
            decided_at timestamptz NOT NULL DEFAULT abacus_now(),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'),
            CONSTRAINT independence_annual_decline_noted
                CHECK (decision = 'confirmed' OR note IS NOT NULL),
            FOREIGN KEY (tenant_id, user_id) REFERENCES memberships (tenant_id, user_id),
            FOREIGN KEY (tenant_id, statement_version)
                REFERENCES independence_statements (tenant_id, version)
        )
        """
    )
    op.execute(
        "CREATE INDEX independence_annual_by_person ON independence_annual_confirmations "
        "(tenant_id, year, user_id, seq DESC)"
    )
    _insert_only("independence_annual_confirmations")
    insert_columns(
        op,
        "independence_annual_confirmations",
        ("tenant_id", "user_id", "year", "decision", "note", "statement_version"),
    )

    op.execute(
        """
        CREATE TABLE access_end_notices (
            tenant_id uuid NOT NULL,
            access_ends_on date NOT NULL,
            members integer NOT NULL CHECK (members >= 1),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, access_ends_on)
        )
        """
    )
    _insert_only("access_end_notices")
    insert_columns(op, "access_end_notices", ("tenant_id", "access_ends_on", "members"))

    op.execute(_OWN_ROW)
    for table in ("independence_statements", "independence_annual_confirmations"):
        op.execute(
            f"CREATE TRIGGER {table}_own_row BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION independence_own_row()"
        )
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_HUMAN_ONLY_0164)
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
        op.execute(f"DROP FUNCTION {table}_immutable()")
    op.execute("DROP FUNCTION independence_own_row()")
