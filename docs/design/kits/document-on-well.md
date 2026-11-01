# Document-on-well kit (T10) and the TPL-10 specimen: hand-off to ENG-04, NOT-03, AUD-21, POR-20

F-06-T23 (from F-06-T14 to T17). The T10 `DocumentOnWell` kit, `DocBlocks` and the structure pane
are locked for their consumers: N-02's ENG-04 engagement letter, N-04's NOT-03 notice response,
A-07's AUD-21 representation letter, R-02's POR-20 email templates and P-11's generated documents.
This page is the written mapping from a consumer's payload to the kit's props; a fresh session
builds NOT-03 from it alone. The kit composes no text and writes nothing: the document's status
is the server's (DF-31, `generated_document`), and Approve, Edit, Regenerate, the clause toggles
and the variables are callbacks.

Code: `packages/ui/src/templates/document-on-well/` (`DocumentOnWell.tsx`, `DocBlocks.tsx`,
`StructurePane.tsx`, `types.ts`). Specimens: `/components/screens/TPL-10?st=…`. Parity:
`docs/design/parity-manifest.json` keys `t10*`, `tpl-10*`; acceptance tests in
`f06t17-independent.test.tsx`.

## Frame

Under the toolbar 46, the record subbar 42 and the tabsbar 50: the 470 structure pane beside the
896 paper pane; the paper pane's header (46) centres the title with Edit, Regenerate… and the
approval HumanAction at its right; the #F8F8F6 well (padding 14) centres the 600 paper card. A
draft stamps the DRAFT watermark (hidden from assistive technology).

## `DocumentVM` ← the consumer's document read

| `DocumentVM` field | From | Notes |
|---|---|---|
| `status` | C11 `generated_document.status` | drafting · draft · approved · locked; never derived |
| `variant` | the consumer | `paper` (firm-internal), `letter`, `email` (reach clients) |
| `modelTextToClients` | omit | ADR P-25 off: a letter or email drops agent prose and the agent Drafting state |
| `structure` | `{kind: "kv", sheets}` (a memo's facts) or `{kind: "clauses", clauses, variables}` (a letter) | clause `required` cannot be turned off; `reason` is the server's |
| `title` | the document's title | the paper pane's centred title |
| `approve` | `{actor, object, disabledReason}` | `actor` is the signed-in person; an agent or system actor renders nothing (INV-1); `disabledReason` when `allowed_actions` lacks `document.approve` |
| children | `DocBlocks` over the rendered blocks | `DocSegment` with `Provenance` agent · human · template; agent segments only through `AgentText` |

## Callbacks

| Prop | When | Consumer wires it to |
|---|---|---|
| `onApprove()` | the approval HumanAction | SHL-12 (P-04); the kit never signs |
| `onEdit()` | Edit | the consumer's editor |
| `onRegenerate()` | Regenerate… | P-11's render (a new version) |
| `onToggleSection(id, on)` | a clause toggle | the consumer's PATCH; the server re-renders |
| `onVariable(id, value)` | a variable's ValueRow | the consumer's PATCH |
| `onOpenLink(linkId)` | a KV value that links | the record's route |

## Consumers

- **N-02 ENG-04** (engagement letter): `variant: "letter"`, clauses and variables, Approve as the
  EP; the envelope send is SIG-02 (the kit has no Send).
- **N-04 NOT-03** (notice response): `variant: "letter"`, structure `kv` (notice facts) beside the
  response; template- and clause-only until ADR P-25 is accepted (S55).
- **A-07 AUD-21** (representation letter): `variant: "letter"`; the signed copy is a document
  version, never a field on the kit.
- **R-02 POR-20** (email templates): `variant: "email"` inside `EmailFrame`; never "Accrued".
- **A-04 / A-05 / A-06**: workpaper memos that are documents use `variant: "paper"`.
