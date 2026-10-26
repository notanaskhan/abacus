---
id: TASK-1311
title: P-06 docs close-out - READMEs, final SPEC, C5 v1 freeze note, erase and hold runbook, temporal-workflow skill, flag renewals, hand-off (P-06-T27)
spec: SPEC-319
acceptance_criteria: [AC-1, AC-15]
risk_zone: red
status: in-review
epic: P-06
plan_key: P-06-T27
branch: s10-p06-closeout
created: 2026-10-26
updated: 2026-10-26
---

## Objective
P-06-T27: "Docs: requests, evidence and agents READMEs, final SPEC, C5 v1 frozen note, runbook for erase failures and hold conflicts, temporal-workflow skill (durable timer + hold check), flag renewal plan, task log hand-off". Acceptance: "Docs merge in the last S10 train and the capacity ledger is updated."

## Plan (red zone: written before building)
- **Files (docs only, no code, no migration, no registry or flag edit):**
  - `backend/src/abacus/modules/{requests,evidence,agents}/README.md`: what P-06 shipped, read from the code; what is not built, said so.
  - `docs/specs/SPEC-319-requests-binders-engine.md`: the outline note becomes a Final note; status `approved` (not `done`: T16, T21, T22, T25, T26 are open); stale lines (non-goals, test plan, rollout, OQ-1, deferred) corrected from the repo; Story 7 (AC-29, AC-30) from the epic's §5.5 and §5.6, for P-06-T26.
  - `docs/contracts/README.md` and `c5-requests-binders.md`: the C5 v1 freeze note, only if the register's gate is met. The gate is the consumer suites green in `make check` stage 2, then `--freeze`. The pytest suites cannot run here, so the note reads "ready to record frozen at the batch merge once … green".
  - `docs/runbooks/RB-32-withdrawal-erase-and-hold-conflicts.md` and its index row: from `evidence/withdrawals.py`, `evidence/workflows.py`, `kernel/holds.py`, migration 0144.
  - `.claude/skills/temporal-workflow/SKILL.md`: the durable-timer and hold-check pattern, facts from the purge only.
  - `docs/plan/status/flag-renewals-2027.md`: P-06's three flags, renewal dates outside Sep 1 – Oct 20 and Jan 1 – Apr 20.
  - `docs/product/capacity-ledger.md`: the P-06 close-out section. `docs/product/decision-log.md`: DEC-409.
- **Tests:** none added (docs). Checks: `validate_docs`, `secrets_scan`; the C5 TypeScript consumer assertions (`c5.test.ts`, vitest) as the half of the freeze gate that can run here.
- **Rollback:** revert the commit.

## Progress log
- 2026-10-26: plan written; built on `s10-p06-closeout` with TASK-1310.
- 2026-10-26: READMEs. requests: lifecycle v2, what follow-ups chase, the withdrawal's requests side, and "Not built". evidence: withdraw refusals, the purge step by step (statuses of `evidence_key_destroy`, retries, continue-as-new), the API for other modules, staff accept. agents: the stale P-4 line ("Routine sends as the agent") corrected to draft-only (DEC-220), follow-ups v2, withdrawn versions.
- 2026-10-26: SPEC-319 final (approved). C5: `c5.test.ts` passed (12 tests); the pytest half not run; the freeze recorded as ready, not done. C5's header expiries corrected to 2027-04-21 (DEC-137).
- 2026-10-26: RB-32 written (number: the README's next free; RB-33 onward now owed to Q-02-T51). Skill section added. Flag rows added. Capacity ledger updated (26 of 29 rows delivered, 23.75 of 26.0 te).

## Hand-off (P-06 close-out)
**State of the epic.** 23 rows done, 3 in review (T22, T26, T27), 2 in progress (T16, T21), T25 not started (`docs/product/capacity-ledger.md`). The epic's DoD (§10) is not met yet.

**Owed before P-06 can close, in order:**
1. **At the batch merge:** `make check` (stage 2 runs the C5 consumer suites), then record C5 v1 frozen as `docs/contracts/README.md` describes (add the C5 models to `abacus_tools.contracts.MODELS`, `--freeze c5_requests_binders v1`, the register row and §10 to `frozen`).
2. **Parity and axe (T26):** pin the 23 crops, fetch baselines, run the four `e2e/screens/*.spec.ts` axe specs and `pnpm parity:screens`, record numbers in `docs/quality/parity-P-06.md`, then lock BND-01 and BND-02 at Tier C (`C (locked)` in their contracts) and decide whether a locked Tier C blocks (`screen-rows.ts` `gateOf`, F-04-T33). BND-02 must be `fixture` in `routes/manifest/bnd.ts` first.
3. **T16:** walk Grace's follow-up send on staging with the Reminder template imported; then BND-01 turns `live`.
4. **T21:** the reviewer fake for the fast run and the direct-route run at the protected thresholds.
5. **T22:** close the reviews of TASK-1223 and TASK-1252.
6. **T25:** the journey specs j06 2, j16 5, j03 4 and 10, j10 2, j22 3–4, plus the j02 and j04 steps.
7. **Flags:** renew `binders.engine`, `screening.card` and `evidence.withdrawal` in the Thu Feb 25, 2027 train to Wed May 26, 2027 (`docs/plan/status/flag-renewals-2027.md`).

**Open seams (not built; none is hidden in a done row):**
- No module registers `requests.register_live_facts`, so BND-02's "Waiting n" and "screening running" read 0 and false on the live stack (DEC-158). P-06 §4.1's `evidence.inbox_waiting_for` does not exist; N-01 plans its v2.
- The OQ-1 preparer path (DEC-136) is not built: on the live stack Kevin (the preparer) cannot publish the Feld binder as J06 step 2 shows.
- `PUT /v1/binders/{id}/follow-up-override` answers 501.
- `requests.api.awaiting_review_count` (for I-01) does not exist.
- §5.6 keyboard gaps carried by DEC-408: T1 rows are not keyboard-selectable; the Eye's helper is not linked by `aria-describedby`.
- RB-32 has no alarm yet; its §8 names the first one to add.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-409 | C5 freeze left pending (gate not runnable here), SPEC-319 `approved` not `done`, RB-32's number, the flag renewal dates and conditions, READMEs only describe what exists | No |
