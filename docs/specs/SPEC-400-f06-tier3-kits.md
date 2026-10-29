---
id: SPEC-400
title: F-06 design system tier 3 kits (signing, document on well, workbook, portal mobile, tax index)
status: draft
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-041, ADR-042, ADR-050, ADR-052, ADR-065, ADR-066, ADR-078, ADR-111, ADR-138, ADR-149, ADR-155, ADR-160]
related_specs: []
created: 2026-10-27
updated: 2026-10-27
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - Stories are in `docs/plan/epics/F-06.md` §3; the ACs below carry them by number and add no scope.

## 1. Summary
F-06 ships the tier-3 kits ahead of their consumers: `SigningCeremony` (T16, provider mode only),
`DocumentOnWell` (T10), `WorkbookLayout` + `CalcTree` + `SignOffSlots` (T6) and the portal-mobile
kit (T7-M), with five seeded specimens (TPL-01, TPL-06, TPL-10, TPL-16, TPL-19). No backend, no
product route, no flag and no dependency.

## 2. Problem and context
N-02 (POR-06, SIG-01, ENG-04), T-02 (TAX-01), R-01 (POR-20), A-04 to A-07 and N-04 compose these
surfaces from 2027. Without tested kits each consumer would invent its own layout. F-06.md §0–§2.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Signer (Mira Kapoor, Claire Feld) | Reviews and signs in the ceremony; never acts for another signer |
| Reviewer (Samuel Ito) | Approves a document or opens a sign-off; the kit never writes |
| Tax manager (Hannah Leclerc) | Reads the practice board |
| Accrued Agent | Drafts paper prose (firm-internal only); never decides, never signs |

## 4. Context
Consumed contracts: C7 envelope view (N-02; stub due S14, no merged contract yet: the kit types
are L2 view models and the L3 mapping lands with N-02), C5 `/v1/me` portal scopes, C3 sign-off
read, C4 citation v2 locators, C2 `docs/product/status-vocabulary.yaml`.

## 5. Acceptance criteria

Signing kit (F-06.md §3 F1):
- **AC-1** Story 1.1: provider-mode review and sign; return parameters never trusted.
- **AC-2** Story 1.2: one signer cannot act for another; non-signer gets `restricted`.
- **AC-3** Story 1.3: completion card with six evidence rows; TINs only as masked strings.
- **AC-4** Story 1.4: DF-11 verification failed, no retry; identity method per envelope type.
- **AC-5** Story 1.5: decline needs a reason; `onDecline` once; focus returns.
- **AC-6** Story 1.6: signing at 390 with the sticky bar and 44 × 44 targets.
- **AC-7** Story 1.7: native artboards are Tier C screenshots; no native identity components.
- **AC-8** Story 1.8: no agent element; sign controls are `HumanAction`s.

Tax practice board (F2): **AC-9** Story 2.1 · **AC-10** Story 2.2 · **AC-11** Story 2.3 ·
**AC-12** Story 2.4 · **AC-13** Story 2.5.

Portal mobile (F3): **AC-14** Story 3.1 · **AC-15** Story 3.2 · **AC-16** Story 3.3 ·
**AC-17** Story 3.4 · **AC-18** Story 3.5.

Document on well (F4): **AC-19** Story 4.1 · **AC-20** Story 4.2 · **AC-21** Story 4.3 ·
**AC-22** Story 4.4 · **AC-23** Story 4.5 · **AC-24** Story 4.6 · **AC-25** Story 4.7.

Workbook (F5): **AC-26** Story 5.1 · **AC-27** Story 5.2 · **AC-28** Story 5.3 · **AC-29** Story 5.4
· **AC-30** Story 5.5 · **AC-31** Story 5.6 · **AC-32** Story 5.7.

Quality and hand-off (F6):
- **AC-33** Each of the eight screen contracts maps every artboard to a data condition, persona,
  clock, parity tier and copy key, and every superseded state cites its DF or DEC row (T01).
- **AC-34** The E0 tax fixtures foot (79, 224, 2,296, 6,866,200, 1,256,200, 733,500) and the L10
  contamination scan is clean (T02).
- **AC-35** The DF-31 status rows exist with display words and pill variants, and the codegen
  regenerates `status.gen.ts` with no hand edit (T03).
- **AC-36** C7 and C5 consumer contract tests (T09).
- **AC-37** Parity and axe locks (T11, T13, T22).
- **AC-38** Kit docs and consumer hand-off (T23).
- **AC-39** ADR P-24 (structured agent output) drafted and accepted (T24).
- **AC-40 T16 identity and exception states (F-06-T05; DF-11, DF-12; DEC-1053).** Provider mode shows Completed only after the envelope status says so, TPL-16e offers no retry and names the paper-form path, Decline stays disabled until a reason is chosen, and no native identity component is exported.
- **AC-41 T16 at 390 (F-06-T06).** At 390 px nothing scrolls sideways, the sticky bar never hides the active field, and every control has at least a 44 by 44 target; TPL-19 frame 9 hands off to the same ceremony.

## 6. Open questions
- Q1 (iframe or redirect) and Q5 (provider-mode CTA copy): open, decide by Fri Apr 30, 2027; they
  block T05 and T06 only. T04 renders the provider frame slot and keeps the built label.
- Q2: settled, screenshots only. Q4, Q6, Q7: settled in T01 (`packages/ui/src/tokens/DECISIONS.md`).
