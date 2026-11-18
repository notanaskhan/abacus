"""Records destruction in evidence (Q-05-T06; SPEC-711 AC-19 to AC-27, AC-31, AC-32; Q-05 §4.2;
DEC-5612; red). Expand-only; the pipeline runs it after 8 pm CT inside the window (P-29).

Q-02's tables are extended, never redefined (AC-32):
- `retention_policy_versions` (0112, insert-only) gains `policy_text` and `effective_from`.
- `legal_holds` (0126) gains `display_name`, `document_classes` and `until_released`; its
  `reason_code` CHECK widens additively with `state_controversy` and `client_dispute`.
- `evidence_versions` (0007) gains `destroyed_at` and `destruction_certificate_id`, settable only
  once, NULL to a value, inside a unit of work whose `app.archived_write` is
  `destruction_tombstone`; every other update or delete is still refused (ADR-004).
- `platform_controls` and `platform_control_changes` accept the `destruction_execute` kill switch.

New tables with forced RLS: `destruction_batches` (status moves forward only), insert-only
`destruction_batch_items`, `destruction_item_exclusions` (shrink-only) and
`destruction_certificates`, and insert-only human-only `destruction_approvals` (at most two per
batch, distinct person and role, the second carrying the typed phrase's hash).

Revision ID: 0964
Revises: 0963
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0964"
down_revision = "0963"
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
_STATUSES = "('awaiting_approval', 'approved', 'destroying', 'destroyed', 'cancelled')"
_REASONS = "('irs_examination', 'litigation', 'regulatory_inquiry', 'subpoena', 'other')"
_REASONS_V2 = (
    "('irs_examination', 'litigation', 'regulatory_inquiry', 'subpoena', 'other', "
    "'state_controversy', 'client_dispute')"
)
_CONTROLS = (
    "'ai_pause', 'model_route_block', 'email_pause', 'read_only', 'portal_sign_in', "
    "'confirmation_links', 'integration_pause'"
)
_HISTORY = f"{_CONTROLS}, 'portal_sign_in_disabled'"
_NEW = "'destruction_execute'"

# (table, body, insert columns, update columns, insert-only)
TABLES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    ("destruction_batches", f"""
            ref text NOT NULL CHECK (ref ~ '^[0-9]{{4}}-Q[1-4]$'),
            scope_description text NOT NULL
                CHECK (char_length(scope_description) BETWEEN 1 AND 200),
            status text NOT NULL DEFAULT 'awaiting_approval' CHECK (status IN {_STATUSES}),
            assembled_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            eligible_count integer NOT NULL CHECK (eligible_count >= 0),
            held_excluded_count integer NOT NULL DEFAULT 0 CHECK (held_excluded_count >= 0),
            destroyed_count integer NOT NULL DEFAULT 0 CHECK (destroyed_count >= 0),
            client_count integer NOT NULL CHECK (client_count >= 0),
            confirmation_phrase text NOT NULL,
            certificate_id uuid NULL,
            hold_recheck_at timestamptz NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            CONSTRAINT destruction_batches_phrase CHECK (confirmation_phrase = 'DESTROY ' || ref),
            CONSTRAINT destruction_batches_counts
                CHECK (destroyed_count + held_excluded_count <= eligible_count),
            CONSTRAINT destruction_batches_certificate
                CHECK ((status = 'destroyed') = (certificate_id IS NOT NULL)),
            UNIQUE (tenant_id, ref),""",
     ("tenant_id", "ref", "scope_description", "eligible_count", "client_count",
      "confirmation_phrase"),
     ("status", "held_excluded_count", "destroyed_count", "certificate_id", "hold_recheck_at",
      "version"), False),
    ("destruction_batch_items", """
            batch_id uuid NOT NULL,
            evidence_version_id uuid NOT NULL,
            object_key text NOT NULL CHECK (char_length(object_key) BETWEEN 1 AND 1024),
            object_version_id text NOT NULL
                CHECK (char_length(object_version_id) BETWEEN 1 AND 1024),
            replica_version_id text NULL CHECK (char_length(replica_version_id) <= 1024),
            record_type text NOT NULL CHECK (record_type ~ '^[a-z][a-z0-9_]{0,59}$'),
            client_id uuid NULL,
            eligible_at timestamptz NOT NULL,
            retain_until_observed timestamptz NULL,
            UNIQUE (batch_id, evidence_version_id),
            FOREIGN KEY (tenant_id, batch_id) REFERENCES destruction_batches (tenant_id, id),""",
     ("tenant_id", "batch_id", "evidence_version_id", "object_key", "object_version_id",
      "replica_version_id", "record_type", "client_id", "eligible_at", "retain_until_observed"),
     (), True),
    ("destruction_item_exclusions", """
            item_id uuid NOT NULL UNIQUE,
            reason text NOT NULL CHECK (reason IN
                ('held', 'retention_extended', 'shared_object', 'missing_object')),
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (tenant_id, item_id)
                REFERENCES destruction_batch_items (tenant_id, id),""",
     ("tenant_id", "item_id", "reason"), (), True),
    ("destruction_approvals", f"""
            batch_id uuid NOT NULL,
            approver_user_id uuid NOT NULL,
            approver_role text NOT NULL CHECK (approver_role IN ('firm_admin', 'security_admin')),
            approved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            mfa_verified_at timestamptz NOT NULL,
            phrase_sha256 text NULL CHECK (phrase_sha256 ~ '^[0-9a-f]{{64}}$'),
            items_seen integer NOT NULL CHECK (items_seen >= 0),
            {_HUMAN}
            UNIQUE (batch_id, approver_user_id),
            UNIQUE (batch_id, approver_role),
            FOREIGN KEY (tenant_id, batch_id) REFERENCES destruction_batches (tenant_id, id),""",
     ("tenant_id", "batch_id", "approver_user_id", "approver_role", "mfa_verified_at",
      "phrase_sha256", "items_seen"), (), True),
    ("destruction_certificates", """
            batch_id uuid NOT NULL UNIQUE,
            ref text NOT NULL CHECK (ref ~ '^DC-[0-9]{4}-Q[1-4]$'),
            document_version_id uuid NOT NULL,
            manifest_object_key text NOT NULL CHECK (char_length(manifest_object_key) <= 1024),
            manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
            audit_checkpoint_root text NOT NULL CHECK (audit_checkpoint_root ~ '^[0-9a-f]{64}$'),
            generated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, ref),
            FOREIGN KEY (tenant_id, batch_id) REFERENCES destruction_batches (tenant_id, id),""",
     ("tenant_id", "batch_id", "ref", "document_version_id", "manifest_object_key",
      "manifest_sha256", "audit_checkpoint_root"), (), True),
)  # fmt: skip

_ORDER = "ARRAY['awaiting_approval', 'approved', 'destroying', 'destroyed']"


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


def _controls_check(table: str, values: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_control_check")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {table}_control_check CHECK (control IN ({values}))"
    )


def _evidence_trigger(tombstone: bool) -> None:
    """ADR-004's second layer, with (or, on downgrade, without) the one tombstone write."""
    allow = (
        """
            IF TG_OP = 'UPDATE'
               AND current_setting('app.archived_write', true) = 'destruction_tombstone'
               AND OLD.destroyed_at IS NULL AND NEW.destroyed_at IS NOT NULL
               AND OLD.destruction_certificate_id IS NULL
               AND NEW.destruction_certificate_id IS NOT NULL
               AND (to_jsonb(NEW) - 'destroyed_at' - 'destruction_certificate_id')
                 = (to_jsonb(OLD) - 'destroyed_at' - 'destruction_certificate_id') THEN
                RETURN NEW;
            END IF;"""
        if tombstone
        else ""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION evidence_versions_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN{allow}
            RAISE EXCEPTION 'evidence versions are immutable (ADR-004)'
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )


def upgrade() -> None:
    # Q-02's tables, extended (AC-32).
    op.execute(
        "ALTER TABLE retention_policy_versions ADD COLUMN policy_text text NULL "
        "CHECK (char_length(policy_text) <= 4000)"
    )
    op.execute("ALTER TABLE retention_policy_versions ADD COLUMN effective_from date NULL")
    # Written by Q-02's policy trigger (the app never inserts versions); Q-05-T11 extends it.
    op.execute(
        "ALTER TABLE legal_holds ADD COLUMN display_name text NULL "
        "CHECK (char_length(display_name) BETWEEN 1 AND 200)"
    )
    op.execute("ALTER TABLE legal_holds ADD COLUMN document_classes text[] NULL")
    op.execute("ALTER TABLE legal_holds ADD COLUMN until_released boolean NOT NULL DEFAULT true")
    op.execute(
        "GRANT INSERT (display_name, document_classes, until_released) ON legal_holds "
        "TO abacus_app"
    )
    op.execute("ALTER TABLE legal_holds DROP CONSTRAINT legal_holds_reason_code_check")
    op.execute(
        "ALTER TABLE legal_holds ADD CONSTRAINT legal_holds_reason_code_check "
        f"CHECK (reason_code IN {_REASONS_V2})"
    )
    # Tombstones (AC-25): set once under `destruction_tombstone`, never unset.
    op.execute("ALTER TABLE evidence_versions ADD COLUMN destroyed_at timestamptz NULL")
    op.execute("ALTER TABLE evidence_versions ADD COLUMN destruction_certificate_id uuid NULL")
    op.execute(
        "ALTER TABLE evidence_versions ADD CONSTRAINT evidence_versions_tombstone "
        "CHECK ((destroyed_at IS NULL) = (destruction_certificate_id IS NULL))"
    )
    op.execute(
        "GRANT UPDATE (destroyed_at, destruction_certificate_id) ON evidence_versions "
        "TO abacus_app"
    )
    _evidence_trigger(tombstone=True)
    # The kill switch (AC-27): stops DestructionExecuteWorkflow between items.
    _controls_check("platform_control_changes", f"{_HISTORY}, {_NEW}")
    _controls_check("platform_controls", f"{_CONTROLS}, {_NEW}")

    for table, body, _ins, _upd, _io in TABLES:
        op.execute(f"CREATE TABLE {table} ({_ID}{body}{_KEYS}\n        )")
    for table, _body, ins, upd, io in TABLES:
        tenant_table(op, table)
        insert_columns(op, table, list(ins))
        if io:
            insert_only(op, table)
            _immutable(table)
        else:
            op.execute(f"REVOKE UPDATE, DELETE ON {table} FROM abacus_app")
            op.execute(f"GRANT UPDATE ({', '.join(upd)}) ON {table} TO abacus_app")
    # A batch's status moves forward only; cancelled only before destroying.
    op.execute(
        f"""
        CREATE FUNCTION destruction_batches_forward() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;
            IF NEW.status = 'cancelled' AND OLD.status IN ('awaiting_approval', 'approved') THEN
                RETURN NEW;
            END IF;
            IF OLD.status = 'cancelled' OR OLD.status = 'destroyed'
               OR array_position({_ORDER}, NEW.status) <= array_position({_ORDER}, OLD.status) THEN
                RAISE EXCEPTION 'destruction batch status moves forward only'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER destruction_batches_forward BEFORE UPDATE OF status "
        "ON destruction_batches "
        "FOR EACH ROW EXECUTE FUNCTION destruction_batches_forward()"
    )
    # AC-22, AC-23: two approvals at most, distinct person and role; the second carries the phrase.
    op.execute(
        """
        CREATE FUNCTION destruction_approvals_two() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE n integer;
        BEGIN
            SELECT count(*) INTO n FROM destruction_approvals
             WHERE tenant_id = NEW.tenant_id AND batch_id = NEW.batch_id;
            IF n >= 2 THEN
                RAISE EXCEPTION 'a batch takes two approvals' USING ERRCODE = 'check_violation';
            END IF;
            IF n = 1 AND NEW.phrase_sha256 IS NULL THEN
                RAISE EXCEPTION 'batch_phrase_mismatch' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER destruction_approvals_two BEFORE INSERT ON destruction_approvals "
        "FOR EACH ROW EXECUTE FUNCTION destruction_approvals_two()"
    )


def downgrade() -> None:
    for table, _body, _ins, _upd, _io in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION destruction_approvals_two()")
    op.execute("DROP FUNCTION destruction_batches_forward()")
    for table, _body, _ins, _upd, io in TABLES:
        if io:
            op.execute(f"DROP FUNCTION {table}_immutable()")
    op.execute("DELETE FROM platform_controls WHERE control = 'destruction_execute'")
    _controls_check("platform_controls", _CONTROLS)
    _evidence_trigger(tombstone=False)
    op.execute("ALTER TABLE evidence_versions DROP CONSTRAINT evidence_versions_tombstone")
    op.execute("ALTER TABLE evidence_versions DROP COLUMN destruction_certificate_id")
    op.execute("ALTER TABLE evidence_versions DROP COLUMN destroyed_at")
    op.execute("ALTER TABLE legal_holds DROP CONSTRAINT legal_holds_reason_code_check")
    op.execute(
        "ALTER TABLE legal_holds ADD CONSTRAINT legal_holds_reason_code_check "
        f"CHECK (reason_code IN {_REASONS})"
    )
    for column in ("until_released", "document_classes", "display_name"):
        op.execute(f"ALTER TABLE legal_holds DROP COLUMN {column}")
    for column in ("effective_from", "policy_text"):
        op.execute(f"ALTER TABLE retention_policy_versions DROP COLUMN {column}")
