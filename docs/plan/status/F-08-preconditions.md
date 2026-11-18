# F-08 precondition check (F-08-T01, TASK-8616, DEC-5616; main 1ca51eec9, 2026-11-18)

F-08 §0 lists the decisions and ADRs that must be on `origin/main` before its kits build. Each row
names the F-08 tasks it gates; the S50 rows (T01, T02, T03, T05) need none of the open ones.

| P-ID / DEC | ADR on main | State | Gates (F-08 tasks) | Note |
|---|---|---|---|---|
| P-07 / DEC-36 review grammar | ADR-160 | accepted | T06, T07, T08 (sign-off locks, slots) | |
| P-35 / DEC-24, DEC-28 suggestions and Undo | ADR-161 | accepted | T07 (agent columns), T12 | |
| P-42 / DEC-29 comments on anchors | ADR-236 | accepted | T21, T23 (TPL-22d) | |
| P-28 / DEC-55 flags vs entitlements | ADR-148 | accepted | T10, T14 (flag-off, entitlement-off states) | |
| P-24 structured agent output | ADR-230 | accepted | T07 | |
| P-48 citation v2 (+ ADR-343) | ADR-166 | accepted | T07 (typed C4 locators) | |
| P-49 autonomy policy versions | ADR-186 | accepted | T11 ("Run agent on move" off by policy) | |
| P-15 / DEC-23 SSE plus presence | ADR-232 | **proposed** | T13 presence anchors (S52) | the S50 kits use no SSE; T13 waits for acceptance |
| P-59 / DEC-80 document model and editor | — | **not drafted** | T20 document editor, TPL-22 (S54–S55) | drafted before S54 or T20 slips (F-08 R-risk) |
| P-20 / DEC-95 add-in surface | — | proposed by plan (W-04 accepts by S68) | none in F-08 (the pane is `packages/ui` only) | DEC-95 decided |
| P-25 / DEC-79 model text to clients | — | not accepted | TPL-22f, TPL-24 client paths | client-share paths stay free of agent text |
| DEC-16 dependency batch (`@dnd-kit/*`, `@tiptap/*`) | dependency allowlist | decided; installs after Oct 20 | T09 (S52) | S50–S51 kits add no dependency |

Ten screen contracts: `docs/screens/{T18,T19,T20,T21,T22,TPL-20,TPL-21,TPL-22,TPL-23,TPL-24}.md`
(74 artboards = 41 template + 33 specimen), with persona, clock, parity tier B, AVOID and
deviations (spec time wins over a README rendered cell).
