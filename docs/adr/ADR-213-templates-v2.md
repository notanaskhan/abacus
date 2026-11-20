---
id: ADR-213
title: Templates v2 - gated template updates, one publish flow, engagement template links
status: accepted
date: 2026-11-20
deciders: ayushkbhatia
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

P-41 (DEC-56). Reserved as ADR-213 by F-02; drafted and accepted with K-03-T01 (TASK-8800,
DEC-5802) under AMENDMENT-solo. Supersedes SPEC-008 Q4, SPEC-008 AC-5 and the SPEC-008 section 4
non-goal "no in-place template upgrades".

## Context
SPEC-008 pins an engagement to a template version once, at creation, and builds new versions by
import. Firms change methodology every year and mid-season (a new standard, a fixed procedure, a
new agent column). Under pin-once an engagement either keeps stale work for its life or is
re-created, which loses sign-offs and citations. DEC-56 chose gated upgrades (option b). K-03
builds the engine (KNW-06, KNW-07, SHL-22, SHT-03) and K-04 hosts the update card on ENG-11.

## Decision
1. **Content lives in the database.** Engagement templates, their versions and components are
   firm content rows (`engagement_templates`, `template_versions`, `template_components`), loaded
   through admin screens and the import endpoint, never constants or migrations.
2. **Drafts are component rows** (Q2): a draft version owns component rows with draft-only
   triggers; each component has its own ETag and comment anchor. Publish freezes the rows and
   records a snapshot fingerprint (sha256 over the canonical component set). Published versions
   are immutable (ADR-004); a change is a new draft.
3. **One publish flow (KNW-07).** A methodology version is a *component* of a template version:
   the KNW-02/03 approve of a methodology draft that belongs to a template draft routes to KNW-07
   for that draft (Q6). One effective date per published template version. Deprecate marks a
   version not offered for new engagements; it never changes engagements already linked.
4. **`engagement_template_links`** record each engagement's template version and its state:
   `current`, `update_available`, `updated`, `held` (with a reason code and text). Rollout picks,
   per engagement, *update now*, *on rollover* or *hold*; code suggests the action from the
   engagement phase (planning approved → on rollover), the human decides. Walled engagements get
   the code-suggested action, their manager is notified, and no count or row reveals them (Q4,
   DEC-43).
5. **Apply is a resumable Temporal workflow** started by a manager on the engagement. It never
   touches a signed-off row, a citation on signed work, or a locked or archived engagement
   (`archived_guard`, P-43). Removed items become read-only "Removed in vN" rows, never deleted;
   engagement-added columns are kept and listed "Engagement column · kept"; template and engagement
   column keys are separate namespaces (Q3). A dry run must produce exactly the change list the
   apply writes (Added · Changed · Removed), and the test suite holds that equality.
6. **Scoping rules** on a firm template draft are edited by the QM owner (`quality_partner`) only;
   managers read and comment (Q1). Rules are evaluated by code, never by a model.
7. **The agent never publishes, rolls out, applies, holds or releases** a template update and never
   evaluates scoping; every one of those matrix actions is `agent: deny` (INV-1).

## Options considered
### Option A: gated upgrades with links and one publish flow — chosen
- Pros: engagements take fixes without losing signed work; one effective date; auditable rollout.
- Cons: an apply workflow and a change-list engine to build and test.

### Option B: keep pin-once (SPEC-008)
- Pros: nothing to build.
- Cons: stale methodology for the life of an engagement or a destructive re-create.
- Why rejected: DEC-56.

### Option C: single `template_drafts` JSON document
- Pros: one row per draft.
- Cons: no per-component ETags, comment anchors or template-mode columns; whole-document conflicts.
- Why rejected: Q2.

## Consequences
**Positive** — methodology fixes reach live engagements under a human decision; signed work is
untouched by construction; rollout is visible on KNW-07.
**Negative** — more tables (versions, components, links, rollout actions, changes) and an apply
workflow with replay history; the dry-run equality must stay tested.
**Follow-ups** — SPEC-720 (K-03-T02) numbers the ACs; TV-1 becomes contract C22 (Q5).

## Related
DEC-56, P-41, SPEC-008, ADR-004, ADR-143 (P-43), ADR-118 (P-06), K-03, K-04, KNW-06, KNW-07,
SHL-22, SHT-03.
