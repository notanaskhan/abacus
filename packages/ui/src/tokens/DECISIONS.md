# Token decisions (conflict log)

Every change to a design token adds a row here: what changed, why, and the decision or ADR behind it (ADR-155). Newest last.

| Date       | Token                        | Value                                                                               | Why                                                                       | Source          |
| ---------- | ---------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------- |
| 2026-10-20 | `--color-ink-2`              | rgba(43,31,23,.70)                                                                  | WCAG 2.2 AA for small text on every surface; the handoff's value fails    | DEC-11, ADR-155 |
| 2026-10-20 | `--color-ink-3`              | rgba(43,31,23,.66)                                                                  | Same; the handoff's .54 and the earlier .60 fail (4.08-4.28:1)            | DEC-11, DEC-115 |
| 2026-10-20 | `--color-match-ink`          | #7E4590                                                                             | AA match text; the handoff's #9253A2 fails on match tint                  | DEC-11          |
| 2026-10-20 | focus outline                | 2px solid rgba(43,31,23,.55), offset 2px                                            | An outline survives forced-colors; replaces the box-shadow ring           | DEC-11, ADR-155 |
| 2026-10-20 | `--color-*`, `--shadow-*`    | initial                                                                             | Only plan tokens compile; Tailwind's palette and default shadows are gone | ADR-155         |
| 2026-10-20 | casing and copy              | Title Case for nav, tab and button labels; sentence case for content; copy verbatim | Design-system details                                                     | DEC-15          |
| 2026-10-20 | `--radius-pill` for controls | pills                                                                               | TASK-093's 7px squares revert in F-05-T14                                 | DEC-109         |
| 2026-10-20 | body line height             | 1.45 kept for now                                                                   | The plan says 15.6px (1.2); it moves every screen, so F-05-T05 decides    | open, F-05-T05  |
