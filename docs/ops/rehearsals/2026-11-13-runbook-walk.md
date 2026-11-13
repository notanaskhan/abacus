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
