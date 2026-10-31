"""The K-1 release gate (T-02-T21; T-02 §3.6, §4.9, §5; DEC-24, DEC-53, DEC-78, DEC-88; DEC-1476).
Expand-only. RED.

- `k1_releases`: one person's release of a return's final K-1 packages, held by a single-use
  approval grant whose `not_before` is the end of the ten-second Undo window. The row is the
  person's: it is inserted only in a transaction whose actor is that person
  (`app.actor_kind`/`app.actor_id`, the 0015 pattern), so neither an agent, the system nor a
  policy principal can request one (INV-1's database layer). Status moves `pending` → `undone`
  (the requester, before `not_before`) or `pending` → `running` → `completed`/`failed` (the
  workflow, as the system); nothing else changes after insert.
- `k1_release_deliveries`: the workflow's per-recipient ledger, one row per release and package,
  each step stamped once (contact, grant or invitation, released, email, hand-offs), so a replayed
  half-finished release skips what is done and never sends a second email.
- `k1_packages`: a package becomes `released` only while a release naming it is `running`
  (the trigger below); the application may now set `released_at`. `k1_recipients.contact_id`
  becomes writable for the contact the release delivers to.
- `approval_grants.action` takes the matrix's action pattern (digits after the first letter,
  DEC-1162), so `k1_package.release` can be granted.
- `schedule_k_release.requested` and `schedule_k_release.undone` join the human-only audit
  register (65 entries; the downgrade restores 0563's 63).

Classification: ids and times Internal; `failure_code` a code, never a value.

Revision ID: 0566
Revises: 0524
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import tenant_table

revision = "0566"
down_revision = "0524"
branch_labels = None
depends_on = None

_BEFORE = [
    "acceptance.decided",
    "acceptance.review_completed",
    "ai_policy.approved",
    "ai_policy.declined",
    "assurance.archive_recorded",
    "assurance.phase_recorded",
    "assurance.release_recorded",
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "client_import.row_decided",
    "conflict.cleared",
    "contact.unlocked",
    "decision.decided",
    "decision.reassessed",
    "engagement.acceptance_recorded",
    "engagement.accepted",
    "engagement.letter_recorded",
    "engine_export.generated",
    "engine_export.marked_exported",
    "eqr.eligibility_approved",
    "evidence.accepted",
    "firm.ai_client_data_opted_in",
    "firm_export.approved",
    "firm_export.declined",
    "follow_up.sent",
    "fulfilment.voided",
    "going_concern.decided",
    "guidance_draft.approved",
    "independence.annual_confirmed",
    "independence.annual_declined",
    "independence.concluded",
    "independence.confirmed",
    "independence.declined",
    "independence.statement_published",
    "legal_hold.lifted",
    "legal_hold.placed",
    "letter.approved",
    "materiality.decided",
    "methodology_version.approved",
    "nas.evaluated",
    "portal_mfa.reset",
    "procedure.concluded",
    "proposal.approved",
    "proposal.approved_with_edits",
    "proposal.rejected",
    "proposal.routed",
    "report.approved",
    "report.released",
    "retention_policy.updated",
    "review.decided",
    "review.released",
    "review_decision.created",
    "review_decision.undone",
    "risk.approved",
    "sample.approved",
    "service_line_policy.updated",
    "sign_off.recorded",
    "statement.approved",
    "suggestion.adopted",
    "suggestion.dismissed",
    "suggestion.edited",
    "team.approved",
]
_HUMAN_ONLY = sorted([*_BEFORE, "schedule_k_release.requested", "schedule_k_release.undone"])


def _human_only(actions: list[str]) -> None:
    listed = ", ".join(f"'{a}'" for a in actions)
    op.execute(
        "CREATE OR REPLACE FUNCTION abacus_human_only_actions() RETURNS text[] "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        f"AS $$ SELECT ARRAY[{listed}]::text[] $$"
    )


_RELEASES = """
CREATE TABLE k1_releases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    engagement_id uuid NOT NULL,
    work_item_id uuid NOT NULL,
    package_ids uuid[] NOT NULL CHECK (cardinality(package_ids) BETWEEN 1 AND 500),
    grant_id uuid NOT NULL,
    not_before timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'undone', 'running', 'completed', 'failed')),
    requested_by uuid NOT NULL,
    requested_by_kind text NOT NULL DEFAULT 'human' CHECK (requested_by_kind = 'human'),
    mfa_at timestamptz NOT NULL,
    email_template_version_id uuid NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    undone_at timestamptz NULL,
    undone_by uuid NULL,
    started_at timestamptz NULL,
    completed_at timestamptz NULL,
    failure_code text NULL CHECK (failure_code ~ '^[a-z][a-z_]{0,59}$'),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, grant_id),
    CHECK ((status = 'undone') = (undone_at IS NOT NULL AND undone_by IS NOT NULL)),
    CHECK (status NOT IN ('completed', 'failed') OR completed_at IS NOT NULL),
    CHECK (status <> 'failed' OR failure_code IS NOT NULL),
    FOREIGN KEY (tenant_id, work_item_id) REFERENCES work_items (tenant_id, id),
    FOREIGN KEY (tenant_id, requested_by) REFERENCES memberships (tenant_id, user_id)
)
"""

_DELIVERIES = """
CREATE TABLE k1_release_deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    release_id uuid NOT NULL,
    package_id uuid NOT NULL,
    contact_id uuid NULL,
    access_grant_id uuid NULL,
    invitation_id uuid NULL,
    access_at timestamptz NULL,
    released_at timestamptz NULL,
    message_id uuid NULL,
    emailed_at timestamptz NULL,
    handoffs_at timestamptz NULL,
    UNIQUE (tenant_id, release_id, package_id),
    CHECK ((emailed_at IS NULL) = (message_id IS NULL)),
    FOREIGN KEY (tenant_id, release_id) REFERENCES k1_releases (tenant_id, id),
    FOREIGN KEY (tenant_id, package_id) REFERENCES k1_packages (tenant_id, id)
)
"""

_GUARD = """
CREATE FUNCTION k1_releases_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
           OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.requested_by::text
           OR NEW.status <> 'pending' THEN
            RAISE EXCEPTION 'a K-1 release is requested by the session''s own person'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END IF;
    IF (NEW.tenant_id, NEW.engagement_id, NEW.work_item_id, NEW.package_ids, NEW.grant_id,
        NEW.not_before, NEW.requested_by, NEW.requested_by_kind, NEW.mfa_at,
        NEW.email_template_version_id, NEW.requested_at)
       IS DISTINCT FROM
       (OLD.tenant_id, OLD.engagement_id, OLD.work_item_id, OLD.package_ids, OLD.grant_id,
        OLD.not_before, OLD.requested_by, OLD.requested_by_kind, OLD.mfa_at,
        OLD.email_template_version_id, OLD.requested_at) THEN
        RAISE EXCEPTION 'a K-1 release changes only its status'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'pending' AND NEW.status = 'undone' THEN
        IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
           OR current_setting('app.actor_id', true) IS DISTINCT FROM OLD.requested_by::text
           OR NEW.undone_by IS DISTINCT FROM OLD.requested_by THEN
            RAISE EXCEPTION 'only the person who released undoes it'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF abacus_now() >= OLD.not_before THEN
            RAISE EXCEPTION 'undo_window_closed' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF (OLD.status = 'pending' AND NEW.status = 'running')
       OR (OLD.status = 'running' AND NEW.status IN ('completed', 'failed'))
       OR (OLD.status = 'pending' AND NEW.status = 'failed') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'a K-1 release cannot move from % to %', OLD.status, NEW.status
        USING ERRCODE = 'check_violation';
END
$$
"""

_PACKAGE_GUARD = """
CREATE FUNCTION k1_packages_release_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NEW.status = 'released' AND OLD.status IS DISTINCT FROM 'released' AND NOT EXISTS (
        SELECT 1 FROM k1_releases r
        WHERE r.tenant_id = NEW.tenant_id AND r.status = 'running'
          AND NEW.id = ANY(r.package_ids)
    ) THEN
        RAISE EXCEPTION 'a K-1 package is released only by a running release'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.released_at IS DISTINCT FROM OLD.released_at AND OLD.released_at IS NOT NULL THEN
        RAISE EXCEPTION 'a K-1 package''s release time is written once'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$$
"""


def _grant_action(pattern: str) -> None:
    op.execute("ALTER TABLE approval_grants DROP CONSTRAINT approval_grants_action_check")
    op.execute(
        "ALTER TABLE approval_grants ADD CONSTRAINT approval_grants_action_check "
        f"CHECK (action ~ '{pattern}')"
    )


def upgrade() -> None:
    _grant_action(r"^[a-z][a-z0-9_]{0,59}\.[a-z][a-z_]{0,59}$")
    op.execute(_RELEASES)
    op.execute(
        "CREATE INDEX k1_releases_by_return ON k1_releases (tenant_id, work_item_id, requested_at)"
    )
    op.execute(_DELIVERIES)
    for table in ("k1_releases", "k1_release_deliveries"):
        tenant_table(op, table)
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM abacus_app")
    op.execute(
        "GRANT UPDATE (status, undone_at, undone_by, started_at, completed_at, failure_code) "
        "ON k1_releases TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (contact_id, access_grant_id, invitation_id, access_at, released_at, "
        "message_id, emailed_at, handoffs_at) ON k1_release_deliveries TO abacus_app"
    )
    op.execute(_GUARD)
    op.execute(
        "CREATE TRIGGER k1_releases_guard BEFORE INSERT OR UPDATE ON k1_releases "
        "FOR EACH ROW EXECUTE FUNCTION k1_releases_guard()"
    )
    op.execute(_PACKAGE_GUARD)
    op.execute(
        "CREATE TRIGGER k1_packages_release_guard BEFORE UPDATE ON k1_packages "
        "FOR EACH ROW EXECUTE FUNCTION k1_packages_release_guard()"
    )
    op.execute("GRANT UPDATE (released_at) ON k1_packages TO abacus_app")
    op.execute("GRANT UPDATE (contact_id) ON k1_recipients TO abacus_app")
    _human_only(_HUMAN_ONLY)


def downgrade() -> None:
    _human_only(_BEFORE)
    op.execute("DELETE FROM approval_grants WHERE action = 'k1_package.release'")
    _grant_action(r"^[a-z][a-z_]{0,59}\.[a-z][a-z_]{0,59}$")
    op.execute("REVOKE UPDATE (contact_id) ON k1_recipients FROM abacus_app")
    op.execute("REVOKE UPDATE (released_at) ON k1_packages FROM abacus_app")
    op.execute("DROP TRIGGER k1_packages_release_guard ON k1_packages")
    op.execute("DROP FUNCTION k1_packages_release_guard()")
    op.execute("DROP TABLE k1_release_deliveries")
    op.execute("DROP TABLE k1_releases")
    op.execute("DROP FUNCTION k1_releases_guard()")
