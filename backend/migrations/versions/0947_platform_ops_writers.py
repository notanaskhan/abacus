"""G-04-T10 (DEC-5417): the operator may run the console's global writers.

0920 left its owner-only writers with the migration owner alone. Status incidents, help-article
drafts, publication and withdrawal, and the tenant directory upsert are run by the operator
command (`abacus_tools.platform_console`) as `abacus_ops`, the EXECUTE-only role (ADR-156): the
API and the worker still cannot call them. Grants only; no table or function changes.

Revision ID: 0947
Revises: 0946
"""

from __future__ import annotations

from alembic import op

revision = "0947"
down_revision = "0946"
branch_labels = None
depends_on = None

WRITERS = (
    "platform_directory_upsert(uuid, text, text, text, integer, integer, text[], text, text,"
    " text, text, timestamptz, integer, boolean, uuid, date)",
    "help_article_draft(text, text, text, text, text[], integer, jsonb, text, text)",
    "help_article_publish(uuid, text, text)",
    "help_article_withdraw(uuid, text, text)",
    "status_incident_post(text, text, text, text, text)",
    "status_incident_update(uuid, text, text)",
    "status_incident_resolve(uuid, text, text)",
)


def upgrade() -> None:
    for signature in WRITERS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO abacus_ops")


def downgrade() -> None:
    for signature in WRITERS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM abacus_ops")
