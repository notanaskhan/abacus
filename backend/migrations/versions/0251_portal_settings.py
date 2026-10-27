"""ADM-10's portal settings: one draft per firm and insert-only published versions (R-01-T26;
`docs/contracts/portal-settings.md`; SPEC-345; DEC-653).

- New `portal_settings_drafts`: the firm's one draft (primary key `tenant_id`): the brand slots,
  the client-experience toggles and the follow-up policy as JSON objects (bounded), the version it
  was based on, `expected_version` (a save at an older one is 409 `stale_version`), and a new logo
  waiting for the publish (`logo`, the raw upload, at most 2 MB; P-08 re-encodes it on publish).
  Saved and discarded by the app; nothing else reads it.
- New `portal_settings_versions` (insert-only): each publish, numbered per firm, with its content
  hash and who published it. The live brand stays P-08's `portal_branding` and the live policy
  communications' `follow_up_policies`; a version is the record of what a publish applied.

Revision ID: 0251
Revises: 0250
"""

from __future__ import annotations

from alembic import op

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

revision = "0251"
down_revision = "0250"
branch_labels = None
depends_on = None

_OBJECT = "jsonb_typeof({c}) = 'object' AND octet_length({c}::text) <= 4096"


def upgrade() -> None:
    brand, experience, policy = (
        _OBJECT.format(c=c) for c in ("brand", "client_experience", "follow_up_policy")
    )
    op.execute(
        f"""
        CREATE TABLE portal_settings_drafts (
            tenant_id uuid PRIMARY KEY,
            expected_version integer NOT NULL CHECK (expected_version >= 1),
            base_version integer NULL CHECK (base_version >= 1),
            brand jsonb NOT NULL CHECK ({brand}),
            client_experience jsonb NOT NULL CHECK ({experience}),
            follow_up_policy jsonb NOT NULL CHECK ({policy}),
            logo bytea NULL CHECK (octet_length(logo) <= 2097152),
            saved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            saved_by uuid NOT NULL,
            FOREIGN KEY (tenant_id, saved_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE portal_settings_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            brand jsonb NOT NULL CHECK ({brand}),
            client_experience jsonb NOT NULL CHECK ({experience}),
            follow_up_policy jsonb NOT NULL CHECK ({policy}),
            content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{{64}}$'),
            logo_sha256 text NULL CHECK (logo_sha256 ~ '^[0-9a-f]{{64}}$'),
            published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            published_by uuid NOT NULL,
            UNIQUE (tenant_id, version),
            FOREIGN KEY (tenant_id, published_by) REFERENCES memberships (tenant_id, user_id)
        )
        """
    )
    tenant_table(op, "portal_settings_drafts")
    tenant_table(op, "portal_settings_versions")
    insert_only(op, "portal_settings_versions")
    _draft = (
        "tenant_id",
        "expected_version",
        "base_version",
        "brand",
        "client_experience",
        "follow_up_policy",
        "logo",
        "saved_by",
    )
    insert_columns(op, "portal_settings_drafts", _draft)
    op.execute(
        "GRANT UPDATE (expected_version, base_version, brand, client_experience, "
        "follow_up_policy, logo, saved_at, saved_by), DELETE ON portal_settings_drafts "
        "TO abacus_app"
    )
    insert_columns(
        op,
        "portal_settings_versions",
        (
            "tenant_id",
            "version",
            "brand",
            "client_experience",
            "follow_up_policy",
            "content_sha256",
            "logo_sha256",
            "published_by",
        ),
    )


def downgrade() -> None:
    op.execute("DROP TABLE portal_settings_versions")
    op.execute("DROP TABLE portal_settings_drafts")
