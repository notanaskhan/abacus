---
id: SPEC-305
title: "Notifications drawer (SHL-04): tabs by kind, day groups, the engagement each concerns, and notifications for the decisions reserved to the engagement partner"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-005, ADR-018]
related_specs: [SPEC-013, SPEC-300, SPEC-301]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
The firm app's notifications become a 480-wide drawer (overlay O2) instead of a side panel. The partner is now told when a decision is reserved to them. The client portal keeps its panel.

## 2. Acceptance criteria
- **AC-1** New catalogue kinds, sent to the engagement partner only:
  - `materiality.proposed`, on every proposed version;
  - `risk.approval_requested`, on a version with a significant risk or rebuttal;
  - `finding.severity_proposed`.

  Each is emitted by fieldwork in the same unit of work, and each has fixed text.
- **AC-2** Tabs: All, Needs you, Mentions, and Client activity, each with an unread count; kinds map to tabs by code. An "Unread only" toggle.
- **AC-3** Notifications are grouped by day: Today, Yesterday, Earlier this week, Older. Each row shows its text, its engagement ("Client · engagement") and the time. "Load older" pages back by `before`.
- **AC-4** Opening a notification marks it read and goes to its page: Planning for materiality and risks, Findings for severity, Requests for reminders. "Mark all read" marks every notification read.
- **AC-5** Nothing is approved or decided from the drawer (ADR-005).

## 3. Out of scope
Inline document Accept and Return (needs the Undo-versus-immutability decision), notification settings, and the agent's run notifications.
