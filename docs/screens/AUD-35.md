# AUD-35 · Component auditors · Harlow & Pike

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/group/components?ca=<id>` |
| Template and host frame | T9 queue · detail inside the T2 cockpit (queue 300 + detail 735) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-35 Component auditors - Harlow and Pike/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | A-09 · SPEC-658 · A-09-T04 (contract), A-09-T03 (stubs), A-09-T07 (scenarios), screen rows per A-09 §9 |
| Persona | Omar Haddad; Margaret Okonkwo on d |
| Flags | `group_audit` capability; `assurance.group_audit` |
| Priority | P0 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

7 artboards, all built.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Draft | §5 needs input (no group risk assessment for Distribution); Send instructions… disabled with its reason; "Drafted by Omar Haddad via Agent · 4:12 PM" | Mon Sep 14, 2026, 4:30 PM CT | E1 | D · **C locked** | planned · `aud35.a` |
| b | Sent | Awaiting acknowledgement; component grant issued to Renee Pruett | Mon Sep 21, 2026, 2:20 PM CT | E1 | D · C report-only | planned · `aud35.b` |
| c | Acknowledged | "Sep 23 · Renee Pruett 9:46 AM"; Questions thread | Wed Sep 23, 2026, 11:20 AM CT | E1 | D · **C locked** | planned · `aud35.c` |
| d | Late deliverable | Interim memo due Nov 30 → "Late · 1 day"; drafted follow-up → Send; toast "Follow-up sent to Renee Pruett · 8:52 AM" | Tue Dec 1, 2026, 8:30 AM CT | E1 | D · C report-only (toast masked) | planned · `aud35.d` |
| e | Received | Review… → Reviewed | Wed Dec 2, 2026 | E1 | D · C report-only | planned · `aud35.e` |
| f | Make reference on | Amber banner; EP decides via SHL-11 (default No) | Mon Sep 14, 2026, 4:30 PM CT | E1 variant | D · C report-only | planned · `aud35.f` |
| g | Flag off | Capability off state | Mon Sep 14, 2026, 4:30 PM CT | E1 | D · C report-only | planned · `aud35.g` |
| loading | — | skeleton per the template's loading grammar | — | — | D | planned |
| error | — | the read failed: designed error with Retry | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3); portal scopes isolated (INV-4) | — | — | — | planned |
| capability off | — | `group_audit` off (entitlement ∧ rollout flags): the designed flag-off state, never blank | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/AUD-35/scenarios.ts` (A-09 §5.4, A-09-T07), derived from the Harlow & Pike slice's footing figures, never typed by hand. Copy keys are `aud35.<state>.<element>`.

## API

Every state reads this endpoint set (A-09 §4.3; stubs in A-09-T03):

- `GET|POST /v1/audits/{wid}/component-auditors` · `GET|PATCH /v1/component-auditors/{id}` (`component_auditor.read` / `.manage`)
- `POST …/{id}/instructions/draft` · `GET|PATCH /v1/component-instructions/{id}` (`component_instructions.draft` / `.edit`)
- `POST /v1/component-instructions/{id}/send` (`component_instructions.send`; 10-s Undo)
- `POST …/{id}/make-reference` (`component_auditor.manage`)
- `GET|POST …/{id}/deliverables` · `POST /v1/component-deliverables/{id}/request|review|return` · `POST …/follow-ups` → `POST /v1/follow-ups/{id}/send`
- `GET /v1/component-auditors/{id}/portal-preview` (`component_auditor.read`)

Matrix actions from `permission-matrix/{ledger,adjustments,assurance,portal,connections}.yaml` (A-09-T02): every finalize, approve, post, decide, send and review is a named person's; agent, support and portal principals deny every firm write.

## Links

| From | To | Status |
|---|---|---|
| Preview as Pruett & Lang | POR-23 (read-only projection) | live |
| Make reference | SHL-11 | live |
| Today Late item | HOME-05 | planned (I-02) |
| tooltip or toast inside kits/AUD35 Component Auditors | AUD-34 | designed (handoff link graph) |

## Notes

Status words fixed: instructions Draft · Sent · Acknowledged; deliverables Expected · Received · Reviewed · Late (derived). No signature envelope. The follow-up's author is the person who sends it.

## Deviations

- DV-6 the letter is a deterministic merge of the firm's DB template; provenance "Drafted by Omar Haddad via Agent".
- DV-7 the follow-up is the POR-20 template merge on real tenants.
- DV-10 questions show on AUD-35's thread; INB-04 lists them with N-03.
- DV-12 (A-09-T02) the send and acknowledge actions read `component_instructions.send` / `.acknowledge`.

## Acceptance

SPEC-658's criteria for this screen; each becomes a test named "AUD-35 acceptance: <criterion>".
