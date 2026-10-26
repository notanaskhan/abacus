---
id: TASK-1343
title: Live swap and legacy client page retirement (R-01-T18)
spec: SPEC-020
acceptance_criteria: [AC-1, AC-7, AC-8, AC-9]
risk_zone: green
status: in-review
epic: R-01
plan_key: R-01-T18
branch: s10c-fe
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"The legacy client page is gone before Tue Mar 16, 2027 and every moved test still passes under
its original AC name." `/documents` already serves POR-03 and POR-04 in the portal entry.

## Plan
- Delete `legacy/ClientEngagement.tsx`, `ClientGuidance.tsx`; `clientHubMessages.ts` moves to
  `domain/portal/clientHub.ts`; `sourceLabel` to `legacy/GuidanceDrafts.tsx`.
- Move spec020, spec031clienthub and spec042portal into `domain/portal/client-hub.test.tsx` under
  their AC names, over POR-03/POR-04 fixtures; the DecisionActions notice to
  `legacy/DecisionActions.test.tsx`.
- `/client/engagements/$id` (firm bundle's legacy tree) redirects to `/client` until P-08-T28.
- POR-03 contract updated. DEC-443.
- **Deferred:** `portal.documents_v2` retirement (backend + protected registry; DEC-443).
- Rollback: revert the commit.

## Progress log
- 2026-10-27: Frontend half built. Four legacy assertions have no designed home in POR-03/04 and
  are listed in DEC-443 rather than faked. The flag retirement is the open item.
