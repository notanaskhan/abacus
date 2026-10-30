---
id: TASK-2038
title: N-01-T23 Fixture to live swap for INB-01, INB-02 and FIL-01
spec: SPEC-380
acceptance_criteria: [AC-27]
risk_zone: green
status: in-review
epic: N-01
plan_key: N-01-T23
branch: s15c-n01-t23
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Fixture to live swap for INB-01, INB-02 and FIL-01 on staging; Log received documents O3 sheet live
(`?ov=log-intake`); polling per DEC-23 (inbox 10 s and triage 2 s while visible); live
AI-unavailable states; flags on for Brightwater Hale on staging.

## Built
- `apps/web/src/routes/firm/inbox.tsx`: `/inbox` behind `inbox.firm_intake` with `?thread`,
  `?ov=file&message` (INB-02) and `?ov=log-intake`; registered as the Inbox area's routes.
- `apps/web/src/domain/inbox/LogIntakeSheet.tsx` (+ `LOG_COPY`): the DV-1 sheet on existing kits;
  batch then raw files with their own keys; limits and refusals in the design's words.
- INB01: optional toolbar (bare inside the shell), File… item → INB-02, Log received documents…;
  `packages/ui` InboxLayout bare mode; TriageSheet polls every 2 s.
- Manifests: INB-01 `live` at `/inbox`, FIL-01 `live`; screen contracts updated.
- `inbox.firm_intake` and `files.browser` in the scenario's `FLAGS_ON` (staging and local seeds).
- DEC-1066; SPEC-380 AC-27; tests `apps/web/src/domain/inbox/LogIntakeSheet.test.tsx`,
  `packages/ui/src/templates/inbox-layout-bare.test.tsx` (run at the end review).

## Not done here
- The staging walk (Grace logs, files and ignores; the audit log names her): needs the batch merged
  and staging re-seeded; recorded when it runs.
- AI-unavailable classification states: the bundle's classification is empty until N-01-T17.

## Progress log
- 2026-10-30: route, sheet, polling, bare layout, flags, docs and tests built.
