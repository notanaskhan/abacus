---
id: TASK-021
title: Output controls and the outbound message scope checker
spec: SPEC-006
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: red
status: awaiting-plan-approval
branch: task-021-output-controls
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-006 (approved, Q1–Q5): sanitise model text when it is stored; a frontend rule that renders model text through `AgentText` only; and a guarded `communications.send` that checks every message's scope, blocking and flagging violations.

## Scope
All of SPEC-006. Excluded: delivery transports, drafting, and any message UI.

## Context to load
- Spec: `docs/specs/SPEC-006-output-controls.md`
- ADRs: ADR-065, ADR-005, ADR-050, ADR-052, ADR-064
- Code: `ai_gateway/`, `modules/agents/service.py` (where results are stored), `modules/communications/`, the `ledger`, `organisations`, `engagements` and `evidence` APIs, and `apps/web/eslint.config.js`

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **Sanitiser** (`ai_gateway/sanitise.py`, exported as `sanitise_text`):
   - URLs (`scheme://…`, `www.…`), markdown links and images, and HTML `<a>` and `<img>` become `[link removed]` unless their host is in `settings().output_link_allowlist` (empty by default);
   - an allowed link stays as plain text;
   - no other markup is changed, because rendering is plain text.

   `agents.service` applies it to `rationale`, quotes and `unverified` before insert.
2. **OUT-001** (eslint, `apps/web/eslint.config.js`):
   - `no-restricted-syntax` on `dangerouslySetInnerHTML`;
   - `no-restricted-imports` on markdown and HTML renderers (`react-markdown`, `marked`, `markdown-it`, `dompurify`, `html-react-parser`);
   - a lint test is added. "Render a model-text field outside `AgentText`" is enforced by convention plus review (no static check for it is practical); recorded as a decision.
3. **Scope** (`communications/scope.py`, D1):
   - engagements provides the engagement's client and entities;
   - organisations gains `firm_names(tenant)` (every client and entity name in the firm);
   - ledger gains `scope_facts(tenant, snapshot_ids)` (account codes, names and amounts) and `firm_accounts(tenant)`;
   - evidence gains `snapshot_ids(tenant, engagement_id)` (snapshots behind the engagement's evidence versions).

   Amounts are normalised to cents, with column totals included. The rounding forms (whole units, `k`, `m`) and the threshold under 100 follow Q2. Names follow Q3 (case-insensitive, word boundaries, at least 4 characters, a stoplist). Account names must be at least 8 characters and absent from this engagement's ledger.
4. **The send path** (`communications/service.py`):
   - `send(ctx: AuthContext, engagement_id, draft)`:
     1. refuse unless serving a request (like `decide`, ADR-005);
     2. `lock_ref`, then `authorise(ctx, "message.send", …)` (a new matrix action, Q4);
     3. check the draft; a checker error is the violation `checker_error`;
     4. record the message in one unit of work: `sent` with `message.sent` audited and the outbox `message.ready`, or `blocked` with `message.blocked` audited and `OutOfScope` raised (409 `out_of_scope`).
   - Migration 0017: `messages` (insert-only, forced RLS, body classified confidential).
5. **COMM-001** (`banned_patterns`): `smtplib`, `email.mime` and messaging SDKs (`boto3` SES, `sendgrid`, `twilio`), and the string `message.ready`, are allowed only in `modules/communications/`.
6. **Module dependencies** (D2): communications may depend on identity, engagements, organisations, ledger and evidence (`MODULE_DEPENDENCIES`); ADR-106's registration isn't needed, since none of those import communications.

**Protected paths (approval file):**
- `backend/src/abacus/ai_gateway/**`, `modules/agents/**`, `modules/evidence/**`, `modules/identity/**` (matrix codegen), `modules/communications/**`;
- `backend/migrations/**`;
- `docs/architecture/permission-matrix.yaml`;
- `backend/src/abacus_tools/quality/banned_patterns.py` and its test, `schema_check.py`.

### Questions for approval
- **D1. Scope facts come from each owning module's API (new small functions in ledger, organisations and evidence), never their tables?** *Recommendation: yes.*
- **D2. Communications may depend on identity, engagements, organisations, ledger and evidence (a BOUND-002 map change)?** *Recommendation: yes.*
- **D3. "Model text only through `AgentText`" is enforced by lint for the dangerous APIs and libraries, and by review for field-level use?** *Recommendation: yes.* A field-level static check isn't practical.
- **D4. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-07` — SPEC-006 approved and merged (#36). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Questions for the human
- Design questions D1–D4 (above).

## Handoff
- **Next:** on approval, write the approval file and implement design 1–6.
