# Audit planning flip: per-firm order, rollback and what persists (A-04-T40)

**Owner:** the builder (solo; AMENDMENT-solo) · **Module:** `assurance` (A-04), `workpapers`,
`ledger` · **Severity of a failed flip:** SEV-3 (flag off restores the previous screens) ·
**Last reviewed against an incident:** never · **Task:** A-04-T40 (TASK-3241)

The audit planning screens (AUD-04, AUD-05, AUD-07, AUD-08, AUD-09, AUD-10) reach a firm in three
per-firm flips, each in the Tuesday 7 pm CT slot (`deploy/windows.yaml`), each with the planning
journey green on staging within 24 hours, a shadow run clean, and both approvals (solo: Ayush's,
recorded in the release record).

## 1. Order

| Slot (plan calendar) | Flags turned on for the firm | Screens | Before it |
|---|---|---|---|
| Tue Oct 26, 2027 | `assurance.materiality` | AUD-07 a–e (locked at Tier C) | CPA review memo for `materiality@1` signed; materiality goldens green (A-04-T17) |
| Tue Nov 9, 2027 | `workpapers.core`, `workpapers.drafting`, `assurance.risk_register` | AUD-04, AUD-05, AUD-08 | The section drafter's modes cleared through Q-02's path (Bedrock eval runs, shadow stage) |
| Tue Nov 23, 2027 (inside the window) | `assurance.internal_control` (and service organizations) | AUD-09; AUD-10 only if A-04-T37 and its Tier C lock are in the Thu Nov 18 train | Otherwise AUD-10 stays dark and the tier-2 AUD-10 cut applies |

`ledger.tb_mapping` (A-03) flips separately, on Oct 19 (Q-04-T092).

## 2. Flip
1. Confirm the slot's `flag_flip` record names the flip, its approver and this runbook as the
   rollback; `abacus_tools.flip_guard` checks it against `deploy/windows.yaml`.
2. Turn each flag on for the one firm: `make flag FIRM=<tenant_id> FLAG=<name> VALUE=true
   OPERATOR=<name> REASON=<text>` with `--approved-by` and `--rollback
   docs/runbooks/audit-planning-flip.md`, as an ECS one-off task, never from a laptop against a
   hosted database.
3. Run the planning journey on the firm's tenant as its engagement partner; check AUD-07's figures
   against the firm's materiality ranges and G4's facts on one engagement.

## 3. Rollback: flag off
Turn the same flags off for the firm (`make flag ... VALUE=false`, or the tool's `--all-off`).
Nothing is deleted or reversed:
- **Decisions persist.** Materiality versions, `significant_risk` and planning decisions, their
  cards and audit events stay as recorded (insert-only; human-only actions).
- **Versions persist.** Workpaper versions, sign-offs and the risk register's rows and history
  stay; with the flag off the screens are hidden (C-20 flag-off state), not the records.
- **G4** reads its facts again when the flag returns (`assurance.planning_gate.g4_facts` is met
  with the risk register flag off, by design).

## 4. Flag calendar
Every A-04 flag (`assurance.materiality`, `assurance.risk_register`, `assurance.internal_control`,
`workpapers.core`, `workpapers.drafting`) and `ledger.tb_mapping` expires between Apr 28 and
Apr 29, 2027: none inside the Jan 1 – Apr 20, 2028 freeze. Renewal to Dec 30, 2027 is due before
each flag's expiry; retirement once on for every live firm (planned for the Dec 14 train),
recorded in `docs/plan/status/flag-renewals-2027.md`.

## 5. Verify
The planning journey green on the firm's tenant; AUD-07's tie-out to the firm's ranges; G4 met on
the engagement whose planning finished (the `planning` slice reproduces Northwind's on PF-X1).

## Rehearsal log
| Date | Kind | Result | Changes made |
|---|---|---|---|
| — | staging walk-through (pending) | Not rehearsed: no staging deploy since S26 and no real firm (DEC-1391); the `planning` slice (A-04-T28) is the PF-X1 data for it | — |
