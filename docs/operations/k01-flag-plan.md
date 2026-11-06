# K-01 flags: renewal calendar and the per-firm flip plan

**Status: draft, not approved.** K-01-T26's acceptance needs both founders to approve the flip plan,
and the flip needs K-02-T20's counsel-approved TY2026 rules content, which is firm content outside
the repo. Neither has happened, so nothing below is scheduled to run.

## Flags
Every K-01 flag is owned by `ayushkbhatia`, defaults off and is declared in
`docs/architecture/feature-flags/methodology.yaml`.

| Flag | Turns on | Expires | First on for real firms |
|---|---|---|---|
| `knowledge.catalog` | KNW-01 at `/knowledge` | 2027-04-21 | per firm at onboarding |
| `methodology.lifecycle` | Needs review, submit, approve, supersede, version-for-date pinning | 2027-04-21 | per firm at onboarding |
| `methodology.programs` | Programs and steps, KNW-03, drafts, export | 2027-04-21 | per firm from S19 |
| `methodology.import_review` | Upload, diff, standards mapping, flags, draft review in KNW-02 | 2027-04-21 | Tue Oct 26, 2027 |
| `methodology.importer` | AI parsing of documents; also the kill switch | 2027-04-21 | only after clearance and opt-in, no earlier than Tue Oct 26, 2027 |

## Renewal calendar
Each flag is renewed in the monthly flag-hygiene batch and expires within 90 days of a renewal. No
expiry may land in the Sep 1 – Oct 20 window: a renewal that would is pulled forward to the August
batch. All five expire on 2027-04-21, so the first renewal is the batch before that date.

## Per-firm flip of `methodology.import_review`
Planned for Tue Oct 26, 2027, 7 pm CT, one firm at a time. Before it:
1. K-02-T20's TY2026 sets and standards sets resolve in production, with both founders' handles.
2. The journey e2e is green on staging, and a shadow run on PF-X1 is recorded as synthetic.
3. Both founders approve this plan in writing.

**Flip:** turn the flag on for the one firm, then walk an upload through to its diff in KNW-02.

**Rollback:** turn the flag off. Versions already approved stay approved and engagements keep their
pinned version; only upload, diff, mapping and flags go away, and the workbook path still works.

`methodology.importer` is not part of this flip. It needs its Bedrock evals passing, the firm's
opt-in and clearance (ADR-112), and has its own decision per firm. See RB-49.
