---
id: TASK-8935
title: "T-06-T45: AUD-38 a-e, AUD-06 menu item, TXP-13 d, shared HandoffProvenanceBanner"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t06t45
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-06-T45
---

## Objective
AUD-38 states a-e as the O3 sheet over AUD-06 (?ov=tax-handoff), the AUD-06 menu item with the G8-disabled reason, the O4 128-mapping table, toggles and toast; TXP-13 d frame; shared HandoffProvenanceBanner on TXP-13 and the TXP-02 DF-08 state. Acceptance: Hand off is the only primary button, focus stays trapped in the sheet, and the banner copy matches the revision exactly.

## Done
- C12 stub preview additive fields (source, target, schedule_rows, accounts, independence, review/tax-item detail); landing additive counts, candidates, source_work_item_id (landing service fills them)
- Python slice: AUD-38 previews a/b/d/e + TXP-13 d landing, exported as scenario.aud38.json
- AUD-38 sheet (screens/AUD-38) registered as ?ov=tax-handoff, ov.AUD38; O4 mappings table; toggles; toast; landed preview
- AUD-06 menu item on the live gate (useTaxHandoffGate) with the G8 reason; planned facts only in dev builds
- HandoffProvenanceBanner (domain/tax) on TXP-02 (DF-08) and TXP-13 d; TXP-13 d route /tax-returns/$returnId/review/workpapers
- Kit: Segmented active={null} (none chosen) + test
- Tests: AUD-38 10, TXP-13 2, banner 3, slice 3, kit 1; e2e specs AUD-38, TXP-13

## Progress log
- `2026-11-23` — 2026-11-23: built in the S53 sequential run. Preview/create live assembly is T-06-T59 (S55); DF-08 PF sign-off (T-06-T02) is a human remainder. Targeted tests pass; integration/e2e in the end pass.
