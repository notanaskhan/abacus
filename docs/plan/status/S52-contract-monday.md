# S52 Contract Monday (Mon Oct 16, 2028 · held 2026-11-20, solo edition)

K-03 kickoff gate (K-03-T01, TASK-8800).

## ADRs (both Accepted on origin/main with this PR)
| P | ADR | Zone | Decision | DEC |
|---|---|---|---|---|
| P-41 Templates v2 | ADR-213 | amber | gated updates via `engagement_template_links`; one publish flow; content in the DB | DEC-56, DEC-5802 |
| P-52 Firm-authored instructions | ADR-345 (alias ADR-162 is P-31) | red | delimited, semi-trusted layer after the registered prompt; bounded by tools and the matrix | DEC-90, DEC-5801, DEC-5802 |

No red row of K-03 §0.1 is open: every other gating ADR is accepted on main (P-07 ADR-133, P-35
ADR-126/161, P-22 ADR-157/233, P-24/P-46 ADR-234, P-47, P-48 ADR-144/343, P-49, P-28, P-15
ADR-156, P-42 ADR-236, P-12 ADR-146, P-43 ADR-159, P-29 ADR-151). P-51 and P-53 are not gates.

## Upstream consumer tests (C3, C4, C6, C16)
Run once at the S52 end pass (build first, test last; Ayush 2026-11-20). Result recorded in
`docs/plan/status/S52.md` §End pass.

## Open questions Q1–Q8 (recorded as decisions, recommended answers taken)
Q1 DEC-5803 · Q2 DEC-5804 · Q3 DEC-5805 · Q4 DEC-5806 · Q5 DEC-5807 (C22 TV-1, C23 SH-1) · Q6
DEC-5808 · Q7 DEC-5809 · Q8 DEC-5810.

## Contract requests
- C3 additive v1: optional `before_sign(tx, ctx, target_id, level)` on the reviewable provider
  (K-03-T27, S55).
- C2: eight status objects (K-03-T07, this sprint).
- C16: notification kind `template_update_available` (K-03-T06, this sprint).
- K-01: `methodology.api.publish_as_component(version_id, effective_from)` (K-03-T26).
