---
id: TASK-104
title: "Follow-ups v2 (the plan's P-06-T14, DEC-74): the agent only drafts, one follow-up per client contact; a person drafts on demand, reads the exact email, adds a note and sends with ten seconds to undo"
spec: SPEC-027
acceptance_criteria: [AC-3, AC-4]
risk_zone: red
status: done
branch: task-104-follow-ups
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Objective
Replace the agent's automatic reminder emails with drafts a person sends. This is the plan's DEC-74, and it supersedes the shelved SPEC-039 (no model-written text to clients, per ADR-111).

## Scope
**In**
- `agents/reminders.remind`: always drafts, at every autonomy level. The send path (`_send`, the agent run that sent as the agent) is removed. This supersedes SPEC-027 AC-3's sending at Routine. The cadence (3 business days, at most 3 per due date) is unchanged.
- `reminders.draft_now` and `POST /reminders/draft` (`follow_up.draft`): a person drafts follow-ups for everything overdue now, one per contact, outside the cadence. Items already in a waiting draft, or reminded three times for this due date, are left out.
- `communications.render_reminder` and `POST /reminders/{id}/preview` (`follow_up.draft`): the subject and body exactly as `send_reminder` sends them, from the fixed template, with the person's optional note.
- Web: `FollowUps.tsx` on the Requests tab.
  - A pane listing drafts (to, overdue items, drafted), plus "Draft follow-ups for overdue items".
  - "Review and send" opens a Sheet with the email preview, an optional note (refreshed on blur), Dismiss and Send.
  - Send holds the action for ten seconds with Undo (`toast.deferred`).
  - The old reminder panel on Setup is removed. The component stays for its existing tests.
- Tests: `test_reminders.py` updated (the agent drafts at Routine; no partner is needed to draft); `task104followups.test.tsx` (2); `test_app_gates` pins.

**Out**
- `follow_up.send` set to `agent: deny` in the matrix. The agent can no longer send, because its send path is gone, but changing the rule also needs the engagement agent spec's task scope and the autonomy-condition tests changed (follow-up).
- Renaming `reminders` to `follow_ups` in code (the plan's F-03-T16).

## Definition of done
- [x] Targeted tests pass; `make check-fast` passes.
- [ ] Not walked live (the dev server was stopped).
