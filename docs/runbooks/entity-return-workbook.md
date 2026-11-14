---
title: "Entity-return workbook: run, debug and roll back (T-05; TXP-00, TXP-02, TXP-11)"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2028-07-07
---
# Entity-return workbook

| Field | Value |
|---|---|
| Owner | ayushkbhatia (the workbook and its runs); notanaskhan (the run runtime and the §7216 gateway) |
| Task | T-05-T71 part 1 (TASK-8015); T-05 §4.5, F2–F8; SPEC-651 |
| Screens | TXP-00 run, TXP-02 trial balance, TXP-11 workbook, TXP-10 issues |
| Flags | `tax.entity_workspace` (routes), `tax.workbook_run` (runs and imports), `tax.entity_agents` (model-backed steps) |
| Kill switches | `tax.workbook_run` off stops new runs and imports (404) and leaves the workbook readable; `tax.entity_agents` off makes every model-backed step a question and the code-only steps still run |
| Related | RB-17 (consent expiry and revocation wave), RB-19 (tax-engine bridge failure), `runtime-v2-flip.md`, `tax-workspace-flip.md` |
| Rehearse | on staging with the synthetic test firm PF-X1 (Ridgeline 1065), then set `last_rehearsed` |

The workbook is a numbered set of sheets on the return (`tax_workbook` target): every cell is a
review field with insert-only versions, written by an engine (`formula`, `engine_import`,
`tb_linked`) or by a person (`human`, with a citation note). The run is P-10's engagement run with
the `tax.entity_workbook` plan provider: ten code steps in six groups (import → map → compute →
capital, apportion → K-1s), at most 3 at once, and every step keeps a person's cells
(`keep_human`). No model computes a figure (ADR-050); the engine of record (CCH Axcess) still
computes and files the return (DEC-77).

## 1. Run it
1. A person with `workbook_run.start` presses ▶ Run on TXP-00: `POST /v1/tax-returns/{id}/workbook-runs`
   with a scope (`all`, a `group` or a `task`). A group or task runs with its dependants, never its
   dependencies, whose last results stand.
2. Watch TXP-00 (or `GET /v1/tax-returns/{id}/workbook-runs`): each step reads Queued, Running,
   Needs attention, Done or Failed. One run per return at a time (409 `run_in_progress`).
3. A finished run freezes a workbook version (T-05-T46); Open in Excel reads the newest finished
   run (the live workbook is refused while a run is open, 409 `export_blocked`).

## 2. A stuck run
**Symptom.** TXP-00 shows a step Running long after its peers, or the run never leaves Running.
1. Read the run: `GET /v1/agent-runs/{run_id}` and its steps. A step `waiting_on_inputs` is not
   stuck: it is a question (a missing §7216 consent, §4 below, or a decision card); answer it.
2. A step that failed answers its failure class (`trial_balance_missing`, `token_expired` …):
   fix the input (import the trial balance; ask the client to reconnect) and retry the step from
   TXP-00 (a retry is a new step row; the failed one stays).
3. A step that is genuinely hung (no heartbeat, the worker restarted): a person with
   `agent_run.control` stops the run, `POST /v1/agent-runs/{run_id}/stop`; the cells the run held
   unlock, and its finished steps' cells stand. Start a new run with the scope that covers the
   unfinished steps.
4. Never edit `agent_run_steps` or the workbook's versions by hand.

## 3. A recompute storm
**Symptom.** A person's edit answers 422 `recompute_too_large`, or many cells recompute after one
change and TXP-11 is slow.
- A cell edit recomputes its dependents synchronously only up to `MAX_RECOMPUTE` (500) cells in
  the DAG's order (`tax/cell_edit.py`). Beyond that the edit is refused and the person starts a run
  instead, which recomputes the affected groups in the background.
- If runs are being started in a loop (an integration or a person re-pressing ▶ Run), turn
  `tax.workbook_run` off for the firm, let the open run finish or stop it (§2), find the source,
  then turn the flag back on. The workbook stays readable throughout.
- A formula that makes a cycle is refused before anything is evaluated (422 `formula_invalid`,
  code `cycle`, naming the addresses): it never storms.

## 4. Consent revoked mid-run (with RB-17)
A step that sends tax return information to a model (`map_lines`' mapper suggestions,
`interim_closing_706d`'s agreement reading) needs both §7216 consents of the partnership for the
year. Without them the step becomes the question `consent_7216`, its branch waits on inputs, no
model is called and the code-only steps still run.
- A revocation during a run: the gateway refuses the next model call for that subject (fail closed,
  `entity_return_subjects`); the step turns into the consent question and the run waits. Nothing
  the model already returned is kept unless a person adopted it.
- A revocation wave across firms (an expiry date, a template change): follow **RB-17**; the
  workbook needs no action beyond answering or abandoning the waiting branches once consents are
  renewed.

## 5. An engine version out of date
Every persisted engine output carries `engine_name`, `engine_version`, `inputs_hash` and
`computed_at` (T-05 §4.4). A new engine version marks its dependents out of date and proposes a
recompute checkpoint for a person: nothing recomputes by itself.
1. TXP-00 names the outdated sections; a person re-runs the affected group.
2. Sign-offs whose content hash covered the old figures go stale through review's own detection;
   the reviewer re-signs.
3. A version that changes a filed figure is a correction, not a re-run: the CPA memo for that
   engine version (T-05-T39, T-05-T70) must be signed before the module holds for a real firm.

## 6. CCH differences
Waits on T-05-T60 (CCH file-bridge export section) and T-05-T61 (reconciliation to the engine of
record), both open in S43 (#1954, #1957). Until they merge, RB-19 covers the bridge, and the
section is written with them (T-05-T71 part 2).

## 7. Roll back
- **Flags off, in reverse order:** `tax.entity_agents`, then `tax.workbook_run`, then
  `tax.entity_workspace`. Data persists: every cell version, run and checkpoint stays; the 1065
  opens TAX-02's coordination view again.
- **A bad run's figures:** restore the workbook to a checkpoint from before the run (P-04's
  checkpoint restore; a person's act), or re-run the group after fixing the input. Never delete
  versions.
- **CCH stays authoritative** throughout.
