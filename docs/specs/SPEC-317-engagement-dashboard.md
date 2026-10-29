---
id: SPEC-317
title: "Engagement dashboard, first slice: gates, progress tiles and next up, all computed by code from the modules' own facts"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-050, ADR-005, ADR-140]
related_specs: [SPEC-313, SPEC-314, SPEC-316]
created: 2026-10-22
updated: 2026-10-22
---

## 1. Summary
This is K-04 ENG-12, built on what exists: the Board over programs waits for K-03's templates.

- One read model, `GET /v1/engagements/{id}/dashboard` (`dashboard.read`: the engagement team, independence-bound; clients and the agent are denied).
- Every number comes from the owners' own facts.
- Other modules contribute through a fail-closed `register_progress_source` slot. Fieldwork registers procedures run, findings concluded, entries awaiting approval and passed entries.

## 2. Acceptance criteria
- **AC-1 Gates and tiles.** It returns G1, G2, G3 and G5–G9 (met and blockers), and the tiles below. A tile carries `attention` where something needs action.
  - from the sign-off matrix: working papers signed off (L1 and L2 current, no open notes) of all papers, ready for review (L1 current, L2 missing), and changed after sign-off;
  - open review notes;
  - requests received of those requested, and requests overdue (the list's default due date applies);
  - the trial balance of record's checks that tie, of all checks, and accounts mapped, of all accounts;
  - every registered progress fact.
- **AC-2 Next up.** Up to 20 things the caller can do now. The permission matrix decides (`could`), never role names:
  - sign as preparer where a reviewable has content and no current L1;
  - review where L1 is current, L2 is missing and the caller isn't the L1 signer;
  - answer open notes the caller didn't raise;
  - clear answered notes the caller raised;
  - chase overdue requests, for those who may update requests.
- **AC-3 Web.** A "Dashboard" engagement tab shows:
  - the gate strip;
  - tiles, each linking to where the work lives, with an amber edge on attention;
  - "Next up for you", whose rows open the working paper, trial balance, sign-offs or requests.
- **AC-4 HOME-01 lite MVP proof (I-01-T14).** HOME-01 a, a2, f and g are parity-locked at Tier C, the geometry holds at Tier D (subbar 42, tiles 120 × 99 r14, pane header 46, rows 44, right column 420), and every scenario is axe clean and keyboard-walkable.

## 3. Out of scope
- The program Board (needs K-03).
- Milestones and the health rule.
- Reviewer, Preparer and Client lenses.
- Budget.
- The cross-engagement portfolio view.
