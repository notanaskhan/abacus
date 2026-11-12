# AUD-29 · Engagement activity log (cockpit)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/activity?segment=&type=&since=&until=` (filters in the URL; the search text never is: request body only, AC-34) |
| Template and host frame | T2 RecordCockpit (audit bar 59 · rail 330 · pane header 46), rail row Overview › Activity, `Timeline` (when-column 76, mark 20) · `Wave 3 - Audit Fieldwork.dc.html#aud29` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-29 Engagement activity log - cockpit/` (README.md, spec.md) |
| Epic and tasks | P-05 · bundle and 501 stubs T02 · AC suite T08 · backend T11 · seed T12 · screen T14 · journeys T15 · SPEC-650 |
| Manifest status | fixture (P-05-T14: `screens/AUD-29`; live in the T2 cockpit with the A-01 host) |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a All | hannah-leclerc | Mon Sep 14, 2026 2:30 PM | Northwind timeline: 23 events since Aug 19, newest first, day separators TODAY, SEP 11, SEP 10, SEP 8, SEP 1, AUGUST | live (T14; golden 23 = 12 + 11 + 0) |
| b via Agent | hannah-leclerc | 2:30 PM | Segment via Agent 11; rows end " · via Agent" with the atom glyph | live (T14) |
| c Human | hannah-leclerc | 2:30 PM | Segment Human 12 | live (T14) |
| d Policy | hannah-leclerc | 2:30 PM | Policy 0: "No policy acceptances." / "Policy acceptance is off for Brightwater Hale (Firm settings › AI policy)." | live (T14) |
| e Search · Materiality | hannah-leclerc | 11:20 AM | Three rows: 11:12 "Materiality decided by Margaret Okonkwo", 9:27 "Materiality proposed · Marcus Delaney via Agent", 11:20 "Run resumed · Marcus Delaney via Agent" (matched in its detail) | live (T14) |
| f Row hover | hannah-leclerc | 2:30 PM | Hover shows "Open"; the click routes by kind | live (T14) |
| loading, error, not allowed, off | as above | — | walled user: the not-allowed state; `audit_trail.engagement_activity` off: designed flag-off state, routes answer the P-36 flag-off error; 501 before T11 | live |

Parity tier: Tier C report-only (P1) on a–f; Tier D blocking on audit bar 59, rail 330, pane header
46, Timeline when-column 76 and mark 20.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–f | C | reported (gallery `AUD-29`, P-05-T15) | P1, report-only |
| host | D | — | audit bar 59, rail 330, pane header 46, Timeline when-column 76 and mark 20 (blocking) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `POST /v1/engagements/{engagement_id}/audit-events/query` | body `{segment, categories[], since, until, q, cursor, limit ≤ 100}`; list envelope with `counts` {all, human, via_agent, policy}; codes and facts, never labels | `audit_event.read_engagement` | engagement team, specialist, EQR, reviewer; practice leader and quality partner in scope; firm admin and client roles refused |
| read | `POST /v1/engagements/{engagement_id}/audit-events/export` | streamed CSV of the same filter, masked, formula cells neutralised | `export.create` (`mfa_recent: required`) | engagement partner, manager; others never see Download |

Both routes are stubs from P-05-T02 (501 behind `audit_trail.engagement_activity`) until P-05-T11.

## Status
None of its own; rows show each object's own status word through its C2 object.

## Copy
"Activity", "Search activity", "‹n› events", "All ‹n› · Human ‹n› · via Agent ‹n› · Policy ‹n›",
"No policy acceptances.", "Policy acceptance is off for ‹firm› (Firm settings › AI policy).",
"Open", " · via Agent". Titles are composed by the SPA's copy module from the action code and facts.

## Deviations
- OQ-4: collaboration events stay out of the default list except "To-do deleted" and "Comment
  redacted", under "To-dos & comments".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Run, draft, resume rows | WB-09 | live (P-09-T10) |
| Sign-off rows | AUD-06 | handoff link (A-04) |
| Materiality rows | AUD-07 | handoff link (A-03) |
| Document rows | AUD-03 | handoff link (A-01) |
| Risk rows | AUD-08 | handoff link (A-03) |
| Gate rows | ENG-02, CLI-07 | handoff link |
| To-do rows | SHL-17 | handoff link (P-05) |
| Client chip | CLI-02 | handoff link |
| Methodology chip | KNW-03 | handoff link (K-01) |
| Team rows | ENG-05 | handoff link |
| General Audit Planning rows | AUD-04 | handoff link (A-03) |
| Internal Control rows | AUD-09 | handoff link (A-04) |
| Service Organizations & SOC 1 rows | AUD-10 | handoff link (A-04) |
| Sample Selection rows | AUD-11 | handoff link (A-03) |
| Testing rows | AUD-12 | handoff link (A-04) |
| Fraud Brainstorming rows | AUD-05 | handoff link (A-04) |

## Acceptance
- Every artboard letter above carries live with its owning task.
- No approval, decision, sign-off, acceptance, release or send appears with an agent actor (INV-1).
- No edit or delete affordance or endpoint for events.
