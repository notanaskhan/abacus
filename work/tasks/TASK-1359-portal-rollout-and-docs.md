---
id: TASK-1359
title: Portal sign-in and home rollout, C5 v1.1 portal freeze, READMEs and the lockout and pause runbooks (P-08-T28)
spec: SPEC-320
acceptance_criteria: ["The canary walks sign-in with a second factor on the production build, both flags are gone before expiry, and each runbook is rehearsed once."]
risk_zone: amber
status: in-review
epic: P-08
plan_key: P-08-T28
branch: s10c-ops
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Do the repository side of P-08's rollout; write every staging and production step down for the
builder; retire the flags only after the production canary has walked (DEC-456).

## Plan (repository side, this task)
- **Flags on for synthetic firms:** the Brightwater Hale `portal` slice replays
  `platform.flag_set` for `portal.sign_in_v2` and `portal.home_v2` (so `make seed-staging`, which
  passes `--slice portal`, turns them on for staging's demo firm); the load profiles
  (`abacus_tools.synthetic.fleet`, TASK-1357) turn them on for every fleet firm.
- **C5 v1.1 portal half frozen:** `abacus_tools.contracts.MODELS["c5_portal"]` (37 models),
  snapshot `backend/tests/contracts/c5_portal/v1.1.json` (`--freeze c5_portal v1.1`), the register
  note in `docs/contracts/README.md`, and the status and flags rows of `portal-identity.md`.
- **READMEs:** `modules/identity`, `modules/communications`, `modules/portal`: rollout, retirement
  and the runbooks.
- **Runbooks:** RB-35 (a client locked out of sign-in or two-step) and RB-36 (pause a firm's
  portal sign-in), indexed in `docs/runbooks/README.md` and linked from RB-22.
- **Tests:** `backend/tests/unit/scenarios/test_p08t28_portal_rollout.py`.
- **Rollback:** revert. The flag events only add rows to synthetic firms; the snapshot only adds a
  check.

## Human steps (staging and production; in this order)
1. **Staging, at the batch deploy:** import the C16 templates `portal.sign_in_code`,
   `portal.link_renewed` and `portal.mfa_reset_notice` (and `notification.mention`) first, then
   `make seed-staging` (no deploy in flight) so the demo firm has both flags on. Walk j12 1 and
   j12 2b on staging (Claire Feld's code; Tess Moreno's second step).
2. **Rehearse RB-35 and RB-36 once on staging** (a lock and an unlock for Claire; a pause and a
   resume of Brightwater Hale's portal sign-in through the staging ops task) and fill each
   runbook's rehearsal log and `last_rehearsed`.
3. **Production canary:** through an ops-request PR, `make flag FIRM=<canary tenant>
   FLAG=portal.sign_in_v2 VALUE=true` and the same for `portal.home_v2`, with the operator and a
   reason; import the templates in production first.
4. **M7 evidence:** a canary client with an owner grant signs in with a code and a TOTP second
   step on the production build; file the configuration export (flag states, the MFA floor), the
   test report and screenshots without data in the M7 dossier for "MFA enforced for portal
   owners and signers".
5. Then the retirement PR below, merged in the batch before the flags' expiry (registry:
   2027-04-21; plan date Tue Mar 16, 2027).

## Retirement checklist (one PR, after step 4)
- Backend: drop the `portal.sign_in_v2` check in `identity/portal_session.py` (code email),
  `organisations/contacts_contract.py` (unlock and MFA reset 404) and the `portal.home_v2` check
  in `portal/contract.py`; delete both entries from `docs/architecture/feature-flags/identity.yaml`
  and `portal.yaml`; `make regenerate` (never hand-edit `kernel/_flags.py`).
- Tests that assert the flag-off 404 become assertions that the route is served (not deleted:
  `tests/contracts/c5_portal/test_c5_portal_stub.py`'s flag cases, `test_portal_sign_in.py`'s home
  404); tests that set the flags stop setting them.
- Frontend: remove the legacy `ClientAccept`, `ClientHome` (and `ClientEngagement` only if R-01's
  `portal.documents_v2` has retired) from `routes/portal.tsx` and the firm bundle's `/client/*`
  subtree; their `legacy/spec0xx` tests go with them under an approval line in the PR, as
  G-01-T17 does for its legacy screens.
- Docs: `portal-identity.md` flags row, POR-01 and POR-02 "Flag off" rows, SPEC-320 AC-4, the
  module READMEs, the portal slice's `FLAGS` and the fleet's `FLEET_FLAGS`.

## Progress log
- 2026-10-27: repository side built (DEC-456). Flag retirement deliberately not done: it follows
  the canary walk (human step 4). Runbooks written, not rehearsed.
