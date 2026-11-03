---
id: TASK-3234
title: A-04-T27 AUD-04 Audit program and workpaper, scenarios a-f
spec: SPEC-620
acceptance_criteria: [AC-1, AC-4, AC-5]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T27
branch: s26b-a04-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3234 · A-04-T27 · AUD-04 Audit program & workpaper

## Built
- `apps/web/src/screens/AUD-04/` (Program, copy, index, scenarios, test): T2 without the dock over the A-04-T04 record by tab (`service_organizations`, `linkage`, `approach`) and the paper's C4 citations, drawn through the C-02 `WorkpaperPane` (its first screen use): section bands, captions, key/value rows, the service-organization table, the after rows, citation markers, SHL-07 popover and the pinned Citations/Procedures footer.
- Header state: "Draft · Accrued Agent" while any value is suggested, "Prepared · MD" once adopted, "Signed off" with ✓ MD ✓ HL; Adopt (L1)… and Sign off… open SHL-12 (L1/L2); Sign off… is disabled until the draft is adopted.
- Route `/audits/$auditId/program/$wpRef?tab=linkage|approach`; manifest path.
- Fixtures `seed/aud04.ts` and scenarios a–f; 14 tests pass.

## Partial
- Outlined agent tickmarks (◌): the C-02 kit has no outlined tick variant; the drafted state shows in the header pill, and adopted table cells carry ✓.
- d's stepper is covered by the kit's popover; the test checks the cited cells carry match ids, not the stepper itself.
- Two citation quotes (Keystone SOC 1 p. 14 section III, BH-EBP-140 step 3) are withheld: the handoff names the sources without their text.
- Open in Excel and the download are icon actions without an export yet; the rail is AUD-02's.
- Security review (S26 batch 2): agent-drafted cell values reach the C-02 `WorkpaperPane` as plain, escaped text, not through `AgentText` (ADR-065's rendering path). No injection risk, but the kit should take an `AgentText` slot for `value_source: agent` cells: follow-up in S27.

## Progress log
- 2026-11-03: built; tsc and eslint clean; vitest 14 passed.
