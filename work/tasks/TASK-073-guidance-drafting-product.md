---
id: TASK-073
title: "Drafted guidance, part 2: drafting in the product, review and approval, and the client display setting"
spec: SPEC-035
acceptance_criteria: [AC-1, AC-2, AC-4, AC-5, AC-6, AC-8]
risk_zone: red
status: done
branch: task-073-guidance-drafting-product
worktree:
created: 2026-10-15
updated: 2026-10-15
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-035 §7, TASK-073: the guidance drafter built in TASK-072 runs in the product on request items, for synthetic firms only. A person reviews and approves every draft. Approved drafted text reaches clients only when the firm's setting allows it (ADR-111).

## Scope
SPEC-035 AC-1, AC-2, AC-4, AC-5, AC-6, AC-8 for request items. Template items, part of SPEC-035 Q3, are D1.

## Context to load
- Spec: `docs/specs/SPEC-035-drafted-guidance.md`; ADR-005, ADR-111, ADR-112
- Code:
  - `agents/guidance_draft.py`, `agents/match_start.py` (the starter and workflow pattern), `agents/workflows.py`;
  - `requests/service.py` (`set_item_guidance`, `request_items_for`, `_view`), `requests/guidance.py`;
  - `identity/firm_settings.py` (autonomy, firm settings);
  - `apps/web/src/screens/ClientGuidance.tsx`, `Board.tsx`

## Plan
- [x] Plan approved by human (founder, 2026-10-15: D1–D4 as recommended; templates in TASK-074). Approved by founder: the paths named in D4

### What the code shows
- **Request items carry `guidance_source`** (`template`, `kind_default`, `firm`). The firm writes guidance through `set_item_guidance` (`request_item.update`), which sets `firm`.
- **The client's request list** is built in requests from the same item rows, so a display rule fits there.
- **Firm settings** (autonomy level and others) live in identity's `firm_settings`, set by a firm admin with fresh MFA.
- **`agent_runs` requires an engagement,** so a template item, which belongs to no engagement, can't have a run without schema and budget changes (TASK-072's finding).

### Design (for founder review)
1. **Data** (migration 0053):
   - `request_items.guidance_source` also allows `drafted`;
   - `guidance_draft_decisions` (agents, insert-only): draft, decision (`approved`, `discarded`), edited (bool), confirmed-read (bool), by whom, when;
   - `firm_settings.drafted_guidance_to_clients` (boolean, default false), D2.
2. **Permissions:**
   - `guidance_draft.request`: partner, manager, senior, with independence;
   - `guidance_draft.decide`: the same roles;
   - client roles are refused by the matrix.
3. **Starting** (agents, `draft_start.py`):
   - `POST …/request-items/draft-guidance {item_ids}` checks the flag `guidance.drafting`, a real model route, a synthetic firm (the gateway refuses others, AC-2) and the daily cap;
   - it starts `GuidanceDraftWorkflow` (`guidance_draft:<tenant>:<request>`, batch): one activity per item, reusing the screener's slot and fail steps; replay histories recorded;
   - items with firm-written guidance are skipped unless named explicitly;
   - without a real route the request is refused as `ai_drafting_unavailable` (409).
4. **Reading** (`GET …/guidance-drafts`, firm roles): per item, its latest draft that passed the checks and has no decision yet, with why, good looks like and the suggestions with their reasons. Drafts that failed the checks are never returned.
5. **Approving and discarding:**
   - `POST …/guidance-drafts/{id}/approve {why, good_looks_like, effort?, blocks_fieldwork?}`: the person may edit the text, and code checks the edited text with the same rules;
   - approval writes the item's guidance through requests (a new `apply_drafted_guidance`, source `drafted`, `request_item.update`), records the decision with `edited`, and is audited;
   - `POST …/guidance-drafts/approve-all {draft_ids, read_confirmed: true}`: bulk approval needs the confirmation (SPEC-035 Q5), and each draft gets its own decision;
   - `POST …/guidance-drafts/{id}/discard`;
   - editing approved drafted guidance later through `set_item_guidance` makes it `firm` (AC-6), as today.
6. **Client display (AC-5, ADR-111):** where requests builds the client's request list, an item with source `drafted` shows its why and what good looks like only when the firm's `drafted_guidance_to_clients` is on. Otherwise it shows the item's kind default, or nothing. The firm always sees it, labelled "Drafted with AI, approved by {name}" (the approver comes from the decision).
7. **Screens:**
   - the Board gets "Draft guidance" for selected items, or all items without guidance;
   - a **Drafts to review** panel lists each draft beside its request, with the AI tag (`AgentText`): edit, approve, discard, and "Approve all I've read" (with its checkbox);
   - item detail's Client guidance panel shows a pending draft, and the "Drafted with AI" label;
   - the firm admin settings page gets the toggle "Show guidance drafted with AI and approved by your team to clients" (fresh MFA), available only to synthetic firms;
   - loading, empty, error and not-allowed states.
8. **Flag** `guidance.drafting`: off; on for the Dev firm (synthetic) in the seed.
9. **Tests:**
   - the starter's refusals (flag, route, cap, non-synthetic);
   - approve, edit-then-approve (checks rerun on the edit), discard, bulk with and without confirmation;
   - source becomes `drafted`, and later editing makes it `firm`;
   - the client list with the setting on and off;
   - clients refused on every drafting route;
   - workflow replay;
   - vitest for the panel, labels and toggle;
   - a local smoke on the Dev firm with the real model allowed.

### Questions for the human
- **D1 — templates.** Drafting on methodology template items needs agent runs without an engagement, and a firm-level budget for them, which is a change to the agents run model and budgets. Recommended: do it as its own task (TASK-074) after this one, so request items ship first. Alternative: include it here, which roughly doubles this task.
- **D2 — where the client display setting lives.** Recommended: a column on identity's `firm_settings` beside the autonomy level, set by a firm admin with fresh MFA, like the other firm settings. This touches identity, a protected path.
- **D3 — the label clients see.** Recommended: clients see drafted guidance (when allowed) without an AI label, because by then it's text the firm has approved and chosen to publish. The firm sees "Drafted with AI, approved by {name}". Alternative: clients also see a small "Drafted with AI" note.
- **D4 — approval file:**
  - `backend/src/abacus/modules/agents/**`, `backend/src/abacus/modules/identity/**` (the setting and `_matrix.py`);
  - `docs/architecture/permission-matrix.yaml`, `docs/architecture/feature-flags.yaml`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation; clients never see an unapproved or disallowed draft
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-15` — Design written for founder review after TASK-072 merged (#127).
- `2026-10-15` — Built (D1–D4): migration 0053 (`drafted` source, `guidance_approved_by`, `guidance_draft_decisions`, `firms.drafted_guidance_to_clients`); the setting and its routes (identity); `apply_drafted_guidance` and the client display rule (requests); `draft_start.py`, `GuidanceDraftWorkflow` and activities with replay histories; `guidance_draft.read/request/decide`; flag `guidance.drafting`; the Board's drafts panel, item detail's label and the admin toggle. Unit and workflow tests (10,756), web (327) and gates pass. Real-model smoke on the Dev firm: a draft passed the checks; an edit adding a name and phone number was refused; the edited approval wrote `drafted` with the approver; the client saw nothing with the setting off and the approved text with it on.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| One workflow per item, not one per request | Each item takes its own work slot and retries alone, as the matcher does | No |
| `guidance_approved_by` on request items | The firm's label needs the approver, and requests can't read agents' tables | No |
| A separate read action, `guidance_draft.read` | List queries need a read action for `visible()` | No |
| The setting refuses non-synthetic firms, and reading it is false for them | ADR-111/112: a person's approval alone doesn't let drafted text reach a real client | No |

## Handoff
Done. Next: TASK-074 (drafting on methodology template items: runs without an engagement, a firm-level budget).
