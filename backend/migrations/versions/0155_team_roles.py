"""P-07-T30 (M4): team and roles for ENG-05 (P-07 §4.2 M4; SPEC-332; DEC-327).

- `engagement_members` + `budget_hours numeric(7,1) NULL` (never negative), `shown_on_portal
  bool NOT NULL DEFAULT false` (POR-02's team card) and `proposed_at timestamptz` (when the
  person joined the team: new rows default to the insert time; rows from before stay NULL, so
  they never read as a change since an approval). The app may update `budget_hours` and
  `shown_on_portal` only; roles and removals stay behind the 0027 definers.
- `team_member_set_role` and `team_member_remove` (0027) are redefined to handle `specialist`
  (and, for removal, `eqr_reviewer`, so the EQR can be replaced). The last-partner rule stands.
- `team_approvals` (new, insert-only): the engagement partner's approval of the team, with the
  sha256 of the member set it approved. `actor_kind` must be `human`.
- `eqr_eligibility_approvals` (new, insert-only): the quality owner's approval of an EQR
  candidate, the checks as codes and the result. `actor_kind` must be `human`.
- The human-only register gains `team.approved` and `eqr.eligibility_approved`:
  `abacus_human_only_actions()` is 0135's 28 entries plus these two; the downgrade restores
  exactly 0135's list.

Revision ID: 0155
Revises: 0146
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0155"
down_revision = "0146"
branch_labels = None
depends_on = None

# The register as 0135 left it (28 entries).
_HUMAN_ONLY_0135 = sorted(
    [
        "assurance.phase_recorded",
        "engagement.acceptance_recorded",
        "engagement.accepted",
        "engagement.letter_recorded",
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
        "procedure.concluded",
        "report.approved",
        "report.released",
        "retention_policy.updated",
        "review.decided",
        "review.released",
        "risk.approved",
        "sample.approved",
        "sign_off.recorded",
        "statement.approved",
        "review_decision.created",
        "review_decision.undone",
    ]
)
_HUMAN_ONLY = sorted([*_HUMAN_ONLY_0135, "team.approved", "eqr.eligibility_approved"])

_STAFF_0027 = "'engagement_partner', 'manager', 'senior', 'staff', 'reviewer'"
_TEAM = f"{_STAFF_0027}, 'specialist'"
_REMOVABLE = f"{_TEAM}, 'eqr_reviewer'"

_SET_ROLE = """
    CREATE OR REPLACE FUNCTION team_member_set_role(p_engagement uuid, p_user uuid, p_role text)
    RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public, pg_temp
    SET statement_timeout = '5s'
    AS $$
    DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
            v_current text;
    BEGIN
        IF p_role NOT IN ({roles}) THEN
            RAISE EXCEPTION 'not a staff role' USING ERRCODE = 'check_violation';
        END IF;
        SELECT role INTO v_current FROM public.engagement_members
         WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user
         FOR UPDATE;
        IF v_current IS NULL OR v_current NOT IN ({roles}) THEN
            RETURN 'not_found';
        END IF;
        IF v_current = 'engagement_partner' AND p_role <> 'engagement_partner' AND NOT EXISTS (
            SELECT 1 FROM public.engagement_members
             WHERE tenant_id = v_tenant AND engagement_id = p_engagement
               AND role = 'engagement_partner' AND user_id <> p_user
        ) THEN
            RETURN 'last_partner';
        END IF;
        UPDATE public.engagement_members SET role = p_role
         WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user;
        RETURN 'ok';
    END $$
"""
_REMOVE = """
    CREATE OR REPLACE FUNCTION team_member_remove(p_engagement uuid, p_user uuid)
    RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public, pg_temp
    SET statement_timeout = '5s'
    AS $$
    DECLARE v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
            v_current text;
    BEGIN
        SELECT role INTO v_current FROM public.engagement_members
         WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user
         FOR UPDATE;
        IF v_current IS NULL OR v_current NOT IN ({roles}) THEN
            RETURN 'not_found';
        END IF;
        IF v_current = 'engagement_partner' AND NOT EXISTS (
            SELECT 1 FROM public.engagement_members
             WHERE tenant_id = v_tenant AND engagement_id = p_engagement
               AND role = 'engagement_partner' AND user_id <> p_user
        ) THEN
            RETURN 'last_partner';
        END IF;
        DELETE FROM public.engagement_members
         WHERE tenant_id = v_tenant AND engagement_id = p_engagement AND user_id = p_user;
        RETURN 'ok';
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
    # --- engagement_members ----------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE engagement_members
            ADD COLUMN budget_hours numeric(7, 1) NULL CHECK (budget_hours >= 0),
            ADD COLUMN shown_on_portal boolean NOT NULL DEFAULT false,
            ADD COLUMN proposed_at timestamptz NULL
        """
    )
    op.execute(
        "ALTER TABLE engagement_members ALTER COLUMN proposed_at SET DEFAULT clock_timestamp()"
    )
    op.execute("GRANT UPDATE (budget_hours, shown_on_portal) ON engagement_members TO abacus_app")
    op.execute(_SET_ROLE.format(roles=_TEAM))
    op.execute(_REMOVE.format(roles=_REMOVABLE))

    # --- team_approvals --------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE team_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            approved_by uuid NOT NULL,
            approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            member_set_hash text NOT NULL CHECK (member_set_hash ~ '^[0-9a-f]{64}$'),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX team_approvals_by_engagement ON team_approvals "
        "(tenant_id, engagement_id, approved_at)"
    )
    _insert_only("team_approvals")
    insert_columns(
        op, "team_approvals", ("tenant_id", "engagement_id", "approved_by", "member_set_hash")
    )

    # --- eqr_eligibility_approvals ---------------------------------------------------------
    op.execute(
        """
        CREATE TABLE eqr_eligibility_approvals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            candidate_user_id uuid NOT NULL,
            checks jsonb NOT NULL CHECK (jsonb_typeof(checks) = 'array'),
            result text NOT NULL CHECK (result IN ('eligible', 'not_eligible')),
            approved_by uuid NOT NULL CHECK (approved_by <> candidate_user_id),
            approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind = 'human'),
            FOREIGN KEY (tenant_id, engagement_id) REFERENCES engagements (tenant_id, id)
        )
        """
    )
    op.execute(
        "CREATE INDEX eqr_eligibility_approvals_by_engagement ON eqr_eligibility_approvals "
        "(tenant_id, engagement_id, candidate_user_id, approved_at)"
    )
    _insert_only("eqr_eligibility_approvals")
    insert_columns(
        op,
        "eqr_eligibility_approvals",
        ("tenant_id", "engagement_id", "candidate_user_id", "checks", "result", "approved_by"),
    )

    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_HUMAN_ONLY_0135)
    for table in ("eqr_eligibility_approvals", "team_approvals"):
        op.execute(f"DROP TABLE {table}")
        op.execute(f"DROP FUNCTION {table}_immutable()")
    # 0027's definitions, exactly; a specialist or EQR row is refused by them again.
    op.execute(_SET_ROLE.format(roles=_STAFF_0027))
    op.execute(_REMOVE.format(roles=_STAFF_0027))
    op.execute(
        "REVOKE UPDATE (budget_hours, shown_on_portal) ON engagement_members FROM abacus_app"
    )
    op.execute(
        """
        ALTER TABLE engagement_members
            DROP COLUMN proposed_at,
            DROP COLUMN shown_on_portal,
            DROP COLUMN budget_hours
        """
    )
