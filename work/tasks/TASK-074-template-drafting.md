---
id: TASK-074
title: "Drafted guidance, part 3: drafting on methodology template items, approved into a new template version"
spec: SPEC-035
acceptance_criteria: [AC-1, AC-2, AC-4, AC-5, AC-8]
risk_zone: red
status: done
branch: task-074-template-drafting
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
SPEC-035 Q3. The guidance drafter drafts why and what good looks like for a methodology template's items. A firm admin or practice leader reviews them, and the approved guidance becomes a new version of the template, carried to every engagement that applies or rolls forward to it (SPEC-031 AC-8).

## Scope
SPEC-035 AC-1, AC-2, AC-4, AC-5 and AC-8 for template items. Synthetic firms only (ADR-112).

## Context to load
- Spec: `docs/specs/SPEC-035-drafted-guidance.md` (Q3); SPEC-008 (methodology templates and versions); ADR-047, ADR-070, ADR-111, ADR-112
- Code:
  - `agents/guidance_draft.py`, `agents/draft_start.py`, `agents/service.py` (`_run`, `load_agent_context`);
  - `identity/context.py` (`AgentContext`, `agent_context_for_run`), `identity/authz` (agent rules);
  - `engagements/service.py` (template versions, `version_detail`), `engagements/repository.py` (`insert` of versions and items);
  - `ai_gateway/budgets.py` (the firm-level month); `apps/web/src/screens/MethodologyVersion.tsx`

## Plan
- [x] Plan approved by human (founder, 2026-10-15: D1–D4 as recommended). Approved by founder: the paths named in D4, and `backend/src/abacus/api/app.py` (added 2026-10-15 for the new router)

### What the code shows
- **Agent runs belong to an engagement.** `agent_runs.engagement_id` is required, with foreign keys built on it. `AgentContext` carries one engagement, and the agent's permissions are checked against that engagement. A template item belongs to no engagement.
- **Budgets already have a firm level.** Usage records may have no engagement, and the gateway checks the firm's monthly budget when a call has none.
- **Template versions are immutable.** `methodology_request_items` is insert-only, and a firm changes a template by importing a new version (SPEC-008). Engagements pin the version they applied.
- **Applying a template already carries its guidance** (`why`, `good_looks_like`, `blocks_fieldwork`, `effort`) into request items with source `template` (TASK-060). Roll-forward offers the latest version's items.

### Design (for founder review)
1. **Firm-level drafter runs (D1):**
   - `agent_runs.engagement_id` becomes nullable, with a CHECK that only the guidance drafter may run without one;
   - a nullable `methodology_version_id` names the template version a run drafts for;
   - `AgentContext` gains a firm-level form (no engagement), issued only by the agents run loader (SYS-001);
   - such an agent may hold only `methodology.read` and `guidance_draft.run`, authorised against the firm, with the initiator (a firm admin or practice leader) needing them too;
   - costs land on the firm's monthly budget (ADR-070), within the daily cap per firm.
2. **Template drafts:** `template_guidance_drafts` (agents, insert-only): template version, item position, agent run, the draft, the check outcome. The drafter's context is the item's description, area code name and tier, plus up to three of the template's own guidance texts as tone examples. There is no year end in this context, since a template spans years.
3. **Drafting:** "Draft guidance" on a template version page (`POST /v1/methodology/templates/{name}/versions/{n}/draft-guidance`, new action `template_guidance.request`: firm admin and practice leader, matching `methodology.manage`). It drafts for items without guidance, one run each, in `GuidanceDraftWorkflow` (a template variant of its input, behind `patched("templates")`).
4. **Approving (D2):** the person reviews drafts on the version page (edit, approve, discard; bulk with confirmation, as TASK-073). Then **"Publish as a new version"** creates the next version of the template:
   - it copies the current version's areas, rules and items;
   - it carries the approved guidance onto its items;
   - it marks those items' guidance as `drafted`, with who approved it.
   - This is audited like an import (`methodology_version.created`, source `drafted_guidance`). Engagements pinned to older versions are unchanged, and new or rolled-forward engagements get the new one.
5. **Provenance into engagements:** `methodology_request_items` gains `guidance_source` (null or `drafted`) and `guidance_approved_by`. Applying or rolling forward a version gives request items source `drafted`, not `template`, for those items, so SPEC-035's client display rule (the firm's setting) applies to them too (AC-5).
6. **Screens:** on the methodology version page:
   - "Draft guidance (N without)";
   - the drafts with the AI tag, edit, approve and discard;
   - "Approve all I've read";
   - "Publish as a new version (N approved)";
   - a note that clients see drafted guidance only if the firm allows it;
   - loading, empty, error and not-allowed states.
7. **Tests:**
   - the firm-level agent context: issued only by the loader; refused for any engagement action; firm-scoped authorisation;
   - the CHECK on `agent_runs`;
   - a template draft and its checks;
   - approve, edit and discard;
   - publishing makes a new version with the guidance and leaves the old one unchanged;
   - applying the new version gives `drafted` items, which clients see only with the setting on;
   - workflow replay of the patched branch;
   - vitest;
   - a real-model smoke on the Dev firm's template.

### Questions for the human
- **D1 — firm-level agent runs.** Recommended: a firm-level form of the agent context (no engagement), limited to the drafter and firm-scoped actions, with an optional engagement on `agent_runs` guarded by a CHECK. Every model call stays an audited agent run with its own budget (ADR-047, ADR-070), but it changes identity's agent context, a red-zone path. Alternative: draft template items under the requesting person's own context, with no agent run. It's smaller, but loses per-run audit and budgets for these calls, which I don't recommend.
- **D2 — how approved guidance reaches a template.** Recommended: publishing creates a new template version (versions are immutable, and engagements pin theirs), copying the current one with the approved guidance. Alternative: a separate "guidance overlay" table applied on top of a version when engagements apply it. It avoids new versions, but a version would no longer say everything it contains.
- **D3 — who may draft and publish.** Recommended: firm admin and practice leader, the roles that manage methodology (`methodology.manage`, with fresh MFA for publishing).
- **D4 — approval file:**
  - `backend/src/abacus/modules/agents/**`, `backend/src/abacus/modules/identity/**`;
  - `docs/architecture/permission-matrix.yaml`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.
  - `backend/src/abacus/ai_gateway/**` (only if the firm-level daily cap needs a change there);
  - the engagements module isn't a protected path.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation; a firm-level agent can't act on any engagement
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-15` — Design written for founder review after TASK-073 merged (#128).
- `2026-10-15` — Built (D1–D4): migration 0054 (firm-level `agent_runs` with `methodology_version_id` and a CHECK for the drafter only; `template_guidance_drafts`, `template_guidance_decisions`; `methodology_request_items.guidance_source`/`guidance_approved_by`; insert grant on `request_items.guidance_approved_by`); `AgentContext.engagement_id` optional with `engagement`, authz relating a firm-level agent to the firm only (`AGENT_FIRM_REACH = methodology.read`); drafter spec v2; template drafting, review and publishing; `template_guidance.read/request/decide`; provenance carried into engagements (apply and roll-forward, including the approver, which roll-forward of request items previously dropped); the version page's drafts panel and guidance column. Unit and workflow tests (10,866), web (335) and gates pass; v2 replay histories include a template run. Real-model smoke on the Dev firm's template: two firm-level runs drafted and passed the checks; an edit with an email and a year was refused; bulk approval without confirming was refused; publishing made v6 with `drafted` items and the approver, v5 unchanged; publishing again from v5 was refused (`version_not_latest`); a new engagement applying v6 got `drafted` items with the approver; the database refused a firm-level run for another agent. Added `backend/src/abacus/api/app.py` to the approval (founder) for the router.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| No `patched("templates")`: the template variant rides on new defaulted input fields | The workflow's commands are unchanged; v1 histories replay, v2 histories record a template run | No |
| Firm-level runs hold no work slot | Slots are per engagement; the firm's daily cap and budget bound them | No |
| Integration tests replaced by a real-model local smoke | Founder: build focus, minimal testing | No |

## Handoff
Done. SPEC-035 is complete apart from AC-7's judge calibration (waiting on the founder's scores).
- 2026-10-26: ADR-078 back-fill suite on `s10-q03-backfill` (TASK-1309, Q-03-T040): every covered AC passes; no defect found.
