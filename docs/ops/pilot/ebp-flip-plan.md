---
version: ebp-flip-plan v1
updated: 2026-11-07
---
# EBP-01 to EBP-06: M15 readiness and the per-firm flip (A-05-T49)

M15 target: on Fri Dec 10, 2027, J03 fieldwork P0 (EBP-01 to EBP-06) is walkable in production on
the canary tenant, and the `ebp_audits` entitlement refuses any firm that isn't synthetic until
the EBP CPA memo is signed.

## 1. What has to be true first

| # | Gate | Evidence | Who |
|---|---|---|---|
| 1 | The audit CPA (EBP) signs `docs/quality/golden-reviews/ebp@1.md`; the same PR sets `assurance/compute/ebp/reference/review.yaml` to `signed: true` with the date and the vault reference, and names the V-reference in `reviewed_by` of `irs_plan_limits.yaml` and `irc_6621_rates.yaml` | the merged PR; `test_a05t49_ebp_entitlement.py` keeps memo and record in step | CPA, AY |
| 2 | Staging soak on the Northwind slice: EBP-01 to EBP-06 walked on staging's synthetic firm for 5 business days, no 5xx on `/v1/audits/{id}/ebp/*`, the J03 fieldwork journey green | the soak log row below | N |
| 3 | The canary tenant (synthetic) holds `ebp_audits` and `ebp.modules` in production; J03 fieldwork walked there | the canary walk row below | N |
| 4 | Each pilot firm's admin acknowledges the shadow rules and the EBP scope in writing | the firm's go-live dossier | AY |

## 2. The flip, per firm

- **Window:** a Tuesday, 19:00 CT (`docs/ops/release-windows.md`), the first after gates 1 to 4.
- **Order:** the operator grants `ebp_audits` (`make entitlement FIRM=<code> MODULE=ebp_audits ENABLED=true OPERATOR=<you> REASON="M15 EBP flip" APPROVED_BY=<the other founder>`),
  then turns `ebp.modules` on for the firm. Without the signed memo the entitlement answers as
  absent for a real firm, so the routes stay 404 whatever the flag says.
- **Shadow run first:** for the first window the firm's EBP engagement runs beside its own
  workpapers; the engines' figures are compared to the firm's for the plan year and differences
  recorded in the dossier before the firm relies on any screen.
- **Both founders** approve each firm's flip in writing in the dossier.
- **Rollback is the flag off:** `ebp.modules` off for the firm hides the routes and screens;
  imports, results and decisions persist and read again when it turns back on. Removing the
  entitlement is the stronger stop and is used only if the memo's findings require it.

## 3. Flag renewals in the M15 bundle

`ebp.modules`, `ebp.form5500_tieout` and `assurance.estimates_rp` expire 2027-04-30 under DEC-137.
They are renewed in the M15 bundle (Tue Dec 7, 2027), registry only: `created: 2027-12-07`,
`expires: 2028-05-31` with `override: DEC-137` (inside the 180-day override, after Apr 20, 2028,
and outside every release window). They can't be renewed earlier: a renewal runs from the day it is
made, so a renewal today couldn't reach past Apr 20, 2028.

## 4. Records

| Date | What | Result | By |
|---|---|---|---|
