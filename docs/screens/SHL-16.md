# SHL-16 · Checkpoint diff drawer

| Field | Value |
|---|---|
| Route and params | Overlay `?ov=checkpoints:<target_type>:<target_id>` over any firm route, registered in `routes/firm/sheets.tsx` (behind `review.checkpoints`). No route of its own. Artboards: `/components/screens/SHL-16?st=a…f` |
| Template and host frame | O2 drawer 480 · `Wave 0 - Shell.dc.html#shl16` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-16 Checkpoint diff drawer/` (README.md, spec.md) |
| Epic and tasks | P-04 · services P-04-T32; fixtures P-04-T34; drawer P-04-T43 (TASK-2227); independent AC tests P-04-T44 |
| Manifest status | fixture (`routes/manifest/shl.ts`) until the staging walk |

Code: `src/domain/review/checkpoints.ts`, `src/screens/SHL-16/{index.tsx, copy.ts, scenarios.ts, SHL-16.test.tsx}`, `src/fixtures/scenarios/SHL-16.ts`.

## States

| Artboard | Viewer | Clock | Data condition | Status |
|---|---|---|---|---|
| a | samuel-ito | E0 | `SHL16.a` + Checkpoint 6 detail: proposed by the agent, steps, diff, tie | fixture (T43) |
| b | samuel-ito | E0 | `SHL16.b`: 6 approved and Current | fixture (T43) |
| c | samuel-ito | E0 | Checkpoint 3 selected, diff vs Current, restore dialog → Checkpoint 7 | fixture (T43) |
| d | samuel-ito | E0 | `SHL16.d`: Checkpoint 5 named "Before K-1 treatment", starred, name field open | fixture (T43) |
| e | samuel-ito | E0 | `SHL16.e`: 6 rejected, "Samuel Ito · reason: Wait for final K-1" | fixture (T43) |
| f | samuel-ito | E0 | `SHL16.f`: no checkpoints; "Save checkpoint…" | fixture (T43) |

## API
| Read or write | Endpoint | Matrix action |
|---|---|---|
| read | `GET /v1/checkpoints?target_type&target_id&filter=agent\|named\|all` | `checkpoint.read` |
| read | `GET /v1/checkpoints/{id}?compare=current\|previous` | `checkpoint.read` |
| write | `POST …/approve {seen_hash}`, `POST …/reject {seen_hash, reason}` | `checkpoint.approve`, `checkpoint.reject` (agent deny) |
| write | `PATCH /v1/checkpoints/{id} {name?, starred?}` | `checkpoint.rename` |
| write | `POST …/restore {seen_hash}`: always a new checkpoint | `checkpoint.restore` |
| write | `POST /v1/checkpoints {target_type, target_id, name?}` | `checkpoint.create` |

## Open
- Diff rows lighting their fields in the underlay need a typed locator per row (INV-2); the detail carries `field_key` only. As SHL-10.
- The Assistant segment opens TAX-08 (planned): drawn disabled where planned screens are.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b | C (locked) | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | P-04 lock; axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| c, d, e, f | C | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | report-only (the import variant has no artboard); axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| host | D | not run | O2 drawer 480 (`e2e/visual/tier-d-review.spec.ts`) |

Gate: chapter 04 §9.3 keeps Tier C report-only, so the locks are listed and reported, not blocking (DEC-1970). Keyboard: Escape closes the topmost layer and focus returns to the opener.
