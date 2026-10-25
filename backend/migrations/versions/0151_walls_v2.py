"""Walls v2 (G-01-T09; G-01 sections 3.8, 4.2; SPEC-002 amended; DEC-43, DEC-73, DEC-318).

- `ethical_walls` gains why (`reason_code`, one of five, existing walls `other`; `reason_text`,
  Confidential, at most 500 characters), who approves (`approver_user_id`, a named partner), the
  approval (`approved_by`, `approved_at`, set together, once) and why it was lifted
  (`removed_reason`). A wall applies the moment it is created (DEC-73); the approval records the
  partner's agreement and changes nothing about access.
- `ethical_walls_forward_only` is replaced: an active wall may be approved once (only the
  approval columns change, from empty) or removed (only the removal columns change); a removed
  wall never changes again; who, which client, why and the named approver never change.

Revision ID: 0151
Revises: 0150
"""

from __future__ import annotations

from alembic import op

revision = "0151"
down_revision = "0150"
branch_labels = None
depends_on = None

_REASONS = (
    "('personal_relationship', 'financial_interest', 'relative', 'prior_employment', 'other')"
)

_FORWARD_ONLY_V2 = """
    CREATE OR REPLACE FUNCTION ethical_walls_forward_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        IF OLD.status <> 'active' THEN
            RAISE EXCEPTION 'ethical wall % is removed', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.user_id IS DISTINCT FROM OLD.user_id
           OR NEW.client_id IS DISTINCT FROM OLD.client_id
           OR NEW.created_by IS DISTINCT FROM OLD.created_by
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR NEW.reason_code IS DISTINCT FROM OLD.reason_code
           OR NEW.reason_text IS DISTINCT FROM OLD.reason_text
           OR NEW.approver_user_id IS DISTINCT FROM OLD.approver_user_id THEN
            RAISE EXCEPTION 'ethical wall % is immutable', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.status = 'removed' THEN
            IF NEW.approved_by IS DISTINCT FROM OLD.approved_by
               OR NEW.approved_at IS DISTINCT FROM OLD.approved_at THEN
                RAISE EXCEPTION 'ethical wall % is approved or removed, not both at once', OLD.id
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END IF;
        IF NEW.status <> 'active' THEN
            RAISE EXCEPTION 'ethical wall % may only be approved or removed', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        -- An active wall stays active: the only change is its approval, set once.
        IF OLD.approved_at IS NOT NULL OR NEW.approved_at IS NULL
           OR NEW.removed_by IS DISTINCT FROM OLD.removed_by
           OR NEW.removed_at IS DISTINCT FROM OLD.removed_at
           OR NEW.removed_reason IS DISTINCT FROM OLD.removed_reason THEN
            RAISE EXCEPTION 'ethical wall % may be approved once', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END
    $$
"""

# 0012's function, restored on downgrade.
_FORWARD_ONLY_V1 = """
    CREATE OR REPLACE FUNCTION ethical_walls_forward_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        IF OLD.status <> 'active' THEN
            RAISE EXCEPTION 'ethical wall % is removed', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.status <> 'removed' THEN
            RAISE EXCEPTION 'ethical wall % may only be removed', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.user_id IS DISTINCT FROM OLD.user_id
           OR NEW.client_id IS DISTINCT FROM OLD.client_id
           OR NEW.created_by IS DISTINCT FROM OLD.created_by
           OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'ethical wall % is immutable', OLD.id
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN NEW;
    END
    $$
"""


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE ethical_walls
            ADD COLUMN reason_code text NOT NULL DEFAULT 'other' CHECK (reason_code IN {_REASONS}),
            ADD COLUMN reason_text text NULL CHECK (length(reason_text) BETWEEN 1 AND 500),
            ADD COLUMN approver_user_id uuid NULL,
            ADD COLUMN approved_by uuid NULL,
            ADD COLUMN approved_at timestamptz NULL,
            ADD COLUMN removed_reason text NULL CHECK (length(removed_reason) BETWEEN 1 AND 500),
            ADD CONSTRAINT ethical_walls_approved
                CHECK ((approved_at IS NULL) = (approved_by IS NULL)),
            ADD CONSTRAINT ethical_walls_approved_by_the_named_approver
                CHECK (approved_by IS NULL OR approved_by = approver_user_id),
            ADD CONSTRAINT ethical_walls_approver_fkey
                FOREIGN KEY (tenant_id, approver_user_id)
                REFERENCES memberships (tenant_id, user_id),
            ADD CONSTRAINT ethical_walls_approved_by_fkey
                FOREIGN KEY (tenant_id, approved_by) REFERENCES memberships (tenant_id, user_id)
        """
    )
    op.execute(
        "GRANT INSERT (reason_code, reason_text, approver_user_id) ON ethical_walls TO abacus_app"
    )
    op.execute(
        "GRANT UPDATE (approved_by, approved_at, removed_reason) ON ethical_walls TO abacus_app"
    )
    op.execute(_FORWARD_ONLY_V2)


def downgrade() -> None:
    op.execute(_FORWARD_ONLY_V1)
    op.execute(
        "REVOKE UPDATE (approved_by, approved_at, removed_reason) ON ethical_walls FROM abacus_app"
    )
    op.execute(
        "REVOKE INSERT (reason_code, reason_text, approver_user_id) ON ethical_walls "
        "FROM abacus_app"
    )
    op.execute(
        "ALTER TABLE ethical_walls DROP CONSTRAINT ethical_walls_approved_by_fkey, "
        "DROP CONSTRAINT ethical_walls_approver_fkey, "
        "DROP CONSTRAINT ethical_walls_approved_by_the_named_approver, "
        "DROP CONSTRAINT ethical_walls_approved, DROP COLUMN removed_reason, "
        "DROP COLUMN approved_at, DROP COLUMN approved_by, DROP COLUMN approver_user_id, "
        "DROP COLUMN reason_text, DROP COLUMN reason_code"
    )
