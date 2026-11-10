# C10 · Deliverables and release registry with download audit

| Field | Value |
|---|---|
| Register row | C10 in `docs/contracts/README.md` |
| Version | v1 |
| Status | service live (R-02-T09, 2026-11-08; DEC-2805): `publish_deliverable`, `supersede_deliverable`, `withdraw_deliverable`, `deliverables_for_work_item`, `expected_deliverables`, `portal_deliverables` and FIL-01's `deliverables` folder provider. Every portal route still answers 501 until R-02-T14 turns on `portal.deliverables` |
| Provider epic | R-02 (SPEC-646) |
| Consumers | A-06 (FS drafts), A-07 (release pack at G8, governance letter PDFs), C-02 (packages), T-02, T-04, T-06, T-08 (client copy, filing letter), T-09 (memo), X-01 (SOC reports) |
| Freeze sprint | S29 (frozen once R-02-T08's suites are green) |
| Flags | `portal.deliverables`, `portal.governance_room` arrive with R-02-T14; until then 501. **Publishing is never flagged** |
| Code | `backend/src/abacus/modules/portal/deliverables_contract.py`, `backend/src/abacus/modules/reporting/deliverables.py` |
| Screens | `docs/screens/POR-09.md`, `docs/screens/POR-15.md` |

## 1. Purpose
Publish a deliverable once, to the right audiences, and see when each person opened it. A provider
calls C10 inside its own unit of work; the client reads through the portal routes below.

## 2. Service API (`reporting.api`, no route)
| Call | Rule |
|---|---|
| `publish_deliverable(tx, spec) -> PublishedDeliverable` | One `deliverables` row per `(source_module, source_ref)`, one insert-only version per evidence version, audiences as listed; the same source version again is a no-op with the same ids and `created=False` (AC-17) |
| `supersede_deliverable(tx, deliverable_id, spec)` | The new version; `superseded` recorded on the old; the portal shows the latest with prior versions under Earlier versions (AC-19) |
| `withdraw_deliverable(tx, version_id, reason, actor_user_id, note)` | `withdrawn` with a reason (`wrong_file`, `reissued`, `other`); the client reads "Replaced by ‹firm› · ‹date›" |
| `deliverables_for_work_item(tenant, work_item_id)` | AUD-24's dock and CLS-08: delivery state per audience contact (AC-20) |
| `expected_deliverables(tenant, work_item_id)` | POR-09's Coming next from C1's client-visible milestones |

Errors: `draft_without_watermark` (422) when `is_draft` and the generated document has no DRAFT
watermark (AC-18). `restricted_use` limits a version to the listed audiences.

```python
from abacus.modules.reporting.api import DeliverableAudience, DeliverableSpec, publish_deliverable

published = await publish_deliverable(
    tx,
    DeliverableSpec(
        client_id=client_id,
        kind="fs_draft",
        title="Financial statements and supplemental schedules",
        source_module="reporting",
        source_ref=f"statement_version:{version_id}",
        evidence_version_id=evidence_version_id,
        render_hash=render_hash,
        page_count=14,
        audiences=[DeliverableAudience("work_item", work_item_id)],
        published_by_user_id=user_id,
        is_draft=True,
        page_comments=True,
        approval_kind="fs_draft",
    ),
)
```

## 3. Who may call it
Matrix: `docs/architecture/permission-matrix/portal.yaml`. Firm roles, agents, system and support
have no cell on any route. Every read is `scope_only`; out of scope or outside an audience is 404.

| Operation | Method and path | Matrix action | Lands with |
|---|---|---|---|
| POR-09 rail | `GET /v1/portal/deliverables?scope_id=&section=k1s` | `deliverable.read` | T09 |
| Meta and versions | `GET /v1/portal/deliverables/{id}` | `deliverable.read` | T09 |
| One version | `GET …/{id}/versions/{v}` | `deliverable.read` | T09 |
| Page image | `GET …/{id}/versions/{v}/pages/{n}` (PNG, watermarked when draft) | `deliverable.read` | T07, T09 |
| Download | `GET …/{id}/versions/{v}/download` (302, 60 seconds) | `deliverable.download` | T07, T09 |
| Management approval | `POST …/{id}/versions/{v}/approve` + `Idempotency-Key` | `statement.client_approve` | T09 |
| Page comments | `GET·POST …/{id}/versions/{v}/comments` | `deliverable.comment` | T22 |
| Rooms | `GET /v1/portal/governance/rooms` | `tcwg.read` | T12 |
| Letters of a room | `GET …/rooms/{room_id}/communications` | `tcwg.read` | T12 |
| Inquiries, reports | `GET …/rooms/{room_id}/inquiries`, `…/reports` | `tcwg.read` | T12 |
| Letter | `GET …/communications/{id}`, `…/{id}/pdf` | `tcwg.read` | T12 |
| Acknowledge | `POST …/communications/{id}/acknowledge` + `Idempotency-Key` | `tcwg.acknowledge` | T12 |
| Ask the auditor | `GET·POST …/communications/{id}/questions` | `tcwg.ask` | T22 |

## 4. Rules consumers rely on
- **No model text and no pack-rule field** (AC-7): no materiality, threshold, policy name, review
  note, sign-off, agent, confidence or internal status in any DTO.
- **Client strings are hostile** (AC-34): restricted, sealed, never HTML, never in an audit row.
- **A draft byte is never unwatermarked** (AC-22, AC-38). Finals and drafts come from P-11.
- **Audit:** `deliverable.published`, `.superseded`, `.withdrawn`, `.downloaded`, `.commented`. Page
  views write `access_events` only. Outbox: `deliverable.published`, `.superseded`, `.withdrawn`,
  identifiers only.

## 5. Change log
| Version | Date | Change |
|---|---|---|
| v1 | 2026-11-06 | Stub (R-02-T02, DEC-2402) |

## 9. Read-through slots (R-02-T09)
POR-09's rail shows rows other modules own. Those modules import `reporting`, so they register:
- `register_k1_rows(provider)`: T-02's released K-1s for the person (`tax.k1_portal.deliverable_k1_rows`,
  registered by `tax.api`). Only the person's own released packages; never a draft, another
  partner's K-1 or the partnership return (INV-4).
- `register_envelope_rows(provider)`: C7 envelopes on a work item ("Representation letter · In
  Sign"). Registered by A-07-T24's representation letter service once its sends go through C7.
- `register_expected_deliverables(provider)`: C1's client-visible milestones for Coming next. C1
  has no client-visible milestone yet, so Coming next is empty until one registers.

FIL-01's Deliverables folder (`folder:<work item>:deliverables`) lists the evidence versions of
the work item's live (published, not withdrawn) deliverable versions through
`evidence.api.register_folder_provider("deliverables", ...)`. Files keeps its own `visible()`
filter, so a walled viewer sees nothing.

## 10. POR-09's "In Sign" rows (R-02-T09 close; DEC-2824)
C7 registers `register_envelope_rows` from `signatures.api`. For each work item a client person's grant reaches, the rail lists that person's own envelopes:
- out for signature (`sent`, `viewed`, `partially_signed`) reads `in_sign`;
- one they have signed reads `signed`.

The row's `deliverable_id` is the envelope's id. Its kind is `governance_letter` for a governance-letter envelope, otherwise `other`. It has no version or page count. A firm user, and a person who is no contact, see none.

