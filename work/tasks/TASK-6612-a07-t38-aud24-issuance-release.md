---
id: TASK-6612
title: "A-07-T38: AUD-24 Issuance & release in fixture mode on T2"
spec: SPEC-644
acceptance_criteria: [AC-38]
risk_zone: green
status: in-review
branch: s34-a07-t38
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T38
---

## Objective
All six AUD-24 artboards render from fixtures and Release report… is enabled only in state a for
Margaret Okonkwo's persona.

## Plan
1. `screens/AUD-24/copy.ts`: the handoff spec's words and figures verbatim.
2. `screens/AUD-24/Issuance.tsx`: G5–G7 gate cards with KV values linking to their screens, the
   Also required card, the dashed G8 card (solid only once released, with the archive clock), the
   pinned release bar ("Reserved to the engagement partner", blocked and non-partner captions),
   the release dialog with the partner's attestation (confirm disabled until ticked), the toast,
   the Deliverables dock with the pack, delivery and the Form 5500 filing card (awaiting, filed).
3. `AUD-24.test.tsx`: every state, the enable rule, b blocked by G7, c's attestation, d's G8 and
   clock, e's caption, f's filing.

## Progress log
- `2026-11-10` — Built; prettier, tsc, eslint clean. Tests not run (end pass). Partial: fixture
  mode only (no route mounts it yet; the live read of `GET …/release` and `…/filings` and the
  step-up before G8 come with the screen's live row); the rail is the T2 shell's, not redrawn here.
