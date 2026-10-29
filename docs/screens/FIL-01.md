# FIL-01 · Files browser & document drawer

| Field | Value |
|---|---|
| Route and params | `/files` (nav "Files"); `/files/$clientId` with `?node=<folder_ref>&doc=<evidence_item_id>`; `?doc` opens the O2 drawer. Artboards: `/components/screens/FIL-01?st=a…j` |
| Template and host frame | T2 record cockpit, tree · list (tree 330 · list 1036) + O2 drawer (480) with the R2 control row · `Wave 4 - Platform & Portal.dc.html#fil01` |
| Surface | firm (portal Files is not in MVP-1) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/FIL-01 Files browser and document drawer/` (README.md, spec.md, revision.md R2; revision wins, DEC-15) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | N-01 · contract N-01-T05 (this file); stub T02; client-scoped files T06; read model T19; frontend T16; journeys and parity T23–T28 |
| Spec and ADRs | SPEC-380 (Stories 7, 8); ADR-004, ADR-024, ADR-158; DEC-33, DEC-43, DEC-71 |
| Flags | `files.browser` |
| Manifest status | `fixture` (N-01-T16: `/files`, `/files/$clientId`, `/components/screens/FIL-01?st=a…j`); `live` with N-01-T23 behind `files.browser` |

Read-only in N-01: no write control is offered (DV-10). The writes slice (upload, move, void, new version, sign-off, lock, client access, accepting virtual splits) is the proposed Q-05 slice (N-01 OQ-6).

## States

FIL-01 has 10 artboards (a–g from spec.md, h–j from the R2 revision). Clock E0 unless stated.

| Artboard | Viewer | Clock | Snapshot | Data condition that produces it | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | olivia-brandt | 9:24 AM | E0 | Ridgeline Property Partners, LP › 2025 › TY2025 Form 1065 › Source documents: 12 documents, 7 virtual; mortgage interest statements open; three virtual statements total 512,400 and a mapped TB snapshot exists, so the tie pill reads "ties to 5500" (DV-13) | C report; C lock before M10 | live (T19) |
| b | olivia-brandt | 8:47 AM | E0 | Owen Calder's roof invoice classification running → drawer spinner and skeleton links | C report | live; "(from Owen's message)" fixture-only (DV-14) |
| c | dina-sato | 9:24 AM | E0 + INB-02 g | Iyer TY2025 Source documents: the March 1099-DIV version `superseded`, struck, "Replaced by Iyer_2025_1099DIV_Halvard_Corrected.pdf · Sep 14" | C report | live (T19) |
| d | felix-andersen | 9:24 AM | E0 | Collins TY2023 Form 1040 under legal hold → 32h amber banner; `security_admin` metadata only (DV-11) | C report | live (T19) |
| e | hannah-leclerc | 9:24 AM | E0 | Meridian FY2025 FS audit archive sealed | C report | **fixture-only** until A-07 ("Locked · sealed", DV-12) |
| f | olivia-brandt | 9:24 AM | E0 | Reveal of the borrower TIN through P-03's logged reveal | C report | live (P-03 reveal; T19 access log) |
| g | olivia-brandt | 9:24 AM | E0 | Signed authorizations folder empty | C report | live (T19) |
| h | olivia-brandt | 9:26 AM | E0 | After a preparer sign-off: P slot "OB", R ring | report-only (positions masked, DV-10) | **fixture-only** (writes slice) |
| i | olivia-brandt | 9:24 AM | E0 | Version 1 locked | report-only | **fixture-only** (writes slice) |
| j | olivia-brandt | 9:24 AM | E0 | Client access "Can view" | report-only | **fixture-only** (writes slice) |

Artboard count check (N-01 §2.1): INB-01 7 + INB-02 8 + FIL-01 10 = 25; 19 live and 6 fixture-only (INB-01 c, INB-02 d, FIL-01 e, h, i, j). INB-02 b is live for request destinations.

Non-artboard states: Walled (no greyed placeholder; a walled client, folder or document answers 404, INV-3); metadata-only viewer (firm admin, practice leader, security admin: no thumbnail, no reveal, no Open); client-scoped "Permanent file" node (ADR-158); flag off (C-20); error and loading (F-05 ViewStates); not allowed (client, agent, system: 403).

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/files/tree?client_id&expand` | tree nodes with counts over visible rows | `evidence.read_metadata` |
| read | `GET /v1/files/folders/{folder_ref}/items?q&cursor` | list envelope; rows with virtual children | `evidence.read_metadata` |
| read | `GET /v1/evidence-items/{id}/drawer` | document card, virtual documents and tie, linked to, versions, retention and hold, sign-off slots (read), client access (read), `allowed_actions` (no writes) | `evidence.read_metadata` (+ `evidence.read` for content fields) |
| read | `GET /v1/evidence-items/{id}/access-log?cursor` | audit events on the item's versions in the actor grammar | `evidence.read_access_log` |
| consumed | `GET /v1/evidence-versions/{v}/viewer`, `POST /v1/evidence-versions/{v}/pii-reveals` | SHL-08 and the logged reveal (P-03) | `evidence.read`, `pii.reveal` |

Contract: `docs/contracts/files-browser.md` (N-01-T02).

## Status
`file_document` codes: `processing` "Processing", `needs_review` "Uploaded – needs review" (amber, DV-4), `accepted` "Approved" with the olive disc (DV-17), `superseded` "Superseded" (struck, with "Superseded · Replaced by {name} · {date}"), `on_hold` "On hold" (amber banner). Folder kinds: Source documents, Workpapers, Correspondence, Deliverables, Signed authorizations.

## Copy
| Key | String |
|---|---|
| `folders.sourceDocuments` | "Source documents" |
| `folders.workpapers` | "Workpapers" |
| `folders.correspondence` | "Correspondence" |
| `folders.deliverables` | "Deliverables" |
| `folders.signedAuthorizations` | "Signed authorizations" |
| `tree.permanentFile` | "Permanent file" |
| `list.count` | "12 documents · 7 virtual" (template `{n} documents · {v} virtual`) |
| `tie.pill` | "ties to 5500" (template `ties to {account}`; DV-13) |
| `superseded.line` | "Replaced by {file_name} · {date}" |
| `hold.banner` | "On hold · IRS CP2000 TY2023 disagreed (N3) · placed by Victor Hammond Aug 12, 2026 · destruction suspended" (template from the hold record) |
| `processing.line` | "Classifying…" |
| `reveal.note` | "Logged to the audit log as {viewer}" |
| `reveal.button` | "Reveal (logged)" |
| `empty.signed.title` | "No signed authorizations yet." |
| `empty.signed.body` | "Form 8879-PE lands here when Owen Calder signs (SIG-01)." |
| `archive.locked` | "Locked · sealed" (DV-12; never "WORM") |
| `drawer.accessLog` | "Access log" |
| `drawer.retention` | "Retention" |
| `drawer.linkedTo` | "Linked to" |
| `drawer.versions` | "Versions" |

## Deviations (N-01 §2.4)
DV-10 (no writes; P · R read-only; positions masked for parity), DV-11, DV-12, DV-13, DV-14, DV-17. Spec.md's "Delete…" is "Void…" when the writes slice lands (DF-20).

## Links
Inbound: SHL-01 nav "Files", TXP-00/TXP-01 "Files →", CLI-02 Files tab, INB-02 filed destination, AUD-25, SIG-01 signed copies. Outbound: SHL-08 (live), BND-02, TXP-11, TAX-02 (live as built), FIL-02 (Q-05, planned), NOT-02/NOT-03 (N-04, planned), ADM-12, AUD-25 (planned).
| Retention policy link in the document drawer (designed link, handoff link graph) | FIL-02 | as the target's manifest status |
| Legal hold banner and the drawer’s Legal hold link (designed link, handoff link graph) | FIL-02 | as the target's manifest status |
| Opens CLI-01 · All clients (designed link, handoff link graph) | CLI-01 | as the target's manifest status |
| Opens SHL-08 · source viewer (designed link, handoff link graph) | SHL-08 | as the target's manifest status |
| Opens SHL-12 · Preparer level (designed link, handoff link graph) | SHL-12 | as the target's manifest status |
| Opens TXP-11 · 01 Trial Balance (designed link, handoff link graph) | TXP-11 | as the target's manifest status |
| Opens TAX-02 · TY2025 Form 1065 · Form 8825 line 2a (designed link, handoff link graph) | TAX-02 | as the target's manifest status |
| Opens BND-02 · Ridgeline 2025 Binder pt 2 · Elm Street roof replacement: contractor invoice and placed-in-service date (designed link, handoff link graph) | BND-02 | as the target's manifest status |
| Opens TAX-05 · TY2023 Form 1040 (read-only) (designed link, handoff link graph) | TAX-05 | as the target's manifest status |
| Opens NOT-02 · notice workspace · Collins CP2000 (N3) (designed link, handoff link graph) | NOT-02 | as the target's manifest status |
| Opens NOT-03 · response · Collins CP2000 (N3) (designed link, handoff link graph) | NOT-03 | as the target's manifest status |
| Opens ADM-12 · Monitoring & inspections · finding QM-F-01 (designed link, handoff link graph) | ADM-12 | as the target's manifest status |
| Opens AUD-25 · FY2025 archive · A Planning (designed link, handoff link graph) | AUD-25 | as the target's manifest status |

