# AUD-25 · Assembly & archive

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/archive` · `?tab=` and `?dock=` in the URL; sheets and dialogs in local state |
| Template and host frame | T2 with Agent dock (rail 330 · canvas 696 · dock 330) · `Wave 2 - Audit Completion.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-25 Assembly and archive/` (README.md, spec.md; revision.md wins where present) |
| Epic and tasks | A-07 · stubs T05 · migration T09 · guard T13/T14 · checklist T31 · lock and seal T37 · additions and verify T42 · screen T39 · SPEC-644 |
| Manifest status | planned in the route manifest (final, A-07-T53, S36): built and live inside the AUD-02 cockpit, with no route of its own (DEC-195, DEC-3414) |

## States
Clock is the demo clock (DEC-27): CDT (UTC−5) until Sun Nov 1, 2026, CST (UTC−6) after. Snapshots
E0–E7 are the Northwind PY2025 completion timeline of A-07-T11's scenario.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | marcus-delaney | Thu Oct 22, 2026, 9:30 AM CDT | E4 | Assembling: "Archive in 47 days"; 8 of 9; Request lock… disabled; R2 "Archive and roll forward…" disabled with its tooltip | live (T31) |
| b | hannah-leclerc | Thu Dec 3, 2026, 4:12 PM CST | E5 | Ready to lock: 9 of 9; "Lock archive…"; R2 button enabled | live (T31) |
| b2 | hannah-leclerc | 4:12 PM CST | interact | Lock archive… O3: read-only and sealed text, "Assembly is complete", R2 row "Then roll forward to PY2026 (ENG-13)"; step-up | live (T37) |
| c | hannah-leclerc | Thu Dec 3, 2026, 4:18 PM CST | E6 | Locked · G9: seal 7c41…a9e2; checklist read-only; R2 "Roll forward…"; dock narration on what roll-forward carries (16,861,000, 24 requests, 2 triggers) | live (T37) |
| d | margaret-okonkwo | Fri Jan 15, 2027 CST | E7 | Post-lock addition: PI-02 memo added by HL, approved by MO, reason "AU-C 585 omitted procedure"; "+ Add after lock…" | live (T42) |
| e | hannah-leclerc | Thu Dec 3, 2026 CST | illustrative | Deadline risk: red-tint "Archive in 5 days" | live (T31, T36) |
| loading, not allowed, off | as AUD-02 | — | — | flag off (from A-07-T33): 404 and the C-20 state; 501 before | live |

Parity tier: Tier C on the locked artboards named in A-07-T48; Tier D on the T2/T10 geometry.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/archive` · `…/archive/manifest` · `…/archive/additions` | `AuditArchiveStateOut` · `ArchiveManifestOut` | `archive.read` † | team, EQR, security admin (metadata) |
| write | `POST …/archive/binder-index` (202) · `POST …/archive/request-lock` | — | `archive.build_index` · `archive.request_lock` | senior and above |
| write | `POST …/archive/lock` (202, Idempotency-Key, step-up) | `ArchiveLockIn` | `archive.lock` | manager or EP; 9 of 9 |
| write | `POST …/archive/additions` · `/{id}/approve` · `/{id}/reject` · `POST …/archive/verify` | `ArchiveAdditionIn` | `archive_addition.*` † · `archive.verify` † | EP approves with step-up |

Every endpoint is in `docs/contracts/audit-completion.md` (A-07-T04, T05); 501 until its task.

## Status
`archive`, `archive_addition`, `audit_engagement`.

## Copy
"Archive in 47 days", "Request lock…", "Lock archive…", "Contents become read-only and are sealed with a SHA-256 hash", "Assembly is complete", "Then roll forward to PY2026 (ENG-13)", "Locked · sealed", "Locked Dec 3, 2026 · 4:18 PM · Hannah Leclerc · seal 7c41…a9e2 · G9 ✓", "+ Add after lock…", "Archive and roll forward…", "Roll forward…", "Available once the archive can be locked (8 of 9)", "Locking…". Copy keys live in `apps/web/src/copy/aud-25.ts` with the screen task; the words are the handoff's.

## Deviations
- DV-2: "Locked · sealed" instead of "Locked · WORM" (DF-20; OQ-2)
- DV-7: audit-bar pill "Locking…" while the seal computes
- DV-8: the AUD-30 link renders as a reference chip until Q-05

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 | AUD-01 | handoff link (A-01; status in the manifest) |
| Opens AUD-17 | AUD-17 | handoff link (A-06; status in the manifest) |
| Opens AUD-19 | AUD-19 | handoff link (A-07; status in the manifest) |
| Opens AUD-22 | AUD-22 | handoff link (A-07; status in the manifest) |
| Opens AUD-24 | AUD-24 | handoff link (A-07; status in the manifest) |
| Opens AUD-30 | AUD-30 | planned link (DV-8; inline list, chip or download until Q-05) |
| Opens ENG-13 | ENG-13 | handoff link (P-07; status in the manifest) |
| Opens FIL-01 | FIL-01 | handoff link (N-01; status in the manifest) |
| Opens WB-09 | WB-09 | handoff link (P-09; status in the manifest) |

## Acceptance
- Every artboard letter above carries live, fixture-only or deferred with its owning task or epic.
- No agent-owned control carries Approve, Sign off, Release, Send, Post or Decide; final verbs are never optimistic (A-07-T44).

## Final status (A-07-T53, S36)

Built and **live** in the AUD-02 cockpit (`releaseArchiveHosts.tsx` → `ArchiveLive`, A-07-T47) behind `audits.archive`; e is an illustrative state built on fixtures.

| Artboard | Final status |
|---|---|
| a | built · live behind the flag |
| b | built · live behind the flag |
| b2 | built · live behind the flag |
| c | built · live behind the flag |
| d | built · live behind the flag |
| e | built · live behind the flag |

| Deviation | Evidence |
|---|---|
| DV-2 | **Not applied:** `screens/AUD-25/copy.ts` reads "Locked · WORM" (the handoff's words); DF-20 keeps it until OQ-2 (the SOC 2 auditor's answer on GOVERNANCE-mode wording) is closed. Open, owner A-07 / Q-02. |
| DV-7 | `IssuanceLive` ("Releasing…") and `ArchiveLive` ("Locking…") show the transient states while the workflow runs; applied. |
| DV-8 | **Partly:** AUD-23 g names AUD-30 in its copy; no inline list, DOCX download or reference chip for FSP-06, XLA-02, AUD-28 or AUD-30 was found. Open until A-10, W-04 and Q-05 draw their targets. |

Copy: the L1–L12 copy lint (L2: verbatim from the handoff) runs over `screens/AUD-25/copy.ts` at the S36 end pass; no key changed in S36.
