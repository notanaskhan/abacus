"""A-06 `adjustments_core` (A-06-T03; A-06 §4.2; SPEC-642; DEC-1962): expand-only, red.

The adjustments module's first tables (C8). Every table is work-item scoped with forced
row-level security:

- `proposed_entries`: an AJE, RJE, PAJE, TJE or elimination proposed on the audit, with its
  threshold result and status. **Nothing is ever posted**: `pe_posting_dormant` refuses the
  posting statuses until a C-02 migration under an accepted ADR P-16 drops it (ADR-040, DEC-69),
  and an attest client's entry is always `review_required` (ADR P-13).
- `proposed_entry_lines`: debit xor credit per line; a deferred constraint trigger holds each
  entry balanced at commit (`unbalanced_entry`), and another refuses a line change once the entry
  has left Proposed, Within threshold or Review required (`entry_locked`).
- `proposed_entry_decisions` (insert-only): a person's decision on an entry, bound to the
  session's own actor (the `0015_review_decisions.py` pattern); a recorded client decision names
  its evidence.
- `approval_batches` (insert-only): a named person's batch of approved entries under a policy.

Status CHECKs are the status vocabulary's `proposed_entry` codes as of this migration.

Revision ID: 0643
Revises: 0642
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0643"
down_revision = "0642"
branch_labels = None
depends_on = None

_SCOPE = """
            tenant_id uuid NOT NULL,
            engagement_id uuid NOT NULL,
            work_item_id uuid NOT NULL,"""
_SCOPE_FK = """
            FOREIGN KEY (tenant_id, engagement_id, work_item_id)
                REFERENCES work_items (tenant_id, engagement_id, id)"""
_HUMAN = (
    "actor_kind text NOT NULL DEFAULT current_setting('app.actor_kind', true) "
    "CHECK (actor_kind = 'human' AND actor_kind = current_setting('app.actor_kind', true)), "
    "actor_id text NOT NULL DEFAULT current_setting('app.actor_id', true) "
    "CHECK (actor_id = current_setting('app.actor_id', true))"
)
# The status vocabulary's `proposed_entry` codes (A-06-T02), frozen here.
STATUSES = (
    "proposed",
    "within_threshold",
    "review_required",
    "approved",
    "rejected",
    "client_approved",
    "client_declined",
    "posted",
    "failed_post",
    "reversed",
)
OPEN = ("proposed", "within_threshold", "review_required")
_TABLES = (
    "approval_batches",
    "proposed_entry_decisions",
    "proposed_entry_lines",
    "proposed_entries",
)
_INSERT_ONLY = ("proposed_entry_decisions", "approval_batches")
INSERTS: dict[str, tuple[str, ...]] = {
    "proposed_entries": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "kind",
        "number",
        "ref",
        "description",
        "misstatement_id",
        "source_ref",
        "amount",
        "account_class",
        "threshold_policy_version_id",
        "threshold_result",
        "is_attest_client",
        "status",
        "client_wording_template_version_id",
        "created_by_kind",
        "created_by_id",
        "on_behalf_of_user_id",
    ),
    "proposed_entry_lines": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "entry_id",
        "line_no",
        "account_code",
        "account_name",
        "fs_line_key",
        "debit",
        "credit",
    ),
    "proposed_entry_decisions": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "entry_id",
        "decision",
        "actor_principal",
        "client_grant_id",
        "channel",
        "reason_code",
        "note_sealed",
        "evidence_version_id",
        "approval_batch_id",
        "approval_grant_id",
        "seen_version",
    ),
    "approval_batches": (
        "tenant_id",
        "engagement_id",
        "work_item_id",
        "policy_version_id",
        "entry_ids",
        "approver_user_id",
        "label",
    ),
}
# An entry's status, description and version move through the adjustments service; its lines are
# replaced only while it is open (the lock trigger).
UPDATES: dict[str, tuple[str, ...]] = {
    "proposed_entries": ("status", "description", "amount", "account_class", "version"),
    "proposed_entry_lines": ("account_code", "account_name", "fs_line_key", "debit", "credit"),
}


def _in(codes: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{c}'" for c in codes) + ")"


_BALANCED = """
CREATE FUNCTION proposed_entry_balanced() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    entry uuid := COALESCE(NEW.entry_id, OLD.entry_id);
    tenant uuid := COALESCE(NEW.tenant_id, OLD.tenant_id);
    dr numeric;
    cr numeric;
BEGIN
    SELECT COALESCE(sum(debit), 0), COALESCE(sum(credit), 0) INTO dr, cr
      FROM public.proposed_entry_lines WHERE tenant_id = tenant AND entry_id = entry;
    IF dr <> cr THEN
        RAISE EXCEPTION 'unbalanced_entry' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END
$$
"""
_LOCKED = """
CREATE FUNCTION proposed_entry_lines_locked() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    state text;
BEGIN
    SELECT status INTO state FROM public.proposed_entries
     WHERE tenant_id = COALESCE(NEW.tenant_id, OLD.tenant_id)
       AND id = COALESCE(NEW.entry_id, OLD.entry_id);
    IF state IS NOT NULL AND state NOT IN ('proposed', 'within_threshold', 'review_required') THEN
        RAISE EXCEPTION 'entry_locked' USING ERRCODE = 'check_violation';
    END IF;
    RETURN COALESCE(NEW, OLD);
END
$$
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE proposed_entries (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            kind text NOT NULL CHECK (kind IN ('aje', 'rje', 'paje', 'tje', 'elimination')),
            number integer NOT NULL CHECK (number >= 1),
            ref text NOT NULL CHECK (ref ~ '^(AJE|RJE|PAJE|TJE|ELIM)-[1-9][0-9]{{0,3}}$'),
            description text NULL CHECK (char_length(description) <= 500),
            misstatement_id uuid NULL,
            source_ref jsonb NULL
                CHECK (source_ref IS NULL OR jsonb_typeof(source_ref) = 'object'),
            amount numeric(20, 2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
            account_class text NULL CHECK (char_length(account_class) <= 60),
            threshold_policy_version_id uuid NULL,
            threshold_result text NOT NULL
                CHECK (threshold_result IN ('within_threshold', 'review_required')),
            is_attest_client boolean NOT NULL,
            status text NOT NULL DEFAULT 'proposed' CHECK (status IN {_in(STATUSES)}),
            client_wording_template_version_id uuid NULL,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_by_kind text NOT NULL CHECK (created_by_kind IN ('human', 'agent')),
            created_by_id text NOT NULL,
            on_behalf_of_user_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, work_item_id, kind, number),
            -- ADR-040, DEC-69: no entry is posted to any client system while this stands.
            CONSTRAINT pe_posting_dormant
                CHECK (status NOT IN ('posted', 'failed_post', 'reversed')),
            -- ADR P-13: an attest client's entry always needs a person's review.
            CONSTRAINT pe_attest_review_required
                CHECK (NOT is_attest_client OR threshold_result = 'review_required'),
            CHECK (created_by_kind = 'human' OR on_behalf_of_user_id IS NOT NULL),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE proposed_entry_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            entry_id uuid NOT NULL,
            line_no integer NOT NULL CHECK (line_no >= 1),
            account_code text NOT NULL CHECK (char_length(btrim(account_code)) BETWEEN 1 AND 64),
            account_name text NULL CHECK (char_length(account_name) <= 200),
            fs_line_key text NULL CHECK (char_length(fs_line_key) <= 80),
            debit numeric(20, 2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
            credit numeric(20, 2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            UNIQUE (tenant_id, entry_id, line_no),
            CONSTRAINT pe_line_one_side CHECK ((debit = 0) <> (credit = 0)),
            FOREIGN KEY (tenant_id, entry_id) REFERENCES proposed_entries (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE approval_batches (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            policy_version_id uuid NULL,
            entry_ids uuid[] NOT NULL CHECK (cardinality(entry_ids) BETWEEN 1 AND 500),
            approver_user_id uuid NOT NULL,
            label text NOT NULL CHECK (char_length(btrim(label)) BETWEEN 1 AND 200),
            {_HUMAN},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            -- The approver is the session's own person (a batch is a named human's act).
            CONSTRAINT approval_batches_own_person
                CHECK (actor_id = approver_user_id::text),{_SCOPE_FK}
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE proposed_entry_decisions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),{_SCOPE}
            entry_id uuid NOT NULL,
            decision text NOT NULL CHECK (decision IN ('approved', 'rejected', 'sent_to_client',
                'client_accepted', 'client_declined', 'client_question', 'send_undone')),
            actor_principal text NOT NULL CHECK (actor_principal IN ('firm_user', 'client_user')),
            client_grant_id uuid NULL,
            channel text NOT NULL CHECK (channel IN ('app', 'portal', 'record')),
            reason_code text NULL CHECK (char_length(reason_code) <= 60),
            note_sealed bytea NULL CHECK (octet_length(note_sealed) <= 65536),
            evidence_version_id uuid NULL,
            approval_batch_id uuid NULL,
            approval_grant_id uuid NULL,
            seen_version integer NOT NULL CHECK (seen_version >= 1),
            {_HUMAN},
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (tenant_id, id),
            CHECK (channel <> 'record' OR evidence_version_id IS NOT NULL),
            CHECK (decision <> 'rejected' OR reason_code IS NOT NULL),
            FOREIGN KEY (tenant_id, entry_id) REFERENCES proposed_entries (tenant_id, id),
            FOREIGN KEY (tenant_id, approval_batch_id) REFERENCES approval_batches (tenant_id, id),
{_SCOPE_FK}
        )
        """
    )
    op.execute(
        "ALTER TABLE proposed_entries ADD CONSTRAINT proposed_entries_scope "
        "UNIQUE (tenant_id, engagement_id, work_item_id, id)"
    )
    op.execute(_BALANCED)
    op.execute(
        "CREATE CONSTRAINT TRIGGER proposed_entry_balanced AFTER INSERT OR UPDATE OR DELETE "
        "ON proposed_entry_lines DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION proposed_entry_balanced()"
    )
    op.execute(_LOCKED)
    op.execute(
        "CREATE TRIGGER proposed_entry_lines_locked BEFORE INSERT OR UPDATE OR DELETE "
        "ON proposed_entry_lines FOR EACH ROW EXECUTE FUNCTION proposed_entry_lines_locked()"
    )
    for function in ("proposed_entry_balanced()", "proposed_entry_lines_locked()"):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    for table, column in (
        ("proposed_entries", "work_item_id"),
        ("proposed_entry_lines", "entry_id"),
        ("proposed_entry_decisions", "entry_id"),
        ("approval_batches", "work_item_id"),
    ):
        op.execute(f"CREATE INDEX {table}_{column} ON {table} (tenant_id, {column})")
    for table in _TABLES:
        tenant_table(op, table)
        op.execute(f"REVOKE DELETE, TRUNCATE ON {table} FROM abacus_app")
    for table in _INSERT_ONLY:
        insert_only(op, table)
    for table, columns in INSERTS.items():
        insert_columns(op, table, columns)
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ON {table} FROM abacus_app")
        op.execute(f"GRANT UPDATE ({', '.join(columns)}) ON {table} TO abacus_app")
    # A line is replaced while its entry is open: delete is granted, the lock trigger guards it.
    op.execute("GRANT DELETE ON proposed_entry_lines TO abacus_app")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION proposed_entry_lines_locked()")
    op.execute("DROP FUNCTION proposed_entry_balanced()")
