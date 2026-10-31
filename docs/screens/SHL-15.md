# SHL-15 · Issue composer & fix instructions

| Field | Value |
|---|---|
| Route and params | Overlay over any firm route, registered in `routes/firm/sheets.tsx` (behind `review.grammar_api`, DEC-1752): `?ov=issue:<issueId>` (fix instructions), `?ov=issue:new:<recordType>:<recordId>[:<engagementId>]` (new issue), `?ov=issue:bulk:<recordType>:<recordId>:<id>,<id>` (instructions for several). Builders `ov.SHL15`, `ov.SHL15New`, `ov.SHL15Bulk`. Artboards: `/components/screens/SHL-15?st=a…e` (`ap`, `app` for a′, a″; `agents_off`) |
| Template and host frame | O3 sheet (500, top 52) + the issue's T9 detail block · `Wave 0 - Shell.dc.html#shl15` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-15 Issue composer and fix instructions/` (README.md, spec.md) |
| Epic and tasks | P-04 · issues service P-04-T29/T31; fixtures P-04-T34; issue kit F-05-T55; sheet P-04-T54 (TASK-2702) |
| Manifest status | fixture (`routes/manifest/shl.ts`); live per firm as A-04, A-06 and T-04 register issue hosts |

Code: `src/domain/review/issues.ts`, `src/screens/SHL-15/{index.tsx, copy.ts, scenarios.ts, SHL-15.test.tsx}`, `src/fixtures/{scenarios/SHL-15.ts, seed/issues-shl15.ts}`.

## States

| Artboard | Viewer | Data condition | Rendering | Live? |
|---|---|---|---|---|
| a | kevin-osei | the 18A issue, 3rd of Feld's 4 open issues, assigned to Accrued Agent, with the agent's suggestion | issue card (Class, Priority, Assigned to, Linked chips; the file chip lit), "Suggested by Accrued Agent" + "Use suggestion", instructions, Apply to (This issue only · All 2 Missing information issues on this return), Cancel · Set Fix Instructions | needs a fix runner (P-10, T-04): fixture until then |
| agents_off | kevin-osei | the same, with no fix runner registered | the API's 409 `fix_runner_unavailable` shows the agents-off banner and disables Set Fix Instructions | live |
| a′ | — | the issue's fix run running | T9 detail: "In progress — agent fixing", run row "Adding 1,550 to Form 1040 line 2a · Running" | fixture (P-10) |
| a″ | — | the run succeeded with a proposal | "Proposed 2 changes for your approval", the values as ghosts (dashed match line on match fill), Accept → SHL-10 | fixture (P-10) |
| b | ana-cruz | new Waiting on client issue on EBP-04 F12:F15 | Issue (Title, Class segmented, Priority, Assignee, Client contact), Linked, Internal note, "Client wording — what Dana sees"; Cancel · Create issue · Create & send to client; "Sends as a request in Dana's portal (POR-04). Internal notes stay internal." | live |
| c | samuel-ito | new Review point from a field flag on Feld's return | prefilled chip "Ridgeline K-1 box 5 → Form 1040 line 2b", Assignee Kevin Osei, Create issue; "Feld Issues 4 → 5" from the open issues count | live |
| d | — | the issue's pinned explanation | the Explanation block: agent text and its three citation chips; no control | fixture (P-10) |
| e | — | two Missing information issues picked | "Instructions for 2 issues", both issues with checkboxes, one shared editor, "Applies to the 2 selected issues only", Set Fix Instructions for 2 | live (bulk records one instruction per issue) |

## API
| Read or write | Endpoint | Notes |
|---|---|---|
| read | `GET /v1/issues/{issue_id}`, `GET /v1/issues?record_type=&record_id=&status=open` | position "Issue n of m", class counts, the Issues count |
| read | `GET /v1/engagements/{id}/team`, `GET /v1/engagements/{id}/client-contacts` | assignees (Accrued Agent first), the client contact |
| write | `POST /v1/issues` | the person's draft; never the agent's |
| write | `POST /v1/issues/{id}/send-to-client` with `Idempotency-Key` | body is only `client_wording`, `contact_id`, `seen_version` (INV-4) |
| write | `POST /v1/issues/{id}/fix-instructions`, `POST /v1/issues/fix-instructions:bulk` | 409 `fix_runner_unavailable` → agents-off |
| read | `GET /v1/proposals/{ref}` | a″'s proposed values; Accept opens SHL-10 |

## Deviations
| ID | What differs from the handoff | Why | Decision |
|---|---|---|---|
| DV-1 | No "Propose changes for my approval" checkbox (a, e) | every fix ends in a proposal (DF-13) | DEC-53 |
| DV-2 | Instructions are plain text: no rich-text toolbar | the API stores `text`; formatting would not survive | DEC-1752 |
| DV-3 | Gated by `review.grammar_api`, not a new `review.issues` flag | the flag is not registered; it arrives with the issue hosts | DEC-1752 |
| DV-4 | "Mark as Resolved" and "Explain…" on the T9 detail are the hosts' (TAX-06, AUD-15) | they act on the host's selection | DEC-1752 |
