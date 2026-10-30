---
id: TASK-2200
title: F-06-T13 signing and tax-index parity lock and hand-off
spec: SPEC-400
acceptance_criteria: [AC-37]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T13
branch: s17-f06-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Lock T16, TPL-16 and TPL-01 for their consumers: Tier B frames (provider frame masked), Tier A
chrome strips, Tier D geometry, the f06-signing and f06-tax-index specimen walks, and the written
hand-off to N-02 and T-02.

Acceptance: "By Fri Jun 11, 2027 the three boards are parity-locked and axe clean, and N-02 and
T-02 hold a written mapping from C7 and the tax list payload to the kit props."

## Scope
**In**
- Parity manifest entries for T16b/c, TPL-16a–g, TPL-01a–e; Tier A strips; masks (DEC-1250).
- The harness's `strip` field (support.ts, parity.spec.ts, crop_handoff.py).
- TPL-16a in the gallery as the production provider-mode state; TPL-01 framed in the firm window.
- `e2e/visual/tier-d-signing.spec.ts`; `e2e/specimens/f06-signing.spec.ts`, `f06-tax-index.spec.ts`.
- `docs/design/kits/signing.md` (C7 → EnvelopeVM, the tax list → IndexList and DueCell).
- DECISIONS.md and the three screen contracts' Parity tables.

**Out**
- Native KBA or Adopt components (DF-12). TPL-19 (F-06-T11). T6/T10 (F-06-T22).
- Posting the hand-off on the N-02 and T-02 epic issues (an outward GitHub action; the kit doc is
  the hand-off and the PR links it).

## Context to load
- Spec: `docs/specs/SPEC-400-f06-tier3-kits.md` (AC-37)
- Epic: `docs/plan/epics/F-06.md` §5.4, §8.3, §10 items 1 and 3
- `docs/design/parity.md`; `docs/contracts/c7-envelopes.md`; `apps/web/src/domain/signing/envelope-vm.ts`

## Plan
Steps:
1. [x] Manifest entries with pinned hashes, window and phone crops, masks (DEC-1250).
2. [x] Harness: a `strip` cut from the frame's render and its baseline.
3. [x] Gallery: TPL-16 `?st=a` (provider view), `data-artboard` wrappers, TPL-01 in the firm window.
4. [x] Tier D spec; specimen walks; unit tests for TPL-16a; crop tool tests for `strip`.
5. [x] Kit doc; DECISIONS.md; decision log; screen contracts.
6. [ ] End review: crop and fetch baselines, run parity, Tier D, the walks and axe; set `locked: true`
       on every entry that measures in tolerance and record the diffs in DECISIONS.md.

Tests to write (mapped to ACs):
- AC-37 → `e2e/visual/parity.spec.ts` entries (`t16-signing-ceremony.*`, `tpl-16*`, `tpl-01*`),
  `e2e/visual/tier-d-signing.spec.ts`, `e2e/specimens/f06-signing.spec.ts`,
  `e2e/specimens/f06-tax-index.spec.ts`, `TPL16.test.tsx` (TPL-16a), `test_crop_handoff.py` (strip).

## Progress log
- `2026-10-29` — Built steps 1–5 on `s17-f06-t13` (build-only; tests written, run at the S17 end
  review). Locks wait for the measured run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1250: page masked as the provider frame region; TPL-16a = provider view; TPL-16c Tier C; strips cut from the frame baseline; TPL-01 in the firm window; walks on the chromium project | F-06 §5.4 masks, DF-12, no hand-measured crops | no |

## Gotchas and discoveries
- The harness's fixture project matches only journeys; gallery walks run on chromium with
  `ABACUS_VISUAL=1` (as F-06-T07's `e2e/screens/TPL-16.spec.ts`).
- TPL-16g's PNG is 880 × 1800: the phone sits at 50 56 830 1744.

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** the end review's parity run, then flip `locked` per measured entry.
