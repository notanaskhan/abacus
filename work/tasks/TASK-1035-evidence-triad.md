---
id: TASK-1035
title: T3 EvidenceTriad (Review, Prepare and Two-pane presets in a MatchScope); states T3a to T3e (F-05-T53)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T53
branch: s7-f05-t50-t53-ui-kit
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"T3b shows the ink check micro-pill (never green), T3d shows the red-ink mismatch with Flag, and
Approve Document is a HumanAction."

## Scope
**In**
- `packages/ui/src/templates/evidence-triad.tsx`: `EvidenceTriad` (toolbar, the default record
  subbar 42, the compact tabsbar 44 whose ViewToggle picks the preset, and the panes in one
  `MatchScope`, 706 tall): Review 452 · 452 · 452 and Prepare 214 · 571 · 571 on the C-09
  `review` and `taxReview` presets, Two-pane as the sheet flexing beside a 490 viewer. `TriadTree`
  (group bands 31, sub-heads 26, document rows 29 on the x26 guide rail, the CheckPill, the amber
  flag pill with its count, Requested), `TriadFooter` (Approve Document through `HumanAction`,
  Approved once done, Issue…; stacked in the 214 tree), `TriadSheetBar`.
- `packages/ui/src/specimens/t3.tsx`: `t3-evidence-triad`, artboards `t3a` to `t3e` on the T3
  handoff's Feld 2025 Form 1040 (`feld-t3.ts`): the three source documents in the E5 SourceViewer
  with their boxes as regions, the Worksheets field rows, the Leadsheets, the 2-Year Comparison.
  Live: tree picks, approve, Issue…, sheet tabs, presets, search; a field and its box light
  together.
- Parity `t3-evidence-triad.t3a` to `.t3e` at Tier B with a recorded deviation (synthetic page
  images); Tier D: subbar 42, tabsbar 44, panes 706 tall at 214 · 571 · 571, 452 × 3 and 876 · 490.

**Out**
- TPL-03, the Feld 1040 review specimen on the seed's figures (F-05-T54).

## Definition of done
- [x] 9 tests in `templates/evidence-triad.test.tsx`; 3 Tier D tests
- [x] axe harness, INV sweep and white-label sweep over the gallery
- [x] lint, tsc, prettier for `packages/ui` and `apps/web`

## Progress log
- 2026-10-24: built. Decisions in `tokens/DECISIONS.md` (F-05-T53). The Two-pane preset is the
  template's own row: SplitLayout's presets are pinned to chapter 04 §3.11's twelve by test.
