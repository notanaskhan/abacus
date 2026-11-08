---
id: TASK-6401
title: A-04-T26 remainder - Link EBP-03… opens the link picker and links the risk
spec: SPEC-000  # row
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T26
branch: s26p-a04-t26-link
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-08
updated: 2026-11-08
---

# TASK-6401 · A-04-T26: Link EBP-03… opens the picker and links the risk

TASK-3221 drew "Link EBP-03…" with an `onLink` prop that no screen passed, so the button did nothing.

AC-1: On the Linkage tab, "Link EBP-03…" opens a menu of responses with the risk's suggested ones first, each marked Suggested.

AC-2: Choosing one posts `risk.link` for that risk and target, and the matrix and register read again; a failure says so in words.

AC-3: The control appears only for a person whose register allows `risk.link`.

## Decisions (DEC-2951)
- The label ends with "…", so it opens a picker (the kit's rule), not a one-click link. The suggested targets come first; the server accepts a suggested link into a live one.

## Known limits
None.

## Progress log
- 2026-11-08: built on main a801fff01; tests written, run at the S26 partials end pass.
