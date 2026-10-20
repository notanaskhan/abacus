---
id: SPEC-051
title: "Compliance and data boundary, setup tier (Q-02 sprint 0): gate tracker and SOC 2 control map, AI threat model, Bedrock provider-terms draft"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-031, ADR-064, ADR-097, ADR-113, ADR-114]
related_specs: [SPEC-036]
created: 2026-10-20
updated: 2026-10-20
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test or check must reference the acceptance criterion (AC-n) it proves.
> - Solo edition (`docs/plan/AMENDMENT-solo.md`): "founder", "N", "AY" and "other founder" in the epic read as "the builder"; no approvals; red tasks write their plan into the task file before work.

## 1. Summary
This is the sprint-0 slice of epic Q-02 (`docs/plan/epics/Q-02.md`): rows Q-02-T01, T02 and T03. It sets up the compliance programme (gate tracker, SOC 2 control map, Qualified Individual designation), writes the AI threat model, and drafts the Bedrock provider-terms entry for counsel.

The data-boundary behaviour itself (opt-in, stages, exclusion, shadow) is **SPEC-036** and is referenced, not duplicated: this spec only prepares the Bedrock register entry that SPEC-036 AC-1 and AC-8 depend on. The compliance-kernel ACs (epic §3, AC-1 to AC-46) belong to the Q-02-T04 spec and are not repeated here.

## 2. Problem and context
- The M4 (Fri Dec 11, 2026) and M7 (Fri Apr 16, 2027) criteria have no tracker, and SOC 2 controls have no map to ADRs.
- ADR-064 calls for an AI threat model; `docs/architecture/ai-threat-model.md` does not exist.
- `docs/operations/provider-terms.yaml` has `entries: []`; with no Bedrock entry, client data stays off for every real firm (ADR-114, SPEC-036 AC-8).
- Epic §3 has no Given/When/Then for these three setup rows; the criteria below come from the CSV acceptance text and ADR-114's field list.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Builder | Writes all three artefacts; is the Qualified Individual |
| Counsel | Reviews the Bedrock entry through F-09 before it merges |
| Auditor (F-09) | Later reads the control map |

## 4. Goals and non-goals
**Goals**
- A gate tracker and SOC 2 control map skeleton covering Security, Availability and Confidentiality.
- A threat model with every listed threat mapped to a test or ADR.
- A complete draft Bedrock register entry, unmerged until counsel reviews.

**Non-goals**
- Any code, route, migration or flag (Q-02-T06 onward).
- The second-approver schema change and the live entry (Q-02-T18).
- Counsel's floors, auditor, pen tester, policy set (F-09).
- The kernel SPEC and contract (Q-02-T04).

## 5. User stories and acceptance criteria
### Story 1: programme set-up (Q-02-T01)
- **AC-1** Given `docs/ops/compliance/README.md`, then it is a gate tracker in which every M4 and M7 criterion has a named owner and date. Under the solo amendment the owner is the builder, or the external party (counsel, auditor, pen tester) where one acts.
- **AC-2** Given `docs/ops/soc2-control-map.md`, then it maps Security, Availability and Confidentiality controls to ADRs and owners, and every control cites at least one ADR and one owner.
- **AC-3** Given the Qualified Individual designation, then it is recorded in the compliance README (the builder, as the single designated person) and an F-01 `soc2-risk` issue is queued for the compliance tool.

### Story 2: AI threat model (Q-02-T02, ADR-064)
- **AC-4** Given `docs/architecture/ai-threat-model.md`, then it covers assets; trust boundaries (gateway, Bedrock route, tool layer, portal); hostile-content and prompt-injection paths; cross-tenant and TRI exposure; and each mitigation is mapped to an existing or planned test or an ADR, with every listed threat mapped.
- **AC-5** Given the threat model is ready to merge, then a self-review (security reviewer subagent) is recorded in the file. It blocks nothing (solo amendment).

### Story 3: Bedrock provider-terms draft (Q-02-T03, ADR-114, SPEC-036)
- **AC-6** Given a draft Bedrock entry against `docs/operations/provider-terms.yaml`, then it carries every ADR-114 field: route `bedrock`; provider Amazon Web Services; documents relied on (AWS Customer Agreement, Service Terms, AWS DPA, Bedrock data-protection terms) each with title, version and accepted date; `training: none`; `retention.beyond_processing: false` (invocation logging off); region `us-east-2` with the US Geo inference profile; subprocessors; breach notice; and `approved_by`, `approved_on` and `review_by` (at most 12 months after approval) left pending for counsel.
- **AC-7** Given the draft, then it is handed to counsel through F-09 with the documents list, and it is not merged to `main` before counsel has reviewed it; until then the register has no Bedrock entry and client data stays off (SPEC-036 AC-8).

## Task map
| Plan key | Task | Acceptance criteria |
|---|---|---|
| Q-02-T01 | TASK-154 | AC-1, AC-2, AC-3 |
| Q-02-T02 | TASK-155 | AC-4, AC-5 |
| Q-02-T03 | TASK-156 | AC-6, AC-7 |

## 6. Behaviour and flows
**Happy path**
1. T01 creates the tracker and control map; T02 writes the threat model (no dependency); T03 drafts the entry after F-09-T11 (Bedrock access filed).
2. The Bedrock entry stays on its branch until counsel returns comments.

**Alternate paths**
- Counsel is late: the entry stays unmerged; the M7 criterion shows red in the tracker (epic R8).

**State transitions:** N/A.

## 7. Domain and data changes
Documentation and one draft register entry only. **Invariant:** never edit an old register entry; a change is a new entry (ADR-114). No migrations; the compiled `_provider_terms.py` is regenerated only when the entry merges.

## 8. Interfaces
None. The register is read by the boundary check (SPEC-036 AC-1, AC-8).

## 9. Authorisation and tenancy
N/A: documents only. The threat model describes tenant and wall boundaries but changes none.

## 10. AI behaviour
N/A: no model calls. The threat model describes them.

## 11. Integrations
- **External systems:** AWS Bedrock terms (documents only, no API calls); counsel through F-09.
- **Failure behaviour:** until counsel reviews, Bedrock has no entry and real firms are refused at the boundary.

## 12. Edge cases and failure modes
- The register's header example shows region `us-east-1`; this entry uses `us-east-2` with the US Geo inference profile, never Global (ADR-113).
- The draft must not be merged or auto-approved; `approved_by` must not name a person who has not approved.
- Any retention exception must be named with `max_days` of 30 or less (ADR-114 Q1); the draft names none.

## 13. Security and privacy
- **Data classification:** internal (compliance documents). **PII involved:** none.
- **Secrets:** none; no account IDs or keys in the repo (public).
- **Threats considered:** unreviewed terms enabling client data; mitigated by AC-7 and boot validation.

## 14. Audit trail and evidence integrity
The register is append-only by convention (new entry, never an edit). Document versions and accepted dates in the entry are the evidence.

## 15. Observability
N/A.

## 16. Performance and scale
N/A.

## 17. UX
N/A: no screens.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 | doc check | script or review checklist: each M4/M7 criterion row has owner and date |
| AC-2 | doc check | each control row cites an ADR id (exists on disk) and an owner |
| AC-3 | doc check | designation present; issue exists |
| AC-4 | doc check | each threat row names a test path or ADR id; paths exist or are marked planned with a task id |
| AC-5 | review | self-review note present |
| AC-6 | unit | existing register test (every entry has every field; compiled module equals YAML) passes against the draft with the pending fields filled by counsel |
| AC-7 | manual | the PR or branch is unmerged; hand-off to F-09 recorded in the task log |

## 19. Rollout
- **Feature flag:** none. **Migration:** none.
- **Rollback:** delete the documents; the Bedrock draft is simply not merged.

## 20. Open questions
None open. Answered with the plan's proposed option:
- Who approves an entry? The founder now; counsel becomes second approver before the first paying firm (ADR-114 Q3; schema change in Q-02-T18).
- Who is the Qualified Individual? The builder (epic names notanaskhan with ayushkbhatia as deputy; the solo amendment collapses both).

## 21. Future / explicitly deferred
- Second-approver fields and live entry (Q-02-T18); parity report (Q-02-T11).
- Kernel SPEC, contract doc, hash chain, holds, retention floors (Q-02-T04 onward).
