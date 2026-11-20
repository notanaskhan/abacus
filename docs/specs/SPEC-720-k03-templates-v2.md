---
id: SPEC-720
title: K-03 Templates v2 — drafts, checks, change list, publish and deprecate, rollout, gated in-place update (KNW-06, KNW-07, SHL-22, SHT-03)
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-050, ADR-143, ADR-159, ADR-161, ADR-213, ADR-236]
related_specs: [SPEC-008, SPEC-721]
created: 2026-11-20
updated: 2026-11-20
epic: K-03
task: K-03-T02 (TASK-8801)
---

# SPEC-720 · Templates v2

> **Instructions for coding agents**
> - The design is `docs/plan/epics/K-03.md` §1–§5; its §3.1–§3.6, §3.13 and §3.14 stories are
>   adopted verbatim and this file numbers their testable cores AC-1 to AC-34.
> - Binding: ADR-213 (P-41). Screen contracts `docs/screens/{KNW-06,KNW-07,SHL-22,SHT-03}.md`,
>   module contract `docs/contracts/templates-v2.md` (C22, TV-1).
> - Code computes checks, change lists, scoping and rollout suggestions (ADR-050). The agent never
>   publishes, rolls out, applies, holds, releases or evaluates scoping (INV-1).

## 1. Summary
Margaret drafts BH Audit Methodology · FS v6 from FS v5 without touching a live engagement,
previews it as Harlow & Pike and Granite Peak, fixes the two check errors, publishes it once with
fresh MFA, and rolls it out with a reason for every hold. Omar applies the update in place on
Harlow & Pike through a resumable workflow that never touches signed-off work.

## 2. Superseded SPEC-008 clauses (ADR-213)
| SPEC-008 clause | Was | Now |
|---|---|---|
| Q4 (re-pin) | an engagement is pinned to one template version at creation; re-pin answers 409 | `engagement_template_links` with `current · update_available · updated · held`; re-pin answers 409 only while `templates_v2.enabled` is off (AC-33) |
| AC-5 | versions are built by import only | drafts are component rows created from the latest published version; import stays for the first version |
| §4 non-goal "no in-place template upgrades" | non-goal | in scope: `TemplateUpdateWorkflow` under the merge invariants (AC-24 to AC-29) |

## 3. Acceptance criteria

### Drafts (KNW-06 a, c, d, e, f)
- **AC-1** "New version…" on FS v5 creates Draft FS v6 with a copy of every component; the
  banner reads "Drafting FS v6 · changes are not live until you publish"; no link, sheet or
  request changes (DB triggers refuse writes to published components).
- **AC-2** A second draft for the same template answers 409 `draft_exists`.
- **AC-3** A stale component ETag answers 412; the tab shows "Changed by … — reload"; autosave
  reads "Saved 9:09 AM".
- **AC-4** Checks on the seed draft give exactly 2 errors (Group scoping › Component has no
  source; a request shown by a rule on a field absent from the planning form) and 1 warning
  (draft skill BH-SK-430 v2); Publish… disabled with "Fix 2 errors to publish". Checks are code.
- **AC-5** Hannah (manager) reads "Draft by Margaret Okonkwo · you can comment, not edit"; Edit,
  + Step and Publish… are absent; comments land on the `template_version` anchor. Staff get 404.
- **AC-6** Request list reads "41 + 6 by rule"; the six group requests are tagged New and
  "Group audit = Yes".
- **AC-7** Triggers shows two read-only C-33 defaults and "every run follows the firm's AI policy
  and produces suggestions only".
- **AC-8** Template-mode column changes write the template draft only; an engagement column never
  changes the firm template; a required column needs a Source binding.

### Preview (KNW-06 b)
- **AC-9** Preview as group: 38 steps · 14 sheets · 47 requests · 2 triggers · 3 report templates ·
  5 skills; single entity: 35 · 12 · 41 and no Group audit band; read-only; Escape exits.
- **AC-10** Preview is `POST /v1/template-versions/{id}/preview` running the engagement rule
  engine; zero gateway calls.

### Scoping rules (SHT-03 a–f; KNW-03 g)
- **AC-11** As Harlow & Pike: "Shows 3 steps · 2 sheets · hides 1 · adds 6 requests"; as Granite
  Peak rules 1–5 "No change", rule 6 "Shows".
- **AC-12** Rule 7 hiding BH-FS-720 while rule 2 shows it answers 422 `rule_conflict` naming both
  rules and the target; Save stays disabled.
- **AC-13** The AND group (Inventory · Valuation · RMM High) reads "No answer yet" on Harlow & Pike.
- **AC-14** A rule that now hides a step with a prepared row leaves it visible, tagged "Out of
  scope by rule"; nothing is deleted.
- **AC-15** Only `quality_partner` edits rules on a firm template draft; managers read and
  comment (DEC-5803); SHT-03 opens read-only from SHT-01 and KNW-03.
- **AC-16** DF-34: rules 1–3 and 6 act on steps, 4 on a request group, 5 hides a section.

### Publish and deprecate (KNW-07 b, f, g; KNW-01 g, h)
- **AC-17** Publish (fresh MFA, effective Oct 1, 2026, previous "Deprecated for new work") publishes
  FS v6 and its methodology component with one effective date, fingerprints the snapshot, makes it
  immutable and emits `template_version.published`. FS v5 reads "Deprecated for new work"; only
  FS v4 reads "Superseded".
- **AC-18** Any error answers 409 `checks_failing`; a pin to a draft skill answers 409
  `skill_not_published`.
- **AC-19** Used by on FS v5 lists six live engagements with phase pills and A20 Meridian
  "Archived" (not eligible); walled engagements are absent with no count.
- **AC-20** Deprecate… reads "New engagements can no longer choose FS v5. The 6 live engagements
  keep it until they update or roll forward; archived files keep it permanently."
- **AC-21** KNW-01 g/h show the Engagement templates category and Oct 1 counts (107 items) from the
  registered catalogue provider.

### Rollout (KNW-07 a, c, d, e)
- **AC-22** Suggested actions are code: planning not approved → Update now; approved or later →
  Hold. Tiles: 6 live · 3 Update now · 0 On rollover · 3 Hold · 0 Updated.
- **AC-23** A Hold or On rollover row without a reason blocks Start rollout… with "Add a reason for
  1 row" (DB CHECK and 409 `reason_required`). Confirming moves links to `update_available`,
  notifies Omar Haddad (A28, A21) and Laura Kemp (A18) in Accrued and by email
  (`template_update_available`); nothing changes on an engagement. Dry run on A28 opens SHL-22
  read-only (Close, Download changes (CSV)); 10:25 reads "1 of 3 updates applied". Walled
  engagements get the suggested action and their manager is notified (DEC-5806).

### Apply, hold, release (SHL-22 a–e)
- **AC-24** SHL-22a: Added 3 · Changed 5 · Removed 0, effects computed against this engagement;
  CSV cells beginning `=`, `+`, `-`, `@` are escaped.
- **AC-25** Update to FS v6 (Manager+, `template.apply_update`, `Idempotency-Key`) runs
  `TemplateUpdateWorkflow`; "Applying · 5 of 8"; "Nobody is signed out"; completion writes banner,
  toast "Template updated · FS v6", version history and AUD-29 "Template updated FS v5 → FS v6 by
  Omar Haddad".
- **AC-26** Merge invariants: signed-off rows and the citations on signed work never change;
  team-edited values are kept; new steps, sheets and columns arrive empty; new requests arrive as
  Draft and are never sent; engagement triggers are kept; removed items become read-only "Removed
  in vN" (DEC-5805).
- **AC-27** The dry run equals the apply (same change list, same end state).
- **AC-28** A worker dying at change 6 resumes without re-applying 1–5 (idempotent on
  `(update_id, change_key)`); the end state equals an uninterrupted run.
- **AC-29** Held Granite Peak: "Held by Hannah Leclerc · Planning approved Sep 14; adopt at the
  FY2027 roll-forward"; BH-FS-430 "Signed off (P CH · R HL, Oct 1); it would not change"; Update
  disabled "Held. Release the hold to update."; Release hold… needs a reason.
- **AC-30** Aiden Ward (Staff): read-only, "Managers and the QM owner apply template updates.",
  CSV only. No rollback, no overwrite. The agent principal is denied every template action.

### Walls, attribution, live path
- **AC-31** Walled users get 404 on a client's sheets; its engagements are absent from used-by,
  rollout and the preview-as picker; no count reveals them.
- **AC-32** Added requests are Draft and client-invisible.
- **AC-33** With `templates_v2.enabled` off, SPEC-008's path behaves as today (409 on re-pin) and
  every existing test passes.
- **AC-34** Every TV-1 route has exactly one matrix action; every write action denies `agent`.

## 4. Data model (ADR-213; K-03 §4.2)
`engagement_templates`, `template_versions` (draft · published · deprecated · superseded,
`effective_from`, `fingerprint`), `template_components` (kind, ETag, draft-only trigger),
`template_checks` (computed), `template_changes` (frozen change list per version pair),
`scoping_rules`, `template_rollouts` and `template_rollout_actions` (action, reason CHECK),
`engagement_template_links` (state, held reason), `template_updates` and
`template_update_changes` (idempotent on `(update_id, change_key)`). Every table tenant-scoped,
forced RLS, `archived_guard`.

## 5. Task map
T06 protected bundle · T07 status objects · T08 TV-1 stub · T10 consumer tests (S52); T11–T26
build (S53–S56); T32–T33 screens; T40 journey J24.
