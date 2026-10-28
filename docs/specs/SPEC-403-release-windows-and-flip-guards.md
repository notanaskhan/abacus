---
id: SPEC-403
title: "Release windows as code: the windows file, release gate, flip guard, flag calendar, flip requests and the go-live check (Q-04 groups A to D and F; Q-04-T002 to T005, T009 to T011)"
status: approved
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-089, ADR-092, ADR-097]
related_specs: []
created: 2026-10-28
updated: 2026-10-28
---

> **Instructions for coding agents**
> - Implement only what this spec describes. ADR P-29 (DEC-68) and `docs/ops/release-windows.md` (Q-04-T001) bind; where this spec and the note differ, the note wins and this spec is corrected.
> - Every test names the acceptance criterion it proves.

## 1. Summary
Once real firms rely on production, P-29's freeze contract decides when production may change. This spec makes it machine-checked: one protected calendar file (`deploy/windows.yaml`) read by the release gate, the flag and entitlement CLIs, the flag registry check, the flip ops-request check and the go-live check (Q-04 §3.1 to §3.4, §3.6).

## 2. Problem and context
Dates in heads drift. A promotion in a deadline week, a flip outside the Tuesday slot, a flag that expires on Sep 10 in a firm's autumn window, or a firm going live without MFA at 100% are each a pilot incident (RK-15, RK-47). The pipeline cannot read production, so window membership lives in git, by pilot code (never a firm name).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| N | Operates releases and flips (operator); owns the red rows |
| AY | The other founder: approver of N's flips and releases; writes the independent AC tests (T011, T013) |
| CI | Runs `make check-fast`, the release gate and `flip-precheck` |

## 4. Acceptance criteria
**The windows file (Q-04-T002).**
- **AC-1** `release_windows.in_window(PF-A1, Wed Sep 1, 2027 00:00 CT)` is `autumn-2027` for a firm with real data since Jun 1, 2027 and `autumn_window: true`; for an audit-only firm it is none until Sat Jan 1, 2028 (Q-04 AC-1.1).
- **AC-2** With no firm's `real_data_since` set, every guard is inert (Q-04 AC-1.2; DEC-68).
- **AC-3** `make check-fast` fails naming the entry for an overlapping window, an undated mini-freeze or deadline week, dates that differ from the P-29 rule, a tenant UUID with no `code`, or a `code` that is not a pilot code (`PF-A1`) or cohort code (`PC28-07`) (Q-04 AC-1.3; DEC-806).
- **AC-4** `make windows YEAR=2027` prints mini-freezes Sep 8–15, Sep 23–30 and Oct 8–15, and every year 2027–2029 prints Q-04 §4.9's mini-freezes, deadline weeks and Tuesday slots (Q-04 AC-1.4).

**The release gate (Q-04-T003).**
- **AC-5** On a simulated in-window date, a release record without `window_mode` (`defect_only` or `dark_only`) or a rollback link fails the gate (Q-04 AC-2.1).
- **AC-6** In a deadline week the gate refuses promotion unless `hotfix: {reason, requested_by}` is set; with it, it passes and is counted (Q-04 AC-2.3).
- **AC-7** Inside a window the migrate step is held to 20:00 CT (Q-04 AC-2.5); the gate calls Q-03-T081's contract-operation guard in window mode once it lands, never its own (Q-04 AC-2.4).

**The flip guard (Q-04-T004).**
- **AC-8** For a firm inside its window, a flip outside the Tuesday 19:00–21:00 CT slot, in a deadline week or mini-freeze, approved by its own operator, or without a rollback link is refused with nothing written; outside a window only the approval and rollback rules hold (Q-04 AC-4.1 to AC-4.4).
- **AC-9** An allowed flip's `feature_flag.set` audit event carries operator, approver, slot and request fingerprint; `--all-off` sets every flag for one firm to its default in one unit of work with one `feature_flag.bulk_off` event (Q-04 AC-4.1, AC-4.7). The entitlement CLI takes the same guard.

**The flag calendar (Q-04-T005).**
- **AC-10** A registry entry whose `expires` falls inside any window fails `feature_flags --check` with the window named, unless it carries `window_exception: {reason, approved_by}` with `approved_by` not the owner; `make flag-calendar` lists every flag with owner, expiry, last train before expiry, window conflicts and a 21-day warning (Q-04 AC-3.1, AC-3.3).

**The go-live check (Q-04-T009).**
- **AC-11** `make go-live-check FIRM= LEVEL=` reports pass, fail or manual for each chapter 06 §8.3 item it can read at that level, as JSON for the dossier; a tenant below 100% MFA or with a lapsed provider-terms review fails with the item named (Q-04 AC-6.1 to AC-6.4).

**The flip ops-request check (Q-04-T010).**
- **AC-12** A `deploy/production/ops-requests/flip-<date>-<code>.yaml` request whose journey last passed on staging more than 24 hours before, that names no shadow run, names its operator as approver, or whose slot is not valid for the firm's window fails `flip-precheck` (Q-04 AC-4.1).

**Independent tests (Q-04-T011).**
- **AC-13** A suite written from the P-29 note covers Sep 1 00:00 CT, Oct 20 23:59 CT, every deadline week and the Tuesday slot edges, and fails when any guard is removed.

## 5. Out of scope
The pilot tables and metrics workflow (T006 to T008, T012), Q-03-T081's migration guard itself, PLT-01 (G-04), the firm-facing metrics reads (I-03).

## 6. Open questions
None open. OQ-1 (mini-freeze rule) follows the Q-04 note; OQ-2 (platform versus per-firm rules) is decided in the note §1.
