---
id: TASK-099
title: Design foundation, step 4c — the client portal is white-labelled (the firm's name, never the product's) and the client home lists what needs them first, with the rest folded away
spec: SPEC-031
acceptance_criteria: [AC-6]
risk_zone: green
status: done
branch: task-099-client-portal
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Scope
**In**
- `shell/PortalBrand.tsx`: the portal header shows the client's firm (a monogram tile and name), or "Client portal" before a firm is known. Used on the client home, the client engagement and invitation acceptance; the plan's white-label rule says "Abacus" never reaches clients.
- `ClientHome.tsx`:
  - Each firm is a pane of engagement rows (name, period, "your part" pill).
  - Rows that block fieldwork come first in brick, then the rest by items left in ochre.
  - Engagements with nothing left fold under "Show n with nothing left for you".
  - The headings use the plan's sizes.

## Definition of done
- [x] Web tests pass (353); the portal checked on the dev stack as the client contact.
- [x] `make check-fast` passes.
