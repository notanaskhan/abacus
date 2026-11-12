"""T-05-T20 (S38; TASK-7404; T-05 §4.2 M2; DEC-4403): the tax workbook and the preparer memo,
expand-only.

A-04's workpaper tables take the entity return's workbook; four new `tax` tables hold the memo.
No live-path code reads them yet (they run dark).

- `workpapers.kind` admits `tax_workbook` (one per `tax_return` work item, code "WB"; A-04's
  UNIQUE (work_item_id, code) already holds). Sheets are `workpaper_sections` with
  `band_kind = 'sheet'` and `sheet_key` "01" to "09".
- `workpaper_cells` gains `formula` (the closed grammar's source, validated by code),
  `formula_inputs text[]`, `engine_name` and `engine_version`; a `formula` cell must carry its
  formula. Cells stay insert-only (0072), written only through `review.api.record_value`.
- `workpaper_versions` gains `engine_manifest jsonb` ({engine: version}) and `inputs_hash`;
  `agent_run_id` (0581) is the run link ("Version 2 · Run 2").
- `preparer_memos`: one per work item; `current_version_no`, `figure_fingerprint` (sha256 over
  the cited cell values), `drafted_run_id` and `content_hash` move by column grant. Status is
  derived (Drafting, Adopted at L1, Approved at L2, Stale when the fingerprint differs); nothing
  stores it.
- `preparer_memo_versions` (insert-only): `sections jsonb`, a list of `{key, segments [{text,
  citations [{n, start, end}]}], human_owned}`; `cause` draft, edit or regenerate; who made it
  (`created_by_kind`, `agent_run_id`, `on_behalf_of_user_id`). TRI, so Restricted (ADR-167); never
  model markup (P-24).
- `preparer_memo_events` (insert-only): drafted, section_edited, regenerated, adopted, approved,
  went_stale, with the actor bound to the session's GUCs.
- `planning_opportunities`: from a memo (`source_kind` memo), `status` open only in T-05 (T-08
  widens it to raised, accepted and declined).

Every new row carries its tenant, engagement and work item, so `tenant_table()` attaches forced
RLS, `tenant_isolation` and the `archived_guard`. The pipeline runs it after 8 pm CT inside the
window (P-29).

Revision ID: 0830
Revises: 0821
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0830"
down_revision = "0821"
branch_labels = None
depends_on = None

_PLANNING = (
    "general_audit_planning",
    "risk_assessment",
    "internal_control",
    "service_organizations",
)
_EBP = (
    "ebp_plan",
    "ebp_provisions",
    "ebp_eligibility",
    "ebp_contributions",
    "ebp_distributions_loans",
    "ebp_investments",
    "ebp_form5500",
    "ebp_participant_accounts",
    "ebp_admin_expenses",
)
_TAX = ("tax_workbook",)
_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id),
            FOREIGN KEY (work_item_id) REFERENCES tax_returns (work_item_id) ON DELETE RESTRICT"""
_SHA = "~ '^[0-9a-f]{64}$'"
_CREATED = "created_at timestamptz NOT NULL DEFAULT clock_timestamp()"
# Sections or segments: a JSON list; the shape is code's (P-24).
_SEGMENTS = "jsonb_typeof({col}) = 'array' AND jsonb_array_length({col}) <= 200"

TABLES = (
    "preparer_memos",
    "preparer_memo_versions",
    "preparer_memo_events",
    "planning_opportunities",
)
IMMUTABLE = ("preparer_memo_versions", "preparer_memo_events")
_S = ("tenant_id", "engagement_id", "work_item_id")
INSERTS: dict[str, tuple[str, ...]] = {
    "preparer_memos": (
        *_S, "id", "workpaper_id", "current_version_no", "figure_fingerprint", "drafted_run_id",
        "content_hash",
    ),
    "preparer_memo_versions": (
        *_S, "memo_id", "version_no", "sections", "cause", "created_by_kind", "agent_run_id",
        "on_behalf_of_user_id", "content_hash", "figure_fingerprint",
    ),
    "preparer_memo_events": (*_S, "memo_id", "event", "version_no", "ref"),
    "planning_opportunities": (
        *_S, "id", "memo_id", "source_kind", "title", "body", "citation_ids",
    ),
}  # fmt: skip
UPDATES: dict[str, tuple[str, ...]] = {
    "preparer_memos": (
        "current_version_no", "figure_fingerprint", "drafted_run_id", "content_hash",
        "updated_at",
    ),
    "planning_opportunities": ("title", "body", "citation_ids", "updated_at"),
}  # fmt: skip


def _kinds(kinds: tuple[str, ...]) -> str:
    listed = ", ".join(f"'{k}'" for k in kinds)
    return f"CHECK (kind IN ({listed}))"


def upgrade() -> None:
    op.execute("ALTER TABLE workpapers DROP CONSTRAINT workpapers_kind_check")
    op.execute(
        "ALTER TABLE workpapers ADD CONSTRAINT workpapers_kind_check "
        f"{_kinds(_PLANNING + _EBP + _TAX)}"
    )
    op.execute(
        """
        ALTER TABLE workpaper_cells
            ADD COLUMN formula text NULL CHECK (char_length(formula) BETWEEN 1 AND 2000),
            ADD COLUMN formula_inputs text[] NULL
                CHECK (formula_inputs IS NULL OR cardinality(formula_inputs) <= 200),
            ADD COLUMN engine_name text NULL CHECK (char_length(engine_name) <= 80),
            ADD COLUMN engine_version text NULL CHECK (char_length(engine_version) <= 40),
            ADD CONSTRAINT workpaper_cells_formula_source
                CHECK (value_source <> 'formula' OR formula IS NOT NULL),
            ADD CONSTRAINT workpaper_cells_engine_pair
                CHECK ((engine_name IS NULL) = (engine_version IS NULL))
        """
    )
    op.execute(
        """
        ALTER TABLE workpaper_versions
            ADD COLUMN engine_manifest jsonb NULL
                CHECK (engine_manifest IS NULL OR jsonb_typeof(engine_manifest) = 'object'),
            ADD COLUMN inputs_hash text NULL CHECK (inputs_hash IS NULL OR inputs_hash {sha})
        """.replace("{sha}", _SHA)
    )
    op.execute(
        "GRANT INSERT (formula, formula_inputs, engine_name, engine_version) "
        "ON workpaper_cells TO abacus_app"
    )
    op.execute("GRANT INSERT (engine_manifest, inputs_hash) ON workpaper_versions TO abacus_app")

    op.execute(
        f"""
        CREATE TABLE preparer_memos (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            workpaper_id uuid NULL,
            current_version_no integer NOT NULL DEFAULT 0 CHECK (current_version_no >= 0),
            figure_fingerprint text NULL
                CHECK (figure_fingerprint IS NULL OR figure_fingerprint {_SHA}),
            drafted_run_id uuid NULL,
            content_hash text NULL CHECK (content_hash IS NULL OR content_hash {_SHA}),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (work_item_id),
            FOREIGN KEY (tenant_id, workpaper_id) REFERENCES workpapers (tenant_id, id),
            FOREIGN KEY (drafted_run_id) REFERENCES agent_runs (id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE preparer_memo_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            memo_id uuid NOT NULL,
            version_no integer NOT NULL CHECK (version_no >= 1),
            sections jsonb NOT NULL CHECK ({_SEGMENTS.format(col="sections")}),
            cause text NOT NULL CHECK (cause IN ('draft', 'edit', 'regenerate')),
            created_by_kind text NOT NULL CHECK (created_by_kind IN ('human', 'agent')),
            agent_run_id uuid NULL,
            on_behalf_of_user_id uuid NULL,
            content_hash text NOT NULL CHECK (content_hash {_SHA}),
            figure_fingerprint text NULL
                CHECK (figure_fingerprint IS NULL OR figure_fingerprint {_SHA}),
            -- TRI forces Restricted (ADR-167 §1; Q-02 AC-19: there is no "Confidential TRI").
            classification text NOT NULL DEFAULT 'restricted'
                CHECK (classification = 'restricted'),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true),
            actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            {_CREATED},
            UNIQUE (memo_id, version_no),
            -- An agent's version names its run and the person it acted for; a person's names none.
            CHECK (created_by_kind <> 'agent'
                   OR (agent_run_id IS NOT NULL AND on_behalf_of_user_id IS NOT NULL)),
            CHECK (created_by_kind <> 'human' OR agent_run_id IS NULL),
            -- An edit is a person's (human-owned sections, P-24).
            CHECK (cause <> 'edit' OR created_by_kind = 'human'),
            FOREIGN KEY (tenant_id, memo_id) REFERENCES preparer_memos (tenant_id, id),
            FOREIGN KEY (agent_run_id) REFERENCES agent_runs (id),
            FOREIGN KEY (on_behalf_of_user_id) REFERENCES users (id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE preparer_memo_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            memo_id uuid NOT NULL,
            event text NOT NULL CHECK (event IN ('drafted', 'section_edited', 'regenerated',
                                                 'adopted', 'approved', 'went_stale')),
            version_no integer NULL CHECK (version_no IS NULL OR version_no >= 1),
            ref jsonb NULL CHECK (ref IS NULL OR jsonb_typeof(ref) = 'object'),
            actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true)
                CHECK (actor_kind IN ('human', 'agent', 'system', 'policy')),
            actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true),
            {_CREATED},
            -- Adopting (L1) and approving (L2) are a person's (ADR-005, INV-1).
            CHECK (event NOT IN ('adopted', 'approved') OR actor_kind = 'human'),
            FOREIGN KEY (tenant_id, memo_id) REFERENCES preparer_memos (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE planning_opportunities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            memo_id uuid NULL,
            source_kind text NOT NULL CHECK (source_kind IN ('memo')),
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            body jsonb NOT NULL CHECK ({_SEGMENTS.format(col="body")}),
            citation_ids uuid[] NOT NULL DEFAULT '{{}}',
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open')),
            {_CREATED},
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, memo_id) REFERENCES preparer_memos (tenant_id, id),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "CREATE INDEX preparer_memo_events_memo ON preparer_memo_events (memo_id, created_at)"
    )
    op.execute("CREATE INDEX planning_opportunities_item ON planning_opportunities (work_item_id)")
    op.execute(
        """
        CREATE FUNCTION preparer_memo_rows_immutable() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION 'insert-only: a memo change is a new version or a new event'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION preparer_memo_rows_immutable() FROM PUBLIC")
    for table in TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table in IMMUTABLE:
        insert_only(op, table)
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION preparer_memo_rows_immutable()"
        )
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION preparer_memo_rows_immutable()")
    op.execute(
        """
        ALTER TABLE workpaper_versions
            DROP COLUMN inputs_hash,
            DROP COLUMN engine_manifest
        """
    )
    op.execute(
        """
        ALTER TABLE workpaper_cells
            DROP CONSTRAINT workpaper_cells_engine_pair,
            DROP CONSTRAINT workpaper_cells_formula_source,
            DROP COLUMN engine_version,
            DROP COLUMN engine_name,
            DROP COLUMN formula_inputs,
            DROP COLUMN formula
        """
    )
    op.execute("ALTER TABLE workpapers DROP CONSTRAINT workpapers_kind_check")
    op.execute(
        f"ALTER TABLE workpapers ADD CONSTRAINT workpapers_kind_check {_kinds(_PLANNING + _EBP)}"
    )
