---
id: TASK-973
title: Draft P-12 as ADR-167 - TRI, phi and pii_kind flags, gateway TIN refusal, consent-gate shape (Q-02-T25)
spec: SPEC-036
acceptance_criteria: [AC-2]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T25
branch: s5-ops-closeout
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"P-12 is Accepted by Fri Jan 22 with both founders and counsel's naming of AWS Bedrock as the recipient recorded" (Q-02-T25; DEC-52; conflicts C-01 to C-03).

## Plan
- `docs/adr/ADR-167-...md`, status **proposed**. The number is the next free one on `origin/main` (ADR-166 was the last). It covers three things:
  - three field flags beside ADR-031's four levels (`tri`, `phi`, `pii_kind`), each forcing Restricted;
  - the gateway's `pii_in_context` refusal of unmasked SSN, ITIN and EIN patterns, before any network call;
  - the shape of T-01's C19 consent gate: the `consent(<purpose>)` condition, gateway condition 6 with reason `consent_7216`, the tool-layer `require_tri_consent`, the agents-off path, and recipients generated from the registers.
- Open questions OQ-1 to OQ-3. OQ-1 is counsel confirming "Amazon Web Services (Bedrock)" as the recipient named for model inference.
- `docs/adr/README.md` index row; `docs/adr/backlog.md` row P-12 = ADR-167, proposed.
- No code. Q-02-T32 builds the flags and the refusal only after acceptance.

## What changed
- As planned. The ADR records engineering shapes only. It gives no legal advice and holds no consent text. The consent text is counsel's and is database content. It writes no example identifiers.
- Not accepted, by instruction: acceptance needs both founders and counsel.

## Not done (needs the humans)
- Acceptance by notanaskhan and ayushkbhatia.
- Counsel's naming of the model-inference recipient (OQ-1), through F-09-T38/T47, recorded in the ADR.
- Due **Fri Jan 22, 2027**. Q-02-T32 (S7) waits for it.

## Progress log
- 2026-10-23: `validate_docs` passes (frontmatter, index row and status agree).
