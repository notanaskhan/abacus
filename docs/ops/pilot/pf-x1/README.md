# PF-X1 synthetic runs (DEC-4100)

Every S0–S25 row whose acceptance needs a pilot firm, run on the synthetic test pilot firm PF-X1
(Brightwater Hale). The row list, with each row's outcome, is
[`docs/plan/status/PF-X1-runs.md`](../../../plan/status/PF-X1-runs.md). **Everything here is
synthetic (PF-X1), never a live firm's evidence.** No hosted database, staging stack or AWS
account was touched.

## The run (2026-11-10)

| What | Value |
|---|---|
| Code | `origin/main` 3e4935e86 plus the held PRs of this run (TASK-7100, TASK-7101) |
| Stack | the local compose stack of the worktree (`make worktree-env`, offset 30): Postgres, MinIO, Temporal; the worker running |
| Seed | `make seed-demo SLICE="pilot portal portal_pbc people"` at E0 (Mon Sep 14, 2026, 9:24 AM CT), scenario `bh-2026.10.3` |
| Firm | PF-X1 = tenant `293fc3e7-be13-4767-ae6a-ce245b2dbda9`, `synthetic: true` in `deploy/windows.yaml` |
| Operator, approver | `pfx1-rehearsal-operator`, `pfx1-rehearsal-approver`: rehearsal names, not people. No founder approved anything in this run |

## Records

| Record | Rows |
|---|---|
| [go-live-rehearsal.md](go-live-rehearsal.md) | dossiers, M9 and M10 checks, A1–A3, contract section |
| [pilot-0.md](pilot-0.md) | LOIs, Pilot 0 plan, sessions A–F, usability log, tax sessions, exit |
| [pw1-pw2.md](pw1-pw2.md) | metrics, shadow scoring, enrolment modes, flips, support, invoices |
| [season.md](season.md) | tax pilot, autumn window, deadline-week desks, support reserves |
| [shadow-rules-ack.md](shadow-rules-ack.md) | the firm admin's shadow-rules acknowledgement (synthetic) |
| [`brightwater_hale/files/pf_x1/`](../../../../backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/files/pf_x1/) | synthetic MSA, DPA and pilot terms (SYNTHETIC on every page; never sent) |

## Findings for the product (real, found by the synthetic run)

1. **`make pilot-metrics` wrote nothing, ever.** The CLI imported only identity and platform, so
   no W4–W7 source was registered and the platform (fail closed) skipped every metric. Fixed in
   TASK-7101: the command imports every module's api first, as the worker does. After the fix
   week 2026-09-14 wrote 2 snapshots (W4 0.0%, W5 45.8%; both amber).
2. **No firm can opt in to AI on client data.** `abacus.kernel._provider_terms.ENTRIES` is empty,
   so `ai.provider_terms` fails and `set_ai_client_data_setting` refuses
   (`AiClientDataUnavailable`). Registering the providers' terms is Ayush's (DEC-2098).
3. **`integrations.no_writes` fails for every firm** since DocuSeal (ADR-342): the write registry
   has `esignature_envelope_send` enabled, and the check counts any enabled write. Either the
   check should exempt a write gated off by the firm's client-facing flags, or the dossier
   should carry it as a known write: a product call for Ayush.
4. **The break-glass account needs a hardware key.** Designating Grace Holloway as the SSO-exempt
   account through ADM-06's service is refused (`SsoExemptNeedsHardwareKey`). A seed cannot give
   a person a passkey, so `identity.break_glass` stays open until someone enrols one locally.
5. **MFA and SSO need sign-ins.** `identity.mfa_all_staff` (0 of 46) and `identity.sso_enforced`
   read real sign-ins (DEC-527); the seed writes none.
6. **`tenant.provisioned` fails on a laptop**: the seed bootstraps the firm without
   TenantProvisioningWorkflow and has no tenant key locally. On staging the loader asks for the
   key (DEC-1012).
7. **A seed rerun turns client-facing flags back on.** The loader's `_finish` sets `FLAGS_ON`
   after every run with new events, so a shadow posture flipped by an operator is undone by the
   next `make seed-demo`. Harmless on the demo tenant; a rehearsal must flip again after seeding.
