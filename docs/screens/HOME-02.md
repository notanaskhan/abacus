# HOME-02 · My approvals & review queue

| Field | Value |
|---|---|
| Route and params | `/home/approvals` · `?gate=<uuid>` selects a row (opaque UUIDs only, ADR-031) · `&done=1` shows Show done. Overlays (P-04, P-04-T52): `?ov=decision:<id>`, `?ov=signoff:<target>`, `?ov=approve:<ref>`. Artboards: `/components/screens/HOME-02?st=a…g` |
| Template and host frame | T9 `QueueDetailLayout`, preset `close-review` (F-05-T55): review pane 790 = queue 310 + 0.5 hair + detail 480 · evidence pane 576 · `Wave 2 - Home & Records.dc.html#home02` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/HOME-02 My approvals and review queue/` (README.md, spec.md; no revision on file) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | I-01 · contract I-01-T01 (this file); C13 counts T04; list facts, snooze, reassign T07; fixtures T15; queue T16 (creates `home.approvals`); detail T17; evidence T18; bulk, reassign, snooze T19; wire-up T21; proof and flips T22; breadth T23; final proof T25 |
| Manifest status | planned (`routes/manifest/home.ts`); `fixture` with T15/T16; `live` per firm from the Tue Nov 2 and Nov 9, 2027 flips (T22) |

Code to come (I-01 §5.1): `src/screens/HOME-02/{index.tsx, scenarios.ts, copy.ts, HOME-02.test.tsx}`, `src/domain/home/{gateClasses.ts, mutations.ts, messages.ts}`, `src/fixtures/handlers/human-gates.ts`. Legacy `src/screens/Review.tsx` stays until the per-firm flips and is retired by T23 with its SPEC-004 assertions mapped.

## States

HOME-02 has 7 artboards (a–g) and 4 catalogue states (Show done, snoozed, reassigned, overdue) that the spec names as interactions but draws no frame for. Clock: Mon Sep 14, 2026, 9:31 AM CT (I-01 §5.3); b is 9:36 AM, the decision time it draws. Tiers are I-01 §5.4's.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | daniel-reyes | Mon Sep 14, 2026, 9:31 AM CT | E0 | Bands Decisions 3 · Sign-offs 6 · Approvals & sends 2 (= 11); `?gate=` the §754 decision card (open, reserved to Daniel as engagement partner); evidence: the Basis workpaper with the Pell Street II match | C report; **C lock at S27** (fixture data) | built: queue T16, detail T17 (DEC-1750), evidence T18 (DEC-1751) |
| b | daniel-reyes | 9:36 AM | E0 + §754 decided | Daniel decided option 2 with a rationale at 9:36: the card is `decided`, the gate `done` (in Show done); badge 10, Decisions 2; Basis loses its block ("Ready to sign · difference explained"); row 10 still waits on Capital Accounts | C report only | built: T17 (decided card held in the detail; `?gate=` found among done rows) |
| c | daniel-reyes | 9:31 AM | E0 | Sign-off request 7 (Capital Accounts) selected; `blocked {reason_code, facts: off 6,200}` from the open M-2 proposal awaiting Samuel Ito | C report; **C lock at S27** | built: detail T17, evidence T18 |
| d | daniel-reyes | 9:31 AM | E0 | Sign-off request 4 (Summary & preparer memo) selected, not blocked, no open review notes; evidence: the TXP-01 memo paper | C report; **C lock at S27** | built: detail T17, evidence T18 |
| e | daniel-reyes | 9:31 AM | E0 | Select mode: rows 4, 5, 6, 9 `bulk_eligible` and checked; 7 and 8 blocked → disabled "Blocked"; bottom bar "4 selected" | C report; **C lock at S27** | to build: T15, T19 |
| f | daniel-reyes | 9:31 AM | E0 | Counts total 0 → queue EmptyState with "Show done"; detail empty; evidence header "Evidence" | C report; **C lock at S27** | to build: T16 |
| g | samuel-ito | 9:31 AM | E0 | Samuel's gates: 0 `decision`, 4 `sign_off_request`, 2 `proposal` (6); the Feld passive-classification proposal selected (see Deviations DV-6) | C report; **C lock at S27** (queue column masked) | built: detail T17 |
| show-done (catalogue) | daniel-reyes | 9:36 AM | E0 + §754 decided | `GET /v1/human-gates?state=done` (last 30 days, newest first, OQ-7): the §754 row with "Decided · Daniel Reyes · 9:36 AM" | — (scenario test only) | to build: T15, T16 |
| snoozed (catalogue) | daniel-reyes | 9:31 AM | E0 + snooze | Daniel snoozes the CP2000 position "Tomorrow 9 AM" (Sep 15, 9:00 AM; on or before its Sep 23 due date): it leaves the queue and every count (10 = 2 + 6 + 2) and lists under `state=snoozed` | — (scenario test only) | to build: T15, T19 |
| reassigned (catalogue) | daniel-reyes | 9:31 AM | E0 + reassignment | Daniel reassigns the CP2000 position (a reserved decision card) to an eligible partner from `reassign-candidates`: it leaves his queue and counts (10 = 2 + 6 + 2); the new assignee receives `gate_reassigned` | — (scenario test only) | to build: T15, T19 |
| overdue (catalogue) | daniel-reyes | Wed Sep 16, 2026, 9:31 AM CT (scenario clock) | E0, clock advanced | The Ridgeline gates due Sep 15 still open: due words "overdue" in red ink, counted in `overdue`; "Snooze until…" absent (overdue gates cannot be snoozed, OQ-4) | — (scenario test only) | to build: T15, T16 |

Non-artboard states:

| State | Data condition | Rendering |
|---|---|---|
| Loading | the list or counts call pending | T9 skeleton rows, `aria-busy` |
| Reserved to someone else | the viewer is not the reserved person | radios disabled; footer "Reserved to the engagement partner. The agent cannot decide." (AC7.2) |
| Stale | the gate was decided elsewhere (SHL-04, AUD-03) or its card changed | dropped on the next poll or mutation invalidation; a stale write answers the owner's 409 (`recommendation_changed`, `stale_version`) and the detail reloads (AC6.5, AC7.1) |
| Unknown subkind | no specific renderer | generic detail: the resolver's KV facts and "Open" to its `subject_route`; never hidden (AC7.8) |
| Walled | the gate's client is walled from the viewer | not listed or counted; its id answers 404 (INV-3) |
| Flag off | `home.approvals` off | HOME-01 rows open their host gates; `/home/approvals` shows F-05's flag-off ViewState |
| Not allowed | client, agent, system or support principal | 403 on `/v1/human-gates*`; `human_gate.snooze` and `human_gate.reassign` deny agent, system and support (INV-1) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/human-gates/counts?office_id=` | `{total, bands {decisions, sign_offs, agent_outputs, approvals_sends}, overdue, snoozed}` — the same call as HOME-01's badge | `human_gate.read` | — |
| read | `GET /v1/human-gates?assignee=me&state=open\|done\|snoozed&band=&office_id=&sort=deadline&cursor=&limit=` | P-36 envelope; rows `id, kind, subkind, band, title, context, due_on, risk, blocked {reason_code, facts}, bulk_eligible, reserved_role, proposed_by {run_id, initiator_user_id, at}, citations_count, subject_route, overlay, glyph, allowed_actions, version` | `human_gate.read` (P-04; filters T07) | `done` covers 30 days |
| write | `POST /v1/human-gates/{id}/snooze {until}` · `POST …/unsnooze` | — | `human_gate.snooze` (assignee only) | 422 `snooze_past_due`, `snooze_in_past`; 409 `gate_not_open`, `gate_overdue` |
| read / write | `GET /v1/human-gates/{id}/reassign-candidates` · `POST …/reassign {to_user_id, seen_version}` | candidates: people holding the reserved role on that engagement, not walled, not blocked by G2 (DEC-39) | `human_gate.reassign` | control renders only with `human_gate.reassign` in `allowed_actions`; 409 `not_reassignable`, `stale_version`; 422 `candidate_not_eligible` |
| read / write | Owners' endpoints (P-04): `GET /v1/decision-cards/{id}`, `POST …/decide {option_key, factors[], rationale, seen_version}`, `POST …/analysis-requests`; `GET /v1/sign-offs/eligibility`, `POST /v1/sign-offs:bulk` (through SHL-12 f); `GET /v1/proposals/{ref}`; C4 viewer routes | `docs/contracts/review-grammar.md` | owners' | Decide only for the reserved person; 422 `rationale_required`; HOME-02 never records a sign-off, approval or send itself |

Every gate write waits for the server (never optimistic, DEC-24), toasts, and invalidates the counts and list keys.

## Status
- Band titles from the DF-25 class (Band rule below); gate state words "Open · Done · Snoozed until … · Voided" and the due-risk words arrive with I-01-T02's status-vocabulary rows.
- Decision card: "Decided · Daniel Reyes · 9:36 AM" (green-tint pill; template `Decided · {person} · {time}`).
- Tally pills: green "4 of 5" (Reconciled), amber "off 28,595" (a) → "explained 28,595" (b); row pills "Reconciled ✓" (green-tint), "off 28,595" (amber) → "explained" (b); c "off 6,200".
- Glyphs: "?" chip (decision), 13 px ring with grey ✓ (sign-off), amber triangle (blocked), check disc (final approval), send glyph (send), agent monogram (agent output). Blocked rows carry words ("Blocked · off 6,200"), never colour alone.

### Band rule (DF-25)
`decision` → **Decisions** · `sign_off_request` → **Sign-offs** · `proposal` → **Agent outputs** · `send`, `final_approval`, `export`, `release` (and `evidence_review`, OQ-2) → **Approvals & sends**. Countersignatures are `send`. Band order is fixed: Decisions · Sign-offs · Agent outputs · Approvals & sends. Empty bands other than Decisions and Sign-offs are hidden; with nothing open at all, f's EmptyState replaces the bands. Within a band rows sort by `due_on`, then the owner's `sort_hint`, then id (AC6.2). One badge rule: only the Approvals segment carries a count, and it is `counts.total`.

### Home segmented control (DF-39)
Five options on HOME-01 and HOME-02 alike: "My work" · "Approvals" + count · "Deadlines" · "Capacity" · "Insights" (Insights behind the `insights` entitlement). The HOME-02 artboards draw four (no Insights); aligned to five (DV-2). Planned segments (Deadlines → HOME-03/T-08, Capacity → HOME-04/I-04, Insights → INS-01/I-03) are hidden in production and shown in fixtures for parity. The control is a `tablist` of links; the badge is announced "Approvals, 11 waiting".

## Copy
Copy keys live in `screens/HOME-02/copy.ts`; band, glyph and summary words in `domain/home/messages.ts`. Verbatim from spec.md; strings marked (artboard) are drawn on the artboard but not in spec.md.

| Key | String |
|---|---|
| `subbar.title` | "Approvals" + "Daniel Reyes" (template `{person}`) |
| `subbar.sort` | "Sort │ Deadline ⇕" (only option, OQ-5) |
| `subbar.select` | "Select" |
| `pane.title` | "Waiting on you" |
| `pane.showDone` | "Show done" |
| `bands` | "Decisions" · "Sign-offs" · "Agent outputs" · "Approvals & sends" (title over count, e.g. "Decisions" / "3") |
| `row.subline` | template `{due} · {kind}`: "Sep 15 · 1 day · Reserved to partner", "Sep 23 · 9 days · Reserved to partner", "Form 706 Nov 2 · 49 days · Gate G1", "Sep 15 · Reviewed · SI", "Sep 15 · Blocked · off 6,200", "Sep 15 · Blocked on decision 1", "Sep 15 · after 6 sign-offs · BH-TAX-02", "Sep 15 · Ready · Synced Sep 11"; b: "Sep 15 · Ready to sign · difference explained"; g: "Sep 15 · Agent output", "Oct 15 · Agent output" (artboard) |
| `rows` (a) | "§754 election — Ridgeline Property Partners, LP" · "CP2000 position — Marcus & Dana Whitley, TY2024" · "Acceptance — Estate of Walter Thornbury" · "Ridgeline 1065 · Summary & preparer memo" · "Ridgeline 1065 · Financials (TB → TTB)" · "Ridgeline 1065 · Schedule K" · "Ridgeline 1065 · Capital Accounts" · "Ridgeline 1065 · Basis" · "Ridgeline 1065 · States & PTET" · "Final approval & export — Ridgeline 2025 Form 1065" · "Send Form 8879-PE — Harborview Dental Properties, LP" |
| `decision.title` | "Recommend a §754 election for the 6/30/2025 transfer?" |
| `decision.kv` | "Reserved to" / "Daniel Reyes · Engagement partner" · "Work item" / "2025 Form 1065 · Ridgeline Property Partners, LP" → · "Due" / "Sep 15, 2026 · with the return (Reg. §1.754-1(b))" · "Proposed by" / "Accrued Agent · run by Olivia Brandt · Sep 11" |
| `decision.why` | "Why This Was Surfaced" + the paragraph "Pell Street Ventures LLC sold 5 of its 35 points … including step-downs." (spec.md, verbatim; rendered through AgentText) |
| `decision.options` | "Recommend electing now" · "File without the election; decide in the cost segregation & §754 analysis" + tag "Agent recommendation" · "Recommend against the election", each with its spec.md detail line |
| `decision.evidence` | "Evidence" · "Membership interest transfer agreement — Pell Street Ventures LLC to Pell Street II LLC · 2 citations" · "Basis at 12/31/2025 (TXP-08) · 1 citation" · "Ridgeline LPA · Article 9 Transfers · 1 citation" (template `{source} · {n} citation(s)`) |
| `decision.rationale` | "Rationale" · placeholder "Why you decided this (kept with the decision)" |
| `decision.footer` | "✓ Decide" · "Request more analysis…" · "Reassign…" · "Snooze until…" · "Reserved to the engagement partner. The agent cannot decide." |
| `decision.decided` | "Decided · Daniel Reyes · 9:36 AM" · "Waiting on client: §754 decision sent to Owen Calder via the portal (POR-04)." |
| `decision.toast` | "Decision recorded" |
| `evidence.basis` | header "Basis at 12/31/2025 · Ridgeline" · "Open in workpaper ↗" · segmented "Basis" · "Transfer agreement" · tally "OUTSIDE BASIS" · "INSIDE SHARE" · "RECONCILED" · columns "Partner" · "Tax capital" · "§752 share" · "Outside basis" · "Inside share" · "Difference" · "TOTAL" |
| `evidence.calc` | "Purchase price paid by Pell Street II LLC 360,000" · "− Capital transferred (5/35 × 2,319,835) 331,405" · "= §743(b) placeholder 28,595" · "Pell Street II outside basis 913,820 = 360,000 + 31,250 income + 155 tax-exempt − 30,000 distributions + 552,415 liabilities." |
| `signoff.kv` (c, d) | "Workpaper" / "Capital Accounts · Version 3" · "Level" / "Partner (L4)" · "Prepared" / "Prepared · OB" · "Reviewed" / "Reviewed · SI"; d: "Workpaper" / "Summary & preparer memo" |
| `signoff.title` (artboard) | "Capital Accounts — Ridgeline 2025 Form 1065" · "Summary & preparer memo — Ridgeline 2025 Form 1065" |
| `signoff.blocked` | "Cannot sign off: M-2 ties · off 6,200. The fix (add tax-exempt interest 6,200 as other increase) is proposed by Accrued Agent and awaits Samuel Ito." |
| `signoff.footer` | "Sign off…" · "Open proposal" (c) · "Signs off at Partner (L4)." (artboard, d/e) |
| `evidence.capital` (c, artboard) | "Capital Accounts · Ridgeline" · "ROLLFORWARD" 6,860,000 · "SCHEDULE L" 6,866,200 · "off 6,200" · "Capital rollforward · 2025" / "Amount" · "Beginning capital" · "Contributions" · "Income (Schedule K, boxes 2 and 5)" · "Distributions (box 19A)" · "Ending capital per rollforward" · "Schedule L, partners' capital" · "Difference" · "Proposed by Accrued Agent · awaits Samuel Ito" · "Add tax-exempt interest 6,200 (Schedule K, box 18A) as an other increase on Schedule M-2. The rollforward then ties to Schedule L at 6,866,200." |
| `evidence.memo` (d) | "Preparer memo · Ridgeline" · "Open memo ↗" (artboard) · "Ridgeline Property Partners, LP — 2025 Form 1065 preparer memo" · "Prepared by Olivia Brandt · Reviewed by Samuel Ito" (artboard); body paragraphs transcribed from the d/e artboard by T15 |
| `bulk.bar` | "4 selected" · "Sign off 4 as Partner" (template `{n} selected` · `Sign off {n} as {level}`) · disabled tooltip "Blocked" |
| `snooze.options` | "Today 2 PM" · "Tomorrow 9 AM" · "Pick date" |
| `empty` | "Nothing waiting on you." · "Show done"; evidence header "Evidence" (artboard) |
| `agentOutput` (g) | "Reasoning" · "Prior-year treatment and the current K-1 support passive activity classification. The proposed change updates the return while preserving the existing treatment elsewhere." · "2025 Schedule K-1 · 2 citations" · "✓ Approve adjustments"; (artboard) title "Classify the Ridgeline K-1 as passive on the Feld return?" · "Work item" / "2025 Form 1040 · Jonah & Claire Feld" · "Proposed by" / "Accrued Agent · run by Kevin Osei" · "Level" / "Manager (L3)" · "Source" · "Reject…" · "The agent cannot approve its own work." · rows "Capital Accounts fix — Ridgeline 2025 Form 1065", "Passive activity classification — Jonah & Claire Feld" |
| `evidence.k1` (g, artboard) | "2025 Schedule K-1 · Feld" · "Open source ↗" · "Item" / "Current" / "Proposed" · "Ridgeline Property Partners, LP · Schedule E, Part II" Nonpassive → Passive · "Form 8582 · rental real estate activities" Not included → Included · "TY2024 treatment (prior year)" Passive · Passive · "Cited on the 2025 Schedule K-1" · "Part II, item G · Limited partner" · "Box 2 · Net rental real estate income (loss)" |

Basis table rows (seed, verbatim): Ridgeline GP LLC 93,124 · 220,966 · 314,090 · 314,090 · Reconciled ✓; Meera Shah 2,529,356 · 4,198,354 · 6,727,710 · 6,727,710 · Reconciled ✓; Pell Street Ventures LLC 1,996,860 · 3,314,490 · 5,311,350 · 5,311,350 · Reconciled ✓; Pell Street II LLC 332,810 · 552,415 · 913,820 · 885,225 · off 28,595 (source match #ECD9F0, ring #BF99C8, ink #9253A2 as tokens); Jonah Feld 1,914,050 · 2,762,075 · 4,676,125 · 4,676,125 · Reconciled ✓; TOTAL 6,866,200 · 11,048,300 · 17,943,095 · 17,914,500 · 28,595.

Undesigned (marked in `copy.ts`): the Show done list rows (reuse "Decided · {person} · {time}" and "Signed off · {person} · {time}"), the snoozed line ("Snoozed until …", status word), the reassign picker and its toast, the overdue due words, the selection announcement.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Segmented "My work" | HOME-01 | per manifest (I-01) |
| Segmented "Deadlines" / "Capacity" / "Insights" | HOME-03 / HOME-04 / INS-01 | planned → T-08 / I-04 / I-03; hidden in production |
| Decision row (inline card) | SHL-11 (inline in the detail) | planned → P-04-T50/T52 |
| "Work item" → | TAX-02 (return overview) | planned (tax hosts T-04/T-05) |
| Evidence rows | SHL-08 in the evidence pane, cited region in purple | planned → P-03-T14 |
| "Open in workpaper ↗" | TXP-08 | planned (later wave) |
| Item 2 (CP2000) | NOT-02 analysis in the evidence pane | planned (N-04) |
| Item 3 (Acceptance) | CLI-07 | per manifest (P-07) |
| "Sign off…" (d) / bulk bar (e) | SHL-12 at L4 / SHL-12 f with `POST /v1/sign-offs:bulk` | planned → P-04-T48/T49 |
| "Open proposal" (c) / "✓ Approve adjustments" (g) | SHL-10 | planned → P-04-T41 |
| Item 10 | SHL-12 final approval, then TAX-09 | planned |
| Item 11 | SIG-01 "To send" | planned (N-02) |
| Memo (d) | TXP-01 | planned |
| b footer | POR-04 (client decision request) | fixture only until T-05 |

Inbound: HOME-01 (rows, segmented, "Open queue →"), SHL-04 ("Open approvals queue →"), SHL-02, T21, TPL-11, TAX-14 ("filtered to standards exceptions"), HOME-03, HOME-04.

## Acceptance
- HOME-02 acceptance: geometry matches `close-review.png`: a 790 pane holding a 310 queue and a 480 detail, a 49 px band "Decisions / 3" in the style of "Low / 11", flag-style rows with ink-3 sub-lines, and a 576 evidence pane.
- HOME-02 acceptance: footer buttons are stacked full width: a dark primary over a white secondary.
- HOME-02 acceptance: "Why This Was Surfaced" uses the 15 px olive check disc; a source row reads "n citations".
- HOME-02 acceptance: the basis table foots in every column and the totals equal 01 §9.8 (6,866,200 · 11,048,300 · 17,943,095 · 17,914,500 · 28,595).
- HOME-02 acceptance: 360,000 − 331,405 = 28,595 and 5/35 × 2,319,835 = 331,405 (2,100,000 + 218,750 + 1,085 = 2,319,835); Pell Street II inside share = 332,810 + 552,415 = 885,225; 913,820 − 885,225 = 28,595.
- HOME-02 acceptance: group counts 3 + 6 + 2 = 11 equal the Count badge on the Approvals segment and on HOME-01.
- HOME-02 acceptance: reserved items show the role; no agent-owned approve button exists anywhere.
- I-01 AC7.1 / OQ-3: ✓ Decide stays disabled until a rationale exists, whichever option is chosen (DV-1).
- I-01 AC8.1: checkboxes only on `bulk_eligible` rows; rows 7 and 8 disabled with "Blocked".
- I-01 AC8.3: a snoozed gate leaves the queue and every count until `until`; overdue gates cannot be snoozed.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Bands (a) | 3 + 6 + 2 = 11 = HOME-01's badge | T15; count equality T25 |
| Bands (b) | 2 + 6 + 2 = 10 after the §754 decision | T15 |
| Bulk (e) | 4 selected = rows 4, 5, 6, 9 = 6 sign-offs − 2 blocked | T15 |
| Samuel (g) | 6 = 0 + 4 + 2 = HOME-01c | T15 |
| Basis columns | 93,124 + 2,529,356 + 1,996,860 + 332,810 + 1,914,050 = 6,866,200 · 220,966 + 4,198,354 + 3,314,490 + 552,415 + 2,762,075 = 11,048,300 · 314,090 + 6,727,710 + 5,311,350 + 913,820 + 4,676,125 = 17,943,095 · 314,090 + 6,727,710 + 5,311,350 + 885,225 + 4,676,125 = 17,914,500 | T15 footing test |
| Basis rows | outside = tax capital + §752 share for the four reconciled rows (e.g. 93,124 + 220,966 = 314,090); Pell Street II inside 332,810 + 552,415 = 885,225; 913,820 − 885,225 = 28,595; Reconciled 4 of 5 | T15 |
| Basis difference | 17,943,095 − 17,914,500 = 28,595 | T15 |
| Calc card | 2,100,000 + 218,750 + 1,085 = 2,319,835; 5/35 × 2,319,835 = 331,405; 360,000 − 331,405 = 28,595; 360,000 + 31,250 + 155 − 30,000 + 552,415 = 913,820 | T15 |
| Capital rollforward (c) | 5,960,000 + 250,000 + 1,250,000 − 600,000 = 6,860,000; 6,866,200 − 6,860,000 = 6,200 | T15 |
| Cross-ties with HOME-01 | income 1,250,000 = box 2 1,231,600 + box 5 18,400; off 6,200 = 18A 6,200; distributions 600,000 = 19A | T15 with T05 |

## AVOID
Each becomes a test in `HOME-02.test.tsx` ("HOME-02 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, red backgrounds on rows, priority stars, any button that lets the Accrued Agent approve or decide, card-per-item queues.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | **Rationale is always required** before ✓ Decide, not only when the chosen option differs from the agent's recommendation (spec.md); the placeholder "Why you decided this (kept with the decision)" is unchanged | P-04, DEC-36 / ADR-160, glossary "rationale required", C3's 422 `rationale_required`; OQ-3 | DEC-403 |
| DV-2 | The subbar segmented has five options (spec and artboards draw four) | DF-39 | DEC-403 |
| DV-3 | Planned segments, the TXP-08/NOT-02/POR-04 targets and other planned links are hidden in production; fixtures show them | Chapter 04 §2.1 rule 4 | DEC-403 |
| DV-4 | Tax content (basis table TXP-08, memo TXP-01, POR-04 decision request, K-1 evidence) is fixture-only until T-05 (S35–S44); the live analog in I-01's window is the audit half (materiality cards, planning sign-offs, screening proposals) | Owning epics; R5 | I-01 §2.1 |
| DV-5 | Show done, snoozed, reassigned and overdue are composed from the existing kits (no artboard): Show done covers 30 days, newest first (OQ-7); no snooze past `due_on`, overdue gates cannot be snoozed, no expiry notification (OQ-4); reassign only for decision cards and subkinds with a hook (OQ-8) | Undesigned states (R10) | DEC-403 |
| DV-6 | g follows the data, not the frame's queue: Samuel's badge is 6 and the queue shows Decisions 0 · Sign-offs 4 · Agent outputs 2 (the artboard draws "Approvals 2" and only the Agent outputs band). Detail and evidence are as drawn | One count source: HOME-01c reads "0 decisions · 4 sign-offs · 2 agent outputs" (AC1.2) | DEC-403 |
| DV-7 | "Reassign…" renders only with `human_gate.reassign` in `allowed_actions`; candidates are the reserved role's holders on that engagement, not "partners" in general | AC8.2, DEC-39 | I-01 §3 F8 |
| DV-8 | Bulk *decide* and bulk approve of agent outputs never exist; bulk is sign-off only, through SHL-12 f | Decisions are individual | I-01 §2.2 |

N's sign-off of these deviations at Contract Monday (Mon Mar 8, 2027) is a solo-edition formality: decided and recorded as DEC-403 (`docs/plan/AMENDMENT-solo.md` items 1, 2, 7).

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, c, d, e, f | C (report; lock at S27 on fixture data) | not run (unbuilt) | `data-contrast="reference"` |
| g | C (report; lock at S27) | not run | queue column and segmented badge masked (DV-6); detail and evidence compared |
| b | C (report only) | not run | — |
| show-done, snoozed, reassigned, overdue | — | — | catalogue states: scenario tests, no artboard |
| host | D (blocking through T9) | — | review pane 790 = 310 + 0.5 hair + 480, evidence 576, band 49, rows 50–72, KV rows 44, stacked footer buttons 36, bulk bar 52 |

Accessibility (I-01 §5.5): the queue is a `listbox` with `aria-activedescendant`; J/K and arrows move, Enter opens the primary action, Escape returns from the detail, selection changes are announced politely; bulk checkboxes have row labels and disabled rows expose "Blocked" through `aria-describedby`; axe AA 0 serious or critical.

## Open gaps
- **g's count.** The g frame's "Approvals 2" and single band contradict HOME-01c's 6 for the same person and clock; decided for data (DV-6).
- **Per-surface titles.** HOME-01 and HOME-02 title the same gate differently ("Partner sign-off — Ridgeline 2025 Form 1065 · Summary & preparer memo" vs "Ridgeline 1065 · Summary & preparer memo"; "Approve M-2 fix — …" vs "Capital Accounts fix — Ridgeline 2025 Form 1065"). Decided: the gate-class registry composes each surface's title from the resolver's facts, so both stay verbatim.
- **OQ-2 (`evidence_review`).** SPEC-004 review assignments and uploads awaiting review are gates SHL-04 counts but fit none of DF-25's seven classes. Decided with the plan's recommendation: add `evidence_review`, banded under Approvals & sends; `docs/contracts/review-grammar.md` gains the kind additively with I-01-T04 (DEC-403).
- **README vs canvas behaviour.** README's section text says "a different option from the agent's needs a rationale"; DV-1 overrides it.
- **b's clock.** README renders every frame at 9:31 AM, but b draws "Decided · Daniel Reyes · 9:36 AM"; the scenario clock is 9:36 AM (I-01 §5.3).
- **Catalogue scenarios.** The snoozed and reassigned gate (CP2000 position), the reassign target and the overdue clock (Wed Sep 16, 9:31 AM) are composed here, not drawn; T15 may pick another seeded gate if the owner's rules refuse these.
- **Memo body.** d's memo paragraphs are drawn on the artboard only; T15 transcribes them verbatim from the screenshot.
- **C3 vs handoff wording.** `docs/contracts/review-grammar.md` illustrates the counts as "3 decisions, 6 sign-offs, 2 exports"; DF-25 puts exports under Approvals & sends, so the UI reads "2 approvals & sends".
