# Go-live rehearsal · PF-X1 (synthetic, DEC-4100)

Rows: Q-04-T021, Q-04-T022, Q-04-T024, Q-04-T026, Q-04-T033, Q-04-T034, Q-04-T039, F-09-T110,
F-09-T114. **Synthetic (PF-X1).** Local stack only (see [README](README.md)); no founder signed.

## Shadow posture first (the flip guard)

The portal slice turns the client-facing flags on for the demo tenant (DEC-456). A shadow firm has
none, so the operator flipped them off for PF-X1 under the flip guard (an approver who is not the
operator, a rollback link), after the last seed run (finding 7):

```
make flag FIRM=293fc3e7-be13-4767-ae6a-ce245b2dbda9 FLAG=<flag> VALUE=false OPERATOR=pfx1-rehearsal-operator \
  APPROVED_BY=pfx1-rehearsal-approver ROLLBACK=docs/runbooks/pilot-onboarding.md REASON="DEC-4100 synthetic (PF-X1): shadow posture"
```

| Flag | Before | After |
|---|---|---|
| `portal.home_v2` | true | false |
| `portal.sign_in_v2` | true | false |
| `signatures.envelopes` | true | false |

## The checks (`python -m abacus_tools.go_live --firm <PF-X1> --level <L> --rehearse-real`)

Plain runs fail `tenant.real` as before; the rehearsal passes it as "synthetic (PF-X1): rehearsed
as real" and stamps the report `rehearsal: true`.

| Level | Items | Passed | Failed |
|---|---|---|---|
| shadow | 21 | 8 pass, 6 manual | `tenant.provisioned`, `identity.sso_enforced`, `identity.mfa_all_staff`, `identity.break_glass`, `ai.provider_terms`, `ai.client_data_opt_in`, `integrations.no_writes` |
| client_facing | 29 | 9 pass, 13 manual | `tenant.provisioned`, `identity.sso_enforced`, `identity.mfa_all_staff`, `identity.break_glass`, `ai.provider_terms`, `ai.client_data_opt_in`, `integrations.no_writes` |
| tax | 35 | 9 pass, 19 manual | `tenant.provisioned`, `identity.sso_enforced`, `identity.mfa_all_staff`, `identity.break_glass`, `ai.provider_terms`, `ai.client_data_opt_in`, `integrations.no_writes` |
| season | 27 | 10 pass, 9 manual | `tenant.provisioned`, `identity.sso_enforced`, `identity.mfa_all_staff`, `identity.break_glass`, `ai.provider_terms`, `ai.client_data_opt_in`, `integrations.no_writes`, `season.runbooks_rehearsed` |

Shadow, item by item (the dossier's generated blocks carry the same, from `go_live_dossier fill`):

| Check | Status | Read |
|---|---|---|
| `tenant.provisioned` | fail | not provisioned |
| `tenant.real` | pass | synthetic (PF-X1): rehearsed as real |
| `windows.entry` | pass | PF-X1 |
| `identity.sso_enforced` | fail | not required |
| `identity.mfa_all_staff` | fail | 0 of 46 staff |
| `identity.break_glass` | fail | none designated |
| `identity.roles_mapped` | pass | 1 firm admins, 1 security admins, 0 staff without a role template (P-10) |
| `identity.walls` | manual | evidence in the dossier |
| `identity.offshore_consent_gated` | pass | 0 offshore members; assignment needs an offshore-disclosure consent (0 clients consented) |
| `operations.support_switch` | pass | support requests allowed |
| `data.retention` | manual | evidence in the dossier |
| `data.audit_chain` | manual | evidence in the dossier |
| `data.tin_sealing` | manual | evidence in the dossier |
| `ai.provider_terms` | fail | no provider terms registered |
| `ai.client_data_opt_in` | fail | not opted in (AC-5.6) |
| `ai.agents_at_shadow` | pass | every cleared agent at shadow or live |
| `ai.platform_pause_tested` | manual | evidence in the dossier |
| `integrations.no_writes` | fail | 1 write capabilities enabled |
| `communications.no_client_facing` | pass | none on |
| `operations.on_call_current` | pass | updated 2026-11-01 |
| `operations.restore_drill` | manual | evidence in the dossier |

What closes each failure (none is a synthetic fill; findings in the [README](README.md)):

| Check | Needs | Who |
|---|---|---|
| `tenant.provisioned` | TenantProvisioningWorkflow and the tenant key on a hosted stack (`make seed-staging`) | Ayush (staging) |
| `identity.sso_enforced` | a verified admin SSO sign-in, then Require SSO on ADM-06 | a firm admin's sign-in |
| `identity.mfa_all_staff` | each staff member's sign-in with a second factor (DEC-527) | each person |
| `identity.break_glass` | the exempt account's hardware key, then the designation (refused without it: `SsoExemptNeedsHardwareKey`) | the account holder |
| `ai.provider_terms` | the providers' terms in `abacus.kernel._provider_terms` | Ayush (DEC-2098) |
| `ai.client_data_opt_in` | the firm admin's opt-in, which needs the terms first | firm admin, after Ayush |
| `integrations.no_writes` | a call on `esignature_envelope_send` (ADR-342) being enabled for every firm | Ayush (product) |
| `season.runbooks_rehearsed` | RB-16, RB-18 and RB-19 rehearsed, `last_rehearsed` set | Ayush (staging) |

## The dossier

`python -m abacus_tools.go_live_dossier fill PF-X1 --report <shadow rehearsal report>` wrote the
generated blocks and the stamp "passed" or "failed … (rehearsal, synthetic, DEC-4100)". By hand,
now `green (synthetic)`: contract-1 (the synthetic pack) and communications-1 (after the flips);
the shadow-rules acknowledgement is recorded ([shadow-rules-ack.md](shadow-rules-ack.md)).

`check PF-X1 --ready --rehearsal` still lists: the go-live check failed (the seven checks above),
and 21 by-hand rows not green. Plain `check PF-X1 --ready` refuses the rehearsal outright. Neither
founder signed (a founder's signature is never synthetic).

## A2, A3 and the second and third firms

PF-X1 is the only test firm (DEC-1530: a copy collides on the scenario's global ids). Q-04-T026's
PW1 slide for A2 is recorded in DEC-4100 (owner AY); Q-04-T033 and T034 close as not needed (no
third audit firm signed); F-09-T114 and Q-04-T027 wait for real firms.

## M10 (client_facing)

Same seven failures as shadow, plus `delta #1 closed` stays open under DEC-1389 (Q-04-T039).

