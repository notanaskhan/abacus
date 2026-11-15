# AUD-14 · Confirmations manager

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/confirmations` (`?c=C3&ov=new-confirmation`; `?ov=accept-reconciliation`) |
| Template and host frame | T1 IndexList under the audit bar (no rail); O2 480 drawer, O3 500 sheet |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-14 Confirmations manager/` |
| Epic and tasks | A-08 · SPEC-657 · A-08-T01 (contract), A-08-T05/T06 (stubs), A-08-T08 (content), screen rows per A-08 §9 |
| Persona | Simone Baptiste (Audit Senior); Hannah Leclerc for Accept reconciliation |
| Flags | `audits.confirmations`; respondent links under the `confirmation_links` control |
| Priority | P1 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

Every artboard is **built** (A-08 §2.1). Fixture-only parts are named in their row. 5 artboards.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Default · exception open | C3 Alpine Ridge: $286,900.00 per books vs $282,600.00; CM-6281 ($4,300.00) reconciles; Unreconciled $0.00; Below CT $7,750; drawer open | Tue Oct 6, 2026, 11:20 AM CT | E0 | D · **C locked** | planned · `granite-peak.confirmations` |
| b | Authorization pending | C1 "Authorization requested · Waiting on Luis Ferrante (SIG-02)"; C2–C4 Draft; tiles Draft 3 · Authorization requested 1 | Wed Sep 16, 2026 | E0 variant | D · C report-only | planned · `granite-peak.confirmations` |
| c | Respondents viewed | C2–C4 Sent, "Viewed Sep 19"; C1 recorded network send (DV-6) | Sat Sep 19, 2026 | E0 variant | D · C report-only | planned · `granite-peak.confirmations` |
| d | Exception cleared | Hannah accepted the reconciliation; C3 Closed; Exception tile 0 | Tue Oct 6, 2026, 11:20 AM CT | E0 variant | D · C report-only | planned · `granite-peak.confirmations` |
| e | Address not verified | New confirmation with a client-only address: red helper, Send disabled (409 `address_not_verified`) | Tue Oct 6, 2026, 11:20 AM CT | E0 variant | D · **C locked** | planned · `granite-peak.confirmations` |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); a client principal always 404 on confirmation routes | — | — | — | planned |
| flag off | — | C-20 "not turned on" state for the screen's flag; never a blank pane | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/AUD-14/scenarios.ts` (A-08 §5.4), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `aud14.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (A-08 §4.3; stubs in A-08-T05 / T06):

- `GET /v1/work-items/{wid}/confirmations` · `…/summary` (`confirmation.read`; never client)
- `POST /v1/work-items/{wid}/confirmations` (`confirmation.create`)
- `POST /v1/confirmations/{cid}/address-verifications` (`confirmation.verify_address`)
- `POST /v1/work-items/{wid}/confirmations/authorization` (`confirmation.request_authorization`)
- `POST /v1/confirmations/{cid}/send` · `…/second-request` · `…/revoke-link` (`confirmation.send`; 409 `address_not_verified`, `authorization_missing`)
- `POST …/record-response` · `…/reconciliation` · `…/accept-reconciliation` · `…/alternative-procedures` · `…/exception` · `…/close`
- `GET …/respondent-preview` · `GET /v1/work-items/{wid}/confirmations/export.xlsx`

Matrix actions from `permission-matrix/{sampling,workpapers,assurance,identity}.yaml` (A-08-T03): every adopt, accept, approve, decide, send and close is a person's (`agent: deny`); every client principal is denied.

## Links

| From | To | Status |
|---|---|---|
| Authorization | SIG-02 / POR-06 envelope | live |
| Preview | POR-17 preview | live |
| Exception… | SHL-15 → AUD-15 / AUD-16 | live |
| Attachment chip | SHL-08 | live |
| Opens SHL-09 · where this balance comes from | SHL-09 | designed (handoff link graph) |

## Notes

Statuses Draft · Authorization requested · Sent · Responded · Exception · Alternative procedures · Closed are in `status-vocabulary.yaml` (DF-05, DF-31). Tiles sum to 4 and are toggle buttons announcing their count. "Accept reconciliation" renders for the manager role only. The footer lock note is always visible: "Requests and responses travel only between Brightwater Hale and the respondent. Granite Peak sees only the authorization it signs." Accounts show `••7712` only. Name collision with independence `MyConfirmations.tsx` avoided (A-08 §5.2).

## Deviations

- DV-6 C1's "Bank confirmation network" is a recorded channel (sent and received logged by a person, the response uploaded as evidence).
- DV-8 the firm's reconciliation cites Granite Peak's credit memo CM-6281; the respondent's typed CM-0628 is kept as submitted (DF-34).
- DV-11 real respondent links stay behind the `confirmation_links` control (pen tests deferred, DEC-1389).

## Acceptance

SPEC-657's criteria for this screen; each becomes a test named "AUD-14 acceptance: <criterion>".
