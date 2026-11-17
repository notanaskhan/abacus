# CLS-09 · Close plan editor — Copperleaf close plan v3

- **Epic / task:** C-01 · C-01-T36 (TASK-8419) · SPEC-655 AC-15 to AC-22
- **Template:** T6 (control bar · tally strip · full-width plan table)
- **Route:** `/close-plans/$clientId` behind `closes.engine` (the client's newest Monthly close
  engagement; a client without one is 404, INV-3)
- **Reads:** `GET /v1/clients/{id}/close-plan` (the newest version: rows, request templates,
  tally, `allowed_actions`), `GET …/close-plan/versions` (History), `GET /v1/close-templates`
  (no plan yet), `GET /v1/clients/{id}` (the header's client name)
- **Writes:** `POST …/close-plan/drafts` (Edit plan), `PATCH …/drafts/{v}/rows/{row}` (drawer
  pickers, If-Match), `POST …/rows/{row}:adopt` (a drafted row's tick), `POST …/drafts/{v}/publish`
  (Manager or Partner, with the confirm), `POST …/drafts/{v}/request-publish` (a Senior),
  `POST …/close-plan/draft-from-history` (the Close Planner, C-01-T30)
- **Persona · clock:** Priya Raman (CAS & Advisory Partner); Raj Malhotra (CAS Senior) on b ·
  Mon Sep 14, 2026, 9:24 AM CT
- **Handoff:** `CLS-09 Close plan editor - Copperleaf close plan v3/` (`README.md`, `spec.md`)

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a published | v3 published Jun 2 by Priya Raman; 23 procedures (Manager 8 + Senior 15), 8 requests, 21 accounts; Publish v4 disabled until edited | `a` |
| a2 row hover | the first row's label-over-value card | `a2` (`initial.hover`) |
| a3 row drawer | O2 480 titled with the account; pickers once the plan is a draft | `a3` (`initial.drawer`) |
| b draft · Raj | v4, Business Savings → Bank feed ("Changed"), "Draft v4 · 1 change", 7 / month, "Request publish…" only | `b` |
| b2 publish · Priya | v4 draft; the confirm "It applies from the September 2026 close; August stays on v3." | `b2` (`initial.publishOpen`) |
| c agent drafting | v1, every row drafted with an outlined tick until adopted; the drafting card 15 of 21; Publish disabled while any row is unadopted (AC-22) | `c` (`initial.drafting`) |
| d empty | 404 on the plan: "No close plan yet", the four templates, Draft from ledger history | `d` |
| e requests | the version's eight request templates with BD due days | `e` |
| f history | v3, v2 by Priya Raman; v1 "Close Planner via Raj Malhotra" | `f` |

## Links

| From | To | Status |
|---|---|---|
| ‹ Back | CLS-02 (history back) | built |
| Threshold cells → KNW-04 · BH AJE thresholds v2 | KNW-04 | tooltip-only in the handoff; not wired |
| Requests rows → CLS-03 preview | CLS-03 | not wired (C-01-T42) |

## Deviations and gaps

- **DV-a.** The AJE POLICY tally card and the "Template · Café with Square/Shopify" tag are not
  drawn: `PlanVersionOut` names neither the plan's AJE policy nor its template (contract gap,
  additive field for C-01-T42).
- **DV-b.** Template cards show the template name only: `CloseTemplateOut` has no description
  line (the artboard's "Card and online sales clearing, …" is template content).
- **DV-c.** The drafting card's progress comes from the scenario: the planner run is code-driven
  and inline (DEC-5413), so live mode has no partial progress to show; the drafted rows and their
  ticks are live.
- **DV-d.** The version stepper (⇕) and "+ Add procedure" are drawn without behaviour; the
  ENG-03 monthly-close step UI is not in this row's build (follow-up).
- **Lint.** The procedure word "Accrual" trips the product-name rule; one line-scoped disable with
  its reason (C-01 §3 F2).
