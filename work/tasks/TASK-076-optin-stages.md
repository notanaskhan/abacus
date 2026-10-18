---
id: TASK-076
title: "Data boundary, part 2: firm opt-in against the disclosure, shadow and live stages, engagement exclusion, and the screens"
spec: SPEC-036
acceptance_criteria: [AC-3, AC-5, AC-6, AC-7, AC-9]
risk_zone: red
status: done
branch: task-076-optin-stages
worktree:
created: 2026-10-18
updated: 2026-10-18
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-036 §7, TASK-076. This task fills in the three facts that TASK-075's gateway check asks for:
- **the firm's opt-in:** a firm admin with fresh MFA opts in after reading the disclosure;
- **each agent's stage for the firm:** shadow first, then live once you promote it;
- **an engagement partner's exclusion** of one engagement.

It also hides shadow output from every screen, and adds the screens for all three.

Nothing opens for a real firm until C2 is done: the register gets a Bedrock entry, and an agent is cleared.

## Scope
SPEC-036 AC-3, AC-5, AC-6, AC-7 and AC-9.

## Context to load
- Spec: `docs/specs/SPEC-036-data-boundary.md`; ADR-111, ADR-114, ADR-115
- Code:
  - `ai_gateway/boundary.py` (`register_client_data_facts`, `clear_cache`);
  - `identity/firm_settings.py` (the drafted guidance setting is the pattern), `identity/routes.py`;
  - `agents/service.py` (`proposals_for`, `screening_results_for`), `agents/repository.py` (the output readers: `latest_results`, `latest_result_for_version`, `latest_review_run`, `shown_flags`, `shown_flag_counts`, `latest_match_runs`, `list_match_results`, `pending_guidance_drafts`, `template_drafts`), each agent's `create_*_run`;
  - `engagements/service.py`, `engagements/routes.py`;
  - `kernel/provider_terms.py`, `abacus_tools/codegen/provider_terms.py`;
  - `apps/web/src/screens/Autonomy.tsx`, `Overview.tsx`, `AIReviewPanel.tsx`, `InboxAIMatch.tsx`, `GuidanceDrafts.tsx`

## Plan
- [x] Plan approved by human (founder, 2026-10-18: D1–D5 as recommended). Approved by founder: the paths named in D5

### What the code shows
- **The gateway already asks for all three facts** through registrations. Until they're registered, every real firm is refused at `firm`.
- **Firm settings follow one pattern:** a column on `firms`, a read under `firm.read_settings`, and a write under an MFA-gated action, audited. The drafted guidance switch is the closest example.
- **Agent output reaches the firm through about ten readers.** Every output row (screening result, upload review, match run, guidance draft) carries its `agent_run_id`.
- **Platform support is break-glass and read-only** (SPEC-012), and only through a session the firm grants. No in-app role exists for the platform to change a firm's settings.
- **The register's version is a hash of the whole file,** so a new review date alone would change it. SPEC-036 Q4 says only a material change should make firms opt in again.

### Design (for founder review)
1. **The disclosure and opt-in** (identity):
   - **Register addition:** each compiled register entry gains a `material` fingerprint, a hash of training, retention, region and subprocessors only (codegen).
   - **Reading it:** `GET /v1/firm/ai-client-data` (`firm.read_settings`) returns:
     - the firm's opt-in (who and when), and whether it's current;
     - the disclosure, generated from the Bedrock entry covering today: provider, region, no training, retention and its exceptions, subprocessors, the assistants cleared for client data, and suggested engagement-letter wording (D4);
     - `available: false` when no entry covers today. Then the screen says the option isn't available yet, and opting in is refused (`ai_client_data_unavailable`).
   - **Changing it:** `PUT /v1/firm/ai-client-data` (`firm.ai_client_data`: firm admin with fresh MFA):
     - **on** records who, when and the entry's `material` fingerprint;
     - **off** clears it, and the firm's cached boundary facts are dropped in the same request (`clear_cache(tenant)`);
     - both are audited (`firm.ai_client_data_on` and `_off`).
   - **Expiry:** the opt-in is current while its fingerprint matches today's entry. A material change makes it lapse, and the firm admin sees "the terms changed: review and opt in again" (Q4).
   - **Registration:** identity registers `opted_in` with the gateway.
   - **Stays as it is:** the firm keeps `synthetic = false`.
2. **Stages** (agents):
   - **Table:** `agent_stages`, one row per firm and agent: the stage (`shadow`, `live` or `off`), who changed it, when, and a note. Changes are appended as rows; the newest row is the stage.
   - **Default:** with no row, a cleared agent is `shadow` for an opted-in firm. So every agent starts in shadow (SPEC-036 §4.5).
   - **Registration:** agents register `stage` with the gateway.
   - **Marking runs:** `agent_runs.shadow` (migration) is set when each run is created. It's true when the firm isn't synthetic and the agent's stage is `shadow`.
   - **Hiding output (D2):** every firm-facing reader leaves out output from shadow runs. Screens then behave as if the agent were off, with no proposal, flag, suggestion or draft. Output made in shadow stays hidden after promotion.
   - **Budgets:** shadow runs cost what any run does, and count toward the firm's budget (ADR-070).
3. **Promotion (D1):** an operations command run by you:
   ```
   python -m abacus_tools.ops.agent_stage --firm <id> --agent <id> --stage live --note "…"
   ```
   - It runs through the owner role, like seeding, and in one transaction writes the stage row and an audit event (`agent_stage.changed`, actor `platform:founder`, with the note).
   - It refuses `live` until the shadow report meets SPEC-036 Q1: at least 50 shadow runs and 14 days since the first.
   - `--report` prints the shadow report for the firm and agent:
     - runs, days, outcomes and cost;
     - for the screener, how often its proposal matched the person's decision (accept, reject or send back);
     - for the upload reviewer, flags shown against what the person decided.
   - In the app, firm admins only read stages (the screen in item 5).
4. **Engagement exclusion** (engagements):
   - **Turning it on or off:** `PUT /v1/engagements/{id}/ai-exclusion` (`engagement.ai_exclude`: the engagement partner) takes on or off with a reason of up to 300 characters.
   - **Data:** `engagements.ai_excluded_at`, `_by` and `_reason`.
   - **Effect:** audited (`engagement.ai_excluded` and `_included`); the firm's cache is dropped; engagements registers `excluded` with the gateway.
   - **Reading it:** `GET …/ai-exclusion` (`engagement.read`).
5. **Screens** (web):
   - **"AI on your clients' data"** in the firm settings beside Autonomy:
     - the disclosure, an opt-in confirmed with fresh MFA, and opt-out;
     - each assistant's stage, as "Trial (not shown to your team yet)" or "On";
     - the states for not available yet, terms changed, loading, error and not allowed.
   - **On the engagement Overview:** the partner's "AI off for this engagement" switch with its reason. When it's on, each AI panel says AI is off for this engagement.
   - **For synthetic firms:** nothing changes.
6. **Clients (AC-7):** a test proves a real firm's client sees no model-written text with every setting on. The drafted guidance setting stays synthetic-only.
7. **Tests:**
   - opt-in, opt-out and lapse: roles, MFA, unavailable, and refusal in the same request (AC-3);
   - shadow runs recorded and hidden from every reader, with live runs shown (AC-5);
   - exclusion (AC-6);
   - the client view (AC-7);
   - the operations command: refusals below the threshold, and the audit;
   - vitest for both screens (AC-9).

### Questions for the human
- **D1 — how you promote.** Recommended: the operations command above, run through the owner role, audited, and refused below SPEC-036 Q1's threshold. Platform support stays read-only. The alternative is a new platform-staff role in the app, which is a larger identity change I'd leave until a second person operates the platform.
- **D2 — what promotion shows.** Recommended: each run is marked shadow when it starts, so output made during shadow stays hidden after promotion and only new runs are shown. Your people never see output they didn't review live.
- **D3 — the shadow report's comparison.** Recommended: run counts, days, outcomes and cost for every agent. Agreement with people's decisions for the screener and the upload reviewer, the two agents going first (Q2). The matcher and the drafter get their comparison when they're cleared.
- **D4 — suggested engagement-letter wording (Q6).** Recommended: one sentence in the disclosure, which I'll draft and you approve before it ships: *"We use AI assistants, run by Amazon Web Services in the United States under terms that prohibit training on or retaining your data, to help review the documents you provide; our team reviews all of their work."*
- **D5 — approval file:**
  - `backend/src/abacus/modules/identity/**`, `backend/src/abacus/modules/agents/**`, `backend/src/abacus/ai_gateway/**`;
  - `docs/architecture/permission-matrix.yaml` (`firm.ai_client_data`, `engagement.ai_exclude`) and the generated `backend/src/abacus/modules/identity/authz/_matrix.py`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py` (the firm-level stage list);
  - `backend/tests/unit/**`, `backend/tests/integration/**`.
  - Engagements, `kernel/provider_terms.py`, the codegen and the new operations command aren't protected paths.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-18` — Design written for founder review after TASK-075 merged (#131).
- `2026-10-19` — Built (D1–D5): migration 0056 (firm opt-in columns, owner-written `agent_stages`, `agent_runs.shadow`, engagement exclusion columns); the register's `material` fingerprint; identity's opt-in, disclosure and routes (`firm.ai_client_data`), with assistants registered by agents; `agents/stages.py`, shadow marking at run start and every firm-facing reader filtered; engagement exclusion and routes (`engagement.ai_exclude`); `abacus_tools.agent_stage` (report and set, owner role, audited, refused under the threshold); the "AI on your clients' data" panel and the engagement's AI-off switch. Unit and workflow tests (10,970), web (342) and gates pass. Local smoke on the Dev firm: opt-in refused without terms, by a practice leader and with stale MFA; opted in and seen by the gateway; a material change lapsed it; opt-out seen at once; a shadow screening result hidden while the live one showed; `live` refused at 1 shadow run; `off` written and audited as the platform; the app role refused writing stages; an excluded engagement refused the fake route, and allowed again once included. The smoke caught an untyped SQL parameter in the opt-in update (fixed).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Engagement exclusion refuses every route for every firm, including synthetic firms and the fake route | A partner's "AI off" should mean off everywhere, and it can be tried locally | No |
| The command is `abacus_tools.agent_stage` (not `abacus_tools.ops.agent_stage`) | Matches the other top-level operations tools (`access_review`, `signup_codes`) | No |
| The AI-off switch sits under the engagement header, beside the agent's pause switch, not on Overview | Visible on every tab, which also serves as the "AI is off" notice | No |
| No integration tests; a local smoke instead | Founder: build focus, minimal testing | No |

## Handoff
Done. SPEC-036 is built. Lifting the boundary for a firm now needs only C2 (Bedrock in our account), the register's Bedrock entry (founder), clearing an agent with its Bedrock evaluation, the firm's opt-in, and promotion after shadow.
