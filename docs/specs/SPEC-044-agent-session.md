---
id: SPEC-044
title: "Agent procedure session: the agent proposes the plan, people approve each gate, the agent assesses each row's support, a preparer adopts its results"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-005, ADR-050, ADR-051, ADR-052, ADR-111, ADR-131, ADR-132]
related_specs: [SPEC-037, SPEC-038, SPEC-040]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
This is the plan's AUD-36 procedure session (epic A-11), and Fieldguide's flagship, built on what exists, without the multi-step runtime (P-10).

A procedure can be run as a session. The agent shows a fixed plan (code's words, one line per step), and a person clicks **Proceed with plan**, which starts the selection. From there each gate is a card:
1. approve the sample (SPEC-040, a manager or partner);
2. send one support request (SPEC-040);
3. **assess the rows**: the entry assessor (SPEC-037 Q4) reads each row's support and proposes, with verified citations;
4. **adopt the results**: a preparer records the agent's proposals as results, marked "adopted";
5. triage (Exceptions · Needs input · Passed);
6. generate and sign the workpaper.

The agent never records a result, approves, sends or signs (ADR-005). Its messages are code-composed (ADR-111). Its judgment is the assessor's, verified by code (ADR-050, ADR-052).

## 2. Acceptance criteria
- **AC-1** The session shows the procedure's plan: fixed steps by definition, code's words.
- **AC-2** **Proceed with plan** (`procedure.run`) records the approval (who, when; insert-only, audited) and starts the selection if none exists.
- **AC-3** Each gate's card appears in order, worked out from recorded state (plan approved → selected → sample approved → support requested → assessments → results → rows signed → workpaper).
- **AC-4** **Adopt** (`entry_assessment.adopt`: staff, senior, manager, partner; agent deny; independence required):
  - for each chosen row with an assessment and no result yet: `explained` → **supported**, `not_explained` → **exception**, with the note "The agent found the support doesn't explain the entry" plus its rationale (up to 400 characters);
  - `unclear` rows stay for a person;
  - the result is recorded by the person, with the assessment's id (`adopted_assessment_id`);
  - the sample-approval gate applies (SPEC-040 AC-3).
- **AC-5** A row whose result was adopted shows **Adopted from the agent** in the item list.
- **AC-6** When the assessor isn't available (flag off, or no model here), the assess step says so and testing continues by hand.

## 3. Data
- `procedure_session_events` (insert-only): `tenant_id`, `procedure_id`, `kind` (`plan_approved`), `by_user`, `created_at`.
- `item_results.adopted_assessment_id` uuid null (expand-only).
