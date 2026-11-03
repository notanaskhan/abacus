# S26 support reserve, N lane (Q-04-T094), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081). The sprint is S26 of the plan (Oct 18-29, 2027: the autumn window closes
Oct 20 and season-2 onboarding begins); no pilot firm is live (DEC-1391) and no production stack
exists.

Acceptance: "Every page in the sprint was acknowledged within 15 minutes and every SEV1/2 has a
postmortem within 5 business days."

## Pages and incidents
No page fired and no SEV1 or SEV2 was declared: nothing is in production for a firm to reach. So
there is no acknowledgement time to measure and no postmortem owed.

## The lane's duties

| Duty | This sprint |
|---|---|
| On-call primary and incident response | No page, no incident (above). |
| Live-path defect fixes | No live path. The period's defects went through the batch: the S26 end review fixed the notices gate that refused every function-scoped action (no work item on the resource), the control-exception insert that broke 0657's CHECK and grants, about 40 contract fields that lost their classification tag, and AUD-08's Edit resending the model's text; each lands with the PR it belongs to (#1126-#1158, merged 2026-11-03). No hotfix ran. |
| Weekly production promotion | None: `deploy/production/release.json` holds no digests. |
| In-window slot duty | Rehearsed: the Oct 19 slot, the Oct 20 close and the Oct 21 train under the real gate (`docs/ops/windows/2027-10-19-tuesday-slot.md`, Q-04-T092). |
| Runbook upkeep | `docs/runbooks/review-grammar.md` (P-04-T61) added: stale storms, projector rebuild, undo-window incidents, grant voids; its staging rehearsal waits on the next staging deploy. |

## What only a live firm can show
A page and its acknowledgement time; a SEV1/2 and its postmortem; a live-path fix and its time to
production; a weekly promotion closed by 21:00 CT.
