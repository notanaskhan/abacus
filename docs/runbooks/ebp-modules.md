# EBP modules: per-firm flip, rollback, corrections, recompute and annual reference updates (A-05-T62)

**Owner:** the builder (solo; AMENDMENT-solo) · **Module:** `assurance` (A-05: EBP-01 to EBP-09,
AUD-27), `workpapers` (the section drafter's EBP modes) · **Severity of a failed flip:** SEV-3 (flag
off restores the previous cockpit) · **Last reviewed against an incident:** never · **Task:**
A-05-T62 (TASK-6222)

EBP plan audits reach a firm through three flags and one gate. Every figure is code's (the
`compute/ebp/*` engines, Decimal only); the agent extracts and proposes; a named person verifies,
adopts, records corrections, concludes and signs (INV-1). Flipping a flag shows or hides screens and
routes; it never changes a recorded figure, decision or sign-off.

## 1. What turns on what

| Switch | Turns on | Off means |
|---|---|---|
| `ebp.modules` (flag) | Every `/v1/audits/{work_item_id}/ebp/*` route but the Form 5500 tie-out; EBP-01 to EBP-06, EBP-08, EBP-09 rail rows and canvases | 404; the rail rows are absent |
| `ebp.form5500_tieout` (flag) | `/ebp/form-5500*`, EBP-07 and the `Form5500TieOut` trigger | 404; EBP-07 is absent |
| `assurance.estimates_rp` (flag) | AUD-27: `/estimates*`, `/related-parties*`, `/parties-in-interest`, `/prohibited-transactions` | 404; AUD-27 is absent |
| `workpapers.drafting` (A-04's gate) | Every EBP mode and every Begin… (`workpapers.section_drafter`) | The screens work agent-off: keyed or imported values with a required citation note (DV-EBP-07-1) |
| EBP audits entitlement (DB, ADR P-28) | The module for the firm | Refused for any non-synthetic firm until the EBP engines' CPA review memo is signed (`docs/quality/golden-reviews/ebp@1.md`) |

The EBP modes stay synthetic-only until A-05-T63's clearance: see section 6.

## 2. Flip (per firm, Tuesday 7 pm CT slot)
1. Confirm the preconditions: the entitlement allows the firm (CPA memo signed); the EBP goldens are green (`tests/golden/ebp`); the J03 fixture steps are green; the slot's `flag_flip` record names this runbook as the rollback (`abacus_tools.flip_guard` checks it against `deploy/windows.yaml`).
2. Turn the flags on for the one firm, in this order, each as an ECS one-off task, never from a laptop against a hosted database:
   ```
   make flag FIRM=<tenant_id> FLAG=ebp.modules VALUE=true OPERATOR=<name> REASON="<text>" APPROVED_BY=<name> ROLLBACK=docs/runbooks/ebp-modules.md
   make flag FIRM=<tenant_id> FLAG=assurance.estimates_rp VALUE=true OPERATOR=<name> REASON="<text>" APPROVED_BY=<name> ROLLBACK=docs/runbooks/ebp-modules.md
   make flag FIRM=<tenant_id> FLAG=ebp.form5500_tieout VALUE=true OPERATOR=<name> REASON="<text>" APPROVED_BY=<name> ROLLBACK=docs/runbooks/ebp-modules.md
   ```
   `ebp.form5500_tieout` goes last: EBP-07 needs AUD-20's FS draft (A-06) on the firm.
3. Verify on one EBP engagement (section 7).

## 3. Rollback: flag off
`make flag FIRM=<tenant_id> FLAG=<name> VALUE=false …` for each flag, or `ALL_OFF=1`. Nothing is
deleted or reversed:
- **Records persist.** Census imports, test results, late remittances, corrections, certification
  evaluations, tie-out lines and every audit event stay as recorded (insert-only tables; RLS).
- **Decisions persist.** Estimate conclusions and every decision card stay decided; sign-offs stay.
- **Sealed PII stays sealed.** SSNs in the census, balance and SDBA schedules are sealed bytes, an
  HMAC fingerprint and the last four; a flag never unseals anything (`pii.reveal` stays logged).
- With the flag back on, the screens read the same rows: no recompute happens on a flip.

## 4. Recording a correction (late remittance, EBP-04 f)
Only a person records a correction (`ebp_correction.record`; the agent and system are denied):
1. Open EBP-04 on the plan's audit, select the late remittance and choose "Record correction…".
2. Attach the evidence (the lost-earnings deposit and, if filed, the VFCP SCC notice). The service
   refuses a correction without evidence (`CorrectionEvidenceRequired`).
3. Enter the lost-earnings deposit date, the SCC notice date (if any) and the Form 5330 status. The
   status reads `pending_vfcp_scc` until the SCC notice, then `corrected`. Time alone never corrects.
4. One `ebp_late_remittances` row is **the** late-remittance object: EBP-04, EBP-07's Part IV 4a and
   AUD-27's prohibited transactions read it in place, so nothing else needs editing.

## 5. Recompute after an engine version change
Each engine stamps `engine_version` and `inputs_hash` on every figure it writes (`compute/ebp/*.py`,
`ENGINE_VERSION`). A version bump never rewrites stored figures:
1. Land the engine change with its goldens updated and the CPA review re-signed for the changed
   engine (`docs/quality/golden-reviews/ebp@1.md` gets a new version entry). This is protected:
   `docs/architecture/protected-paths.md`.
2. On each affected work item, re-run the tie-out or test from its screen (or the workflow's
   re-run). The new result arrives as a **checkpoint** (P-04 SHL-16: `checkpoint.propose` by the
   system, cause `engine_version`). The prior figures stay as the previous checkpoint.
3. A person compares (`previous` and `current` views) and approves or rejects the checkpoint. Any
   sign-off on the changed workpaper goes stale and is re-signed (R-SO stale re-sign).
4. Record the bump and the work items recomputed in the decision log.

## 6. Annual reference updates (with the audit CPA)
All three are protected reference data, reviewed by the audit CPA and pinned by golden tests. A
missing year or quarter is a refusal, never a guess:

| Reference | File | When | Steps |
|---|---|---|---|
| IRC §6621(a)(2) underpayment rates (VFCP lost earnings) | `backend/src/abacus/modules/assurance/compute/ebp/reference/irc_6621_rates.yaml` | Each quarter, when the IRS announces the rate | Add `"YYYY-Qn": "r.rr"`; add a golden for a deposit spanning the new quarter; the CPA signs `reviewed_by` |
| IRS plan limits (402(g), catch-up, 415(c), 401(a)(17)) | `…/compute/ebp/reference/irs_plan_limits.yaml` | Each November, from the IRS cost-of-living notice | Add the plan year's block; keep `requires_review: true` until the CPA signs |
| Schedule H line mapping (FS caption to line) | `ebp_schedule_h_mappings` (database content, versioned by `effective_plan_year`, read when published) | When the Form 5500 instructions change a line | Content belongs in the database: publish a new mapping version. **Gap:** there is no import endpoint for this table yet, so the mapping can only be loaded by the seed (PF-X1 only). Until one exists (follow-up), EBP-07's FS side reads no lines for a real firm |

After any update: run the EBP goldens (`tests/golden/ebp`) and record the change in the decision
log.

## 7. Verify
On the firm's tenant, as the engagement partner:
- EBP-01 shows the plan profile.
- EBP-04's late remittances foot to the 4a schedule.
- EBP-06's certification points are evaluated by a person.
- EBP-07 ties except the documented basis differences, and Part IV 4a agrees with EBP-04.
- AUD-27 shows estimates with code's method tie.

The J03 steps 7 to 13 and J04 11 fixture walks are the reference; on PF-X1 the `ebp` slices reproduce Northwind.

## 8. Flag calendar
Created 2026-11-01, all three expire **2027-04-30** (DEC-137 override), outside the Jan 1 – Apr 20
freeze windows. Renewal and retirement are recorded in `docs/plan/status/flag-renewals-2027.md`:
renew each to Dec 30, 2027 before expiry; renew again in the M15 bundle (Tue Dec 7, 2027) to after
Apr 20, 2028 (the R4 rule), and retire each once it is on for every live firm after PW4 (EBP season
Apr 18 – Oct 15, 2028).

## Rehearsal log
| Date | Kind | Result | Changes made |
|---|---|---|---|
| — | staging walk-through (pending) | Not rehearsed: no staging deploy of the S31 batch and no real firm (DEC-1391); PF-X1 is the data for it | — |
