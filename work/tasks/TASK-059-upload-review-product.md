---
id: TASK-059
title: "Upload reviewer, part 2: running it in the product and the firm's AI review panel"
spec: SPEC-030
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7, AC-9, AC-10]
risk_zone: red
status: done
branch: task-059-upload-review-product
worktree:
created: 2026-10-12
updated: 2026-10-12
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-030 Q7, TASK-059: the upload reviewer built and evaluated in TASK-058 runs on real uploads in the product (synthetic firms only, ADR-112): after SPEC-029's checks, through the engagement agent's policy or "Review now", with its flags shown to the firm in item detail and marked on the Board.

## Scope
SPEC-030 AC-4, AC-5, AC-6, AC-7, AC-9, AC-10.

## Context to load
- Spec: `docs/specs/SPEC-030-upload-reviewer.md` (amended) §4.5–4.7, §6, §8, §9, §17, §19; SPEC-027 (engagement agent policies)
- Code: `agents/upload_review.py`, `agents/screenings.py` (`start_screening`, `request_screening`, workflow IDs), `agents/workflows.py` (`ScreeningWorkflow`), `agents/activities.py`, `agents/engagement_agent.py` (`apply_policy`, `agent_on`, `to_agent`, P-1), `evidence/processing.py` (`check_upload`), `evidence/events.py`; `apps/web/src/screens/ItemDetail.tsx`, `CheckResults.tsx`, `EvidencePreview.tsx`, `Board.tsx`

## Plan
- [x] Plan approved by human (founder, 2026-10-12: D1–D4 as recommended). Approved by founder: the paths named in D4

### What the code shows
- **The screener's start is the pattern:** `evidence_version.created` goes to the engagement agent when it's on (its P-1 decides: paused, agent off, autonomy level), or straight to `start_screening` otherwise; "Screen now" (`request_screening`, `screening.request`) starts it at Advise. Its workflow creates the run, takes a work slot, calls the agent, retries when not admitted, and always ends a failed run.
- **The reviewer has no trigger:** `create_review_run` and `review` exist (TASK-058) and nothing calls them outside the evaluation.
- **Evidence emits no event when checks finish:** `check_upload` records checks and returns.
- **Reads:** nothing exposes `upload_reviews` yet; `upload_review.request` is in the matrix, a read action isn't.

### Design (for founder review)
1. **Event** (evidence): `check_upload` emits `upload_checks.recorded` (engagement, evidence version) after recording checks for a version on a request item.
2. **Policy** (agents): a new engagement agent policy **P-6 review**: on `upload_checks.recorded`, when the firm's `upload_review.enabled` flag is on, the agent isn't paused and the firm is at Routine or above, start the reviewer; otherwise record the skip with its reason in the agent's activity feed. With the engagement agent off, the same rules apply directly (as `start_screening` does).
3. **On whose behalf** (D2): the engagement partner (the person accountable for the review), not the uploader, who may be a client.
4. **Workflow** `UploadReviewWorkflow` (`upload_review:<tenant>:<version>`, background work class): create the run, take a work slot, call `review` (retrying while not admitted), and end any failure with `fail_run` (`data_boundary` for a non-synthetic firm). A replay history is recorded.
5. **"Review now"** (`POST …/request-items/{item}/uploads/{version}/review`, `upload_review.request`, partner, manager, senior): starts the same workflow at Advise, or again after a document kind change; audited.
6. **Reads** (D1): a new action `upload_review.read` (partner, manager, senior, staff, reviewer, with independence; clients denied by role) on `GET …/uploads/{version}/review`: the latest review's status (`none`, `running`, `completed`, `failed` with its reason, including "not available for real client data yet"), and its **shown** flags with their **verified** quotes only. Hidden flags stay in the database for evaluation and audit.
7. **The firm's panel** (`AIReviewPanel` in item detail, under Checks): rendered through `AgentText` with the AI tag (ADR-065): "No concerns" or one card per flag (category, confidence, rationale) with its quotes, each linking to that page of the preview (the viewer opens at a page); "Review now" for partner, manager and senior; loading, empty, error and not-allowed states.
8. **Board:** the evidence-version list gains `ai_flags` (shown flags on the latest review; 0 for client roles); the Board shows an "AI flags" badge and a filter option.
9. **Flag** `upload_review.enabled` (off; on for the local Dev firm, which is synthetic).
10. **Tests:** P-6 decisions (flag, pause, autonomy, agent off); the boundary refusal; reads deny client roles and never return hidden flags or unverified quotes; workflow replay; vitest for the panel, quotes and links, "Review now", the badge; a local smoke on the dev stack with the real model off (fake route errors, so the smoke uses a stand-in model in a script, not in the product) (D3).

### Questions for the human
- **D1 — reads.** Recommended: a new action `upload_review.read` for firm roles only, so client roles are refused by the matrix rather than filtered in code. Alternative: reuse `evidence.read` with a role check in the service.
- **D2 — on whose behalf.** Recommended: the engagement partner. Alternative: the uploader when they're firm staff, else the partner.
- **D3 — the local stack.** The dev stack runs the fake model, which has no reviewer answers (TASK-058 D5 declined), so automatic reviews there end as failed (`no_fake_answer`) and the panel says so. Recommended: keep it that way, and let a developer turn on the real model locally for the synthetic Dev firm when trying it (the existing `allow_real_model_locally`). Alternative: add a simple fake responder for local use only.
- **D4 — approval file:** `backend/src/abacus/modules/agents/**`, `backend/src/abacus/modules/evidence/**`, `docs/architecture/permission-matrix.yaml`, `backend/src/abacus/modules/identity/authz/_matrix.py`, `docs/architecture/feature-flags.yaml`, `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`, `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation; client roles never see a review
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after TASK-058 (#105) and the gateway temperature pin (#106) merged.
- `2026-10-12` — Built (D1–D4): `upload_checks.recorded`; P-6; `review_start` (starter, "Review now", reads); `UploadReviewWorkflow` and activities (reusing the screener's slot and fail steps) with replay histories; `upload_review.read`; flag `upload_review.enabled`; the firm's AI review panel (verified quotes, preview page links), the Board's AI flags marker and filter. Unit (agents 386), workflow (171) and web (256) tests and gates pass. Local smoke: P-6 starts the reviewer; with no real model route it records `no_real_model` (a first run on the fake model retried as a provider outage until cancelled, which led to the guard). The product path with the real model on the synthetic Dev firm flagged a DRAFT statement with a verified quote. Evaluation still passes every threshold.
- `2026-10-26` — Q-03-T032 back-fill: `backend/tests/integration/backfill/test_q03t032_upload_reviewer.py` (AC-4, AC-5, AC-6, AC-7, AC-9; all pass, no defect); see TASK-1283.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| No reviewer run without a real model route (`model_available`) | The fake model has no reviewer answers; it retried as an outage indefinitely | No |
| Board flag counts come from an agents endpoint, not the evidence-version list | Evidence can't depend on agents (agents depends on evidence) | No |
| An altered flag is hidden when code found a period, company, balance or totals problem | The real-model smoke repeated code's wrong-company finding as altered | No |
| Reviewer runs reuse the screener's slot and fail activities | They work on any agent run | No |

## Handoff
Done. SPEC-030 is complete. To try the reviewer locally: run the stack with the real model allowed for the synthetic Dev firm (`.env.evaluation` values). Next per the Act 2 plan: SPEC-031 client hub, then comments; B3 matching builds on the same extraction.
