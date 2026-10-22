"""Database business time (F-04-T06; ADR-143, P-37; DEC-27; chapter F-04 §4.3).

- `abacus_now()`: for a synthetic firm only (`firms.synthetic`, which only the owner can write,
  0038), the transaction's `app.now` when set (a frozen replay or the process demo clock), else
  its `firm_demo_clocks` row when `app.demo_clocks` is on (set outside production only, F-04.2);
  otherwise `clock_timestamp()`. A real tenant can't be moved by any setting (F-04.3). Reading
  the demo clock here keeps the business clock to the transaction's own connection.
- Business timestamps default to `abacus_now()`: the 111 columns in `SWITCHED` below, generated
  from the database at this revision (every `clock_timestamp()` or `now()` default) minus the
  ones that stay system time: `audit_events.occurred_at`, `outbox.occurred_at`, `eval_runs`,
  budgets and usage (spend), sign-up, invitation-token and support-session (security) columns,
  connection secrets and OAuth states, `users` and `firms` (no tenant), feature flags, and the
  access configuration (`client_access_events`, firm policy overrides and setting values).
- `audit_events.effective_at`: business time beside `occurred_at` (system truth), backfilled from
  it; only its default writes it (the app's column-level INSERT grant leaves it out).
- `firm_demo_clocks` (identity): a synthetic firm's demo clock, `offset` or `frozen`; a trigger
  refuses a row for any firm that isn't synthetic.

Revision ID: 0085
Revises: 0084
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None

_ACTOR_CHECK = (
    "ALTER TABLE audit_events ADD CONSTRAINT audit_events_actor_is_transaction_actor CHECK ("
    "actor_kind IS NOT DISTINCT FROM NULLIF(current_setting('app.actor_kind', true), '') "
    "AND actor_id IS NOT DISTINCT FROM NULLIF(current_setting('app.actor_id', true), ''))"
)
# (table, column, the default it had): every business timestamp default, switched.
SWITCHED: tuple[tuple[str, str, str], ...] = (
    ("adjustment_events", "created_at", "clock_timestamp()"),
    ("adjustments", "created_at", "clock_timestamp()"),
    ("agent_activity", "created_at", "now()"),
    ("agent_runs", "started_at", "clock_timestamp()"),
    ("agent_stages", "created_at", "clock_timestamp()"),
    ("archives", "created_at", "clock_timestamp()"),
    ("client_access_grants", "created_at", "clock_timestamp()"),
    ("client_entities", "created_at", "clock_timestamp()"),
    ("client_invitations", "created_at", "clock_timestamp()"),
    ("client_item_responses", "created_at", "clock_timestamp()"),
    ("client_list_done", "created_at", "clock_timestamp()"),
    ("clients", "created_at", "clock_timestamp()"),
    ("comment_redactions", "created_at", "clock_timestamp()"),
    ("comments", "created_at", "clock_timestamp()"),
    ("completion_records", "created_at", "clock_timestamp()"),
    ("connections", "created_at", "clock_timestamp()"),
    ("contacts", "created_at", "clock_timestamp()"),
    ("engagement_acceptance", "created_at", "clock_timestamp()"),
    ("engagement_accounts", "created_at", "clock_timestamp()"),
    ("engagement_agents", "updated_at", "now()"),
    ("engagement_contacts", "designated_at", "clock_timestamp()"),
    ("engagement_entities", "created_at", "clock_timestamp()"),
    ("engagement_letters", "recorded_at", "clock_timestamp()"),
    ("engagement_materiality", "created_at", "clock_timestamp()"),
    ("engagement_members", "created_at", "clock_timestamp()"),
    ("engagements", "created_at", "clock_timestamp()"),
    ("entry_assessments", "created_at", "clock_timestamp()"),
    ("eqr_concurrences", "created_at", "clock_timestamp()"),
    ("ethical_walls", "created_at", "clock_timestamp()"),
    ("evidence_items", "created_at", "clock_timestamp()"),
    ("evidence_versions", "created_at", "clock_timestamp()"),
    ("fieldwork_settings", "created_at", "clock_timestamp()"),
    ("finding_communications", "created_at", "clock_timestamp()"),
    ("finding_severities", "created_at", "clock_timestamp()"),
    ("findings", "created_at", "clock_timestamp()"),
    ("fulfilments", "created_at", "clock_timestamp()"),
    ("gate_policy_overrides", "created_at", "clock_timestamp()"),
    ("gl_imports", "created_at", "now()"),
    ("gl_imports", "updated_at", "now()"),
    ("gl_snapshots", "created_at", "clock_timestamp()"),
    ("grouping_set_versions", "created_at", "clock_timestamp()"),
    ("grouping_sets", "created_at", "clock_timestamp()"),
    ("guidance_draft_decisions", "created_at", "clock_timestamp()"),
    ("guidance_drafts", "created_at", "clock_timestamp()"),
    ("inbox_files", "created_at", "clock_timestamp()"),
    ("inbox_match_runs", "created_at", "clock_timestamp()"),
    ("independence_confirmations", "requested_at", "clock_timestamp()"),
    ("item_results", "created_at", "clock_timestamp()"),
    ("item_signoffs", "created_at", "clock_timestamp()"),
    ("item_support_requests", "created_at", "clock_timestamp()"),
    ("knowledge_documents", "created_at", "clock_timestamp()"),
    ("ledger_imports", "created_at", "now()"),
    ("ledger_snapshots", "created_at", "clock_timestamp()"),
    ("mapping_set_edits", "created_at", "clock_timestamp()"),
    ("mapping_sets", "created_at", "clock_timestamp()"),
    ("materiality_decisions", "created_at", "clock_timestamp()"),
    ("memberships", "created_at", "clock_timestamp()"),
    ("messages", "created_at", "clock_timestamp()"),
    ("methodology_templates", "created_at", "clock_timestamp()"),
    ("methodology_versions", "created_at", "clock_timestamp()"),
    ("misstatements", "created_at", "clock_timestamp()"),
    ("notifications", "created_at", "clock_timestamp()"),
    ("offices", "created_at", "clock_timestamp()"),
    ("populations", "created_at", "clock_timestamp()"),
    ("procedure_conclusions", "created_at", "clock_timestamp()"),
    ("procedure_session_events", "created_at", "clock_timestamp()"),
    ("procedure_workpaper_signatures", "created_at", "clock_timestamp()"),
    ("procedure_workpaper_versions", "created_at", "clock_timestamp()"),
    ("procedures", "created_at", "clock_timestamp()"),
    ("releases", "created_at", "clock_timestamp()"),
    ("reminders", "created_at", "now()"),
    ("representation_removals", "created_at", "clock_timestamp()"),
    ("representations", "created_at", "clock_timestamp()"),
    ("request_items", "created_at", "clock_timestamp()"),
    ("request_lists", "created_at", "clock_timestamp()"),
    ("review_assignments", "assigned_at", "clock_timestamp()"),
    ("review_decisions", "created_at", "clock_timestamp()"),
    ("review_note_events", "created_at", "clock_timestamp()"),
    ("review_notes", "created_at", "clock_timestamp()"),
    ("reviewable_note_events", "created_at", "clock_timestamp()"),
    ("reviewable_notes", "created_at", "clock_timestamp()"),
    ("risk_approvals", "created_at", "clock_timestamp()"),
    ("risk_versions", "created_at", "clock_timestamp()"),
    ("risks", "created_at", "clock_timestamp()"),
    ("screening_results", "created_at", "clock_timestamp()"),
    ("selection_approvals", "created_at", "clock_timestamp()"),
    ("selections", "created_at", "clock_timestamp()"),
    ("sign_offs", "created_at", "clock_timestamp()"),
    ("staff_invitations", "created_at", "clock_timestamp()"),
    ("statement_datasets", "created_at", "clock_timestamp()"),
    ("sync_runs", "started_at", "clock_timestamp()"),
    ("team_rosters", "added_at", "clock_timestamp()"),
    ("teams", "created_at", "clock_timestamp()"),
    ("template_guidance_decisions", "created_at", "clock_timestamp()"),
    ("template_guidance_drafts", "created_at", "clock_timestamp()"),
    ("tie_out_check_versions", "created_at", "clock_timestamp()"),
    ("tie_out_checks", "created_at", "clock_timestamp()"),
    ("trial_balance_annotations", "created_at", "clock_timestamp()"),
    ("trial_balance_versions", "created_at", "clock_timestamp()"),
    ("trial_balances", "created_at", "clock_timestamp()"),
    ("upload_checks", "created_at", "clock_timestamp()"),
    ("upload_extractions", "created_at", "clock_timestamp()"),
    ("upload_previews", "created_at", "clock_timestamp()"),
    ("upload_reviews", "created_at", "clock_timestamp()"),
    ("work_item_assignments", "assigned_at", "clock_timestamp()"),
    ("work_items", "created_at", "clock_timestamp()"),
    ("workpaper_cell_citations", "created_at", "clock_timestamp()"),
    ("workpaper_cells", "created_at", "clock_timestamp()"),
    ("workpaper_sections", "created_at", "clock_timestamp()"),
    ("workpaper_versions", "created_at", "clock_timestamp()"),
    ("workpapers", "created_at", "clock_timestamp()"),
)


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION abacus_now() RETURNS timestamptz
        LANGUAGE plpgsql VOLATILE SECURITY INVOKER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
            v_clock record;
        BEGIN
            IF v_tenant IS NULL OR NOT coalesce(
                (SELECT f.synthetic FROM public.firms f WHERE f.tenant_id = v_tenant), false
            ) THEN
                RETURN clock_timestamp();
            END IF;
            IF NULLIF(current_setting('app.now', true), '') IS NOT NULL THEN
                RETURN current_setting('app.now', true)::timestamptz;
            END IF;
            IF current_setting('app.demo_clocks', true) = 'on' THEN
                SELECT mode, anchor_at, anchored_real_at INTO v_clock
                  FROM public.firm_demo_clocks WHERE tenant_id = v_tenant;
                IF FOUND THEN
                    IF v_clock.mode = 'frozen' THEN
                        RETURN v_clock.anchor_at;
                    END IF;
                    RETURN v_clock.anchor_at + (clock_timestamp() - v_clock.anchored_real_at);
                END IF;
            END IF;
            RETURN clock_timestamp();
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION abacus_now() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION abacus_now() TO abacus_app")
    for table, column, _ in SWITCHED:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT abacus_now()")

    op.execute("ALTER TABLE audit_events ADD COLUMN effective_at timestamptz NULL")
    # Backfill as the owner, who is held to row-level security too (as 0068 does). The actor
    # check compares a row with the *current* transaction's actor, so it would refuse any
    # update of past rows: it is lifted for the backfill and comes back NOT VALID (every new row
    # is checked; past rows were checked when written).
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_is_transaction_actor")
    op.execute("ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY")
    op.execute("UPDATE audit_events SET effective_at = occurred_at")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute(_ACTOR_CHECK + " NOT VALID")
    op.execute(
        "ALTER TABLE audit_events ALTER COLUMN effective_at SET NOT NULL, "
        "ALTER COLUMN effective_at SET DEFAULT abacus_now()"
    )

    op.execute(
        """
        CREATE TABLE firm_demo_clocks (
            tenant_id uuid PRIMARY KEY REFERENCES firms (tenant_id),
            mode text NOT NULL CHECK (mode IN ('offset', 'frozen')),
            anchor_at timestamptz NOT NULL,
            anchored_real_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            set_by text NOT NULL CHECK (length(set_by) BETWEEN 1 AND 200),
            set_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    tenant_table(op, "firm_demo_clocks")
    insert_columns(op, "firm_demo_clocks", ("tenant_id", "mode", "anchor_at", "set_by"))
    op.execute("REVOKE UPDATE ON firm_demo_clocks FROM abacus_app")
    op.execute(
        "GRANT UPDATE (mode, anchor_at, anchored_real_at, set_by, set_at) "
        "ON firm_demo_clocks TO abacus_app"
    )
    op.execute(
        """
        CREATE FUNCTION firm_demo_clocks_synthetic() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NOT coalesce((SELECT f.synthetic FROM public.firms f
                              WHERE f.tenant_id = NEW.tenant_id), false) THEN
                RAISE EXCEPTION 'a demo clock is for synthetic firms only'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER firm_demo_clocks_synthetic BEFORE INSERT OR UPDATE ON firm_demo_clocks "
        "FOR EACH ROW EXECUTE FUNCTION firm_demo_clocks_synthetic()"
    )


def downgrade() -> None:
    op.execute("DROP TABLE firm_demo_clocks")
    op.execute("DROP FUNCTION firm_demo_clocks_synthetic()")
    op.execute("ALTER TABLE audit_events DROP COLUMN effective_at")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_is_transaction_actor")
    op.execute(_ACTOR_CHECK + " NOT VALID")  # past rows were checked when written
    for table, column, before in SWITCHED:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {before}")
    op.execute("DROP FUNCTION abacus_now()")
