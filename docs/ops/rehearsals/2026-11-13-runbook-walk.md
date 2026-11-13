# Runbook walk, 2026-11-13 (Q-04-T107; solo, on PF-X1)

Q-04-T107 asks the firm rollback, in-window flip and onboarding runbooks to be walked by the founder
who did not write them. Under the solo edition there is one builder (DEC-4818 kept the row as a solo
walk on the synthetic firm). Local stack (`make dev`, E0 seed), PF-X1 = Brightwater Hale.

| Runbook | Step walked | Result |
|---|---|---|
| RB-33 binder export and pilot rollback | §2.3 turn `audits.binder_export` on; §4.2 turn it off | **refused**: `make flag` answers `approver_is_operator` (`abacus_tools.flip_guard`): every flip on a firm in `deploy/windows.yaml`, PF-X1 included, needs a second person as approver |
| review-approvals-flip | §3 the flip, §5 its rollback | not walked: the same refusal |
| RB-01 deploy and rollback, flag flips | the flag flips section | not walked: the same refusal; the deploy half needs staging |
| release windows | `make windows YEAR=2027` | passed: the 2027 calendar prints; no firm is live, so every guard is inert |
| RB-18 e-signature outage | §2.3 record mode, §2.5 the handwritten path | passed as a drill on the synthetic suites (10 passed; RB-18's log) |
| pilot onboarding | §1 provision, §3 people and walls | not walked this time |

## Gap found (not fixed: Ayush's call)

The flip guard enforces two people on every flip (P-29), while AMENDMENT-solo item 2 voids approvals.
With one builder, no flag on PF-X1 can be flipped through `make flag`, so the rollback and flip
runbooks cannot be followed as written. Loosening a security control is a decision, not a fix:
either the guard accepts the solo builder as approver for a synthetic firm (or with a named DEC), or
the runbooks keep the two-person rule for real firms and say how the solo builder rehearses.

Q-04-T107 stays partial until that call is made and the walk is finished; Q-04-T137 is the next
quarter's walk.

## Second pass after DEC-4822 (2026-11-13, TASK-7830)

Ayush chose: on a synthetic firm the solo builder approves their own flips; a real pilot firm keeps
two people (DEC-4822). Fresh worktree stack (`ABACUS_PORT_OFFSET=90`), Dev firm seeded, PF-X1 loaded
with `make seed-demo SLICE="pilot portal portal_pbc people"` at E0. Every flip ran through `make flag`
with `APPROVED_BY` = the operator.

| Runbook | Step walked | Result |
|---|---|---|
| RB-33 binder export and pilot rollback | §2 step 3 `audits.binder_export` on; §4.1 `audits.cockpit` off; §4.2 `audits.binder_export` off; the cockpit back on | passed: four flips, each `feature_flag.set` carries `approved_by`, `rollback` and `self_approved: 1` |
| review-approvals-flip | §5 the rollback (`review.approve_agent_output` off, `HOTFIX`), then §3 the flip on | passed after the runbook fix below |
| RB-01 flag flips | `collaboration.v2` on, then off (its rollback) | passed (the route checks on staging stay with RB-01's staging rehearsal) |
| control | a flip with no `APPROVED_BY` | refused: `approver_missing` |
| pilot onboarding (RB-37) | §0 to §6 through the API, signed in through the local hosted email-code flow as the firm admin (Grace Holloway), the security admin (Felix Andersen), a partner (Margaret Okonkwo) and the walled person (Ana Cruz) | passed (third pass below) |

Eight self-approved flips recorded; the guard's unit tests prove a real pilot firm still refuses
`approver_is_operator` in and out of its window.

### Gaps found and fixed (TASK-7830)

1. **The runbooks' `ROLLBACK` values were refused.** review-approvals-flip §3 said
   `ROLLBACK="flag off; decisions persist"` and §5 `ROLLBACK="n/a"`; RB-33 §2 and §4 named none. The
   flip guard takes only a `docs/` path or an https link (`rollback_missing`). Each now links its
   rollback section, and both runbooks say who may approve on PF-X1.
2. **`make flag` and `make entitlement` ignored the worktree's stack.** They ran with no database
   setting, so a worktree at another `ABACUS_PORT_OFFSET` wrote to the default stack on port 55432.
   The first attempt at this pass wrote three PF-X1 flag rows and five `feature_flag.set` events into
   another worktree's local stack; the three rows were deleted (each flag had no row before), the
   events stay (audit is append-only). Both targets now use the environment's database when one is
   set (staging) and this checkout's stack otherwise (`OPERATOR_ENV` in the Makefile).

## Third pass: RB-37 (2026-11-13, TASK-7830)

Same stack. Each seat signed in as on staging (work email, the emailed code, the authenticator
code) through `abacus_tools.fakes.oidc_server`, then called RB-37's routes with its session.

| Section | Result |
|---|---|
| §0 | the firm admin's `GET /v1/firm/settings/overview` 200 |
| §1 offices, teams | created and listed (at `version` 0); a team's members set |
| §2 people | an invitation listed as invited (`invitation_id` set, `user_id` null), resent; a seasonal one revoked; a firm role set; a security role set and cleared by the security admin; the seasonal group's access end moved; tallies 47 used, 1 pending, of 48 |
| §3 | the audit line's policy saved by the firm admin, refused to the security admin (403); the annual statement published, a partner's own confirmation recorded, the firm's list read |
| §4 | the offshore group read (none; TINs masked, consent required) |
| §5 walls | preview, create naming the partner; approval refused to its creator and to the security admin (403), taken by the named partner; the walled person gets 404 on the client and never sees it in Clients, Home or search, with no "hidden" note |
| §6 | the firm admin's audit trail lists each step as theirs (16 actions) |

To walk §2 the firm needed free seats: PF-X1 uses all 46 and `plan.seats` is provisioning's, so the
local database's `plan.seats` was set to 48 (a rehearsal stand-in for a plan change). §6 needed
`audit_log.explorer`, turned on with `make flag` (self-approved, DEC-4822).

### Gaps found and fixed in RB-37

1. §0 now checks free seats (409 `seats_full` otherwise; seats change at provisioning) and the audit
   log explorer flag.
2. §1: an office `code` is two to six capital letters; a team needs its `kind`; new rows are at
   `version` 0, not 1.
3. §2: a seasonal invitation needs `access_ends_on` (422 `access_ends_required`); a firm admin may
   also assign security roles (the permission matrix says so; the runbook said security admin only).
4. §6: the route is `GET /v1/audit-events?actor_id=…` (`limit` at most 100), not `/v1/audit`.

RB-37, RB-33 and review-approvals-flip now carry `last_rehearsed: 2026-11-13`.
