"""An elimination draft may be off balance; approving or posting one may not (CV-2, TASK-9001;
ED-346; DEC-6007; SPEC-658 AC-4.3; AUD-33 c).

0643's deferred constraint trigger refuses any proposed entry whose lines do not balance at
commit. SPEC-658 AC-4.3 (A-09-T20) wants an unbalanced elimination kept, shown "Off 10,000", with
approve answering 409 `unbalanced_entry`; `eliminations.propose_elimination` and
`edit_elimination` were built for that, but the trigger refused the insert, so proposing or editing
an off-balance elimination failed with a 500. CV-2's suite found it.

The line trigger now skips an elimination while it is a draft (`proposed`, `review_required`,
`within_threshold`); every other entry, and every elimination past draft, balances as before. A
new deferred trigger on `proposed_entries` refuses an elimination moving to `approved` or `posted`
unbalanced, so the database still holds what the service checks.
"""

from __future__ import annotations

from alembic import op

revision = "1031"
down_revision = "1030"
branch_labels = None
depends_on = None

_BALANCED = """
CREATE OR REPLACE FUNCTION proposed_entry_balanced() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    entry uuid := COALESCE(NEW.entry_id, OLD.entry_id);
    tenant uuid := COALESCE(NEW.tenant_id, OLD.tenant_id);
    dr numeric;
    cr numeric;
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.proposed_entries e
         WHERE e.tenant_id = tenant AND e.id = entry
           AND e.kind = 'elimination'
           AND e.status IN ('proposed', 'review_required', 'within_threshold')
    ) THEN
        RETURN NULL;  -- an elimination draft shows its off-by (SPEC-658 AC-4.3)
    END IF;
    SELECT COALESCE(sum(debit), 0), COALESCE(sum(credit), 0) INTO dr, cr
      FROM public.proposed_entry_lines WHERE tenant_id = tenant AND entry_id = entry;
    IF dr <> cr THEN
        RAISE EXCEPTION 'unbalanced_entry' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END
$$
"""

_ORIGINAL = """
CREATE OR REPLACE FUNCTION proposed_entry_balanced() RETURNS trigger
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

_DECIDED = """
CREATE FUNCTION elimination_decided_balanced() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    dr numeric;
    cr numeric;
BEGIN
    IF NEW.kind <> 'elimination' OR NEW.status NOT IN ('approved', 'posted') THEN
        RETURN NULL;
    END IF;
    SELECT COALESCE(sum(debit), 0), COALESCE(sum(credit), 0) INTO dr, cr
      FROM public.proposed_entry_lines WHERE tenant_id = NEW.tenant_id AND entry_id = NEW.id;
    IF dr <> cr THEN
        RAISE EXCEPTION 'unbalanced_entry' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END
$$
"""


def upgrade() -> None:
    op.execute(_BALANCED)
    op.execute(_DECIDED)
    op.execute("REVOKE ALL ON FUNCTION elimination_decided_balanced() FROM PUBLIC")
    op.execute(
        "CREATE CONSTRAINT TRIGGER elimination_decided_balanced AFTER UPDATE OF status "
        "ON proposed_entries DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION elimination_decided_balanced()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER elimination_decided_balanced ON proposed_entries")
    op.execute("DROP FUNCTION elimination_decided_balanced()")
    op.execute(_ORIGINAL)
