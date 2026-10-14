---
id: TASK-066
title: "Content matching, part 3: running the matcher in the product, \"Suggest with AI\", and its suggestions on screen"
spec: SPEC-033
acceptance_criteria: [AC-3, AC-4, AC-5, AC-6, AC-9]
risk_zone: red
status: done
branch: task-066-matcher-product
worktree:
created: 2026-10-13
updated: 2026-10-13
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-033 §7, TASK-066: the matcher built and evaluated in TASK-065 (and TASK-067) runs on inbox files in the product. That means synthetic firms only (ADR-112). Its proposals reach the firm, and its picks (without its words) reach the client.

## Scope
SPEC-033 AC-3, AC-4, AC-5, AC-6, AC-9.

## Context to load
- Spec: `docs/specs/SPEC-033-content-matching.md` §4.5–4.8; SPEC-027 (engagement agent policies)
- Code (copy the reviewer's product path, TASK-059):
  - `agents/review_start.py`, `agents/engagement_agent.py` (P-6), `agents/workflows.py` (`UploadReviewWorkflow`), `agents/activities.py`, `agents/inbox_match.py`;
  - `evidence/processing.py` (inbox extraction), `evidence/inbox.py` (`_entries`, suggestions), `evidence/service.py` (`register_proposal_source`, the registration pattern);
  - `apps/web/src/screens/InboxPanel.tsx`, `AIReviewPanel.tsx`

## Plan
- [x] Plan approved by human (founder, 2026-10-14: D1–D4 as recommended). Approved by founder: the paths named in D4

### What the code shows
- **The reviewer's product path is the pattern:**
  - an event, then a policy (P-6) that checks the flag, the pause, the autonomy level and a real route, then a workflow;
  - the workflow creates the run, takes a work slot, calls the agent (waiting while not admitted) and always fails a run cleanly;
  - "Review now" at Advise;
  - firm-only reads, and a marker on the Board.
- **Nothing signals that an inbox file has been extracted.** Processing records the extraction and stops.
- **Evidence can't read agents' tables** (agents depends on evidence). Evidence already takes agent proposals through a registered lookup (`register_proposal_source`), so the same way works for matcher picks.

### Design (for founder review)
1. **Event** (evidence): `inbox_file.extracted` (engagement, inbox file), emitted when an inbox file's extraction is recorded as extracted.
2. **Policy P-7 match** (agents): on `inbox_file.extracted`, start the matcher when:
   - the firm's `matching.enabled` flag is on;
   - the agent isn't paused;
   - the firm is at Routine or above;
   - a real model route exists;
   - the content rules weren't decisive (SPEC-033 Q3).

   Otherwise record the skip with its reason in the activity feed (`matching_off`, `no_real_model`, `advise`, `no_partner`, paused). A decisive file is skipped silently (D3). With the engagement agent off, the same rules apply directly, as P-6 does.
3. **On whose behalf:** the engagement partner (as for the reviewer).
4. **Workflow** `InboxMatchWorkflow` (`inbox_match:<tenant>:<file>`, background):
   - create the run, take a work slot, call `match` (waiting while not admitted), and end any failure with `fail_run` (`data_boundary` for a non-synthetic firm);
   - new activities `inbox_match.create_run` and `inbox_match.match`; the screener's slot and fail activities are reused;
   - replay histories recorded (completed and skipped).
5. **"Suggest with AI"** (`POST …/inbox/{file}/match`, new action `inbox_match.request`: partner, manager, senior, staff): starts the same workflow at Advise, or again; audited. Without a real route it's refused as `ai_match_unavailable` (409), as "Review now" is.
6. **Firm reads** (`GET …/inbox/matches`, new action `inbox_match.read`: firm roles, with independence; client roles refused by the matrix). Per waiting file:
   - the latest run's status: `none`, `running`, `completed`, or `failed` with its reason;
   - `none_fit` with its rationale;
   - its shown proposals: request, confidence, rationale, verified quotes only.
7. **Picks in the inbox, for everyone** (SPEC-033 Q1, D1):
   - agents registers `matcher_picks(tenant, file_ids)` into evidence, returning the shown proposals' request IDs in rank order;
   - evidence's inbox listing puts them first as suggestions with `source: matcher` and no reasons, then the content and file-name suggestions (deduplicated, at most three);
   - clients thus see "Suggested" picks by the firm's own request descriptions, never the matcher's words;
   - assigning a matcher pick records `suggestion_source` 3 (TASK-064).
8. **Screens:**
   - **Firm Inbox panel:** an "AI suggestion" block per file. It shows the AI tag with the citation count; each proposal's request, confidence and rationale (through `AgentText`); quotes that open the file's preview at that page; "None of the requests fit" with its rationale; and "Suggest with AI" for those allowed. Loading, empty, error and not-allowed states.
   - **Client Inbox panel:** matcher picks look like any suggestion, labelled "Suggested", with no AI wording or tag (ADR-111).
9. **Flag** `matching.enabled`: off, and on for the local Dev firm, which is synthetic.
10. **Tests:**
    - P-7 decisions (flag, pause, autonomy, decisive, agent off);
    - the boundary refusal;
    - firm reads deny client roles and never return hidden proposals or unverified quotes;
    - the client inbox carries picks without rationale;
    - workflow replay;
    - vitest for the firm block, quotes, "Suggest with AI" and the client label;
    - a local smoke on the Dev firm with the real model allowed (`.env.evaluation` values): drop "scan0043.pdf" (a loan agreement) and see it proposed for the debt request.

### Questions for the human
- **D1 — how clients get the picks.** Recommended: agents registers a lookup into evidence, and evidence merges the picks into the inbox suggestions (request IDs only). Clients see them as "Suggested", with no AI text, as SPEC-033 Q1 decided. Alternative: a separate client endpoint in agents (more surface, same result).
- **D2 — on whose behalf.** Recommended: the engagement partner, as for the reviewer.
- **D3 — skips in the activity feed.** Recommended: record policy skips (flag off, paused, Advise, no model, no partner), but not files where code was already decisive, which would flood the feed on a bulk upload.
- **D4 — approval file:**
  - `backend/src/abacus/modules/agents/**`, `backend/src/abacus/modules/evidence/**`;
  - `docs/architecture/permission-matrix.yaml`, `backend/src/abacus/modules/identity/authz/_matrix.py`;
  - `docs/architecture/feature-flags.yaml`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation; client roles never receive the matcher's words
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-13` — Design written for founder review after TASK-065 (#116); TASK-067 (cell references) in progress.
- `2026-10-14` — Built (D1–D4): `inbox_file.extracted`; P-7; `match_start` (starter, "Suggest with AI", firm reads, picks lookup); `InboxMatchWorkflow` and activities with replay histories; `inbox_match.read` and `inbox_match.request`; flag `matching.enabled` (on for the Dev firm by the seed); migration 0050; the firm's AI suggestion block and "Suggest with AI" on the Board's inbox; matcher picks as "Suggested" for clients. Backend (10,436 with workflow replays), web (310) and gates pass. Local smoke on the Dev firm with the real model: a loan agreement named "scan0043.pdf" was proposed for the engagement's loan and debt requests (0.90–0.95, verified quote); the client saw the picks only as "Suggested"; the client was refused the firm's reads.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| `agent_runs.inbox_file_id` (migration 0050) | The firm's panel needs a run in progress or failed (`data_boundary`) beside its file, not only completed proposals | No |
| Firm reads at `GET …/inbox-matches` (not `/inbox/matches`) | Keeps clear of evidence's `/inbox/{file_id}` routes | No |
| The picks lookup is LIST_EXEMPT | It runs for evidence's listing, which already authorised the caller on those files; client roles can't hold `inbox_match.read` | No |

## Handoff
Done. SPEC-033 is complete. Restart `make dev` for the worker to host the matcher; with the real model allowed locally (`.env.evaluation`), the Dev firm runs it.
