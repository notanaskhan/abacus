"""Q-02-T43 (TASK-1403; DEC-72, conflict C-11; compliance-kernel §2 to §7; DEC-508, DEC-509): firm
exports with dual approval.

- `firm_exports`: a security admin (`requested_by`, as a person, `requested_by_kind = 'human'`,
  with a fresh second factor `request_mfa_at`) asks for an export of everything the firm holds and
  names the approver (`approver_id`), who is never the requester (CHECK). The app inserts the
  request's columns; `status` starts `awaiting_approval` and moves forward only (the guard):
  awaiting_approval -> building | declined (the named approver, as a person, still an active
  security admin or partner-level member: `decided_by = approver_id`); building -> ready | failed
  (the system); ready -> downloaded (the requester or the approver: the first link);
  ready | downloaded -> expired (the system, after the 7 days). Every stamp is written once.
  The insert's actor must be the requester, an active security admin, and the approver an active
  staff member who is a security admin or at partner level (the requester-insert trigger), so
  neither the service nor a direct statement can make one person both halves (DEC-72).
- `firm_export_links` (insert-only, ADR-004): each 15-minute link, bound to the person it was
  issued to (the actor, the export's requester or approver), never past the export's window,
  only for a ready or downloaded export (CHECKs and the link trigger). The link is a path the
  signed-in person opens; there is no presigned URL (ADR-104, DEC-509).

Revision ID: 0216
Revises: 0220
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, tenant_table

revision = "0216"
down_revision = "0220"
branch_labels = None
depends_on = None

# Whether a person is, now, an active staff member of the row's firm who may approve (a security
# admin or a partner-level member, the derived `firm_partner` of DEC-132).
_APPROVER = """
    EXISTS (
        SELECT 1 FROM memberships m
        WHERE m.tenant_id = {tenant} AND m.user_id = {user} AND m.status = 'active'
            AND m.kind = 'staff' AND (m.firm_role = 'security_admin' OR m.level = 'partner')
    )
"""
_SECURITY_ADMIN = """
    EXISTS (
        SELECT 1 FROM memberships m
        WHERE m.tenant_id = {tenant} AND m.user_id = {user} AND m.status = 'active'
            AND m.kind = 'staff' AND m.firm_role = 'security_admin'
    )
"""


def upgrade() -> None:
    op.execute(
        r"""
        CREATE TABLE firm_exports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            scope text NOT NULL DEFAULT 'all' CHECK (scope = 'all'),
            origin text NOT NULL DEFAULT 'on_demand' CHECK (origin IN ('on_demand', 'scheduled')),
            requested_by uuid NOT NULL,
            requested_by_kind text NOT NULL CHECK (requested_by_kind = 'human'),
            requested_at timestamptz NOT NULL DEFAULT abacus_now(),
            request_mfa_at timestamptz NOT NULL,
            approver_id uuid NOT NULL,
            status text NOT NULL DEFAULT 'awaiting_approval' CHECK (
                status IN (
                    'awaiting_approval', 'declined', 'building', 'ready', 'downloaded',
                    'expired', 'failed'
                )
            ),
            decided_by uuid NULL,
            decided_at timestamptz NULL,
            decided_mfa_at timestamptz NULL,
            decline_reason text NULL CHECK (char_length(decline_reason) <= 500),
            bundle_sha256 text NULL CHECK (bundle_sha256 ~ '^[0-9a-f]{64}$'),
            manifest_sha256 text NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
            bytes bigint NULL CHECK (bytes >= 0),
            segment_count integer NULL CHECK (segment_count >= 1),
            object_prefix text NULL CHECK (char_length(object_prefix) <= 200),
            ready_at timestamptz NULL,
            available_until timestamptz NULL,
            downloaded_at timestamptz NULL,
            failure_code text NULL CHECK (failure_code IN ('build_error')),
            UNIQUE (tenant_id, id),
            CONSTRAINT firm_exports_two_people CHECK (approver_id <> requested_by),
            CONSTRAINT firm_exports_decided CHECK (
                (status = 'awaiting_approval') = (decided_by IS NULL)
                AND (decided_by IS NULL) = (decided_at IS NULL)
                AND (decided_by IS NULL) = (decided_mfa_at IS NULL)
                AND (decided_by IS NULL OR (
                    decided_by = approver_id AND decided_by <> requested_by
                ))
            ),
            CONSTRAINT firm_exports_declined CHECK (decline_reason IS NULL OR status = 'declined'),
            CONSTRAINT firm_exports_ready CHECK (
                status NOT IN ('ready', 'downloaded', 'expired') OR (
                    bundle_sha256 IS NOT NULL AND manifest_sha256 IS NOT NULL
                    AND bytes IS NOT NULL AND segment_count IS NOT NULL
                    AND ready_at IS NOT NULL AND available_until IS NOT NULL
                )
            ),
            CONSTRAINT firm_exports_window CHECK (
                available_until IS NULL OR (
                    available_until > ready_at AND available_until <= ready_at + interval '7 days'
                )
            ),
            CONSTRAINT firm_exports_downloaded CHECK (
                status <> 'downloaded' OR downloaded_at IS NOT NULL
            ),
            CONSTRAINT firm_exports_failed CHECK ((status = 'failed') = (failure_code IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX firm_exports_history ON firm_exports (tenant_id, requested_at DESC, id DESC)"
    )
    tenant_table(op, "firm_exports")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON firm_exports FROM abacus_app")
    insert_columns(
        op,
        "firm_exports",
        (
            "id",
            "tenant_id",
            "scope",
            "origin",
            "requested_by",
            "requested_by_kind",
            "request_mfa_at",
            "approver_id",
        ),
    )
    op.execute(
        "GRANT UPDATE (status, decided_by, decided_at, decided_mfa_at, decline_reason, "
        "bundle_sha256, manifest_sha256, bytes, segment_count, object_prefix, ready_at, "
        "available_until, downloaded_at, failure_code) ON firm_exports TO abacus_app"
    )
    op.execute(
        f"""
        CREATE FUNCTION firm_exports_requester() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.requested_by::text
            THEN
                RAISE EXCEPTION 'a firm export is requested by the person acting'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT {_SECURITY_ADMIN.format(tenant="NEW.tenant_id", user="NEW.requested_by")} THEN
                RAISE EXCEPTION 'a firm export is requested by a security admin'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT {_APPROVER.format(tenant="NEW.tenant_id", user="NEW.approver_id")} THEN
                RAISE EXCEPTION 'approver_invalid' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER firm_exports_requester BEFORE INSERT ON firm_exports "
        "FOR EACH ROW EXECUTE FUNCTION firm_exports_requester()"
    )
    op.execute(
        f"""
        CREATE FUNCTION firm_exports_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        DECLARE
            actor_kind text := current_setting('app.actor_kind', true);
            actor_id text := current_setting('app.actor_id', true);
        BEGIN
            -- A stamp is written once: none already set may change, in any status.
            IF (OLD.decided_by IS NOT NULL AND NEW.decided_by IS DISTINCT FROM OLD.decided_by)
                OR (OLD.decided_at IS NOT NULL AND NEW.decided_at IS DISTINCT FROM OLD.decided_at)
                OR (OLD.decided_mfa_at IS NOT NULL
                    AND NEW.decided_mfa_at IS DISTINCT FROM OLD.decided_mfa_at)
                OR (OLD.decline_reason IS NOT NULL
                    AND NEW.decline_reason IS DISTINCT FROM OLD.decline_reason)
                OR (OLD.bundle_sha256 IS NOT NULL
                    AND NEW.bundle_sha256 IS DISTINCT FROM OLD.bundle_sha256)
                OR (OLD.manifest_sha256 IS NOT NULL
                    AND NEW.manifest_sha256 IS DISTINCT FROM OLD.manifest_sha256)
                OR (OLD.bytes IS NOT NULL AND NEW.bytes IS DISTINCT FROM OLD.bytes)
                OR (OLD.segment_count IS NOT NULL
                    AND NEW.segment_count IS DISTINCT FROM OLD.segment_count)
                OR (OLD.object_prefix IS NOT NULL
                    AND NEW.object_prefix IS DISTINCT FROM OLD.object_prefix)
                OR (OLD.ready_at IS NOT NULL AND NEW.ready_at IS DISTINCT FROM OLD.ready_at)
                OR (OLD.available_until IS NOT NULL
                    AND NEW.available_until IS DISTINCT FROM OLD.available_until)
                OR (OLD.downloaded_at IS NOT NULL
                    AND NEW.downloaded_at IS DISTINCT FROM OLD.downloaded_at)
                OR (OLD.failure_code IS NOT NULL
                    AND NEW.failure_code IS DISTINCT FROM OLD.failure_code)
            THEN
                RAISE EXCEPTION 'a firm export stamp is written once'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.status = OLD.status THEN
                RAISE EXCEPTION 'a % firm export takes no change', OLD.status
                    USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.status = 'awaiting_approval' AND NEW.status IN ('building', 'declined') THEN
                -- DEC-72: the named approver decides, as a person, and is never the requester.
                IF actor_kind IS DISTINCT FROM 'human'
                    OR actor_id IS DISTINCT FROM OLD.approver_id::text
                    OR NEW.decided_by IS DISTINCT FROM OLD.approver_id
                    OR OLD.approver_id = OLD.requested_by
                THEN
                    RAISE EXCEPTION 'approver_must_differ'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                IF NOT {_APPROVER.format(tenant="OLD.tenant_id", user="OLD.approver_id")} THEN
                    RAISE EXCEPTION 'approver_invalid' USING ERRCODE = 'insufficient_privilege';
                END IF;
            ELSIF OLD.status = 'building' AND NEW.status IN ('ready', 'failed') THEN
                IF actor_kind IS DISTINCT FROM 'system' THEN
                    RAISE EXCEPTION 'a firm export is built by the system'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            ELSIF OLD.status = 'ready' AND NEW.status = 'downloaded' THEN
                IF actor_kind IS DISTINCT FROM 'human' OR actor_id IS NULL
                    OR actor_id NOT IN (OLD.requested_by::text, OLD.approver_id::text)
                THEN
                    RAISE EXCEPTION 'a firm export is downloaded by its requester or approver'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            ELSIF OLD.status IN ('ready', 'downloaded') AND NEW.status = 'expired' THEN
                IF actor_kind IS DISTINCT FROM 'system' THEN
                    RAISE EXCEPTION 'a firm export is expired by the system'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            ELSE
                RAISE EXCEPTION 'a firm export moves from % to % never', OLD.status, NEW.status
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER firm_exports_guard BEFORE UPDATE ON firm_exports "
        "FOR EACH ROW EXECUTE FUNCTION firm_exports_guard()"
    )
    op.execute(
        """
        CREATE TABLE firm_export_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            export_id uuid NOT NULL,
            user_id uuid NOT NULL,
            issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            expires_at timestamptz NOT NULL,
            mfa_at timestamptz NOT NULL,
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, export_id) REFERENCES firm_exports (tenant_id, id),
            CONSTRAINT firm_export_links_fifteen_minutes CHECK (
                expires_at > issued_at AND expires_at <= issued_at + interval '15 minutes'
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX firm_export_links_by_person ON firm_export_links "
        "(tenant_id, user_id, issued_at DESC)"
    )
    op.execute(
        """
        CREATE FUNCTION firm_export_links_issue() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
        BEGIN
            IF current_setting('app.actor_kind', true) IS DISTINCT FROM 'human'
                OR current_setting('app.actor_id', true) IS DISTINCT FROM NEW.user_id::text
            THEN
                RAISE EXCEPTION 'a firm export link is issued to the person acting'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM firm_exports e
                WHERE e.tenant_id = NEW.tenant_id AND e.id = NEW.export_id
                    AND e.status IN ('ready', 'downloaded')
                    AND NEW.user_id IN (e.requested_by, e.approver_id)
                    AND NEW.expires_at <= e.available_until
            ) THEN
                RAISE EXCEPTION 'a firm export link needs a ready export, its person, its window'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER firm_export_links_issue BEFORE INSERT ON firm_export_links "
        "FOR EACH ROW EXECUTE FUNCTION firm_export_links_issue()"
    )
    op.execute(
        """
        CREATE FUNCTION firm_export_links_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is insert-only', TG_TABLE_NAME
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER firm_export_links_immutable BEFORE UPDATE OR DELETE ON firm_export_links "
        "FOR EACH ROW EXECUTE FUNCTION firm_export_links_immutable()"
    )
    op.execute(
        "CREATE TRIGGER firm_export_links_no_truncate BEFORE TRUNCATE ON firm_export_links "
        "FOR EACH STATEMENT EXECUTE FUNCTION firm_export_links_immutable()"
    )
    tenant_table(op, "firm_export_links")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON firm_export_links FROM abacus_app")
    insert_columns(
        op,
        "firm_export_links",
        ("id", "tenant_id", "export_id", "user_id", "expires_at", "mfa_at"),
    )


def downgrade() -> None:
    op.execute("DROP TABLE firm_export_links")
    op.execute("DROP FUNCTION firm_export_links_immutable()")
    op.execute("DROP FUNCTION firm_export_links_issue()")
    op.execute("DROP TABLE firm_exports")
    op.execute("DROP FUNCTION firm_exports_guard()")
    op.execute("DROP FUNCTION firm_exports_requester()")
