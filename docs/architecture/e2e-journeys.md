# Critical journeys: the end-to-end registry (ADR-077)

The list of journeys J01 to J28 that the Playwright end-to-end suite must carry, as ADR-077 requires. It holds what changes rarely: each journey's spec file, first slice, gating epic and planned dates (chapter 10 §10.6.6, chapter 01 §1.5.1). Run results do not live here: whether a journey is walkable in each mode, its last green run and any unverified fake belong in the weekly quality report, so a green night never costs a commit, a build or a deploy.

## Status today (Mon Oct 26, 2026)

**Four journeys have a spec file**, all on the journey harness (`apps/web/e2e/harness/`, F-04-T21): `J01-firm-onboarding.spec.ts` (J01-core skeleton), `J02-client-onboarding.spec.ts` (J02-audit-core), `J04-fs-audit.spec.ts` (the J04 PBC slice at the Sep 24 snapshot) and `J12-client-portal.spec.ts` (J12-core). Each runs its walkable steps in every harness project, with axe and INV-1 to INV-5 after each step; every step not yet walkable is `test.fixme` naming its owning epic, task and chapter 01 date. `apps/web/e2e/journey.spec.ts` (the setup-first flow) still exists and belongs to no journey.

| Count | Value |
|---|---|
| Journeys in the registry | 28 |
| Journeys with their own spec file | 4 (J01, J02, J04, J12) |
| Specs that exist but belong to no journey | 1 (`apps/web/e2e/journey.spec.ts`) |

How to write and grow them: the `journey-e2e` skill (a journey's spec), the `journey-step` skill (one step, from the scenario event to the spec) and the `fixture-scenario` skill (the data a fixture-mode step reads). The staging demo tenant the `staging` project runs against is loaded and reset by `docs/runbooks/demo-tenant.md`.

## Rules

1. **Files.** `apps/web/e2e/journeys/JNN-<slug>.spec.ts` (upper-case `J`, as built), tests named `JNN <slice> <step>: <outcome>`. Long journeys split into ordered serial blocks that share one seeded tenant. A spec file exists from the journey's first slice and grows as each epic adds the steps it unlocks. Unbuilt steps are left out, never skipped: a skip needs an issue (ADR-079).
2. **Steps.** Each given-when-then line of the journey becomes a step. Every step that opens a screen runs the accessibility check. Every step that crosses a human gate asserts that the agent principal is refused.
3. **Invariants.** Five invariants are asserted in every scenario by one shared helper: INV-1 the agent never decides; INV-2 citations are verified or read "Uncited"; INV-3 ethical walls hold; INV-4 portal scopes are isolated; INV-5 attribution names a person, "person via Agent", or a policy.
4. **Modes** (chapter 10 §10.6.3), one Playwright project each (`harness/adapters.ts`): `fixture` (browser only; `make journeys`), `fullstack` (real auth and server gates on `make dev` + `make seed-demo`; `make journeys-full`), `staging`, and `canary` (production canary), the last two from the jobs that set their URL. A journey counts as **walkable** only in the full-stack modes, with real auth, fakes only for third parties, every gate enforced on the server, the invariants asserted and the accessibility check clean. It is **walkable in production** when the scenario passes on the released build against the production canary tenant. It is **live** when at least one real design-partner instance exists.
5. **Flags.** A scenario turns on the per-firm flags and entitlements it needs and nothing else (ADR-089).
6. **Data.** Synthetic seed and demo clock only; no real client data before the real-data gate (ADR-085). Production runs add new synthetic engagements and delete nothing.
7. **Owner** of every journey is the builder (solo amendment). Adding or removing a journey, or moving a planned date, is a change to this file in the same change as the work.
8. **Targets.** By Fri Aug 17, 2029 (M23) all 28 are walkable in production and at least 12 are live at partner firms.

## Registry

`Spec` is the path (planned until the file exists); `Status` is `no spec` until the file exists, then `spec`. "P0 core" is the earliest date the journey's priority-zero screens are all walkable; "Full" includes the later screens. The first-slice column is the earliest scenario that has to pass.

| J | Journey | Spec | First slice and milestone | P0 core walkable (gating screen, epic) | Full journey (last screen, epic) | Status |
|---|---|---|---|---|---|---|
| J01 | Firm onboarding and methodology upload | `apps/web/e2e/journeys/J01-firm-onboarding.spec.ts` | J01-core in production, M8 (Fri May 28, 2027) | Jun 22, 2029 (WB-07, W-03) | Aug 17, 2029 (ADM-13, G-03) | spec |
| J02 | Client onboarding and portal invite | `apps/web/e2e/journeys/J02-client-onboarding.spec.ts` | J02-audit-core skeleton on staging, M5 (Fri Jan 22, 2027); production M8; live M10 (Tue Jul 13, 2027) | Oct 13, 2028 (CLS-09, C-01) | Apr 27, 2029 (ENG-14, K-04) | spec |
| J03 | Employee-benefit-plan audit | `apps/web/e2e/journeys/j03-ebp-audit.spec.ts` | Fieldwork P0 live, M15 (Fri Dec 10, 2027); EBP-07 by Fri Jan 7, 2028 | Mar 17, 2028 (AUD-25, A-07) | Mar 31, 2028 (AUD-29, P-05) | no spec |
| J04 | General financial-statement audit | `apps/web/e2e/journeys/J04-fs-audit.spec.ts` | J04-PBC slice on staging, M6 (Fri Mar 5, 2027); production M8; live M10; planning slice M15; core M19 | Apr 27, 2029 (ENG-10, K-04) | Jun 8, 2029 (AUD-36, A-11) | spec |
| J05 | Review, compilation and preparation | `apps/web/e2e/journeys/j05-review-compilation.spec.ts` | Core, M19 (Fri Sep 29, 2028) | Dec 8, 2028 (CLS-08, C-02) | Dec 8, 2028 (TXP-13, T-06) | no spec |
| J06 | Individual 1040 season | `apps/web/e2e/journeys/j06-individual-1040.spec.ts` | Coordination slice live, M11 (Tue Aug 17, 2027); record-mode spine to "Mark transmitted", M13 (Tue Aug 31, 2027) | Apr 28, 2028 (TXI-01, T-04) | Dec 8, 2028 (TAX-10, T-08) | no spec |
| J07 | Trust 1041 | `apps/web/e2e/journeys/j07-trust-1041.spec.ts` | None before P0 core; live Tue Aug 22, 2028 (M18) | Aug 18, 2028 (TXT-02, T-07) | Aug 18, 2028 (TXT-03, T-07) | no spec |
| J08 | Partnership 1065 | `apps/web/e2e/journeys/j08-partnership-1065.spec.ts` | K-1 distribution slice, M13 (Tue Aug 31, 2027) | Jul 7, 2028 (TXP-11, T-05) | Jul 6, 2029 (PRJ-01, T-09) | no spec |
| J09 | IRS notice response | `apps/web/e2e/journeys/j09-irs-notice.spec.ts` | P0 live, M15 (Fri Dec 10, 2027) | Dec 10, 2027 (NOT-03, N-04) | Mar 30, 2029 (POR-19, R-03) | no spec |
| J10 | Client accounting services month-end close | `apps/web/e2e/journeys/j10-cas-close.spec.ts` | Read-only path live, M20 (Tue Oct 31, 2028) | Dec 8, 2028 (CLS-08, C-02) | Mar 16, 2029 (INB-04, N-03) | no spec |
| J11 | Workbench: ad hoc, saved agent, scheduled run | `apps/web/e2e/journeys/j11-workbench.spec.ts` | Read-only sessions on staging by M20 | Jun 22, 2029 (WB-08, W-03) | Aug 17, 2029 (ADM-09, G-03) | no spec |
| J12 | Client side: respond, upload, sign, message | `apps/web/e2e/journeys/J12-client-portal.spec.ts` | J12-core skeleton on staging, M5; production M8; live M10; signing M13 | Mar 3, 2028 (POR-09, R-02) | Mar 30, 2029 (POR-19, R-03) | spec |
| J13 | Partner review and sign-off | `apps/web/e2e/journeys/j13-partner-review.spec.ts` | None before P0 core | Apr 27, 2029 (SHL-19, K-04) | Apr 27, 2029 (SHL-19, K-04) | no spec |
| J14 | Firm admin and integrations | `apps/web/e2e/journeys/j14-firm-admin.spec.ts` | None before P0 core | Sep 1, 2028 (WB-11, W-01) | Aug 17, 2029 (ADM-09, G-03) | no spec |
| J15 | Advisory project | `apps/web/e2e/journeys/j15-advisory-project.spec.ts` | None before P0 core | Jul 7, 2028 (TXP-01, T-05) | Jul 6, 2029 (PRJ-01, T-09) | no spec |
| J16 | Daily practice operations | `apps/web/e2e/journeys/j16-daily-operations.spec.ts` | None before P0 core | Oct 13, 2028 (CLS-01, C-01) | Mar 16, 2029 (INB-03, N-03) | no spec |
| J17 | Practice economics | `apps/web/e2e/journeys/j17-practice-economics.spec.ts` | None before P0 core | Mar 3, 2028 (HOME-01, I-01) | Aug 17, 2029 (HOME-04, I-04) | no spec |
| J18 | Audit quality management | `apps/web/e2e/journeys/j18-audit-quality.spec.ts` | None before P0 core | Mar 17, 2028 (AUD-25, A-07) | Nov 24, 2028 (AUD-30, Q-05) | no spec |
| J19 | Estate and amended returns | `apps/web/e2e/journeys/j19-estate-amended.spec.ts` | None before P0 core | Apr 28, 2028 (TAX-07, T-04) | Mar 30, 2029 (POR-18, R-03) | no spec |
| J20 | Group audit | `apps/web/e2e/journeys/j20-group-audit.spec.ts` | None before P0 core; behind `ff.group_audit` | Sep 29, 2028 (POR-23, A-09) | Aug 17, 2029 (ADM-13, G-03) | no spec |
| J21 | Statements studio | `apps/web/e2e/journeys/j21-statements-studio.spec.ts` | None before P0 core | Apr 13, 2029 (FSP-03, A-10) | Aug 17, 2029 (XLA-02, W-04) | no spec |
| J22 | Search for unrecorded liabilities on the Board | `apps/web/e2e/journeys/j22-unrecorded-liabilities.spec.ts` | None before P0 core | Apr 27, 2029 (SHL-19, K-04) | Aug 17, 2029 (XLA-01, W-04) | no spec |
| J23 | Audit partner's morning | `apps/web/e2e/journeys/j23-partner-morning.spec.ts` | None before P0 core | Apr 27, 2029 (ENG-10, K-04) | Jun 8, 2029 (AUD-37, A-11) | no spec |
| J24 | Methodology template rollout | `apps/web/e2e/journeys/j24-template-rollout.spec.ts` | None before P0 core | Apr 27, 2029 (ENG-11, K-04) | Aug 3, 2029 (KNW-11, K-05) | no spec |
| J25 | SOC 2 Type 2 examination (attest) | `apps/web/e2e/journeys/j25-soc2-examination.spec.ts` | None before P0 core | Apr 27, 2029 for the shared Board; attest path with X-01, Jun 22, 2029 | Aug 3, 2029 (ATT-09, X-02) | no spec |
| J26 | Co-sourced internal audit | `apps/web/e2e/journeys/j26-internal-audit.spec.ts` | None before P0 core | Apr 27, 2029 for the Board; internal-audit path with X-03, Aug 17, 2029 | Aug 17, 2029 (POR-22, X-03) | no spec |
| J27 | Managing partner's insights review | `apps/web/e2e/journeys/j27-insights-review.spec.ts` | None before P0 core | Mar 31, 2028 (SHL-17, P-05) | Aug 3, 2029 (WB-13, K-05) | no spec |
| J28 | Audit to tax | `apps/web/e2e/journeys/j28-audit-to-tax.spec.ts` | None before P0 core | Aug 20, 2027 (TAX-09, T-01) | Dec 8, 2028 (TXP-13, T-06) | no spec |

## Third-party fakes the journeys need

Journeys run against fakes for external systems; chapter 10 §10.6.6 lists them per journey. The first ones needed are the identity provider and mailbox (J01), the mailbox, e-signature provider, ledger sandbox and bank feed (J02, J12), and ledger file import (J04). Later: the tax-engine file bridge, e-signature with identity checks and text extraction (J06 to J08, J19, J28); ledger read and post, bank feed and text extraction (J10); the Office host (J21, J22). A fake is never used to mark a journey "live".

## Open items

- **Spec path.** Chapter 10 §10.6.7 sets `apps/web/e2e/journeys/jNN-<slug>.spec.ts`; the harness built them as `JNN-<slug>.spec.ts` and this file follows what is built. P-03-T25 names `J04-pbc-slice.spec.ts`; it extends `J04-fs-audit.spec.ts` instead. One row in the sprint plan (P-07-T22) writes `apps/web/e2e/j02-client-onboarding.spec.ts`; correct it when that task starts.
- **Existing spec.** Decide when F-04 lands whether `apps/web/e2e/journey.spec.ts` is renamed into J02 or deleted after the J02 fixture journey passes. Do not weaken or delete it before then.
- **Slugs** in the Spec column are proposed here; they are final when the file is created.
