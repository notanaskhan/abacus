---
id: TASK-044
title: Acceptance, independence, the engagement letter and the engagement gate
spec: SPEC-025
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7, AC-9]
risk_zone: red
status: awaiting-plan-approval
branch: task-044-acceptance-independence
worktree:
created: 2026-10-09
updated: 2026-10-09
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-025 task (c), split in two (D1):
- **TASK-044 (this task):** the records (acceptance and continuance, with the predecessor auditor; the partner's independence conclusion; each member's confirmation; the letter), the requests to confirm, and the **engagement-level gate** on client-data actions;
- **TASK-045:** the **per-person gate** (each member's own access to client data opens only when they confirm). It lives in the central permission check inside `identity/authz`; see D1.

## Scope
SPEC-025 AC-4, AC-5, AC-6, the engagement-level half of AC-7, and AC-9 for these screens. The per-person half of AC-7 is TASK-045.

## Context to load
- Spec: `docs/specs/SPEC-025-act-1-the-engagement-opens.md`; ADR-005, ADR-016, ADR-026
- Code:
  - `engagements` (service, routes, `lock_ref`);
  - identity `team.py` (`add_member`) and `service.add_creator_as_partner` / `add_self_joined_admin`;
  - `evidence/storage.py`, `evidence/uploads.py` (`checked`), `item_detail.download`;
  - the client-data entry points: `engagements.invite_client`, `connections.connect.start`/`complete`, `connections.retrievals.trigger_retrieval`, `evidence.uploads.upload`, `evidence.inbox.add_to_inbox`/`assign`;
  - the notifications catalogue.

## Plan
- [ ] Plan approved by human

### What the code shows
- **Nothing records acceptance, independence or the letter.** The matrix has no actions for them.
- **Write-once, encrypted file storage lives in `evidence`** (`evidence/storage.py`), and evidence depends on engagements, not the other way round. So acceptance files and signed letters are uploaded through evidence, and the engagements record holds the stored object's reference (D2).
- **Client data enters through six service functions** across engagements, connections and evidence. Each can ask engagements whether the engagement is open, with no boundary change: connections and evidence already depend on engagements.
- **A person's access to client data is decided in `authorise` and `visible()`,** in `identity/authz/__init__.py`. A per-person rule belongs there (D1).

### Design (for founder review)
1. **Data (engagements migration 0036):**
   - **`engagement_acceptance`**, one live row per engagement, a new row superseding the old: kind (`new_client` or `continuance`, pre-filled: continuance when the client has an earlier engagement of the same type), decision (`accepted` or `declined`), decided by and at, documented at (up to 300 characters), optional file (the stored object's reference), optional predecessor auditor and date communicated (new clients), and the partner's independence conclusion (concluded by, at, documented at).
   - **`independence_confirmations`:** engagement, user, status (`requested`, `confirmed` or `declined`), statement version, note (up to 1,000 characters, declines only), at; one row per person per engagement.
   - **`engagement_letters`:** engagement, status (`not_started`, `sent`, `signed` or `not_required_this_year`), date, reason (required for "not required"), link (an https URL) or file reference.
   - **`firms.require_letter_before_client_data`** (default false), with a toggle on the Autonomy page (`firm.manage_settings`).
2. **Matrix actions (with the generated `_matrix.py`):**
   - `engagement.acceptance.record` (engagement partner, fresh MFA): decision, kind, documented at, file, predecessor fields, and the independence conclusion;
   - `independence.confirm` (every staff engagement role, for oneself only; the service refuses acting for someone else);
   - `engagement.letter.record` (engagement partner, manager);
   - `engagement.setup.read` (every staff engagement role, plus firm administrators and practice leaders): the records and everyone's confirmation state (decline notes only to the partner and manager).
3. **Requests to confirm:**
   - a person joining an engagement's team (creator as partner, added member, self-joined administrator) gets a `requested` confirmation and a notification (`independence.requested`, to that person), in the same unit of work;
   - this hooks into identity's add-member paths through a new registration slot, `register_member_added`, beside the existing removal slot (ADR-106).
4. **The engagement gate (engagement-level AC-7):**
   - `engagements.api.require_open(tenant, engagement_id, action)` raises 409 `engagement_not_open`, with the reason ("acceptance not recorded", "acceptance declined", "independence conclusion missing", or "engagement letter not recorded" when the firm requires it);
   - it's called at the start of the six client-data entry points (client invitation, connection start and complete, retrieval, client upload, inbox add and assign), each audited `client_data.gate_refused` when refused;
   - automatic retrieval checks it too, and is skipped while the engagement isn't open.
5. **Files (D2):**
   - evidence routes `POST …/acceptance/file` and `POST …/letter/file` take a raw body with the SPEC-020 checks (PDF, Word or image, 25 MB);
   - they store write-once, then call `engagements.api.attach_acceptance_file` / `attach_letter_file`;
   - download goes through the SPEC-021 attachment route pattern (audited, verified).
6. **Existing engagements (SPEC-025 Q7):** the migration writes, for every existing engagement:
   - an acceptance row "accepted, before Act 1" (decided by the system, documented at "recorded before Act 1"), with the conclusion the same;
   - `confirmed` rows for each current staff member, marked "before Act 1".

   Live work isn't blocked.
7. **Web** (until the setup page, task d, brings it together):
   - an **Acceptance** panel and a **Letter** panel on the engagement's People tab (partner: record; others: view);
   - an **Independence** list (who has confirmed);
   - a "**Your confirmations**" card on the engagements page with Confirm / Decline (a fixed statement: "I confirm I am independent of {client} for this engagement, under the firm's independence policy");
   - the six client-data buttons show the gate's reason instead of failing.

**Protected paths (approval file):**
- `backend/src/abacus/modules/identity/*` (top-level only: the member-added slot, the firm letter setting);
- `docs/architecture/permission-matrix.yaml` and the generated `backend/src/abacus/modules/identity/authz/_matrix.py`;
- `backend/src/abacus/modules/evidence/**` (file uploads, the gate in uploads and inbox);
- `backend/src/abacus/modules/connections/**` (the gate in connection and retrieval);
- `backend/src/abacus_tools/quality/schema_check.py` (new tables, grants, the `firms` column);
- `backend/src/abacus_tools/quality/banned_patterns.py` (if needed);
- `backend/tests/unit/**`.

Not needed:
- `api/app.py` (the routes go on existing routers);
- `identity/authz` beyond the generated matrix file. TASK-045 is where `authz/__init__.py` would change, and only with your approval.

### Questions for approval
- **D1. Split per-person gating into TASK-045, in the central permission check?**
  - **The file:** `backend/src/abacus/modules/identity/authz/__init__.py` (and `authz/matrix.py` for a new matrix modifier, `requires: independence`, marking client-data actions).
  - **Why there:** `authorise` and `visible()` are the only place every read and list of client data passes. A check in the services would miss the list queries (the Board, the review queue, screening results) and anything added later.
  - **How:** a new layer after "relationships". For an action marked `requires: independence`, a staff member's engagement role counts only once they've confirmed for that engagement. Engagements answers through a registration slot, as walls do (ADR-106). `visible()` applies the same filter.
  - **The marked actions:** `evidence.read`, `evidence.upload`, `review.*`, `evidence.accept` / `reject`, `screening.request`, `connection.read_log`. Request items and the setup stay visible.

  *Recommendation: yes, split, and approve that design for TASK-045 when it comes.* TASK-044 then ships the records and the engagement gate on their own.
- **D2. Upload acceptance files and signed letters through evidence (write-once, encrypted, never rendered) and keep only their reference on the engagements records?** *Recommendation: yes.* There's no new storage path and no boundary change.
- **D3. Mark existing engagements "accepted, before Act 1", with their current staff "confirmed, before Act 1", visibly labelled?** *Recommendation: yes* (SPEC-025 Q7, as approved).
- **D4. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Design written for founder review after TASK-043 merged (#79).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
