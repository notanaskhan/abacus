# Signing kit (T16) and the tax practice board (TPL-01): hand-off to N-02 and T-02

F-06-T13. The T16 `SigningCeremony` kit and the TPL-01 board on T1 `IndexList` are locked for
their consumers: N-02 (POR-06, SIG-01 chips, ENG-04 signing) and T-02 (TAX-01). This page is the
written mapping from each consumer's payload to the kit's props. The kit draws only what it is
given: every count, status, date and evidence row is the server's, and nothing is summed or
derived in the browser.

Code: `packages/ui/src/signing/` (parts, outcomes, field layer, `types.ts`),
`packages/ui/src/templates/signing-ceremony/`, `packages/ui/src/templates/index-list.tsx`.
Specimens: `/components` section `t16-signing-ceremony` (T16b, T16c), `/components/screens/TPL-16?st=a|b|d|e|f|g|pending`,
`/components/screens/TPL-01?st=a…e`. Parity: `docs/design/parity-manifest.json` keys `t16-signing-ceremony.*`,
`tpl-16*`, `tpl-01*`; Tier D in `apps/web/e2e/visual/tier-d-signing.spec.ts`; specimen walks in
`apps/web/e2e/specimens/f06-signing.spec.ts` and `f06-tax-index.spec.ts`.

## Part 1 · C7 `PortalEnvelopeView` → `EnvelopeVM` (N-02, POR-06)

The mapping is code, not prose: `apps/web/src/domain/signing/envelope-vm.ts` (`toEnvelopeVM`),
pinned on the provider side by `backend/tests/contracts/c7_n02/test_f06_consumer.py` (F-06-T09).
POR-06's L3 container calls it; the kit never reads a DTO.

| `EnvelopeVM` field | From C7 | Notes |
|---|---|---|
| `id`, `title` | `row.id`, `row.title` | "Form 8879 · TY2025 · Dev & Mira Kapoor" |
| `status` | `row.status` | `envelope` vocabulary; the header pill |
| `signedCount`, `signerCount` | `signers_signed`, `signers_total` | "1 of 2 signed" is the server's pair, never counted from `signers` |
| `documents[]` | `documents[]` sorted by `order` | `name` ← `title`; `pages` ← `page_count` pages at Letter (612 × 792 pt), `src` the same-origin page route `/v1/portal/envelopes/{id}/documents/{doc}/pages/{n}` |
| `documents[].signerChips` | `extra.chips[doc.id]` | N-02's envelope read; the same `SignerChips` SIG-01 and TPL-01b draw |
| `signers[0]` (the viewer) | `extra.viewer` + `row.my_status` | `isViewer: true`; status from the server |
| `signers[1…]` | `extra.others` | read-only; their fields never take focus (Story 1.2) |
| `fields[]` | `my_fields[]` (kind signature, pin or date) + `extra.otherFields` | `signerId` of `my_fields` is the viewer's; other kinds are dropped |
| `steps` | `extra.steps` | Verify identity · Review · Sign · Done, one `current` |
| `authorizing` | `extra.authorizing` | firm or template text, never model text |
| `signingSession` | `signing_session` (`url`, `presentation`, `expires_at`) | provider mode; only an `https:` URL is hosted, in a sandboxed, titled iframe (`PROVIDER_SANDBOX`) or as one redirect call to action |
| `evidence` | `extra.evidence` | six rows on completion: Signed, Method, Identity, IP address, Login, Documents |
| `outcome` | `outcomeOf(view)` | `verification_failed` when `paper_form_follows` or `my_status = verification_failed`; `declined`, `expired`, `voided` from `outcome` and `row.status` |

What C7 v1 does not carry (other signers, steps' sub-lines, the authorizing text, evidence) comes in
`extra` from N-02's other reads. A missing field is an additive C7 change, never a kit workaround.

### Callbacks

| Prop | When | N-02 wires it to |
|---|---|---|
| `onSignField(fieldId)` | a viewer's field, "Sign here" or "Adopt signature & sign…" | the provider step (provider mode) |
| `onContinueToVerify()` | the redirect presentation's call to action | navigate to `signing_session.url` |
| `onDecline({reason, note})` | "Decline" in the dialog, once, after a reason | `POST /v1/portal/envelopes/{id}/decline` with `DECLINE_CODES[reason]` |
| `onOpenDecline()` | "Decline…" when the container owns the dialog | — (the kit's own dialog when `onDecline` and `copy` are passed) |
| `onDownload()` | "Download" in the envelope header | signed PDFs and the certificate (N-02) |
| `onBack()` | "All documents to sign" | POR-02 or the Sign tab list |
| `onRetry()` | the error view's "Try again" | refetch |
| `onOpenSignatures(envelopeId)` | a signer chip on SIG-01 or TPL-01b | SIG-01 |

### States the container sets

| State | Props |
|---|---|
| Loading, error | `view: "loading" \| "error"` |
| Restricted (viewer is not a signer) | an `envelope.signers` with no `isViewer` |
| Provider view (TPL-16a in production) | `signingSession` set and the `verify` step `current` |
| Back from the provider, not yet signed | `providerReturned: true` until the refetched viewer status is `signed`: the kit shows "Checking your signature", never Completed |
| Completed (TPL-16d) | `status: "completed"` and `evidence` from the server |
| Verification failed (TPL-16e, DF-11) | `outcome: "verification_failed"`: the paper-form card, no control |
| Phone (TPL-16g) | `layout: "phone"`, `stickyBarHeight: 64` (POR-06 uses 64; TPL-19 frame 9 draws 72) |

Every string the kit cannot know comes through `copy` (`SigningOutcomeCopy`); the portal never
renders "Accrued" or a provider's name.

## Part 2 · T-02's tax list payload → TPL-01 on `IndexList` (TAX-01)

TAX-01 is TPL-01 with live data. `GET /v1/tax-returns` (T-02-T01 stub, C-tax v1) answers the T1
list envelope, which `IndexList` takes as is:

| `ListEnvelope` | From the tax list | Kit use |
|---|---|---|
| `items` | `items[]` (one row per return) | rows, through the column plan below |
| `next_cursor` | `next_cursor` | the next page; the kit never pages locally |
| `total` | `total` | "Showing {items} of {total} open" |
| `counts` | `counts` (per `return` status, over every filter but the tile) | the eight tiles; "Filed · Accepted" reads `filed + accepted` as the server sends them in one `filed_accepted` key, never summed in the browser |
| `facets` | `facets.office`, `facets.form`, `facets.partner`, `facets.preparer` | the filter chips' options |

Tiles in order (DEC-801): `prepared`, `in_review`, `action_required` ("Issues"),
`approved` ("Ready"), `gathering`, `preparing`, `awaiting_signature`, `filed_accepted`. Labels come
from the status registry (`home_and_tax_tiles` context); selecting a tile sets `tile` and the
request's `status` filter.

| Column | Row field | Cell |
|---|---|---|
| Return | `tax_year`, `form` | "2025 Form 1065" |
| Client | `client.name` | link to CLI-02 |
| Office | `office` | text |
| Prep / Rev | `preparer.initials`, `reviewer.initials` | "OB / SI" |
| Status | `status`, `review_level` | `StatusPill object="return"` ("In review · Partner") |
| Issues | `open_issues` | red-tint count, "—" for null |
| Engine sync | `sync.code`, `sync.date` | `SyncChip` (white e1 chip, olive disc; never green-tint) |
| Due | `due_date`, `extended`, `due_rule` | DueCell: the date, an "Ext." micro tag when extended, an O1 popover with the rule string (C21 rules tables, K-02) |
| Days | `due_date` | days from `useNow()` (the demo clock): ≤ 7 red-ink, ≤ 30 amber-ink, else ink-2 |
| Signature | `envelope.signers[]` | `SignerChips`; shown with the Awaiting signature tile; a chip calls `onOpenSignatures(envelopeId)` |

`allowed_actions` gates "Bulk actions" items (Assign preparer…, Extend…, Run firm standards…: each
a callback, the kit writes nothing). A walled row never reaches the kit, so no total or count is
derived in the browser (INV-3). Field names in the right-hand column are T-02's planned DTO names
(T-02 §5); where T-02-T01's stub names them differently, the stub wins and this table follows.

## Parity

| Board | Tier | Masks | Lock |
|---|---|---|---|
| T16b, T16c | B frame; A strips (envelope header 46, first 64 document row, steps 300); D geometry | `[data-signing='page']` (the page is the provider's render in provider mode; the specimens draw a blank page) | F-06-T13, from a measured `parity.json` |
| TPL-16a | B frame (chrome) | the well (provider's view) and the verify step row (native KBA progress) | F-06-T13 |
| TPL-16b, d, f | B frame; A strips on b | `[data-signing='page']` | F-06-T13 |
| TPL-16e | B frame | none | F-06-T13 |
| TPL-16c | C (deviation: native Adopt dialog, DF-12) | — | never |
| TPL-16g | B phone; A sticky bar 64 | `[data-signing='page']` | F-06-T13 |
| TPL-01a–e | B frame; D window | none | F-06-T13 |

DECISIONS.md "Signing and tax-index lock (F-06-T13)" records the measured diffs and what locked.
